/* Languages: English (default), Spanish, German, French and Mandarin (Simplified Chinese). The English text of the pages is the
   source. A translation is a dictionary /i18n/<code>.json that maps the English text to the text in the other language:
   - an exact English string ("Start builder") is replaced as a whole,
   - a string with {0}, {1} ... stands for a text with values in it ("Sequence too short ({0} bp, need at least 30 bp).").
   Text that has no entry stays English. The engine walks the page (and everything added to it later) and translates text nodes and
   the attributes placeholder, title, aria-label and alt, so that no page has to be changed text by text. The choice is kept in the
   browser (sessionStorage "encore.lang": a new visit always starts in English). Elements with the attribute translate="no" are left alone. */
(function(){
  var KEY='encore.lang';
  var LANGS=[
    {code:'en', name:'English',  flag:'gb'},
    {code:'es', name:'Español',  flag:'es'},
    {code:'de', name:'Deutsch',  flag:'de'},
    {code:'fr', name:'Français', flag:'fr'},
    {code:'zh', name:'中文 (简体)', flag:'cn'},
    {code:'ru', name:'Русский', flag:'ru'},
    {code:'pt', name:'Português', flag:'pt'},
    {code:'ar', name:'العربية', flag:'ar'}
  ];
  var ATTRS=['placeholder','title','aria-label','alt','label'];
  var RTL={ar:true};                                                   // languages written from right to left
  /* A block is a text element that holds inline markup (<b>, <a>, <code> ...): it is translated as ONE piece of HTML, so that the word
     order of a whole sentence can follow the language. The key of a block is its inner HTML with the white space collapsed. */
  var BLOCK_TAGS={P:1,LI:1,TD:1,TH:1,DD:1,DT:1,H1:1,H2:1,H3:1,H4:1,SUMMARY:1,LABEL:1,FIGCAPTION:1,SPAN:1,DIV:1,A:1};
  var INLINE_TAGS={A:1,B:1,I:1,EM:1,STRONG:1,CODE:1,SPAN:1,SUB:1,SUP:1,BR:1,MARK:1,KBD:1,SMALL:1,ABBR:1,U:1};
  var root=document.documentElement;
  var lang='en', dict=null, templates=[], missing=new Set(), listeners=[], observer=null;

  function stored(){ try{ var v=sessionStorage.getItem(KEY); return LANGS.some(function(l){return l.code===v;}) ? v : 'en'; }catch(e){ return 'en'; } }
  function norm(s){ return s.replace(/\s+/g,' ').trim(); }
  function esc(s){ return s.replace(/[.*+?^$()|[\]\\]/g,'\\$&'); }

  function prepare(d){
    dict={}; templates=[];
    Object.keys(d||{}).forEach(function(k){
      if(/\{\d+\}/.test(k)){
        var parts=k.split(/\{\d+\}/).map(esc);
        templates.push({re:new RegExp('^'+parts.join('((?:(?!\\.\\s+[A-Z])[\\s\\S])+?)')+'$'), out:d[k]});     // a value never reaches over the end of a sentence
      } else dict[k]=d[k];
    });
    templates.sort(function(x,y){ return y.re.source.length-x.re.source.length; });   // the most specific template first
  }
  function translate(en){
    var core=norm(en);
    if(!core || !dict) return null;
    if(Object.prototype.hasOwnProperty.call(dict,core)) return dict[core];
    for(var i=0;i<templates.length;i++){
      var m=core.match(templates[i].re);
      if(m) return templates[i].out.replace(/\{(\d+)\}/g,function(_,n){ var v=m[+n+1]; var t=translate(v); return t===null?v:t; });
    }
    /* a text of several sentences: translate every sentence on its own */
    if(/\.\s+[A-Z]/.test(core)){
      var sentences=core.split(/\.\s+(?=[A-Z])/), changedS=false;
      var outS=sentences.map(function(sent,i){
        var withDot = i<sentences.length-1 ? sent+'.' : sent;
        var t=translate(withDot); if(t!==null){ changedS=true; return t; } return withDot;
      });
      if(changedS) return outS.join(' ');
    }
    /* a line made of pieces ("Type 0.3 · cargo site · toolbox part", "24 nm shell • T=1 • WT"): translate every piece on its own */
    if(/ [\u00B7\u2022] /.test(core)){
      var changed=false;
      var out=core.split(/( [\u00B7\u2022] )/).map(function(piece,i){ if(i%2) return piece; var t=translate(piece); if(t!==null){ changed=true; return t; } return piece; });
      if(changed) return out.join('');
    }
    return null;
  }
  /* keep the white space around the text */
  function wrap(orig,tr){
    var a=orig.match(/^\s*/)[0], b=orig.match(/\s*$/)[0];
    if(/^[:;.,!?)\uFF1A\uFF1B\u3002\uFF0C]/.test(tr)) a='';          // a text that starts with a punctuation mark sticks to the word before it
    return a+tr+b;
  }

  function skip(el){ return !el || (el.closest && el.closest('script,style,textarea,[translate="no"]')); }

  /* a block: a text element whose children are only inline elements (and text), with at least one inline element */
  function isBlock(el){
    if(!BLOCK_TAGS[el.tagName] || !el.firstElementChild || !isInlineOnly(el)) return false;
    return el.innerHTML.length<=8000 && /[A-Za-z]{3,}/.test(el.textContent);
  }
  function isInlineOnly(el){ for(var c=el.firstElementChild;c;c=c.nextElementSibling){ if(!INLINE_TAGS[c.tagName] || !isInlineOnly(c)) return false; } return true; }
  function blockKey(el){ return norm(el.innerHTML); }
  /* the translation of a block: the whole inner HTML as an exact key, or as a template with {0}, {1} ... for the numbers in it */
  function blockTr(key){
    if(!dict) return null;
    if(Object.prototype.hasOwnProperty.call(dict,key)) return dict[key];
    for(var i=0;i<templates.length;i++){
      var m=key.match(templates[i].re);
      if(m) return templates[i].out.replace(/\{(\d+)\}/g,function(_,n){ return m[+n+1]; });
    }
    return null;
  }
  /* true if the block was handled as a whole (translated, or put back to English); false if its pieces have to be walked */
  function doBlock(el){
    var rec=el.__blk, cur=el.innerHTML;
    var base = (rec && rec.tr!==undefined && cur===rec.tr) ? rec.en : cur;
    var tr = lang==='en' ? null : blockTr(norm(base));
    if(tr===null){
      if(rec && rec.tr!==undefined && cur===rec.tr){ el.innerHTML=base; }
      el.__blk={en:base,tr:undefined};
      return false;
    }
    if(cur!==tr) el.innerHTML=tr;
    el.__blk={en:base,tr:el.innerHTML};
    return true;
  }

  function doText(n){
    if(skip(n.parentNode)) return;
    var cur=n.nodeValue;
    var base = (n.__tr!==undefined && cur===n.__tr) ? n.__en : cur;      // our own translation is not new English
    n.__en=base;
    var tr = lang==='en' ? null : translate(base);
    if(tr===null){ if(lang!=='en' && norm(base) && /[A-Za-z]{2,}/.test(base)) missing.add(norm(base)); if(cur!==base) n.nodeValue=base; n.__tr=undefined; }
    else { var out=wrap(base,tr); n.__tr=out; if(cur!==out) n.nodeValue=out; }
  }
  function doAttrs(el){
    if(el.nodeType!==1 || skip(el)) return;
    ATTRS.forEach(function(a){
      if(!el.hasAttribute(a)) return;
      var cur=el.getAttribute(a); el.__a=el.__a||{}; var rec=el.__a[a];
      var base = (rec && rec.tr!==undefined && cur===rec.tr) ? rec.en : cur;
      var tr = lang==='en' ? null : translate(base);
      if(tr===null){ if(lang!=='en' && /[A-Za-z]{3,}/.test(base)) missing.add(norm(base)); if(cur!==base) el.setAttribute(a,base); el.__a[a]={en:base,tr:undefined}; }
      else { if(cur!==tr) el.setAttribute(a,tr); el.__a[a]={en:base,tr:tr}; }
    });
  }
  function walk(node){
    if(node.nodeType===3){ doText(node); return; }
    if(node.nodeType!==1 && node.nodeType!==11) return;
    if(node.nodeType===1){ if(skip(node)) return; doAttrs(node); if(isBlock(node) || (node.__blk && node.__blk.tr!==undefined)){ if(doBlock(node)) return; } }
    for(var c=node.firstChild;c;c=c.nextSibling) walk(c);
  }
  function applyAll(){
    if(observer) observer.disconnect();
    walk(document.documentElement);
    if(document.title){ var t=document.__titleEn!==undefined && document.title===document.__titleTr ? document.__titleEn : document.title; document.__titleEn=t; var tt=lang==='en'?null:translate(t); document.__titleTr=tt===null?t:tt; document.title=document.__titleTr; }
    observe();
  }
  function observe(){
    if(!observer){
      observer=new MutationObserver(function(muts){
        observer.disconnect();
        muts.forEach(function(m){
          if(m.type==='characterData') doText(m.target);
          else if(m.type==='attributes') doAttrs(m.target);
          else m.addedNodes.forEach(walk);
        });
        observe();
      });
    }
    observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:ATTRS});
  }

  function load(code){
    if(code==='en'){ prepare({}); return Promise.resolve(); }
    return fetch('/i18n/'+code+'.json',{cache:'no-cache'}).then(function(r){ return r.ok ? r.json() : {}; }).catch(function(){ return {}; }).then(prepare);
  }
  function setLang(code, remember){
    if(!LANGS.some(function(l){return l.code===code;})) code='en';
    return load(code).then(function(){
      lang=code; root.setAttribute('lang',code==='zh'?'zh-Hans':code); root.setAttribute('dir', RTL[code] ? 'rtl' : 'ltr');
      if(remember!==false){ try{ sessionStorage.setItem(KEY,code); }catch(e){} }
      missing.clear();
      if(document.body) applyAll();
      listeners.forEach(function(f){ try{ f(code); }catch(e){} });
    });
  }
  /* for texts that are put into the page as one piece of HTML (the info windows): key "info.stop.body" and so on */
  function html(key, en){
    if(lang==='en' || !dict) return en;
    return Object.prototype.hasOwnProperty.call(dict,key) ? dict[key] : en;
  }

  window.ENCORE_I18N={
    languages:LANGS, get lang(){ return lang; }, setLang:setLang, html:html, translate:translate,
    onChange:function(f){ listeners.push(f); },
    get missing(){ return Array.from(missing); },
    /* the blocks of the page (for building a dictionary): [{tag, key}] */
    blocks:function(){ var out=[]; (function w(n){ if(n.nodeType!==1 || skip(n)) return; if(isBlock(n)){ out.push({tag:n.tagName, key:blockKey(n)}); return; } for(var c=n.firstChild;c;c=c.nextSibling) w(c); })(document.documentElement); return out; }
  };

  var initial=stored();
  root.setAttribute('lang',initial==='zh'?'zh-Hans':initial); root.setAttribute('dir', RTL[initial] ? 'rtl' : 'ltr');
  function start(){ setLang(initial,false); }
  if(initial==='en'){ lang='en'; prepare({}); }
  else if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start); else start();
})();

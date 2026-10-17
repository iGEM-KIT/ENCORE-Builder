/* Languages: English (default), Spanish, German, French and Mandarin (Simplified Chinese). The English text of the pages is the
   source. A translation is a dictionary /i18n/<code>.json that maps the English text to the text in the other language:
   - an exact English string ("Start builder") is replaced as a whole,
   - a string with {0}, {1} ... stands for a text with values in it ("Sequence too short ({0} bp, need at least 30 bp).").
   Text that has no entry stays English. The engine walks the page (and everything added to it later) and translates text nodes and
   the attributes placeholder, title, aria-label and alt, so that no page has to be changed text by text. The choice is kept in the
   browser (localStorage "encore.lang"). Elements with the attribute translate="no" are left alone. */
(function(){
  var KEY='encore.lang';
  var LANGS=[
    {code:'en', name:'English',  flag:'gb'},
    {code:'es', name:'Español',  flag:'es'},
    {code:'de', name:'Deutsch',  flag:'de'},
    {code:'fr', name:'Français', flag:'fr'},
    {code:'zh', name:'中文 (简体)', flag:'cn'}
  ];
  var ATTRS=['placeholder','title','aria-label','alt'];
  var root=document.documentElement;
  var lang='en', dict=null, templates=[], missing=new Set(), listeners=[], observer=null;

  function stored(){ try{ var v=localStorage.getItem(KEY); return LANGS.some(function(l){return l.code===v;}) ? v : 'en'; }catch(e){ return 'en'; } }
  function norm(s){ return s.replace(/\s+/g,' ').trim(); }
  function esc(s){ return s.replace(/[.*+?^$()|[\]\\]/g,'\\$&'); }

  function prepare(d){
    dict={}; templates=[];
    Object.keys(d||{}).forEach(function(k){
      if(/\{\d+\}/.test(k)){
        var parts=k.split(/\{\d+\}/).map(esc);
        templates.push({re:new RegExp('^'+parts.join('([\\s\\S]+?)')+'$'), out:d[k]});
      } else dict[k]=d[k];
    });
  }
  function translate(en){
    var core=norm(en);
    if(!core || !dict) return null;
    if(Object.prototype.hasOwnProperty.call(dict,core)) return dict[core];
    for(var i=0;i<templates.length;i++){
      var m=core.match(templates[i].re);
      if(m) return templates[i].out.replace(/\{(\d+)\}/g,function(_,n){ var v=m[+n+1]; var t=translate(v); return t===null?v:t; });
    }
    /* a line made of pieces ("Type 0.3 · cargo site · toolbox part"): translate every piece on its own */
    if(core.indexOf(' · ')>0){
      var changed=false;
      var out=core.split(' · ').map(function(piece){ var t=translate(piece); if(t!==null){ changed=true; return t; } return piece; });
      if(changed) return out.join(' · ');
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
    if(node.nodeType===1){ if(skip(node)) return; doAttrs(node); }
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
      lang=code; root.setAttribute('lang',code==='zh'?'zh-Hans':code);
      if(remember!==false){ try{ localStorage.setItem(KEY,code); }catch(e){} }
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
    get missing(){ return Array.from(missing); }
  };

  var initial=stored();
  root.setAttribute('lang',initial==='zh'?'zh-Hans':initial);
  function start(){ setLang(initial,false); }
  if(initial==='en'){ lang='en'; prepare({}); }
  else if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start); else start();
})();

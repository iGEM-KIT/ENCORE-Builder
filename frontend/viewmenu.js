/* View menu, the same on every page and built like the one of the toolKIT wiki: one button with an eye that opens a small panel with
   three buttons: language, dyslexia-friendly font and dark mode. The choices are kept in the browser (localStorage), so that they hold
   on all pages. The old light/dark button of each page stays in the page (hidden): its own code keeps the theme, the panel only presses it. */
(function(){
  var root=document.documentElement;
  var DYS='encore.dyslexia';
  function stored(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } }
  function store(k,v){ try{ localStorage.setItem(k,v); }catch(e){} }

  /* the font mode is set at once, before the page is painted */
  function setDys(on){ root.classList.toggle('enc-dyslexic', on); }
  setDys(stored(DYS)==='1');

  var NS='http://www.w3.org/2000/svg';
  var FLAGS={
    gb:'<rect width="60" height="36" fill="#012169"/><path d="M0 0L60 36M60 0L0 36" stroke="#fff" stroke-width="7"/><path d="M0 0L60 36M60 0L0 36" stroke="#C8102E" stroke-width="2.5"/><path d="M30 0v36M0 18h60" stroke="#fff" stroke-width="11"/><path d="M30 0v36M0 18h60" stroke="#C8102E" stroke-width="6.5"/>',
    es:'<rect width="60" height="36" fill="#AA151B"/><rect y="9" width="60" height="18" fill="#F1BF00"/>',
    de:'<rect width="60" height="12" fill="#000"/><rect y="12" width="60" height="12" fill="#DD0000"/><rect y="24" width="60" height="12" fill="#FFCE00"/>',
    fr:'<rect width="20" height="36" fill="#0055A4"/><rect x="20" width="20" height="36" fill="#fff"/><rect x="40" width="20" height="36" fill="#EF4135"/>',
    cn:'<rect width="60" height="36" fill="#DE2910"/><g fill="#FFDE00"><polygon points="10,4 12.4,10.6 19.4,10.8 13.9,15 15.8,21.7 10,17.8 4.2,21.7 6.1,15 0.6,10.8 7.6,10.6"/><polygon points="22,3 22.9,5.5 25.5,5.5 23.4,7 24.2,9.5 22,8 19.8,9.5 20.6,7 18.5,5.5 21.1,5.5"/><polygon points="26,9 26.9,11.5 29.5,11.5 27.4,13 28.2,15.5 26,14 23.8,15.5 24.6,13 22.5,11.5 25.1,11.5"/><polygon points="26,17 26.9,19.5 29.5,19.5 27.4,21 28.2,23.5 26,22 23.8,23.5 24.6,21 22.5,19.5 25.1,19.5"/><polygon points="22,23 22.9,25.5 25.5,25.5 23.4,27 24.2,29.5 22,28 19.8,29.5 20.6,27 18.5,25.5 21.1,25.5"/></g>'
  };
  function flag(code,cls){ return '<svg class="'+(cls||'vm-flag')+'" viewBox="0 0 60 36" aria-hidden="true" focusable="false"><clipPath id="vmc-'+code+'-'+(cls||'f')+'"><rect width="60" height="36" rx="5"/></clipPath><g clip-path="url(#vmc-'+code+'-'+(cls||'f')+')">'+FLAGS[code]+'</g></svg>'; }

  var ICON_EYE='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var ICON_DYS='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 3.5V16"/><circle cx="8.5" cy="12.5" r="3.5"/><circle cx="15.5" cy="12.5" r="3.5"/><path d="M19 3.5V16"/><path d="M3.5 20.5h17"/></svg>';
  var ICON_THEME='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 6.5a5.5 5.5 0 0 1 0 11a3.6 5.5 0 0 0 0-11z"/><circle cx="12" cy="12" r="5.5"/><path d="M12 1.8v2.2M12 20v2.2M1.8 12H4M20 12h2.2M4.8 4.8l1.6 1.6M17.6 17.6l1.6 1.6M4.8 19.2l1.6-1.6M17.6 6.4l1.6-1.6"/></svg>';

  function build(){
    var theme=document.getElementById('themeToggle');
    if(!theme || document.getElementById('viewMenu')) return;
    var I=window.ENCORE_I18N, langs=I ? I.languages : [{code:'en',name:'English',flag:'gb'}];

    var wrap=document.createElement('div'); wrap.className='vm'; wrap.id='viewMenu';
    wrap.innerHTML=
      '<button type="button" class="hbtn vm-btn" id="vmBtn" aria-expanded="false" aria-controls="vmPanel" aria-label="Reading options" title="Reading options">'+ICON_EYE+'</button>'+
      '<div class="vm-panel" id="vmPanel" hidden>'+
        '<button type="button" class="vm-item" id="vmLang" aria-haspopup="listbox" aria-expanded="false" aria-label="Language" title="Language"></button>'+
        '<button type="button" class="vm-item" id="vmDys" aria-pressed="false" aria-label="Dyslexia-friendly font" title="Dyslexia-friendly font">'+ICON_DYS+'</button>'+
        '<button type="button" class="vm-item" id="vmTheme" aria-pressed="false" aria-label="Dark mode" title="Dark mode">'+ICON_THEME+'</button>'+
        '<ul class="vm-langs" id="vmLangs" role="listbox" aria-label="Language" hidden translate="no">'+
          langs.map(function(l){ return '<li><button type="button" role="option" data-lang="'+l.code+'" aria-selected="false" lang="'+(l.code==='zh'?'zh-Hans':l.code)+'">'+flag(l.flag,'vm-flag')+'<span>'+l.name+'</span></button></li>'; }).join('')+
        '</ul>'+
      '</div>';
    theme.parentNode.insertBefore(wrap, theme);
    theme.classList.add('vm-oldtheme');                                   // kept for the code of the page, not shown

    var btn=wrap.querySelector('#vmBtn'), panel=wrap.querySelector('#vmPanel'), bLang=wrap.querySelector('#vmLang'),
        bDys=wrap.querySelector('#vmDys'), bTheme=wrap.querySelector('#vmTheme'), list=wrap.querySelector('#vmLangs');

    function openPanel(on){
      panel.hidden=!on; btn.setAttribute('aria-expanded', on?'true':'false');
      if(!on) openList(false);
    }
    function openList(on){ list.hidden=!on; bLang.setAttribute('aria-expanded', on?'true':'false'); }
    function sync(){
      var cur = I ? I.lang : 'en';
      var l = langs.filter(function(x){return x.code===cur;})[0] || langs[0];
      bLang.innerHTML = flag(l.flag,'vm-flag');
      list.querySelectorAll('button').forEach(function(b){ b.setAttribute('aria-selected', b.dataset.lang===cur ? 'true':'false'); });
      bDys.setAttribute('aria-pressed', root.classList.contains('enc-dyslexic') ? 'true':'false');
      bTheme.setAttribute('aria-pressed', root.getAttribute('data-theme')==='dark' ? 'true':'false');
    }

    btn.addEventListener('click', function(e){ e.stopPropagation(); openPanel(panel.hidden); });
    bLang.addEventListener('click', function(e){ e.stopPropagation(); openList(list.hidden); });
    list.addEventListener('click', function(e){
      var b=e.target.closest('button[data-lang]'); if(!b) return;
      e.stopPropagation();
      (I ? I.setLang(b.dataset.lang) : Promise.resolve()).then(function(){ sync(); openList(false); });
    });
    bDys.addEventListener('click', function(e){ e.stopPropagation(); var on=!root.classList.contains('enc-dyslexic'); setDys(on); store(DYS, on?'1':'0'); sync(); });
    bTheme.addEventListener('click', function(e){ e.stopPropagation(); theme.click(); sync(); });
    document.addEventListener('click', function(e){ if(!wrap.contains(e.target)) openPanel(false); });
    document.addEventListener('keydown', function(e){ if(e.key==='Escape' && !panel.hidden){ openPanel(false); btn.focus(); } });
    new MutationObserver(sync).observe(root,{attributes:true,attributeFilter:['data-theme','class']});
    if(I) I.onChange(sync);
    sync();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', build); else build();
})();

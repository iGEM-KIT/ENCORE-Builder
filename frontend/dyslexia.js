/* Dyslexia-friendly font mode: one button next to the light/dark switch on every page, the choice is kept in the browser
   (localStorage "encore.dyslexia"), so it holds across all pages. The class is set at once (before the page is painted),
   the button is added when the header exists. */
(function(){
  var root=document.documentElement, KEY='encore.dyslexia';
  function stored(){ try{ return localStorage.getItem(KEY)==='1'; }catch(e){ return false; } }
  function apply(on){ root.classList.toggle('enc-dyslexic', on); }
  apply(stored());
  function addButton(){
    var theme=document.getElementById('themeToggle');
    if(!theme || document.getElementById('dyslexiaToggle')) return;
    var b=document.createElement('button');
    b.type='button'; b.id='dyslexiaToggle'; b.className='hbtn';
    b.title='Dyslexia-friendly font'; b.setAttribute('aria-label','Dyslexia-friendly font');
    b.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 3.5V16"/><circle cx="8.5" cy="12.5" r="3.5"/><circle cx="15.5" cy="12.5" r="3.5"/><path d="M19 3.5V16"/></svg>';
    function sync(){ b.setAttribute('aria-pressed', root.classList.contains('enc-dyslexic') ? 'true' : 'false'); }
    b.addEventListener('click', function(){
      var on=!root.classList.contains('enc-dyslexic');
      apply(on);
      try{ localStorage.setItem(KEY, on ? '1' : '0'); }catch(e){}
      sync();
    });
    theme.parentNode.insertBefore(b, theme);
    sync();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', addButton); else addButton();
})();

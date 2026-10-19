/* Info buttons of the database pages: the same round "i" button and floating box as in the Builder.
   The text sits in a hidden panel (data-info-target) so the language engine translates it like the rest of the page. */
(function(){
  var pop=document.createElement('div'); pop.className='popover'; pop.setAttribute('role','dialog');
  pop.innerHTML='<button type="button" class="pop-close" aria-label="Close">\u2715</button><div class="pop-body"></div>';
  document.body.appendChild(pop);
  var body=pop.querySelector('.pop-body'), anchor=null;
  function place(){
    if(!anchor||!pop.classList.contains('show')) return;
    var r=anchor.getBoundingClientRect(), w=pop.offsetWidth, h=pop.offsetHeight, m=12;
    var left=Math.min(Math.max(m,r.right-w), window.innerWidth-w-m);
    var top=r.bottom+8; if(top+h>window.innerHeight-m) top=Math.max(m, r.top-h-8);
    pop.style.left=left+'px'; pop.style.top=top+'px';
  }
  function close(){ pop.classList.remove('show'); if(anchor) anchor.setAttribute('aria-expanded','false'); anchor=null; }
  function open(btn){
    var src=document.getElementById(btn.getAttribute('data-info-target')); if(!src) return;
    body.innerHTML=src.innerHTML; anchor=btn; btn.setAttribute('aria-expanded','true');
    pop.classList.add('show'); place();
  }
  document.addEventListener('click',function(e){
    var btn=e.target.closest('.info-btn');
    if(btn){ e.stopPropagation(); if(anchor===btn) close(); else { close(); open(btn); } return; }
    if(e.target.closest('.pop-close')||!e.target.closest('.popover')) close();
  });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape') close(); });
  window.addEventListener('resize',place); document.addEventListener('scroll',place,{passive:true,capture:true});
})();

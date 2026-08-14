// Adds Enter-to-send behavior to the chat input without modifying app.js
document.addEventListener('DOMContentLoaded', ()=>{
  const qEl = document.getElementById('questionInput');
  const form = document.getElementById('askForm');
  if(!qEl || !form) return;
  qEl.addEventListener('keydown', e => {
    if(e.key === 'Enter' && !e.shiftKey){
      e.preventDefault();
      if(typeof form.requestSubmit === 'function') form.requestSubmit();
      else form.dispatchEvent(new Event('submit', {cancelable: true}));
    }
  });
});

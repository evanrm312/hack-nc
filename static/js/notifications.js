// Private notification panel. Fetches no message bodies; stops on sign-out.
(function () {
  const toggle=document.getElementById('notifications-toggle'), panel=document.getElementById('notifications-panel');
  if (!toggle || !panel) return;
  let loading=false, generation=0, unread=0, timer=null;
  function stopPolling() {clearTimeout(timer);timer=null;}
  function schedule() {stopPolling();if(api.getToken() && !document.hidden) timer=setTimeout(load,20000);}
  function label() { toggle.textContent=(window.innerWidth<700?'Alerts':'Notifications')+(unread?' ('+unread+')':''); }
  window.addEventListener('resize',label);
  async function load() {
    if (loading || !api.getToken() || document.hidden) return;
    loading=true; const token=api.getToken(), version=generation;
    try {
      const data=await api.get('/api/notifications');
      if (version!==generation || token!==api.getToken()) return;
      toggle.hidden=false; unread=data.unread_count;label();
      const list=panel.querySelector('[data-notifications]'); list.replaceChildren();
      const labels={exchange_created:'New exchange',message:'New message',offer:'Offer changed',offer_accepted:'Offer accepted',reserved:'Pickup confirmation needed',scheduled:'Service scheduled',on_loan:'Loan started',return_pending:'Return confirmation needed',completed:'Exchange completed',cancelled:'Exchange cancelled',disputed:'Dispute opened',completion_confirmation:'Service completion confirmation',confirmation_required:'Condition confirmation needed',condition_confirmation:'Condition confirmed'};
      for (const n of data.notifications) {
        const row=document.createElement('div');row.className='notification-row';
        const link=document.createElement(n.url ? 'a' : 'span');if(n.url)link.href=n.url;link.textContent=n.url ? (labels[n.kind]||'Exchange updated') : 'Exchange no longer available';
        if (!n.read_at) link.classList.add('unread');
        if(n.url) link.onclick=async e=>{e.preventDefault();try {const result=await api.post('/api/notifications/'+encodeURIComponent(n.id)+'/read'); if(result.notification.url)location.assign(result.notification.url);else{panel.querySelector('[data-error]').textContent='Exchange no longer available.';await load();}} catch (_) {panel.querySelector('[data-error]').textContent='Could not open notification. Try again.';}};
        const read=document.createElement('button');read.type='button';read.textContent='Mark read';read.disabled=!!n.read_at;
        read.onclick=async()=>{try {await api.post('/api/notifications/'+encodeURIComponent(n.id)+'/read');await load();}catch(_){panel.querySelector('[data-error]').textContent='Could not mark read.';}};
        row.append(link,read);list.append(row);
      }
      if (!data.notifications.length) list.textContent='No notifications yet.';
      panel.querySelector('[data-error]').textContent='';
    } catch (_) {if (!panel.hidden) panel.querySelector('[data-error]').textContent='Notifications are temporarily unavailable.';}
    finally {loading=false;schedule();}
  }
  function close(focus) {panel.hidden=true;toggle.setAttribute('aria-expanded','false');if(focus) toggle.focus();}
  toggle.onclick=()=>{panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden){panel.querySelector('button').focus();load();}};
  panel.querySelector('[data-read-all]').onclick=async()=>{try {await api.post('/api/notifications/read-all');await load();} catch(_){panel.querySelector('[data-error]').textContent='Could not mark notifications read.';}};
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)close(true);});
  document.addEventListener('click',e=>{if(!panel.hidden&&!panel.contains(e.target)&&!toggle.contains(e.target))close(false);});
  document.addEventListener('campus:auth-changed',()=>{generation++;stopPolling();unread=0;label();close(false);panel.querySelector('[data-notifications]').replaceChildren();toggle.hidden=!api.getToken();load();});
  document.addEventListener('visibilitychange',()=>{stopPolling();if(!document.hidden)load();});
  window.addEventListener('pagehide',stopPolling);
  window.addEventListener('pageshow',load);
  load();
})();

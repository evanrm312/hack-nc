// Separate service lifecycle; never calls evidence, handoff or return APIs.
window.campusServiceRoom = async function(base,initial) {
  const C=window.CampusUI||window.CampusComponents;
  const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
  const root=document.getElementById('room-content');root.replaceChildren();root.hidden=false;
  let detail=initial,me=(await api.get('/api/me')).profile,busy=false,dirty=false,generation=0;
  const originalToken=api.getToken();
  const summary=el('section');summary.className='card';root.append(summary);
  const form=el('form');form.className='card';form.append(el('h2','Propose service terms'));
  const fields={};
  function field(key,label,type,value){const l=el('label',label),i=el('input');i.id='s-'+key;i.type=type;i.value=value||'';l.htmlFor=i.id;form.append(l,i);fields[key]=i;return i;}
  field('price','Price in USD (required)','number');fields.price.min='0';fields.price.step='.01';
  field('duration','Duration in minutes (required)','number');fields.duration.min='1';fields.duration.max='1440';
  field('time','Start time (Eastern)','datetime-local');
  const delivery=el('select');delivery.id='s-delivery';delivery.add(new Option('Remote','remote'));delivery.add(new Option('In person','in_person'));const dl=el('label','Service location');dl.htmlFor=delivery.id;form.append(dl,delivery);
  const meeting=el('select');meeting.id='s-meeting';meeting.add(new Option('Choose a catalog spot',''));const ml=el('label','Meeting spot (required in person)');ml.htmlFor=meeting.id;form.append(ml,meeting);
  const spots=(await api.get('/api/meeting-spots')).meeting_spots;spots.forEach(s=>meeting.add(new Option(s.label,s.id)));
  const send=el('button','Send offer');send.type='submit';form.append(send);root.append(form);
  const actions=el('section');actions.className='card';actions.append(el('p','Simulated payments: no funds are reserved or charged.'));
  const accept=el('button','Accept current offer'),complete=el('button','Confirm service happened');actions.append(accept,complete);root.append(actions);
  const safety=el('section');safety.className='card';safety.append(el('h2','Meeting location and access'));const picker=el('div');safety.append(picker);root.append(safety);
  await window.campusExchangeLocations(picker,base,spot=>{if(detail.exchange.status!=='negotiating')return;delivery.value='in_person';meeting.value=spot.id;dirty=true;syncDelivery();form.scrollIntoView({block:'center'});});
  function syncDelivery(){meeting.hidden=ml.hidden=delivery.value!=='in_person';safety.hidden=delivery.value!=='in_person';}delivery.onchange=syncDelivery;
  const messages=el('section');messages.className='card';messages.append(el('h2','Private conversation'));const list=el('div'),mf=el('form'),body=el('textarea');body.maxLength=4000;body.required=true;body.id='service-message';const label=el('label','Message');label.htmlFor=body.id;const submit=el('button','Send message');submit.type='submit';mf.append(label,body,submit);messages.append(list,mf);root.append(messages);
  const closing=el('section');closing.className='card';const reason=el('input');reason.id='service-reason';reason.maxLength=1000;const rl=el('label','Reason for cancellation or dispute');rl.htmlFor=reason.id;const cancel=el('button','Cancel exchange'),dispute=el('button','Open dispute');closing.append(rl,reason,cancel,dispute);root.append(closing);
  const error=el('p');error.setAttribute('role','alert');root.append(error);
  let displayedVersion=-1,messageKey=crypto.randomUUID();
  function fill(){const o=detail.current_offer||{};fields.price.value=(o.service_price_cents??detail.listing.service_price_cents)/100;fields.duration.value=o.service_duration_minutes||detail.listing.service_duration_minutes;
    if(o.service_scheduled_at){fields.time.value=window.campusExchangeTime.input(o.service_scheduled_at);}delivery.value=o.service_delivery||'remote';meeting.value=o.service_meeting_spot_id||'';dirty=false;displayedVersion=o.version||0;syncDelivery();}
  const reset=el('button','Use current offer');reset.type='button';reset.onclick=fill;form.append(reset);
  function render(){const x=detail.exchange,o=detail.current_offer;document.getElementById('room-title').textContent=detail.listing.title;document.getElementById('exchange-status').textContent=(x.club_review_state==='pending'?'Waiting for club manager approval':x.status.replaceAll('_',' '))+(x.club?' · Club only: '+x.club.name:'')+(x.club_review_state==='changes_requested'?' · Manager requested changes: '+(x.club_review_note||'Propose a new offer'):'');document.getElementById('participants').textContent=detail.participants.map(p=>p.display_name+' · '+p.badge).join(' / ');document.getElementById('page-status').textContent='';
    summary.replaceChildren(el('h2','Current agreement'));
    if(o){summary.append(el('p','Revision '+o.version+' · '+api.formatCents(o.service_price_cents)+' · '+o.service_duration_minutes+' minutes · '+api.formatTime(o.service_scheduled_at)),el('p',o.service_delivery==='in_person'?'In person: '+(spots.find(s=>s.id===o.service_meeting_spot_id)?.label||'Unavailable spot'):'Remote service'),el('p',(o.owner_accepted_at?'Owner accepted':'Owner has not accepted')+' · '+(o.requester_accepted_at?'Requester accepted':'Requester has not accepted')));}
    else summary.append(el('p','No offer yet. Propose a price, duration, and available time.'));
    if(x.status==='scheduled'||x.status==='completed')summary.append(el('p',(x.owner_service_confirmed_at?'Owner confirmed completion':'Owner completion pending')+' · '+(x.requester_service_confirmed_at?'Requester confirmed completion':'Requester completion pending')));
    form.hidden=x.status!=='negotiating';accept.hidden=x.status!=='negotiating'||!o;accept.disabled=busy||dirty||!!(me.id===x.owner_id?o?.owner_accepted_at:o?.requester_accepted_at);complete.hidden=x.status!=='scheduled';complete.disabled=busy||!!(me.id===x.owner_id?x.owner_service_confirmed_at:x.requester_service_confirmed_at);
    cancel.hidden=!['negotiating','scheduled'].includes(x.status);dispute.hidden=!['scheduled','completed'].includes(x.status);closing.hidden=cancel.hidden&&dispute.hidden;mf.hidden=['cancelled','completed'].includes(x.status);
    safety.querySelectorAll('[data-spot]').forEach(b=>{b.disabled=x.status!=='negotiating';});const locationForm=safety.querySelector('form');if(locationForm)locationForm.hidden=['completed','cancelled','disputed'].includes(x.status);
    if(!dirty)fill();}
  async function refresh(){const version=generation;try{const [d,m]=await Promise.all([api.get(base),api.get(base+'/messages')]);if(version!==generation||api.getToken()!==originalToken)return;detail=d;render();list.replaceChildren();m.messages.forEach(msg=>list.append(el('p',detail.participants.find(p=>p.id===msg.sender_id)?.display_name+': '+msg.body)));}catch(e){error.textContent=e.message;}}
  async function action(work){if(busy)return;busy=true;error.textContent='';root.querySelectorAll('button').forEach(b=>b.disabled=true);try{await work();await refresh();}catch(e){error.textContent=e.message;}finally{busy=false;root.querySelectorAll('button').forEach(b=>b.disabled=false);render();}}
  form.oninput=()=>{dirty=true;accept.disabled=true;};form.onsubmit=e=>{e.preventDefault();action(async()=>{if(displayedVersion!==(detail.current_offer?.version||0))throw new Error('The offer changed. Use current offer before revising.');const price=Number(fields.price.value),duration=Number(fields.duration.value);if(!fields.price.value||!Number.isFinite(price)||price<0||!/^\d+(\.\d{1,2})?$/.test(fields.price.value)||!fields.time.value)throw new Error('Enter a valid price, duration and time.');await api.post(base+'/offers',{service_price_cents:Math.round(price*100),service_duration_minutes:duration,service_scheduled_at:window.campusExchangeTime.toUtc(fields.time.value),service_delivery:delivery.value,service_meeting_spot_id:delivery.value==='in_person'?meeting.value:null});dirty=false;});};
  accept.onclick=()=>action(()=>api.post(base+'/accept',{version:detail.current_offer.version}));complete.onclick=()=>action(()=>api.post(base+'/complete',{confirm:true}));
  mf.onsubmit=e=>{e.preventDefault();action(async()=>{await api.post(base+'/messages',{body:body.value.trim()},{headers:{'Idempotency-Key':messageKey}});messageKey=crypto.randomUUID();body.value='';});};
  cancel.onclick=()=>action(()=>api.post(base+'/cancel',{reason:reason.value.trim()}));dispute.onclick=()=>action(()=>api.post(base+'/dispute',{reason:reason.value.trim()}));
  document.getElementById('refresh-room').onclick=refresh;
  const timer=setInterval(()=>{if(!document.hidden&&!busy)refresh();},10000);
  document.addEventListener('campus:auth-changed',()=>{if(api.getToken()!==originalToken){generation++;clearInterval(timer);root.replaceChildren();root.hidden=true;document.getElementById('page-error').textContent='Your account changed. Refresh to reopen this private exchange.';}});
  window.addEventListener('pagehide',()=>clearInterval(timer));render();await refresh();
};

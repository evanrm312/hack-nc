(function(){
  const form=document.getElementById('profile-form');if(!form)return;
  let loaded=false,busy=false,dirty=false;
  form.addEventListener("input",()=>{dirty=true;});
  form.addEventListener("change",()=>{dirty=true;});
  window.addEventListener("beforeunload",e=>{if(dirty&&!busy){e.preventDefault();e.returnValue="";}});
  async function load(profile){if(loaded)return;try{
    const {meeting_spots}=await api.get('/api/meeting-spots');
    const select=form.querySelector('select');select.replaceChildren(new Option('No preference',''));
    meeting_spots.forEach(s=>select.add(new Option(s.label,s.id)));select.value=profile.preferred_meeting_spot_id||'';
    form.querySelector('input').value=profile.display_name;loaded=true;
  }catch(_){document.getElementById('profile-status').textContent='Profile editor unavailable. Try refreshing.';}}
  document.addEventListener('campus:profile-ready',e=>load(e.detail));
  form.onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;const button=form.querySelector('button');button.disabled=true;
    try{await api.patch('/api/me',{display_name:form.querySelector('input').value.trim(),preferred_meeting_spot_id:form.querySelector('select').value||null});dirty=false;document.getElementById('profile-status').textContent='Profile saved.';}
    catch(err){document.getElementById('profile-status').textContent=Object.values(err.fields||{}).join('; ')||err.message;}
    finally{busy=false;button.disabled=false;}};
})();

// Catalog locations remain usable without tiles, coordinates or geolocation.
(function () {
  const C=window.CampusUI;
  const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
  window.campusMeetingPicker=function(root,spots,onChoose) {
    root.replaceChildren();root.classList.add("meeting-picker");
    const note=el('p','Review access information before proposing a meeting. Unknown means unverified; no location is guaranteed safe.');note.className='field__hint';root.append(note);
    const map=el('div');map.className='campus-map';map.setAttribute('aria-label','UNC campus reference map');
    const known=spots.filter(s=>s.latitude!=null&&s.longitude!=null);
    const zoom=16, n=2**zoom;
    const project=(lat,lon)=>[n*(lon+180)/360,n*(1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2];
    const center=project(35.9087,-79.047), x0=Math.floor(center[0])-1,y0=Math.floor(center[1])-1;
    // Only the 3×3 tiles displayed in this fixed campus viewport, normal browser cache.
    for(let x=0;x<3;x++)for(let y=0;y<3;y++) {
      const img=el('img');img.alt='';img.loading='lazy';img.referrerPolicy='strict-origin-when-cross-origin';img.src='https://tile.openstreetmap.org/'+zoom+'/'+(x0+x)+'/'+(y0+y)+'.png';
      img.style.cssText=`position:absolute;width:33.334%;height:33.334%;left:${x*100/3}%;top:${y*100/3}%;`;
      img.onerror=()=>{map.setAttribute('data-unavailable','true');};map.append(img);
    }
    const credit=el('a','© OpenStreetMap contributors');credit.href='https://www.openstreetmap.org/copyright';credit.className='map-credit';map.append(credit);root.append(map);
    const list=el('div');list.className='meeting-list';root.append(list);
    const buttons=[];
    const choose=(spot)=>{buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.spot===spot.id)));onChoose(spot);};
    for(const spot of spots) {
      const row=el('section');row.className='meeting-option';row.append(el('h3',spot.label),el('p',spot.public_area));
      const details=el('details');details.append(el('summary','Access and safety information'));
      if(spot.access_notes)details.append(el('p','Recorded catalog notes (not independently verified): '+spot.access_notes));
      for(const [key,label] of [['lighting','Lighting'],['cameras','Cameras'],['staffing','Staffing'],['public_access','Public access'],['opening_hours','Opening hours']])details.append(el('p',label+': '+((spot.safety_attributes||{})[key]||'Unknown')));
      if(spot.safety_source){const a=el('a','Safety source'+(spot.safety_checked_at?' · checked '+spot.safety_checked_at:''));a.href=spot.safety_source;details.append(a);}
      if(spot.coordinate_source){const a=el('a',spot.coordinate_description||'Coordinate source');a.href=spot.coordinate_source;details.append(a);}
      row.append(details);
      if(spot.straight_line_distances_m)row.append(el('p','Straight-line estimates: '+spot.straight_line_distances_m.join(' m / ')+' m. Not walking distances.'));
      if(spot.preferred_by_participant)row.append(el('p','A participant prefers this spot.'));
      const b=el('button','Propose '+spot.label);b.type='button';b.dataset.spot=spot.id;b.setAttribute('aria-pressed','false');b.onclick=()=>choose(spot);buttons.push(b);row.append(b);list.append(row);
      if(spot.latitude!=null) {
        const [x,y]=project(spot.latitude,spot.longitude),marker=el('button',String(spots.indexOf(spot)+1));marker.type='button';marker.title=spot.label;marker.setAttribute('aria-label','Propose '+spot.label);marker.className='map-marker';marker.dataset.spot=spot.id;marker.setAttribute('aria-pressed','false');marker.style.left=(x-x0)*100/3+'%';marker.style.top=(y-y0)*100/3+'%';marker.onclick=()=>choose(spot);buttons.push(marker);map.append(marker);
      }
    }
    if(!known.length)map.append(el('p','Coordinates unavailable. Choose from the list below.'));
  };
  window.campusExchangeLocations=async function(root,base,onChoose) {
    let busy=false;
    const form=el('form'),label=el('label','Your campus area or landmark'),input=el('input');input.id='private-landmark';input.maxLength=120;label.htmlFor=input.id;
    const note=el('p','Shared only with the other participant for this exchange. Cleared after 24 hours or when the exchange closes. Your profile preference is separate.');note.className='field__hint';
    const save=el('button','Save my area');save.type='submit';const clear=el('button','Clear my area');clear.type='button';const status=el('p');status.setAttribute('role','status');
    const catalog=el('div'),others=el('p'),near=el('select');near.id='nearby-campus-spot';near.add(new Option('No nearby catalog landmark',''));
    const nearLabel=el('label','Nearby catalog landmark (optional)');nearLabel.htmlFor=near.id;
    root.append(form,others,status,catalog);form.append(label,input,nearLabel,near,note,save,clear);
    let currentSpots=[];
    async function load(){const d=await api.get(base+'/locations');currentSpots=d.meeting_spots;if(near.options.length===1)currentSpots.filter(s=>s.latitude!=null).forEach(s=>near.add(new Option(s.label,s.id)));others.textContent=d.locations.map(l=>l.landmark||'Campus coordinates supplied').join(' · ')||'Participant areas not supplied. Locations are unranked.';window.campusMeetingPicker(catalog,d.meeting_spots,onChoose);}
    form.onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;save.disabled=true;try{const spot=currentSpots.find(s=>s.id===near.value);await api.put(base+'/locations/me',{landmark:input.value.trim()||spot?.label||null,latitude:spot?.latitude??null,longitude:spot?.longitude??null});status.textContent='Your area is saved.';await load();}catch(err){status.textContent=err.message;}finally{busy=false;save.disabled=false;}};
    clear.onclick=async()=>{try{await api.del(base+'/locations/me');input.value='';near.value='';await load();}catch(err){status.textContent=err.message;}};
    try{await load();}catch(err){status.textContent='Locations unavailable. Use the catalog selectors in your offer and retry.';}
  };
})();

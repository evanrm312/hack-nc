/* Community profiles use textContent/shared components; no secret code persistence. */
(function () {
  'use strict';
  const C = window.components, api = window.api;
  const $ = id => document.getElementById(id);
  const form = $('profile-form'), publicRoot = $('public-profile');
  if (!form && !publicRoot) return;
  const node = (tag, text, attrs = {}) => C.el(tag, Object.assign({text}, attrs));
  let profile = null, token = null, generation = 0, busy = false, dirty = false;
  const current = (g, t) => g === generation && t === api.getToken();

  function avatar(root, p) {
    root.replaceChildren();
    if (p.avatar_url) root.append(C.el('img', {src: p.avatar_url, alt: 'Avatar of ' + p.display_name}));
    else root.append(node('span', 'No avatar', {role: 'img', 'aria-label': 'No avatar for ' + p.display_name}));
  }
  function summary(root, p) {
    root.replaceChildren(node('h3', 'Public profile summary'), C.el('a', {href: '/profiles/' + encodeURIComponent(p.id), text: 'View public profile'}));
    const r = p.rating;
    root.append(node('p', r.review_count ? r.average.toFixed(1) + '/5 from ' + r.review_count + ' reviews' : 'No reviews yet.'));
    const counts = p.completed_counts;
    root.append(node('p', 'Completed: ' + counts.bought + ' bought · ' + counts.sold_lent_provided + ' sold/lent/provided · ' + counts.borrowed + ' borrowed · ' + counts.services + ' service participations'));
    if (p.transaction_history === null) root.append(node('p', 'Itemized history is private.'));
    else {
      const list = node('ul');
      p.transaction_history.forEach(h => list.append(node('li', h.listing_title + ' · ' + h.mode + ' · ' + h.role + ' · ' + api.formatTime(h.completed_at))));
      root.append(list.childNodes.length ? list : node('p', 'No public completed history.'));
    }
  }
  async function publicSummary(g, t) {
    const p = (await api.get('/api/profiles/' + encodeURIComponent(profile.id))).profile;
    if (current(g, t)) summary($('community-summary'), p);
  }
  function clubs(p) {
    const root = $('community-clubs'); root.replaceChildren();
    (p.clubs || []).forEach(m => root.append(node('p', m.club.name + ' · ' + m.role)));
    if (!p.clubs.length) root.append(node('p', 'You have not joined a club.'));
    $('community-manager').hidden = !p.clubs.some(m => m.role === 'manager');
  }
  async function approvals() {
    const g = generation, t = api.getToken(), root = $('club-reviews');
    root.replaceChildren(node('p', 'Loading approvals…'));
    try {
      const memberships = profile.clubs.filter(m => m.role === 'manager');
      const responses = await Promise.all(memberships.map(async m => ({club: m.club,
        exchanges: (await api.get('/api/clubs/' + encodeURIComponent(m.club.id) + '/exchanges')).exchanges})));
      if (!current(g, t)) return;
      root.replaceChildren(); let count = 0;
      responses.forEach(({club, exchanges}) => exchanges.filter(x => x.club_review_state === 'pending' && x.status === 'negotiating').forEach(x => {
        count++;
        const card = node('section', undefined, {className: 'card'});
        card.append(node('h4', x.listing_title), node('p', club.name),
          node('p', x.participants.owner + ' / ' + x.participants.requester + ' · ' + x.mode + ' · ' + x.status),
          node('p', 'Review: ' + x.club_review_state + ' · revision ' + x.offer_version));
        const terms = node('dl', undefined, {className: 'kv-list'});
        Object.entries(x.agreed_terms).forEach(([key, value]) => terms.append(node('dt', key.replaceAll('_', ' ')), node('dd', value == null ? 'Unknown' : key.endsWith('_cents') ? api.formatCents(value) : ['pickup_at', 'return_deadline', 'service_scheduled_at'].includes(key) ? api.formatTime(value) + ' Eastern' : String(value))));
        const note = node('textarea', undefined, {id: 'review-note-' + x.id, maxlength: 300, rows: 2});
        const label = node('label', 'Manager note (required for changes)', {'for': note.id});
        const result = node('p', undefined, {role: 'status'});
        const buttons = ['approve', 'request_changes'].map(decision => C.button({label: decision === 'approve' ? 'Approve' : 'Request changes', onClick: async () => {
          if (!current(g, t)) return;
          buttons.forEach(b => b.disabled = true);
          try {
            await api.post('/api/clubs/' + encodeURIComponent(club.id) + '/exchanges/' + encodeURIComponent(x.id) + '/review', {decision, note: note.value.trim() || null, version: x.offer_version});
            if (current(g, t)) await approvals();
          } catch (e) { if (current(g, t)) result.textContent = C.errorMessage(e); }
          finally { if (current(g, t)) buttons.forEach(b => b.disabled = false); }
        }}));
        card.append(terms, label, note, ...buttons, result); root.append(card);
      }));
      if (!count) root.append(node('p', 'No pending approvals.'));
    } catch (e) { if (current(g, t)) root.replaceChildren(node('p', C.errorMessage(e), {role: 'alert'})); }
  }
  async function load(p) {
    const t = api.getToken();
    if (profile && profile.id === p.id && token === t) return;
    profile = p; token = t; const g = ++generation;
    dirty = false;
    $('profile-name').value = p.display_name; $('profile-bio').value = p.bio || '';
    $('profile-year').value = p.graduation_year || ''; $('profile-history').checked = p.show_transaction_history;
    avatar($('community-avatar'), p); clubs(p);
    $('profile-status').textContent = 'Loading profile…';
    try {
      const {meeting_spots} = await api.get('/api/meeting-spots');
      if (!current(g, t)) return;
      const select = $('profile-spot'); select.replaceChildren(new Option('No preference', ''));
      meeting_spots.forEach(s => select.add(new Option(s.label, s.id))); select.value = p.preferred_meeting_spot_id || '';
      await publicSummary(g, t); if (!current(g, t)) return;
      $('profile-status').textContent = ''; await approvals();
    } catch (e) { if (current(g, t)) $('profile-status').textContent = C.errorMessage(e); }
  }
  if (publicRoot) {
    publicRoot.textContent = 'Loading profile…';
    api.get('/api/profiles/' + encodeURIComponent(publicRoot.dataset.profileId)).then(({profile: p}) => {
      publicRoot.replaceChildren(node('h1', p.display_name));
      const image = node('div', undefined, {className: 'photo-preview'}); avatar(image, p);
      publicRoot.append(image, node('p', p.bio || 'No bio provided.'), node('p', p.graduation_year ? 'Graduation year: ' + p.graduation_year : 'Graduation year not shared.'));
      const memberships = node('section'); memberships.append(node('h2', 'Clubs'));
      p.clubs.forEach(m => memberships.append(node('p', m.club.name + ' · ' + m.role)));
      if (!p.clubs.length) memberships.append(node('p', 'No club memberships.'));
      const stats = node('section'); summary(stats, p); publicRoot.append(memberships, stats);
    }).catch(e => publicRoot.replaceChildren(node('p', C.errorMessage(e), {role: 'alert'})));
    return;
  }
  document.addEventListener('campus:profile-ready', e => load(e.detail));
  document.addEventListener('campus:auth-changed', () => {
    if (token !== api.getToken()) {
      generation++; profile = null; dirty = false; token = null;
      form.reset(); $('join-club-form').reset(); $('avatar-form').reset();
      ['community-clubs', 'community-summary', 'club-reviews', 'community-avatar'].forEach(id => $(id).replaceChildren());
      $('community-manager').hidden = true;
    }
  });
  form.addEventListener('input', () => dirty = true);
  form.addEventListener('change', () => dirty = true);
  window.addEventListener('beforeunload', e => { if (dirty && !busy) { e.preventDefault(); e.returnValue = ''; } });
  form.onsubmit = async e => {
    e.preventDefault(); if (busy || !profile) return;
    const g = generation, t = token; busy = true; const button = form.querySelector('button'); button.disabled = true;
    try {
      const response = await api.patch('/api/me', {display_name: $('profile-name').value.trim(), bio: $('profile-bio').value.trim() || null,
        graduation_year: $('profile-year').value ? Number($('profile-year').value) : null,
        preferred_meeting_spot_id: $('profile-spot').value || null, show_transaction_history: $('profile-history').checked});
      if (!current(g, t)) return;
      profile = response.profile; dirty = false; $('profile-status').textContent = 'Profile saved.'; await publicSummary(g, t);
    } catch (e) { if (current(g, t)) $('profile-status').textContent = C.errorMessage(e); }
    finally { busy = false; button.disabled = false; }
  };
  $('join-club-form').onsubmit = async e => {
    e.preventDefault(); const g = generation, t = api.getToken(), button = e.target.querySelector('button'); button.disabled = true;
    const code = $('club-code').value; $('club-code').value = '';
    try {
      await api.post('/api/clubs/join', {code}); const p = (await api.get('/api/me')).profile;
      if (!current(g, t)) return;
      profile.clubs = p.clubs; clubs(profile); $('club-status').textContent = 'Club membership saved.'; await approvals();
    } catch (err) { if (current(g, t)) $('club-status').textContent = C.errorMessage(err); }
    finally { button.disabled = false; }
  };
  $('avatar-form').onsubmit = async e => {
    e.preventDefault(); const file = $('avatar-photo').files[0]; if (!file) return;
    const g = generation, t = api.getToken(), button = e.target.querySelector('button'); button.disabled = true;
    try {
      const {profile: p} = await api.upload('/api/me/avatar', 'photo', file);
      if (!current(g, t)) return;
      profile.avatar_url = p.avatar_url; avatar($('community-avatar'), profile); $('avatar-status').textContent = 'Avatar saved.'; e.target.reset();
    } catch (err) { if (current(g, t)) $('avatar-status').textContent = C.errorMessage(err); }
    finally { button.disabled = false; }
  };
  $('refresh-club-reviews').onclick = approvals;
})();

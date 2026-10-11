// Run with: node --test tests/browser_auth.test.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const root = path.join(__dirname, '..');
const apiSource = fs.readFileSync(path.join(root, 'static/js/api.js'), 'utf8');
const authSource = fs.readFileSync(path.join(root, 'static/js/auth.js'), 'utf8');

function harness({ signInPage = false } = {}) {
  const listeners = new Map();
  const elements = new Map();
  const storage = new Map();
  const requests = [];
  let authCallback;
  let session = null;
  let sessionError = null;
  let signOutCalls = 0;
  let signOutError = null;
  let apiFailure = null;
  let apiFailureStatus = 401;
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {
      hidden: true, textContent: '', value: '',
      addEventListener(event, fn) { this[event] = fn; },
      replaceChildren() {}, append() {},
    });
    return elements.get(id);
  };
  const document = {
    getElementById(id) {
      if (!signInPage && ['magic-link-form', 'sign-out', 'me-card', 'me-json', 'sign-in-error'].includes(id)) return null;
      return element(id);
    },
    createElement() { return { textContent: '', className: '' }; },
    addEventListener(event, fn) { listeners.set(event, fn); },
    dispatchEvent(event) { listeners.get(event.type)?.(); },
    head: { appendChild(script) { document.sdkScript = script; } },
  };
  const client = { auth: {
    onAuthStateChange(callback) { authCallback = callback; },
    async getSession() { return { data: { session }, error: sessionError }; },
    async signOut() { signOutCalls++; if (signOutError) return {error:signOutError}; session = null; authCallback?.('SIGNED_OUT', null); return { error: null }; },
    async signInWithOtp() { return { error: null }; },
  } };
  const context = {
    window: {
      CAMPUS_CONFIG: { auth_mode: 'supabase', supabase_url: 'https://example.supabase.co', supabase_anon_key: 'public-key' },
      localStorage: { getItem: (k) => storage.get(k) || null, setItem: (k, v) => storage.set(k, v), removeItem: (k) => storage.delete(k) },
      supabase: { createClient: () => client },
    },
    document,
    CustomEvent: class { constructor(type) { this.type = type; } },
    FormData: class {},
    location: { hash: '', pathname: '/', search: '', origin: 'http://localhost' },
    history: { replaceState() {} },
    fetch: async (url, options) => {
      requests.push({ url, options });
      const failure = apiFailure;
      const body = failure || { profile: { display_name: 'Member', badge: 'UNC email verified', verification_source: 'supabase' } };
      return { ok: !failure, status: failure ? apiFailureStatus : 200, text: async () => JSON.stringify(body) };
    },
  };
  vm.createContext(context);
  context.api = context.window.api;
  vm.runInContext(apiSource, context);
  context.api = context.window.api;
  vm.runInContext(authSource, context);
  document.sdkScript.onload();
  return {
    api: context.window.api, element, requests,
    setSession(value) { session = value; authCallback?.('TOKEN_REFRESHED', value); },
    setSessionError(value) { sessionError = value; },
    setApiFailure(value, status = 401) { apiFailure = value; apiFailureStatus = status; },
    signOutCalls: () => signOutCalls,
    setSignOutError(value) { signOutError = value; },
  };
}

test('every page initializes the session and API calls use refreshed tokens', async () => {
  const h = harness();
  h.setSession({ access_token: 'first' });
  await h.api.get('/api/me');
  assert.equal(h.requests.at(-1).options.headers.Authorization, 'Bearer first');
  h.setSession({ access_token: 'refreshed' });
  await h.api.get('/api/me');
  assert.equal(h.requests.at(-1).options.headers.Authorization, 'Bearer refreshed');
  assert.equal(h.api.getToken(), 'refreshed');
});

test('sign-out calls Supabase and clears app token', async () => {
  const h = harness({ signInPage: true });
  h.setSession({ access_token: 'first' });
  await h.api.get('/api/me');
  await h.element('sign-out').click();
  assert.equal(h.signOutCalls(), 1);
  assert.equal(h.api.getToken(), null);
});

test('expired session and rejected token clear the app token', async () => {
  const h = harness();
  h.setSession({ access_token: 'expired' });
  h.setSessionError(new Error('expired'));
  await assert.rejects(h.api.get('/api/me'), (err) => err.code === 'session_expired');
  assert.equal(h.api.getToken(), null);

  h.setSessionError(null);
  h.setSession({ access_token: 'bad-token' });
  h.setApiFailure({ error: { code: 'invalid_token', message: 'Session is invalid or expired', fields: {} } });
  await assert.rejects(h.api.get('/api/me'), (err) => err.code === 'invalid_token');
  assert.equal(h.api.getToken(), null);
});

test('public browsing remains available when session refresh fails', async () => {
  const h = harness();
  h.setSession({ access_token: 'expired' });
  h.setSessionError(new Error('expired'));
  await h.api.get('/api/listings?limit=10');
  assert.equal(h.requests.at(-1).options.headers.Authorization, undefined);
  await assert.rejects(h.api.get('/api/me'), (err) => err.code === 'session_expired');
});

test('database failure on /api/me does not make a saved session look signed out', async () => {
  const h = harness({ signInPage: true });
  h.setApiFailure({ error: { code: 'internal_error', message: 'Internal server error', fields: {} } }, 500);
  h.setSession({ access_token: 'saved-session' });
  await assert.rejects(h.api.get('/api/me'), (err) => err.status === 500);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(h.requests.at(-1).options.headers.Authorization, 'Bearer saved-session');
  assert.equal(h.api.getToken(), 'saved-session');
  assert.equal(h.element('nav-sign-in').textContent, 'Account');
  assert.equal(h.element('sign-out').hidden, false);
  assert.match(h.element('session-status').textContent, /Session saved/);
  assert.equal(h.signOutCalls(), 0);
});

 test('failed sign-out preserves actual authorization and shows retry message', async () => {
  const h = harness({signInPage:true});
  h.setSession({access_token:'existing-session'});
  h.setSignOutError({message:'unavailable'});
  await new Promise(resolve=>setImmediate(resolve));
  await h.element('sign-out').click();
  assert.equal(h.api.getToken(),'existing-session');
  assert.match(h.element('sign-in-error').textContent,/still signed in/i);
  assert.equal(h.element('sign-out').hidden,false);
 });

test('intended destinations are internal, never protocol-relative or backslash URLs', () => {
  // Pure redirect validator exposed for the shared callback and navigation flow.
  const h=harness();
  // Auth harness runs without URLSearchParams, so no navigation occurs during setup.
  const s=authSource.match(/const safeDestination = (.*);/)[1];
  const validate=vm.runInNewContext(s);
  assert.equal(validate('/exchanges/abc?tab=offer'),'/exchanges/abc?tab=offer');
  for(const value of ['https://elsewhere.example','//elsewhere.example','/\\elsewhere.example','/sign-in','javascript:alert(1)'])assert.equal(validate(value),null);
});

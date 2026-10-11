// Run with: node --test tests/browser_auth.test.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const root = path.join(__dirname, '..');
const apiSource = fs.readFileSync(path.join(root, 'static/js/api.js'), 'utf8');
const authSource = fs.readFileSync(path.join(root, 'static/js/auth.js'), 'utf8');

function harness({ signInPage = false, recovery = false, instantSignup = false } = {}) {
  const listeners = new Map();
  const elements = new Map();
  const storage = new Map();
  const requests = [];
  const authCalls = [];
  const sessionStorage = new Map();
  const navigations = [];
  let providerError = null;
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
      replaceChildren() {}, append() {}, focus() {},
      querySelectorAll() { return [element(id + '-submit')]; },
    });
    return elements.get(id);
  };
  const document = {
    getElementById(id) {
      if (id === 'sandbox-form') return null;
      if (!signInPage && !['session-status', 'nav-sign-in'].includes(id)) return null;
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
    async signInWithPassword(body) {
      authCalls.push({method:'password', body});
      if (!providerError) { session={access_token:'password-token'}; authCallback?.('SIGNED_IN',session); }
      return {error:providerError};
    },
    async signUp(body) {
      authCalls.push({method:'signup',body});
      if (instantSignup && !providerError) { session={access_token:'signup-token'}; authCallback?.('SIGNED_IN',session); }
      return {data:{session},error:providerError};
    },
    async resetPasswordForEmail(email, options) { authCalls.push({method:'recovery',email,options}); return {error:providerError}; },
    async updateUser(body) { authCalls.push({method:'update',body}); return {error:providerError}; },
  } };
  const context = {
    window: {
      CAMPUS_CONFIG: { auth_mode: 'supabase', allowed_email_domain:'unc.edu', supabase_url: 'https://example.supabase.co', supabase_anon_key: 'public-key' },
      localStorage: { getItem: (k) => storage.get(k) || null, setItem: (k, v) => storage.set(k, v), removeItem: (k) => storage.delete(k) },
      sessionStorage: {getItem:k=>sessionStorage.get(k)||null,setItem:(k,v)=>sessionStorage.set(k,v),removeItem:k=>sessionStorage.delete(k)},
      supabase: { createClient: () => client },
    },
    document,
    CustomEvent: class { constructor(type) { this.type = type; } },
    FormData: class {},
    location: { hash: recovery ? '#type=recovery' : '', pathname: signInPage ? '/sign-in' : '/', search: '', origin: 'http://localhost', assign:value=>navigations.push(value) },
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
    api: context.window.api, element, requests, authCalls, sessionStorage, navigations,
    setProviderError(value) { providerError=value; },
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

const submit = async (h,id) => h.element(id).submit({preventDefault(){}});

test('password login authenticates without sending an email and clears the input', async () => {
  const h=harness({signInPage:true});
  h.element('email').value='member@unc.edu';
  h.element('password').value='only-in-test';
  await submit(h,'password-sign-in-form');
  assert.deepEqual(h.authCalls.map(c=>c.method),['password']);
  assert.equal(h.api.getToken(),'password-token');
  assert.equal(h.element('password').value,'');
  assert.equal(h.element('password-sign-in-form').hidden,true);
});

test('wrong-domain login never calls the provider and invalid credentials do not invent a session', async () => {
  const h=harness({signInPage:true});
  h.element('email').value='member@unc.edu.evil.com';
  h.element('password').value='only-in-test';
  await submit(h,'password-sign-in-form');
  assert.equal(h.authCalls.length,0);
  h.element('email').value='member@unc.edu';
  h.setProviderError({status:400,code:'invalid_credentials'});
  await submit(h,'password-sign-in-form');
  assert.equal(h.api.getToken(),null);
  assert.match(h.element('sign-in-error').textContent,/Check your email and password/);
});

test('signup validates password confirmation and leaves email verification with Supabase', async () => {
  const h=harness({signInPage:true});
  h.element('signup-email').value='new@unc.edu';
  h.element('signup-password').value='only-in-test';
  h.element('signup-password-confirm').value='mismatch';
  await submit(h,'password-sign-up-form');
  assert.equal(h.authCalls.length,0);
  h.element('signup-password-confirm').value='only-in-test';
  await submit(h,'password-sign-up-form');
  assert.equal(h.authCalls[0].body.options.emailRedirectTo,'http://localhost/sign-in');
  assert.equal(h.api.getToken(),null);
  assert.match(h.element('auth-hint').textContent,/confirm your account once/);
  assert.equal(h.element('signup-password').value,'');
});

test('signup with confirmation disabled immediately establishes a session', async () => {
  const h=harness({signInPage:true,instantSignup:true});
  h.element('signup-email').value='new@unc.edu';
  h.element('signup-password').value='only-in-test';
  h.element('signup-password-confirm').value='only-in-test';
  await submit(h,'password-sign-up-form');
  assert.equal(h.api.getToken(),'signup-token');
  assert.deepEqual(h.authCalls.map(c=>c.method),['signup']);
  assert.equal(h.element('registration-details').hidden,true);
  assert.match(h.element('auth-hint').textContent,/ready to test/);
  assert.equal(h.element('signup-password').value,'');
  assert.ok(h.requests.some(r=>r.url==='/api/me'));
});

test('recovery uses the approved callback and a generic account-existence message', async () => {
  const h=harness({signInPage:true});
  h.element('email').value='member@unc.edu';
  await h.element('password-recovery').click();
  assert.equal(h.authCalls[0].method,'recovery');
  assert.equal(h.authCalls[0].options.redirectTo,'http://localhost/sign-in');
  assert.match(h.element('auth-hint').textContent,/If this email has an account/);
  h.setProviderError({status:429});
  await h.element('password-recovery').click();
  assert.match(h.element('sign-in-error').textContent,/temporarily limited/);
});

test('password update requires a real session, stays on recovery until saved, then resumes destination', async () => {
  const h=harness({signInPage:true,recovery:true});
  h.sessionStorage.set('campus_return_to','/exchanges');
  h.element('new-password').value='only-in-test';
  h.element('new-password-confirm').value='only-in-test';
  await submit(h,'password-update-form');
  assert.equal(h.authCalls.length,0);
  h.setSession({access_token:'recovery-session'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(h.navigations,[]);
  h.setProviderError({status:500});
  await submit(h,'password-update-form');
  assert.equal(h.sessionStorage.get('campus_password_recovery'),'1');
  assert.deepEqual(h.navigations,[]);
  h.setProviderError(null);
  h.element('new-password').value='only-in-test';
  h.element('new-password-confirm').value='only-in-test';
  await submit(h,'password-update-form');
  assert.equal(h.sessionStorage.has('campus_password_recovery'),false);
  assert.deepEqual(h.navigations,['/exchanges']);
  assert.equal(h.element('new-password').value,'');
  assert.equal(h.requests.some(r=>r.options.body?.includes('only-in-test')),false);
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

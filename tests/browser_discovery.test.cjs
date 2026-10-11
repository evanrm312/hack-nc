// Pure selection checks protect the private purchase-history adapter.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/js/discovery.js'), 'utf8');
function selection() {
  const context = { window: { components: {} }, document: { getElementById: () => null, body: { dataset: {} } } };
  vm.runInNewContext(source, context);
  return context.window.campusDiscovery.completedPurchases;
}
test('history includes only completed sales bought by the current user', () => {
  const rows = [
    { id: 'purchase', mode: 'sale', status: 'completed', requester_id: 'me' },
    { id: 'loan', mode: 'borrow', status: 'completed', requester_id: 'me' },
    { id: 'service', mode: 'service', status: 'completed', requester_id: 'me' },
    { id: 'pending', mode: 'sale', status: 'reserved', requester_id: 'me' },
    { id: 'cancelled', mode: 'sale', status: 'cancelled', requester_id: 'me' },
    { id: 'sold-by-me', mode: 'sale', status: 'completed', owner_id: 'me', requester_id: 'other' },
  ];
  assert.deepEqual(Array.from(selection()(rows, 'me'), row => row.id), ['purchase']);
});
test('missing identity and empty history do not reveal purchases', () => {
  assert.equal(selection()([{ mode: 'sale', status: 'completed' }], null).length, 0);
  assert.equal(selection()(null, 'me').length, 0);
});

test('a late history response cannot restore private content after sign-out', async () => {
  const events = {};
  const hosts = { 'recommended-items': { children: [], append(n) { this.children.push(n); } }, 'previous-buys': { children: [], append(n) { this.children.push(n); } } };
  let token = 'mock-session';
  let finishHistory;
  const pending = new Promise(resolve => { finishHistory = resolve; });
  const C = { clear(host) { host.children = []; return host; }, el(tag, attrs, ...children) { return { tag, attrs, children }; } };
  const context = {
    window: { components: C, addEventListener() {} },
    document: { body: { dataset: { page: 'home' } }, getElementById: id => hosts[id], addEventListener: (name, fn) => { events[name] = fn; } },
    api: { getToken: () => token, get: (path) => path === '/api/me' ? Promise.resolve({ profile: { id: 'me' } }) : path === '/api/exchanges' ? pending : Promise.resolve({ listings: [] }) },
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  token = null;
  events['campus:auth-changed']();
  finishHistory({ exchanges: [{ id: 'private-purchase', mode: 'sale', status: 'completed', requester_id: 'me', listing: { title: 'Private history' } }] });
  await new Promise(resolve => setImmediate(resolve));
  assert.match(hosts['previous-buys'].children[0].attrs.text, /Sign in/);
  assert.doesNotMatch(JSON.stringify(hosts['previous-buys']), /Private history|private-purchase/);
});

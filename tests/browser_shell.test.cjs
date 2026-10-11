// Launcher behavior checks in a lightweight DOM harness (no browser/network).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/js/shell.js'), 'utf8');
function harness() {
  const events = {};
  let document;
  function element() {
    return { attrs: {}, events: {}, hidden: true, dataset: {}, value: '',
      setAttribute(k,v) { this.attrs[k] = v; },
      addEventListener(k,fn) { this.events[k] = fn; },
      focus() { document.activeElement = this; },
      contains(el) { return this === el; },
    };
  }
  const toggle = element(), menu = element(), link = element(), outside = element(), text = element();
  const examples = [element(), element()];
  examples[0].dataset.example = 'Original example'; examples[1].dataset.example = 'Another example';
  menu.contains = (el) => el === menu || el === link;
  menu.querySelector = () => link;
  document = { activeElement: outside, getElementById(id) { return { 'start-toggle': toggle, 'start-menu': menu, 'request-text': text }[id]; }, querySelectorAll() { return examples; }, addEventListener(k,fn) { const previous = events[k]; events[k] = (event) => { if (previous) previous(event); fn(event); }; } };
  vm.runInNewContext(source, { document });
  return { document, events, toggle, menu, link, outside, text, examples };
}
test('launcher opens with destination focus and closes with Escape restoring opener', () => {
  const h = harness(); h.toggle.events.click();
  assert.equal(h.menu.hidden, false); assert.equal(h.toggle.attrs['aria-expanded'], 'true'); assert.equal(h.document.activeElement, h.link);
  let prevented = false; h.events.keydown({ key: 'Escape', preventDefault() { prevented = true; } });
  assert.equal(prevented, true); assert.equal(h.menu.hidden, true); assert.equal(h.document.activeElement, h.toggle); assert.equal(h.toggle.attrs['aria-expanded'], 'false');
});
test('outside pointer closes, while inside interaction does not dismiss', () => {
  const h = harness(); h.toggle.events.click(); h.events.pointerdown({ target: h.link }); assert.equal(h.menu.hidden, false);
  h.events.pointerdown({ target: h.outside }); assert.equal(h.menu.hidden, true); assert.equal(h.document.activeElement, h.toggle);
});
test('tabbing outside dismisses without stealing the destination focus', () => {
  const h = harness(); h.toggle.events.click(); h.outside.focus(); h.events.focusin({ target: h.outside });
  assert.equal(h.menu.hidden, true); assert.equal(h.document.activeElement, h.outside);
});
test('following a launcher link closes the menu without blocking navigation', () => {
  const h = harness(); h.toggle.events.click(); h.menu.events.click({ target: { closest: () => h.link } }); assert.equal(h.menu.hidden, true);
});
test('example pressed states track exact text and clear on editing', () => {
  const h = harness(); h.examples[0].events.click(); assert.equal(h.text.value, 'Original example'); assert.equal(h.examples[0].attrs['aria-pressed'], 'true');
  h.text.value += ' edited'; h.text.events.input(); assert.equal(h.examples[0].attrs['aria-pressed'], 'false'); assert.equal(h.examples[1].attrs['aria-pressed'], 'false');
});

const test=require('node:test'), assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const context={window:{localStorage:{getItem:()=>null},addEventListener(){}},document:{dispatchEvent(){}},CustomEvent:class{},FormData:class{}};
vm.runInNewContext(fs.readFileSync(__dirname+'/../static/js/api.js','utf8'),context);
const api=context.window.api;
test('date editors use Eastern time independent of browser timezone',()=>{
 assert.equal(api.timeInput('2030-10-12T12:00:00Z'),'2030-10-12T08:00');
 assert.equal(api.timeToUtc('2030-10-12T08:00'),'2030-10-12T12:00:00.000Z');
 assert.equal(api.timeToUtc('2030-01-12T08:00'),'2030-01-12T13:00:00.000Z');
});
test('DST gaps and repeated times cannot silently shift a meeting',()=>{
 assert.throws(()=>api.timeToUtc('2026-03-08T02:30'));
 assert.throws(()=>api.timeToUtc('2026-11-01T01:30'));
 assert.throws(()=>api.timeToUtc('2026-02-30T08:00'));
 assert.equal(api.timeToUtc(''),null);
});
test('display is compact, zoned and omits seconds',()=>{
 assert.match(api.formatTime('2030-10-12T12:00:00Z'),/Oct 12, 2030.*8:00.*EDT/);
 assert.doesNotMatch(api.formatTime('2030-10-12T12:00:00Z'),/:00:00/);
 assert.equal(api.formatTime('bad'),'unknown');
 assert.equal(api.formatTimeRange(null,null),'unknown');
 assert.match(api.formatTimeRange('2030-10-12T12:00:00Z','2030-10-12T14:00:00Z'),/Oct 12/);
});

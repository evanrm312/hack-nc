const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function harness() {
 const events={},winEvents={},timers=new Map();let token='test',calls=0,id=0;
 const node=()=>({hidden:true,textContent:'',children:[],setAttribute(){},contains:()=>false,focus(){},append(...x){this.children.push(...x)},replaceChildren(){this.children=[]},classList:{add(){}}});
 const toggle=node(),panel=node(),list=node(),error=node(),readAll=node(),button=node();panel.querySelector=s=>({'[data-notifications]':list,'[data-error]':error,'[data-read-all]':readAll,button})[s];
 const document={hidden:false,getElementById:id=>id==='notifications-toggle'?toggle:panel,createElement:node,addEventListener:(n,f)=>events[n]=f};
 const context={document,window:{innerWidth:1440,addEventListener:(n,f)=>winEvents[n]=f},api:{getToken:()=>token,get:async()=>{calls++;return {notifications:[{id:'n',kind:'message',url:null,read_at:null}],unread_count:1}},post:async()=>({notification:{url:null}})},location:{assign(){throw new Error('inaccessible destination navigated')}},setTimeout:f=>{timers.set(++id,f);return id},clearTimeout:i=>timers.delete(i)};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../static/js/notifications.js','utf8'),context);
 return {events,document,timers,list,toggle,panel,setToken:t=>token=t,calls:()=>calls};
}
const settle=()=>new Promise(r=>setImmediate(r));
test('polling stops when hidden and on signout, resumes once visible',async()=>{
 const h=harness();await settle();assert.equal(h.timers.size,1);
 h.document.hidden=true;h.events.visibilitychange();assert.equal(h.timers.size,0);
 h.document.hidden=false;h.events.visibilitychange();await settle();assert.equal(h.timers.size,1);
 h.setToken(null);h.events['campus:auth-changed']();await settle();assert.equal(h.timers.size,0);assert.equal(h.toggle.hidden,true);assert.equal(h.list.children.length,0);
});
test('inaccessible exchange renders a graceful non-link and can be marked read',async()=>{
 const h=harness();await settle();const row=h.list.children[0];assert.equal(row.children[0].textContent,'Exchange no longer available');assert.equal(row.children[0].href,undefined);assert.equal(row.children[1].disabled,false);
});

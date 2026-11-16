const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {JSDOM}=require('../frontend/node_modules/jsdom');
const source=fs.readFileSync('daily_sessions.py','utf8').split("BROWSER_JS='''")[1].split("'''",1)[0].replace('export default function(component)','function render(component)');
let now=1700000000000;
function browser(saved,blocked=false){const dom=new JSDOM('<html><body></body></html>',{url:'https://example.streamlit.app',pretendToBeVisual:true});const w=dom.window;const events=[],timers=[],timeouts=[];if(saved)w.localStorage.setItem('workspace_day_test',saved);
 if(blocked){Object.defineProperty(w.document,'cookie',{get:()=>'',set:()=>{throw Error('blocked')}});Object.defineProperty(w,'localStorage',{value:{getItem:()=>null,setItem:()=>{throw Error('blocked')},removeItem:()=>{throw Error('blocked')}}})}
 const context=vm.createContext({window:w,document:w.document,location:w.location,localStorage:w.localStorage,Date:{now:()=>now},setInterval:fn=>{timers.push(fn);return timers.length},setTimeout:fn=>{timeouts.push(fn);return timeouts.length},Array,JSON,Math,encodeURIComponent,decodeURIComponent});vm.runInContext(source,context);
 return {w,events,timers,timeouts,render(data){context.render({data,setStateValue:(key,value)=>events.push([key,value])});},value(key){const session=events.filter(e=>e[0]==='session').at(-1)?.[1];return key==='browser'?session?.browser:key==='ack'?session?.receipt?.nonce:key==='storage'?session?.receipt:events.filter(e=>e[0]===key).at(-1)?.[1]}};
}
const data={name:'workspace_day_test',instance:'first',action:null},a=browser();a.render(data);assert.equal(a.value('browser').token,'');
const token='t'.repeat(43),action={value:token,expires:now/1000+10000,nonce:'write-1'};a.render({...data,action});assert.equal(a.value('ack'),'write-1');assert.equal(a.value('storage').saved,true);const saved=a.w.localStorage.getItem(data.name);assert.equal(JSON.parse(saved).token,token);assert(!saved.includes('password'));
// A fresh document/WebSocket with no incoming cookie must still recover its token.
const b=browser(saved);assert.equal(b.w.document.cookie,'');b.render({...data,instance:'refreshed'});assert.equal(b.value('browser').token,token);
// Passing null on ordinary rerenders must not erase the saved daily login.
b.render({...data,instance:'refreshed'});assert.equal(JSON.parse(b.w.localStorage.getItem(data.name)).token,token);
const count=b.events.length;now+=301000;b.timers.forEach(fn=>fn());assert.equal(b.events.length,count,'Idle timer must emit no activity or requests');
b.w.document.dispatchEvent(new b.w.Event('pointerdown'));assert(b.value('activity').at===now/1000,'Real interaction resumes activity');
b.render({...data,instance:'refreshed',action:{value:'',expires:0,nonce:'logout'}});assert.equal(b.w.localStorage.getItem(data.name),null);assert.equal(b.value('ack'),'logout');
const expired=browser(saved);now+=11000000;expired.render({...data,instance:'tomorrow'});assert.equal(expired.value('browser').token,'');
const stale=browser(JSON.stringify({token:'s'.repeat(43),expires:now/1000+1000}));stale.w.document.cookie=data.name+'='+token+'; Path=/';stale.render({...data,instance:'two-stores'});assert.equal(stale.value('browser').tokens[0],'s'.repeat(43));assert.equal(stale.value('browser').tokens[1],token);stale.w.close();
const blocked=browser(null,true);blocked.render({...data,action});assert.equal(blocked.value('storage').saved,false,'Blocked storage must not be reported as persisted');blocked.w.close();
const retry=browser(JSON.stringify({token,expires:now/1000+1000}));retry.render({...data,instance:'lost-handoff',probe:true});retry.timeouts.forEach(fn=>fn());assert.equal(retry.events.filter(e=>e[0]==='session').length,4,'Startup handshake retransmission is bounded');assert.equal(retry.value('browser').token,token);retry.render({...data,instance:'lost-handoff',probe:false});const settled=retry.events.length;retry.timeouts.forEach(fn=>fn());assert.equal(retry.events.length,settled,'Acknowledged restoration stops retries');retry.w.close();
const receipt=a.events.find(e=>e[0]==='session'&&e[1].receipt);assert.equal(receipt[1].receipt.saved,true,'Storage result and acknowledgement travel atomically');
console.log('PASS: browser write/ack, refresh without cookie headers, rerender persistence, idle silence, activity resume, logout and expiry.');
a.w.close();b.w.close();expired.w.close();

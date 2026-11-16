const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
require.extensions['.ts']=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('',{url:'https://planning.test'});Object.assign(global,{window:dom.window,document:dom.window.document});
const storage=new Map();let who='a',source='v1',blocked=false,denied=false,wait=null,calls=[],transferred=0;
global.indexedDB={open(){if(blocked)throw Error('Blocked');const r={result:{objectStoreNames:{contains:()=>true},close(){},transaction(){const tx={objectStore(){return {get(key){const r={};queueMicrotask(()=>{r.result=storage.get(key);r.onsuccess?.()});return r},put(value,key){storage.set(key,value);queueMicrotask(()=>tx.oncomplete?.())},getAllKeys(){const r={};queueMicrotask(()=>{r.result=[...storage.keys()].sort();r.onsuccess?.()});return r},getAll(){const r={};queueMicrotask(()=>{r.result=[...storage.keys()].sort().map(k=>storage.get(k));r.onsuccess?.()});return r},delete(key){storage.delete(key)}}}};return tx}}};queueMicrotask(()=>r.onsuccess());return r}};
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{tableColumnSnapshot:()=>({user:who,accessScope:who+'-rights',version:'master'}),rpc:async(operation,input)=>{calls.push([operation,input]);if(denied)throw Error('Denied');if(wait)return new Promise(resolve=>wait=resolve);const stamp=JSON.stringify([source,operation,input.fy,input.basis,input.segments]);if(input.known_stamp===stamp)return {stamp,not_modified:true};transferred++;return {stamp,data:{rows:[[source,input.basis||operation]]}}}}};
const fresh=()=>{delete require.cache[require.resolve('../src/cached-view.ts')];return require('../src/cached-view.ts')};
(async()=>{
 let cache=fresh();const stamp=JSON.stringify([source,'production_status',undefined,undefined,undefined]);const prepared={rows:[['ready batch',85]]};
 cache.primeView('production_status',prepared,stamp);await new Promise(r=>setImmediate(r));assert.equal(calls.length,0,'Seeding startup rows makes no request');
 assert.deepEqual(await cache.cachedView('production_status'),prepared);assert.equal(transferred,0,'First refresh validates metadata without re-transferring startup rows');assert.equal(calls.at(-1)[1].known_stamp,stamp);
 cache=fresh();assert.deepEqual(await cache.cachedView('production_status'),prepared);assert.equal(transferred,0,'Fresh login/runtime reuses persisted rows');
 const clock=Date.now;Date.now=()=>clock()+86400000;cache=fresh();assert.deepEqual(await cache.cachedView('production_status'),prepared);Date.now=clock;assert.equal(transferred,0,'Day change does not expire the batch cache');
 source='new-plan';assert.equal((await cache.cachedView('production_status')).rows[0][0],'new-plan');assert.equal(transferred,1,'Changed plan/workbook transfers the new portion once');
 await cache.cachedView('production_status');assert.equal(transferred,1);
 denied=true;await assert.rejects(cache.cachedView('production_status'),/Denied/);denied=false;who='another';cache=fresh();await cache.cachedView('production_status');assert.equal(calls.at(-1)[1].known_stamp,undefined,'Other account cannot reuse this snapshot');
 dom.window.close();console.log('PASS: startup-seeded batch cache, first-check metadata only, fresh login/day reuse, one changed-source transfer and live authorization/account isolation.');
})().catch(e=>{console.error(e);process.exitCode=1});

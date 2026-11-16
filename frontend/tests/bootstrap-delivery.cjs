const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript');
require.extensions['.ts']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,f);
const listeners={},sent=[],updates=[];global.window={addEventListener:(n,f)=>listeners[n]=f,parent:{postMessage:x=>sent.push(x)},screen:{availHeight:900},fetch:global.fetch,dispatchEvent:e=>updates.push(e.type)};
global.setTimeout=()=>1;global.setInterval=()=>1;
const bridge=require('../src/bridge.ts'),ready=[];bridge.startBridge(args=>ready.push(args));
const render=args=>listeners.message({source:window.parent,origin:'https://planning.test',data:{type:'streamlit:render',args}}),tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const base={user:'owner',role:'admin',version:'v1',bootstrapId:'a'.repeat(64)};
 render({...base,data:{filename:'A'},tables:[]});const request=bridge.rpc('heartbeat');await tick();let message=sent.filter(x=>x.value).at(-1).value;assert.equal(message.knownBootstrapId,base.bootstrapId);
 render({...base,data:null,tables:null,response:{id:message.id,body:{ok:true}}});await request;assert.equal(ready.at(-1).data.filename,'A');assert.equal((await (await window.fetch('/api/data')).json()).filename,'A');
 const before=updates.filter(x=>x==='stock-data-updated').length;render({...base,bootstrapId:'b'.repeat(64),data:{filename:'B'},tables:[]});assert.equal(ready.at(-1).data.filename,'B');assert.equal(updates.filter(x=>x==='stock-data-updated').length,before+1,'Availability/source signature alone refreshes the visible payload');
 const callbacks=ready.length,newIdentity={...base,user:'viewer',role:'viewer',bootstrapId:'c'.repeat(64),data:null,tables:null};render(newIdentity);render(newIdentity);await tick();assert.equal(ready.length,callbacks,'Never show the prior account data');const recovery=sent.filter(x=>x.value?.action==='workspace_bootstrap');assert.equal(recovery.length,1,'A missing browser copy requests recovery only once');
 message=recovery[0].value;render({...newIdentity,data:{filename:'Scoped C'},tables:[],response:{id:message.id,body:{ok:true}}});await tick();assert.equal(ready.at(-1).data.filename,'Scoped C');console.log('PASS: existing RPC acknowledgement, compact response reuse, source invalidation and account-safe bootstrap recovery.');
})().catch(e=>{console.error(e);process.exitCode=1});

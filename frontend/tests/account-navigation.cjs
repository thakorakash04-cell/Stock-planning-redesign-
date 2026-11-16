const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript');
require.extensions['.ts']=(module,name)=>module._compile(ts.transpileModule(fs.readFileSync(name,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,name);
const sent=[],listeners={};
global.window={addEventListener(name,fn){listeners[name]=fn},parent:{postMessage:packet=>sent.push(packet)},fetch:global.fetch,dispatchEvent(){},screen:{availHeight:900}};
global.setTimeout=()=>1;global.setInterval=()=>1;
const bridge=require('../src/bridge.ts');bridge.startBridge(()=>{});
listeners.message({source:window.parent,origin:'https://workspace.test',data:{type:'streamlit:render',args:{user:'owner',role:'admin',data:{filename:'test'},version:'v1'}}});
const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 bridge.rpc('heartbeat');await tick();
 assert.equal(sent.at(-1).value.action,'heartbeat');
 bridge.saveViewPreference('grid:main:A',{hidden:['Qty']});bridge.flushPreferences();
 const queued=bridge.rpc('heartbeat').catch(()=>{});
 for(const action of ['open_admin','open_workbook','open_email','open_history','logout']){
  bridge.openAccount(action);
  assert.equal(sent.at(-1).value.action,action,'navigation must not await preference acknowledgement');
  assert.deepEqual(sent.at(-1).value.preferences,[{scope:'grid:main:A',value:{hidden:['Qty']}}]);
 }
 const navigationCount=sent.filter(p=>p.value).length,heartbeat=sent.find(p=>p.value?.action==='heartbeat').value;
 listeners.message({source:window.parent,origin:'https://workspace.test',data:{type:'streamlit:render',args:{user:'owner',response:{id:heartbeat.id,body:{ok:true}}}}});
 await tick();await queued;
 assert.equal(sent.filter(p=>p.value).length,navigationCount,'queued preference/heartbeat cannot replace navigation');
 console.log('Passed: all administration routes open immediately with dirty preferences; queued background RPCs cannot overwrite navigation.');
})().catch(error=>{console.error(error);process.exitCode=1});


const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript');
require.extensions['.ts']=(module,name)=>module._compile(ts.transpileModule(fs.readFileSync(name,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,name);
const sent=[],listeners={},timers=[];let now=1000000;Date.now=()=>now;
global.document={hidden:false,addEventListener(name,fn){(listeners[name]??=[]).push(fn)}};
global.window={location:{origin:'https://workspace.test'},addEventListener(name,fn){(listeners[name]??=[]).push(fn)},parent:{postMessage:packet=>sent.push(packet)},fetch:global.fetch,dispatchEvent(){},screen:{availHeight:900}};
global.setTimeout=()=>1;global.setInterval=fn=>{timers.push(fn);return 1};
const bridge=require('../src/bridge.ts');bridge.startBridge(()=>{});
const message=x=>listeners.message.forEach(fn=>fn({source:window.parent,origin:'https://workspace.test',data:{type:'streamlit:render',args:x}}));
message({user:'owner',role:'admin',data:{filename:'test'},version:'v1'});
const tick=()=>new Promise(r=>setImmediate(r)),calls=()=>sent.filter(x=>x.value?.action==='heartbeat');
(async()=>{
 assert(bridge.browserActive());timers.forEach(fn=>fn());await tick();assert.equal(calls().length,1);
 message({user:'owner',role:'admin',response:{id:calls()[0].value.id,body:{ok:true}}});await tick();
 now+=300000;assert(!bridge.browserActive());timers.forEach(fn=>fn());await tick();assert.equal(calls().length,1,'No heartbeat after five idle minutes');
 listeners.pointerdown.forEach(fn=>fn());assert(bridge.browserActive());timers.forEach(fn=>fn());await tick();assert.equal(calls().length,2,'Interaction resumes refresh without password');
 message({user:'owner',role:'admin',response:{id:calls()[1].value.id,body:{ok:true}}});await tick();
 document.hidden=true;timers.forEach(fn=>fn());await tick();assert.equal(calls().length,2,'Hidden tabs must not query');
 console.log('Passed: heartbeat pauses after five minutes/hidden tab and resumes on actual interaction.');
})().catch(e=>{console.error(e);process.exit(1)});

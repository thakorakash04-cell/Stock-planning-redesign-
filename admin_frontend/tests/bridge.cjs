const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript');
require.extensions['.ts']=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,n);
const sent=[],listeners={};global.parent={postMessage:x=>sent.push(x)};global.window={innerHeight:800,addEventListener:(n,fn)=>listeners[n]=fn};global.setTimeout=()=>1;global.setInterval=()=>1;
const bridge=require('../src/bridge.ts');const bootstrap={identity:{username:'admin'},settings:{}};
listeners.message({source:parent,data:{type:'streamlit:render',args:{initialPage:'settings',bootstrap}}});
(async()=>{
 await bridge.ready;assert.equal(bridge.initialPage(),'settings');assert.deepEqual(bridge.initialData(),bootstrap);
 bridge.call('emailInfo');await Promise.resolve();await Promise.resolve();
 assert.equal(sent.at(-1).value.operation,'emailInfo');
 const queued=bridge.call('workbookInfo');await Promise.resolve();
 await bridge.call('consoleClose');assert.equal(sent.at(-1).value.operation,'consoleClose');
 const n=sent.length,old=sent.find(x=>x.value?.operation==='emailInfo').value;
 listeners.message({source:parent,data:{type:'streamlit:render',args:{response:{id:old.id,body:{}}}}});
 await Promise.resolve();assert.equal(sent.length,n,'pending request cannot replace close');
 console.log('Passed: initial administration data arrives without an RPC; Back bypasses pending requests.');
})().catch(e=>{console.error(e);process.exitCode=1});

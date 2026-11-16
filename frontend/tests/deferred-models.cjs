const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript');require.extensions['.ts']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,f);
const listeners={},sent=[];global.window={addEventListener:(n,f)=>listeners[n]=f,parent:{postMessage:x=>sent.push(x)},screen:{availHeight:900},fetch:global.fetch,dispatchEvent:()=>{}};global.setTimeout=()=>1;global.setInterval=()=>1;
const bridge=require('../src/bridge.ts');bridge.startBridge(()=>{});const tick=()=>new Promise(r=>setImmediate(r));
const render=args=>listeners.message({source:window.parent,origin:'https://planning.test',data:{type:'streamlit:render',args}}),base={user:'owner',role:'admin',permissions:{},version:'v1',accessScope:'owner',modelScope:'models1',bootstrapId:'b1',tablesDeferred:true,data:{filename:'Master.xlsx'},tables:null};
const models=[{name:'MB52',headers:['Material','Qty'],rows:[['A',3],['B',9]]}],request=()=>window.fetch('/api/details',{method:'POST',body:JSON.stringify({tab:0,row:['A'],col:0})});
(async()=>{
 render(base);assert.equal(sent.filter(x=>x.value).length,0,'Initial rendering does not fetch models');
 const a=request(),b=request();await tick();let call=sent.filter(x=>x.value).at(-1).value;assert.equal(call.action,'workspace_model_tables');assert.equal(sent.filter(x=>x.value?.action==='workspace_model_tables').length,1,'Concurrent drill-downs share one load');
 render({...base,data:null,response:{id:call.id,body:{tables:models,version:'v1',modelScope:'models1'}}});assert.equal((await (await a).json()).available,true);assert.equal((await (await b).json()).rows[0][0],'A');
 await request();assert.equal(sent.filter(x=>x.value?.action==='workspace_model_tables').length,1,'Reopened records reuse the same immutable model snapshot');
 render({...base,bootstrapId:'branding-only',data:{filename:'Master.xlsx',portal:{title:'Updated title'}}});await request();assert.equal(sent.filter(x=>x.value?.action==='workspace_model_tables').length,1,'Branding changes preserve hydrated models');
 const updated={...base,version:'v2',modelScope:'models2',bootstrapId:'b2'};render(updated);const stale=request();await tick();call=sent.filter(x=>x.value).at(-1).value;
 const viewer={...updated,user:'viewer',role:'viewer',accessScope:'viewer',modelScope:'viewer2',bootstrapId:'viewer2'};render(viewer);render({...viewer,data:null,response:{id:call.id,body:{tables:models,version:'v2',modelScope:'models2'}}});assert.equal((await stale).status,409,'A late model response must never cross an account/scope change');
 const fresh=request();await tick();call=sent.filter(x=>x.value).at(-1).value;assert.equal(call.modelScope,'viewer2');render({...viewer,data:null,response:{id:call.id,body:{tables:[{...models[0],rows:[['A',3]]}],version:'v2',modelScope:'viewer2'}}});assert.equal((await (await fresh).json()).total,1);
 console.log('PASS: deferred source records, one in-flight fetch, reopen/branding reuse, workbook invalidation and late-response access isolation.');
})().catch(e=>{console.error(e);process.exitCode=1});

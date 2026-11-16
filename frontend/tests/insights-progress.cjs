const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});
Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,CustomEvent:dom.window.CustomEvent,localStorage:dom.window.localStorage,IS_REACT_ACT_ENVIRONMENT:true});window.HTMLElement.prototype.scrollIntoView=function(){};
const packets=[];let failures=3;
const report={version:'v1',report_id:'r1',generated_at:'2026-10-26',overview:'Partial business review',sections:[{view:0,title:'Stock overview',records:2,limitation:'Snapshot',charts:[],kpis:[],facets:[]}]};
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{isAdmin:()=>false,rpc:async(action,payload)=>{packets.push({action,payload});if(action==='ai_status')return{configured:true,version:'v1',tables:1};if(action==='generate_insights'){
 if(!payload.job_id)return{pending:true,job_id:'job-1',step:0,progress:{label:'Connecting sources',percent:0}};
 if(payload.step===0)return{pending:true,job_id:'job-1',step:1,progress:{label:'Calculating cards',percent:25}};
 if(payload.step===1)return{pending:true,job_id:'job-1',step:2,progress:{label:'Writing findings',percent:60},report};
 if(payload.step===2&&failures>0){failures--;throw Error('Request timed out. Please retry.')}
 return{pending:false,job_id:'job-1',step:3,progress:{label:'Analysis complete',percent:100},report:{...report,overview:'Completed business review'}};
 }return{}}}};
require.cache[require.resolve('../src/record-grid.tsx')]={loaded:true,exports:{__esModule:true,default:()=>null}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),Insights=require('../src/insights.tsx').default,root=createRoot(document.getElementById('root')),tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 await act(async()=>{root.render(React.createElement(Insights));await tick()});
 await act(async()=>{document.querySelector('.aiconsent input').click();await tick()});
 await act(async()=>{document.querySelector('.insights-controls button').click();await tick()});
 for(let i=0;i<60&&!document.querySelector('[role="alert"]');i++)await act(async()=>{await new Promise(r=>setTimeout(r,100));await tick()});
 assert.equal(packets.filter(p=>p.action==='generate_insights').length,6);
 assert.ok(document.querySelector('.insights-section'),'Completed sections remain visible after a later timeout');
 assert.ok(document.querySelector('[role="alert"]').textContent.includes('Analysis paused'));
 assert.equal(document.querySelector('.insights-controls button').textContent.trim(),'Resume analysis');
 await act(async()=>{document.querySelector('.insights-controls button').click();await tick()});
 assert.equal(packets.filter(p=>p.action==='generate_insights'&&!p.payload.job_id).length,1,'Resume must not initialize a new report');
 assert.deepEqual(packets.filter(p=>p.action==='generate_insights').map(p=>p.payload.step),[undefined,0,1,2,2,2,2]);
 assert.ok(document.querySelector('.insight-summary').textContent.includes('Completed business review'));
 assert.equal(document.querySelector('.insights-controls button').textContent.trim(),'Regenerate analysis');
 assert.equal(document.querySelectorAll('.insights-section').length,1);
 failures=1;const beforeRetry=packets.filter(p=>p.action==='generate_insights').length;
 await act(async()=>{document.querySelector('.insights-controls button').click();await tick()});
 for(let i=0;i<40&&document.querySelector('.insights-controls button').textContent.trim()!=='Regenerate analysis';i++)await act(async()=>{await new Promise(r=>setTimeout(r,100));await tick()});
 assert.equal(document.querySelector('.insights-controls button').textContent.trim(),'Regenerate analysis','One transient failure must complete automatically without Resume');
 const retried=packets.filter(p=>p.action==='generate_insights').slice(beforeRetry);assert.equal(retried.filter(p=>!p.payload.job_id).length,1);assert.deepEqual(retried.at(-1).payload,retried.at(-2).payload,'Retry uses the identical request, job and step');
 await act(async()=>root.unmount());console.log('Passed: staged progress, partial results, timeout pause and idempotent resume of the same job.');
})().catch(e=>{console.error(e);process.exitCode=1});

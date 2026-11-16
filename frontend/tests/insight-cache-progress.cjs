const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,CustomEvent:dom.window.CustomEvent,localStorage:dom.window.localStorage,IS_REACT_ACT_ENVIRONMENT:true});window.HTMLElement.prototype.scrollIntoView=function(){};
const packets=[],chart={id:'g1',title:'Saved quantities',type:'bar',label:'Material',value:'Qty',evidence:{table:'Stock',source_id:'fresh-source',matched_records:1,result_rows:1,shown_rows:1,records:[{Material:'A',Qty:3}]}};
let active=null;let saved={version:'v1',report_id:'restored',generated_at:'2026-10-27',cached:true,answer:'Saved business findings',sections:[{view:0,title:'Stock overview',records:1,limitation:'',charts:[chart]}]};
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{isAdmin:()=>false,rpc:async(action,payload)=>{packets.push({action,payload});if(action==='ai_status')return{version:'v1',tables:1,configured:true,saved_report:saved,active_analysis:active};if(action==='delete_insight_chart'){saved={...saved,report_id:'after-delete',sections:[{...saved.sections[0],charts:[]}]};return{report:saved}}return{}}}};
require.cache[require.resolve('../src/record-grid.tsx')]={loaded:true,exports:{__esModule:true,default:()=>null}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),Insights=require('../src/insights.tsx').default,root=createRoot(document.getElementById('root')),tick=()=>new Promise(r=>setImmediate(r));
const frames=new Map();let frameId=0;
window.requestAnimationFrame=fn=>{frames.set(++frameId,fn);return frameId};window.cancelAnimationFrame=id=>frames.delete(id);
let version='v1',revision='r1',deliver,mode='cache';
require.cache[require.resolve('../src/bridge.ts')].exports.rpc=async(action,payload)=>{
 packets.push({action,payload});if(action==='ai_status'){
  const metadata={configured:true,version,planning_revision:revision,knowledge_revision:'rules1',report_scope:'scope',tables:1};
  if(!payload.load_saved_insights)return metadata;
  return new Promise((resolve,reject)=>{deliver=()=>mode==='error'?reject(Error('Cache connection unavailable')):resolve({...metadata,saved_report:mode==='empty'||mode==='checkpoint'?null:saved,active_analysis:mode==='checkpoint'?{pending:true,request_id:'req',job_id:'job',step:2,progress:{label:'Writing findings',percent:60},report:saved}:null})});
 }
 if(action==='generate_insights')return{pending:false,progress:{percent:100,label:'Analysis complete'},report:{...saved,cache_generation:'confirmed-save',report_id:'generated'}};
 throw Error('Unexpected '+action);
};
const panel=()=>document.querySelector('[aria-label="Saved report cache status"]'),bar=()=>panel().querySelector('progress');
async function frame(){const batch=[...frames.values()];frames.clear();await act(async()=>{batch.forEach(fn=>fn(0));await tick()})}
async function finish(){await frame();await frame()}
async function completeRequest(){await act(async()=>{deliver();await tick()})}
(async()=>{
 await act(async()=>{root.render(React.createElement(Insights));await tick()});assert.equal(bar().value,0);assert.equal(panel().getAttribute('aria-busy'),'true');assert(panel().textContent.includes('Checking saved report cache'));
 await completeRequest();assert.equal(bar().value,67);assert(document.querySelector('.insight-chart'));assert.equal(packets.length,1);
 await frame();assert.equal(bar().value,67,'Receiving the saved response must not immediately claim 100%');await frame();assert.equal(bar().value,100);assert(panel().textContent.includes('Loaded from saved report cache'));assert(panel().textContent.includes('1 view'));assert(panel().textContent.includes('1 graph'));
 await act(async()=>{window.dispatchEvent(new window.Event('stock-data-updated'));await tick()});assert.equal(bar().value,0,'source checks wait for validation');await completeRequest();assert.equal(bar().value,100,'unchanged validated reports keep their completed cache badge');assert.equal(packets.length,2);
 mode='error';revision='r2';await act(async()=>{window.dispatchEvent(new window.Event('stock-manual-data-updated'));await tick()});assert.equal(bar().value,0);assert(document.querySelector('.insight-chart'),'old dashboard remains visible during update');await completeRequest();assert(panel().textContent.includes('loading failed'));assert.equal(bar(),null,'failed restore never displays 100%');assert(document.querySelector('.insight-chart'));
 mode='cache';saved={...saved,report_id:'retry-result'};await act(async()=>{[...panel().querySelectorAll('button')].find(b=>b.textContent.includes('Retry')).click();await tick()});assert.equal(bar().value,0);await completeRequest();await finish();assert.equal(bar().value,100);assert.equal(packets.filter(p=>p.action==='generate_insights').length,0);
 mode='checkpoint';revision='r3';await act(async()=>{window.dispatchEvent(new window.Event('stock-manual-data-updated'));await tick()});await completeRequest();await finish();assert(panel().textContent.includes('Saved analysis progress loaded'));assert(panel().textContent.includes('resume analysis to finish'));assert.equal(document.querySelector('.insights-controls button').textContent.trim(),'Resume analysis');
 mode='empty';version='v2';revision='r4';await act(async()=>{window.dispatchEvent(new window.Event('stock-data-updated'));await tick()});await completeRequest();assert(panel().textContent.includes('No saved report'));assert.equal(bar(),null);assert.equal(document.querySelector('.insight-chart'),null);assert.equal(packets.filter(p=>p.action==='generate_insights').length,0);
 await act(async()=>{document.querySelector('.aiconsent input').click();await tick()});await act(async()=>{document.querySelector('.insights-controls button').click();await tick()});assert.equal(bar().value,67);await finish();assert.equal(bar().value,100);assert(panel().textContent.includes('Analysis saved to cache'));
 mode='cache';revision='r5';await act(async()=>{window.dispatchEvent(new window.Event('stock-manual-data-updated'));await tick()});await completeRequest();assert.equal(bar().value,67);revision='r6';await act(async()=>{window.dispatchEvent(new window.Event('stock-manual-data-updated'));await tick()});await finish();assert.equal(bar().value,0,'old paint callbacks cannot mark a newer restore complete');await act(async()=>root.unmount());await completeRequest();await finish();assert.equal(document.getElementById('root').textContent,'','late restore never remounts a departed account or tab');dom.window.close();
 console.log('PASS: truthful cache restore milestones/paint completion, saved counts, no extra generation, stable badge, failure/retry, checkpoint distinction, workbook cache miss, confirmed save and late-response cancellation.');
})().catch(e=>{console.error(e);process.exitCode=1});

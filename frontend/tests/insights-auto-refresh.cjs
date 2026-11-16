const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,CustomEvent:dom.window.CustomEvent,localStorage:dom.window.localStorage,IS_REACT_ACT_ENVIRONMENT:true});window.HTMLElement.prototype.scrollIntoView=function(){};
const packets=[],chart={id:'g1',title:'Saved quantities',type:'bar',label:'Material',value:'Qty',evidence:{table:'Stock',source_id:'fresh-source',matched_records:1,result_rows:1,shown_rows:1,records:[{Material:'A',Qty:3}]}};
let active=null;let saved={version:'v1',report_id:'restored',generated_at:'2026-10-27',cached:true,answer:'Saved business findings',sections:[{view:0,title:'Stock overview',records:1,limitation:'',charts:[chart]}]};
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{isAdmin:()=>false,rpc:async(action,payload)=>{packets.push({action,payload});if(action==='ai_status')return{version:'v1',tables:1,configured:true,saved_report:saved,active_analysis:active};if(action==='delete_insight_chart'){saved={...saved,report_id:'after-delete',sections:[{...saved.sections[0],charts:[]}]};return{report:saved}}return{}}}};
require.cache[require.resolve('../src/record-grid.tsx')]={loaded:true,exports:{__esModule:true,default:()=>null}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),Insights=require('../src/insights.tsx').default,root=createRoot(document.getElementById('root')),tick=()=>new Promise(r=>setImmediate(r));
let revision='manual1',finishRefresh;
require.cache[require.resolve('../src/bridge.ts')].exports.rpc=async(action,payload)=>{
 packets.push({action,payload});if(action==='ai_status'){
  if(payload.load_saved_insights&&revision==='manual2')await new Promise(resolve=>finishRefresh=resolve);
  return{version:'v1',planning_revision:revision,knowledge_revision:'rules1',report_scope:'scope',tables:1,configured:true,saved_report:payload.load_saved_insights?saved:undefined};
 }throw Error('Unexpected '+action);
};
(async()=>{
 await act(async()=>{root.render(React.createElement(Insights));await tick()});assert(document.querySelector('.insight-chart'));
 revision='manual2';saved={...saved,report_id:'updated',sections:[{...saved.sections[0],charts:[{...chart,evidence:{...chart.evidence,records:[{Material:'A',Qty:42}]}}]}]};
 await act(async()=>{window.dispatchEvent(new window.Event('stock-manual-data-updated'));await tick()});
 assert(document.querySelector('.insight-chart'),'saved report stays visible while automatic recalculation is pending');assert(finishRefresh);
 await act(async()=>{finishRefresh();await tick()});assert(document.querySelector('.insight-chart'));assert(document.querySelector('.insight-chart').textContent.includes('Saved quantities'));assert(document.querySelector('.insight-chart').textContent.includes('42'),'graph exposes the updated numeric value');assert.equal(packets.filter(p=>p.action==='generate_insights').length,0);
 const count=packets.length;await act(async()=>{window.dispatchEvent(new window.Event('stock-source-versions'));await tick()});assert.equal(packets.length,count+1,'unchanged source notification does not repeat restore');
 await act(async()=>root.unmount());dom.window.close();console.log('PASS: manual data updates hydrate recalculated reports without blanking charts or making an AI generation request.');
})().catch(e=>{console.error(e);process.exitCode=1});

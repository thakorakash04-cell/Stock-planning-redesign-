const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,CustomEvent:dom.window.CustomEvent,localStorage:dom.window.localStorage,IS_REACT_ACT_ENVIRONMENT:true});window.HTMLElement.prototype.scrollIntoView=function(){};
const calls=[],prefs={};let finish,version='v1';
const chart={id:'g1',title:'Quantity by material',type:'bar',label:'Material',value:'Qty',evidence:{table:'Stock',source_id:'source',matched_records:1,result_rows:1,shown_rows:1,records:[{Material:'A',Qty:3}]}};
const report={version:'v1',report_id:'r1',generated_at:'2026-10-27',overview:'Calculated stock review',sections:[{view:0,title:'Stock overview',records:1,limitation:'',facets:[],charts:[chart]}]};
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{isAdmin:()=>false,can:p=>p==='use_tools'||p==='use_fiori',browserActive:()=>false,readViewPreference:k=>prefs[k],saveViewPreference:(k,v)=>prefs[k]=v,openAccount(){},rpc:async(action,payload)=>{calls.push({action,payload});if(action==='ai_status')return{configured:true,version,tables:1,report_scope:'viewer',knowledge_revision:'rules',planning_revision:'plans',saved_report:null};if(action==='generate_insights'){if(!payload.job_id)return{pending:true,job_id:'job1',step:0};if(payload.step===0)return{pending:true,job_id:'job1',step:1,report,progress:{label:'Writing findings',percent:70}};return new Promise(resolve=>{finish=()=>resolve({pending:false,job_id:'job1',step:2,report:{...report,overview:'Completed stock review'}})});}return{}}}};
require.cache[require.resolve('../src/record-grid.tsx')]={loaded:true,exports:{__esModule:true,default:()=>null}};
const data={accessibleTabs:[0,8],filename:'Planning.xlsx',updatedAt:null,asOf:'Saved',sheets:Array.from({length:7},(_,i)=>({name:'S'+i,headers:['Material','Qty'],rows:[['A',3]]}))};global.fetch=async()=>Response.json(data);
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),Dashboard=require('../src/dashboard.tsx').default,root=createRoot(document.getElementById('root')),tick=()=>new Promise(r=>setTimeout(r,20));
async function click(label){await act(async()=>{const button=document.querySelector('button[aria-label="'+label+'"]');assert(button,label);button.click();await tick()})}
(async()=>{
 await act(async()=>{root.render(React.createElement(Dashboard,{user:'viewer',initialData:data}));await tick()});
 assert.equal(calls.filter(c=>c.action==='ai_status').length,0);
 await click('Insights & Graphs');
 await act(async()=>{document.querySelector('.aiconsent input').click();await tick()});
 await act(async()=>{document.querySelector('.insights-controls button').click();await tick()});
 assert(document.querySelector('.insight-chart'),'Partial graph appears before review finishes');const page=document.querySelector('.insights-page');
 await click('Stock overview');assert.equal(document.querySelector('.insights-page'),page,'Navigation must retain the actual component');assert(page.closest('[hidden]'));
 await act(async()=>{window.dispatchEvent(new window.Event('stock-data-updated'));await tick()});
 assert(document.querySelector('.insight-chart'),'Same-source notifications must not clear graphs');
 await act(async()=>{finish();await tick()});await click('Insights & Graphs');assert.equal(document.querySelector('.insights-page'),page);
 assert(document.querySelector('.insight-summary').textContent.includes('Completed stock review'),'Generation must finish while another tab is open');
 assert.equal(calls.filter(c=>c.action==='generate_insights'&&!c.payload.job_id).length,1);const checks=calls.filter(c=>c.action==='ai_status').length;
 await act(async()=>{const picker=document.querySelector('.chart-style');picker.value='column';picker.dispatchEvent(new window.Event('change',{bubbles:true}));await tick()});
 for(let i=0;i<3;i++){await click('Stock overview');await click('Insights & Graphs');}
 assert.equal(document.querySelector('.chart-style').value,'column');assert.equal(calls.filter(c=>c.action==='ai_status').length,checks,'Tab switches must trigger no restore/generation calls');
 await act(async()=>{const style=document.querySelector('select[aria-label="UI style"]');style.value='fiori';style.dispatchEvent(new window.Event('change',{bubbles:true}));await tick()});assert.equal(document.querySelector('.insights-page'),page);
 const entry=[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Review insights'));await act(async()=>{entry.click();await tick()});assert.equal(document.querySelector('.chart-style').value,'column');
 version='v2';await act(async()=>{window.dispatchEvent(new window.Event('stock-data-updated'));await tick();await tick()});assert.equal(document.querySelectorAll('.insight-chart').length,0,'Real workbook changes still invalidate reports');
 await act(async()=>root.unmount());dom.window.close();console.log('PASS: actual Dashboard/Fiori tab navigation retains partial/completed Insights, continues one job, preserves presentation and avoids repeat requests.');
})().catch(e=>{console.error(e);process.exitCode=1});

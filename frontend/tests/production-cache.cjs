const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,localStorage:dom.window.localStorage,IS_REACT_ACT_ENVIRONMENT:true});
let polls=0;const originalInterval=global.setInterval;global.setInterval=(...args)=>{polls++;return originalInterval(...args)};
const calls=[],cached={available:true,version:'v1',sourceStamp:1,revision:1,checkedAt:1,signature:'batch1',planStatuses:{plan:'Ready'}};
const report={batchAvailability:cached,version:'v1',sourceStamp:1,ongoing:[],ongoingHeaders:[],qc:{headers:[],rows:[]},upcomingHeaders:['Material','Description','Batch','Quantity'],upcoming:[{id:'plan',materialCode:'A',revision:1,row:['A','Product','NEXT',10],availability:cached}]};
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{can:()=>false,isAdmin:()=>false,browserActive:()=>false,rpc:async(action)=>{calls.push(action);return {...cached,headers:['Component','Status'],rows:[['R','Available']],planHeaders:['Plan','Status'],planRows:[['A','Ready']],calculationHeaders:['Required'],calculations:[[1]]}}}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),Production=require('../src/production.tsx').default,tick=()=>new Promise(r=>setImmediate(r));let root=createRoot(document.getElementById('root'));
async function mount(value){await act(async()=>{root.render(React.createElement(Production,{revision:String(value.sourceStamp),initialReport:value},'Completed'));await tick()})}
async function click(text){await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent.includes(text)).click();await tick()})}
(async()=>{
 await mount(report);assert.equal(polls,0,'Production must not start full-report polling');assert.ok(document.querySelector('.materials-ready'));assert.equal(calls.length,0,'Saved status must render without checking or loading details');
 await click('Check material availability for all plans');assert.equal(calls.filter(x=>x==='production_availability_all').length,1);await click('Close availability');await click('Check material availability for all plans');assert.equal(calls.length,1,'Opened details stay in the browser cache');
 await act(async()=>root.unmount());root=createRoot(document.getElementById('root'));await mount(report);assert.ok(document.querySelector('.materials-ready'));assert.equal(calls.length,1,'A new login/remount uses the persisted summary');
 await mount({...report,sourceStamp:2});assert.equal(document.querySelector('.materials-ready'),null,'Even an identical workbook upload invalidates the old timestamp');assert.ok(document.body.textContent.includes('Check material availability'));
 await act(async()=>root.unmount());global.setInterval=originalInterval;console.log('PASS: persisted availability badges, lazy details, local reuse, login restoration and upload invalidation.');
})().catch(e=>{console.error(e);process.exit(1)});


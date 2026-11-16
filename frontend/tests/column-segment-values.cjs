const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,CustomEvent:dom.window.CustomEvent,IS_REACT_ACT_ENVIRONMENT:true});
const prefs={},calls=[];let assistant,clicked,hold=false,pending;
const definition={name:'Amount',request:'Qty times 10',plan:{sources:[{alias:'s0',table:'USER_VIEW'}],joins:[],calculations:[{name:'Amount',op:'multiply',operands:['s0.Qty',10]}],columns:['calc.Amount']}};
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{can:()=>true,canAccessTab:()=>true,tableColumnSnapshot:()=>({user:'alice',version:'v1'}),persistViewPreferences:async()=>{},readViewPreference:k=>prefs[k],saveViewPreference:(k,v)=>prefs[k]=v,rpc:async(action,input)=>{calls.push({action,input});if(action==='table_column_records')return {page:0,tables:[{name:'Matching records · Price',headers:['Material','Price'],rows:[['A',10]],total:1}],warnings:[]};if(hold)return new Promise((resolve,reject)=>pending={resolve,reject,input});return {definition,columns:[{name:'Amount',values:input.rows.map(r=>r[1]*10)}],warnings:[]}}}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client');require.cache[require.resolve('../src/ask-ai.tsx')]={loaded:true,exports:{__esModule:true,default:props=>{assistant=props;return React.createElement('div',null,'Assistant')}}};
const Grid=require('../src/data-grid.tsx').default,tick=()=>new Promise(r=>setImmediate(r));let root=createRoot(document.getElementById('root'));
let all=[['A',2,'First'],['A',0,'Second'],['B',3,'Second'],['A',2,'Second']],shown=[all[0]];const headers=['Material','Qty','Segment'];
async function render(){await act(async()=>{root.render(React.createElement(Grid,{headers,rows:shown,columnRows:all,storageKey:'segment-test',onCell:r=>clicked=r}));await tick();await tick()})}
function amounts(){return [...document.querySelectorAll('.gridtable tbody tr')].map(tr=>tr.querySelectorAll('td')[3]?.textContent).filter(v=>v!==undefined)}
(async()=>{
 await render();await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Ask Assistant').click();await tick()});
 await act(async()=>{await assistant.addColumn('Qty times 10',true);await tick()});
 assert.equal(calls.length,1);assert.deepEqual(calls[0].input.rows,all,'Add with one Segment still computes all authorized rows');assert.deepEqual(amounts(),['20']);
 shown=[all[2],all[1],all[3],all[0]];await render();assert.deepEqual(amounts(),['30','0','20','20'],'All segments, reordered rows and duplicate material keep correct values');assert.equal(calls.length,1,'Filter changes require no resolver or Gemini call');
 await act(async()=>document.querySelector('.gridcell').click());assert.equal(clicked,all[2],'Drill-through preserves source row identity');
 shown=[all[2].slice(),all[1].slice(),all[3].slice(),all[0].slice()];await render();assert.deepEqual(amounts(),['30','0','20','20'],'Restored copied rows keep AI column values');await act(async()=>{document.querySelector('[aria-label="Matching records for Amount"]').click();await tick()});assert.equal(calls.at(-1).input.row_index,2,'Copied row evidence uses its original source index');await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Close matching records').click();await tick()});calls.pop();
 shown=[];await render();shown=[all[1]];await render();assert.deepEqual(amounts(),['0']);assert.equal(calls.length,1);
 await act(async()=>root.unmount());root=createRoot(document.getElementById('root'));await render();assert.equal(calls.at(-1).action,'table_columns_resolve');assert.deepEqual(calls.at(-1).input.rows,all);assert.deepEqual(amounts(),['0']);
 shown=all;await render();assert.equal(calls.length,2);assert.deepEqual(amounts(),['20','0','30','20']);
 all=[['A',4,'First'],all[1],all[2],all[3]];shown=all;await render();assert.equal(calls.length,3,'Actual source changes recalculate');assert.deepEqual(amounts(),['40','0','30','20']);
 await act(async()=>root.unmount());root=createRoot(document.getElementById('root'));hold=true;await render();
 assert.deepEqual(amounts(),['40','0','30','20'],'Tab remount displays retained values before the resolver replies');
 await act(async()=>{pending.reject(new Error('Request timed out'));await tick()});
 assert(!amounts().includes('40'),'Failed server validation clears retained result');
 hold=false;await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Retry added columns').click();await tick();await tick()});
 assert.deepEqual(amounts(),['40','0','30','20'],'Retry restores values without asking Gemini');
 hold=true;await act(async()=>{window.dispatchEvent(new window.Event('stock-source-versions'));await tick()});
 assert(!amounts().includes('40'),'Source updates invalidate the retained values immediately');
 await act(async()=>{pending.resolve({columns:[{name:'Amount',values:[41,0,30,20]}],warnings:[]});await tick()});
 assert.deepEqual(amounts(),['41','0','30','20']);
 hold=false;await act(async()=>{document.querySelector('[aria-label="Matching records for Amount"]').click();await tick()});
 assert(document.querySelector('[aria-label="Matching records · Amount"]'));
 const drill=calls.at(-1);assert.equal(drill.action,'table_column_records');assert.equal(drill.input.row_index,0);assert.equal(drill.input.column,'Amount');assert.deepEqual(drill.input.rows,all);
 assert(document.querySelector('[aria-label="Matching records · Amount"]').textContent.includes('Matching records · Price'));
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Close matching records').click();await tick()});
 assert.equal(document.querySelector('[aria-label="Matching records · Amount"]'),null);

 await act(async()=>root.unmount());console.log('PASS: tab remount retains values during validation, errors clear cache, retry restores, and source updates invalidate.');console.log('PASS: calculated values survive Segment/All/empty/reorder and restored definitions; duplicate keys, zero, drill-through and source refresh remain correct.');
})().catch(e=>{console.error(e);process.exitCode=1});


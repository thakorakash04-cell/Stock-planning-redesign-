const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
const compile=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
for(const ext of ['.ts','.tsx'])require.extensions[ext]=compile;
const js=require.extensions['.js'];require.extensions['.js']=(m,n)=>n.endsWith('/vendor/fflate.js')?compile(m,n):js(m,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,IS_REACT_ACT_ENVIRONMENT:true});
const prefs={};let authorized=false,authCalls=0,blob,clicked;
global.URL.createObjectURL=b=>{blob=b;return 'blob:pivot'};global.URL.revokeObjectURL=()=>{};window.HTMLAnchorElement.prototype.click=function(){};
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{can:()=>true,authorizeExport:async()=>{authCalls++;return authorized},readViewPreference:k=>prefs[k],saveViewPreference:(k,v)=>prefs[k]=v}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),Grid=require('../src/data-grid.tsx').default,{GroupingSegments}=require('../src/grouping-segments.ts'),{groupedRows,pivotOutput,filterPivotRows}=require('../src/grouping.ts');
const rows=[['001','B1',4],['001','B2',6],['002','B1',0],['003','B3',null]],headers=['Material','Batch','Qty'],mapping={'001':['Surgical','Care'],'002':['Care']},root=createRoot(document.getElementById('root')),tick=()=>new Promise(r=>setImmediate(r));
const props={headers,rows,storageKey:'pivot-test',filename:'Stock',onCell:(r,i)=>clicked={r,i}};
async function choose(label,text){await act(async()=>{const el=[...document.querySelectorAll('[aria-label="'+label+' choices"] .checkbox-values label')].find(l=>l.textContent===text);assert(el,text);el.querySelector('input').click();await tick()})}
async function click(label){await act(async()=>{const el=document.querySelector('[aria-label="'+label+'"]')||[...document.querySelectorAll('button')].find(b=>b.textContent===label);assert(el,label);el.click();await tick()})}
(async()=>{
 await act(async()=>root.render(React.createElement(GroupingSegments.Provider,{value:mapping},React.createElement(Grid,props))));
 await choose('Group table records','Segment');await choose('Group table records','Material');
 assert.deepEqual(prefs['grid:pivot-test'].groupColumns,['Segment','Material']);
 assert.equal(document.querySelectorAll('.pivot-panel tbody tr').length,3,'multi-segment rows must be grouped once');
 await choose('Pivot value columns','Qty');
 assert(document.querySelector('.pivot-panel').textContent.includes('Sum Qty'));assert.deepEqual([...document.querySelectorAll('.pivot-panel tbody tr')].map(tr=>tr.lastChild.textContent),['10','0','0']);
 await click('Move grouping Material up');assert.deepEqual(prefs['grid:pivot-test'].groupColumns,['Material','Segment']);
 await click('Sort pivot Sum Qty');await click('Sort pivot Sum Qty');assert.equal(document.querySelector('.pivot-panel tbody tr').lastChild.textContent,'10');
 await choose('Pivot filter Segment','Care / Surgical');assert.equal(document.querySelectorAll('.pivot-panel tbody tr').length,1);assert(document.querySelector('.gridcount').textContent.includes('2 of 4'));
 await act(async()=>{document.querySelector('tr.group button').click();await tick()});
 await act(async()=>{[...document.querySelectorAll('.gridtable .gridcell')].find(b=>b.textContent==='4').click();await tick()});assert.equal(clicked.r,rows[0]);assert.equal(clicked.i,2);
 await click('Download pivot (Excel)');assert.equal(authCalls,1);assert.equal(blob,undefined,'denied authorization must not produce a file');
 authorized=true;await click('Download pivot (Excel)');assert.equal(authCalls,2);assert(blob);fs.writeFileSync(require('node:os').tmpdir()+'/pivot-filtered.xlsx',Buffer.from(await blob.arrayBuffer()));
 await act(async()=>root.unmount());const restored=createRoot(document.getElementById('root'));await act(async()=>restored.render(React.createElement(GroupingSegments.Provider,{value:mapping},React.createElement(Grid,props))));assert.equal(document.querySelectorAll('.pivot-panel tbody tr').length,1);assert.deepEqual(prefs['grid:pivot-test'].groupColumns,['Material','Segment']);await act(async()=>restored.unmount());
 const tuples=groupedRows([['a · b','c'],['a','b · c'],[1,'x'],['1','x']],['A','B'],['A','B'],()=>'?');assert.equal(tuples.length,4,'tuple grouping must avoid separator and type collisions');
 const {pivotWorkbook}=require('../src/pivot-export.ts');fs.writeFileSync(require('node:os').tmpdir()+'/pivot-literal.xlsx',await pivotWorkbook({headers:['Segment','Qty'],rows:[['=1+1',0],['<Care & "Surgical">',null]]}));
 const many=Array.from({length:85},(_,i)=>[JSON.stringify(['S'+i]),[[i]]]);assert.equal(pivotOutput(many,['Segment'],['Qty'],{},()=>0).rows.length,85,'export model includes all pages');
 console.log('PASS: multi-field pivot, virtual/shared/unmapped Segment, reorder, filters, numeric summaries, sort, saved state, original row drill-down, permission-gated real XLSX, literal text and all-page export.');
})().catch(e=>{console.error(e);process.exitCode=1});

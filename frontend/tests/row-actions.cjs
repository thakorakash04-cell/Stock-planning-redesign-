const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,localStorage:dom.window.localStorage,IS_REACT_ACT_ENVIRONMENT:true});
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{can:()=>false,isAdmin:()=>false}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),Grid=require('../src/data-grid.tsx').default,{ProductLinks}=require('../src/product-links.tsx');
const rows=[['A','BATCH-A'],['B','BATCH-B']],root=createRoot(document.getElementById('root'));let chosen;
const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 await act(async()=>{root.render(React.createElement(ProductLinks.Provider,{value:{version:'catalogue',detailsAllowed:true,products:[{id:'p',name:'Product A',division:'Care',codes:['A'],url:''}]}},React.createElement(Grid,{headers:['Material','Batch'],rows,storageKey:'action-test',rowActions:row=>React.createElement('button',{onClick:()=>chosen=row},'Edit '+row[1])})));await tick()});
 assert.ok(document.body.textContent.includes('Product Name'));
 await act(async()=>{const sort=document.querySelector('[aria-label="Sort by column"]');sort.value='Batch';sort.dispatchEvent(new window.Event('change',{bubbles:true}));const dir=document.querySelector('[aria-label="Sort direction"]');dir.value='-1';dir.dispatchEvent(new window.Event('change',{bubbles:true}));await tick()});
 const first=document.querySelector('tbody tr');assert.ok(first.textContent.includes('BATCH-B'));
 await act(async()=>first.querySelector('.row-actions button').click());assert.equal(chosen,rows[1],'Action receives the original plan row after sorting and product-column augmentation');
 await act(async()=>{const el=document.querySelector('[aria-label="Filter text for Batch"]');Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(el,'BATCH-A');el.dispatchEvent(new window.Event('input',{bubbles:true}));await tick()});
 await act(async()=>document.querySelector('tbody .row-actions button').click());assert.equal(chosen,rows[0]);
 await act(async()=>root.unmount());console.log('PASS: row actions follow original plan identity through sorting, filtering and Product Name enrichment.');
})().catch(e=>{console.error(e);process.exitCode=1});

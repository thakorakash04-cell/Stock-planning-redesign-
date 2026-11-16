const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);require.extensions['.css']=()=>{};
const dom=new JSDOM('<div id="root"></div>',{url:'https://planning.test',pretendToBeVisual:true});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,CustomEvent:dom.window.CustomEvent,localStorage:dom.window.localStorage,IS_REACT_ACT_ENVIRONMENT:true});
const style=document.createElement('style');style.textContent='.datagrid.grid-expanded{overflow:hidden;display:flex;flex-direction:column}.datagrid.grid-expanded .gridtable{flex:1;max-height:none!important}'+fs.readFileSync(require('path').join(__dirname,'../src/pivot.css'),'utf8');document.head.appendChild(style);
const headers=['Material',...Array.from({length:9},(_,i)=>'Qty '+i)],rows=Array.from({length:45},(_,i)=>['M'+i,...Array.from({length:9},(_,j)=>i+j)]),prefs={};
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{can:()=>false,canAccessTab:()=>false,rpc:()=>{throw Error('Unexpected request')},readViewPreference:key=>prefs[key],saveViewPreference:(key,value)=>prefs[key]=value}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),tick=()=>new Promise(r=>setImmediate(r));let root=createRoot(document.getElementById('root'));
async function check(Grid,scope,admin=false){
 const settings={groupColumns:['Material'],pivot:{values:headers.slice(1)}};
 if(admin)localStorage.setItem('product360:grid:'+scope,JSON.stringify(settings));else prefs['grid:'+scope]=settings;
 await act(async()=>{root.render(React.createElement(Grid,{headers,rows,storageKey:scope,filename:'Wide pivot',groupBy:0}));await tick()});
 const region=document.querySelector('[aria-label="Pivot output scroll area"]');assert(region);assert.equal(region.tabIndex,0);assert.equal(region.getAttribute('role'),'region');
 await act(async()=>{document.querySelector('[aria-label="Full-screen table"]').click();await tick()});
 const full=document.querySelector('.datagrid.grid-expanded.grid-with-pivot');assert(full,'Both table implementations mark a full-screen pivot');
 const output=full.querySelector('.pivot-output-scroll');output.focus();assert.equal(document.activeElement,output);
 assert.equal(window.getComputedStyle(full).overflowY,'scroll');assert.equal(window.getComputedStyle(output).overflow,'scroll');assert.equal(window.getComputedStyle(full.querySelector('.gridtools')).position,'sticky');assert.equal(window.getComputedStyle(output.querySelector('th')).position,'sticky');
 assert.equal(output.querySelectorAll('thead th').length,11,'All grouping, count and value columns remain available');
 await act(async()=>{document.querySelector('[aria-label="Exit full screen"]').click();await tick()});assert.equal(document.querySelector('.grid-expanded'),null);assert(document.querySelector('[aria-label="Pivot output scroll area"]'));
 await act(async()=>root.unmount());root=createRoot(document.getElementById('root'));
}
(async()=>{await check(require('../src/data-grid.tsx').default,'main-scroll');await check(require('../../admin_frontend/src/data-grid.tsx').default,'admin-scroll',true);await act(async()=>root.unmount());dom.window.close();console.log('PASS: main/admin full-screen pivot scroll regions, both axes, keyboard focus, sticky headers/controls and restore.');})().catch(e=>{console.error(e);process.exitCode=1});

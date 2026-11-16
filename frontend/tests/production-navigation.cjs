const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,CustomEvent:dom.window.CustomEvent,localStorage:dom.window.localStorage,IS_REACT_ACT_ENVIRONMENT:true});window.HTMLElement.prototype.scrollIntoView=function(){};

require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{isAdmin:()=>false,can:()=>false,browserActive:()=>false,readViewPreference:()=>undefined,saveViewPreference(){},openAccount(){},rpc:async()=>({})}};
require.cache[require.resolve('../src/production.tsx')]={loaded:true,exports:{__esModule:true,default:({section})=>require('react').createElement('div',{'data-production-section':section},section)}};
require.cache[require.resolve('../src/record-grid.tsx')]={loaded:true,exports:{__esModule:true,default:()=>null}};
const data={accessibleTabs:[0,2,3],filename:'Planning.xlsx',updatedAt:null,asOf:'Saved',sheets:Array.from({length:7},(_,i)=>({name:'S'+i,headers:['Material','Qty'],rows:[['A',3]]}))};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),Dashboard=require('../src/dashboard.tsx').default,root=createRoot(document.getElementById('root'));
(async()=>{
 await act(async()=>root.render(React.createElement(Dashboard,{user:'viewer',initialData:data})));
 const menu=document.querySelector('button[aria-label="Production"]');assert(menu);
 assert.equal(document.querySelector('#production-navigation'),null);
 await act(async()=>menu.click());assert.equal(menu.getAttribute('aria-expanded'),'true');
 const options=[...document.querySelectorAll('#production-navigation button')];assert.deepEqual(options.map(b=>b.textContent),['QC Released','Under QC','Ongoing Production','Upcoming Production','Transfer Details']);
 for(const [i,section] of ['released','qc','ongoing','upcoming'].entries()){
  await act(async()=>options[i].click());assert.equal(document.querySelector('[data-production-section]').dataset.productionSection,section);assert.equal(options[i].getAttribute('aria-current'),'page');
 }
 await act(async()=>options[4].click());assert.equal(document.querySelector('h1').textContent,'Transfer Details');await act(async()=>options[0].click());
 const choice=[...document.querySelectorAll('[aria-label="Choose production view"] button')][0];await act(async()=>choice.click());assert.equal(document.querySelector('[data-production-section]').dataset.productionSection,'released');
 await act(async()=>menu.click());assert.equal(document.querySelector('#production-navigation'),null);
 await act(async()=>root.unmount());dom.window.close();console.log('PASS: Production menu exposes five choices, navigates each view and supports in-page switching.');
})().catch(e=>{console.error(e);process.exitCode=1});


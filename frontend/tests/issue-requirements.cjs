const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://planning.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,CustomEvent:dom.window.CustomEvent,IS_REACT_ACT_ENVIRONMENT:true});
let permission=true,allowed=true,authorizations=0,copied='',blocked=false;
Object.defineProperty(global,'navigator',{value:{userAgent:'Test',clipboard:{writeText:async value=>{if(blocked)throw Error('Blocked');copied=value}}},configurable:true});
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{can:p=>p==='download'&&permission,isAdmin:()=>false,readViewPreference:()=>undefined,saveViewPreference(){},authorizeExport:async()=>{authorizations++;return allowed},rpc:async()=>({})}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),{default:IssueRequirements,issueSlipText}=require('../src/issue-requirements.tsx'),root=createRoot(document.getElementById('root'));
const headers=['Plan Reference','SAP Order','Product Batch','Component Code','Required Quantity','Unit'],rows=Array.from({length:45},(_,i)=>['p'+i,null,'B'+i,'RM',0.0375,'EA']);
const tick=()=>new Promise(r=>setImmediate(r));
async function clickCopy(){await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Copy filtered rows for Excel').click();await tick()})}
(async()=>{
 await act(async()=>{root.render(React.createElement(IssueRequirements,{headers,rows}));await tick()});
 assert.equal(document.querySelectorAll('tbody tr').length,40,'Grid paginates display only');await clickCopy();assert.equal(copied.split('\r\n').length,46,'Copy includes all 45 filtered rows and headers, across pages');assert(copied.includes('p44\t\tB44\tRM\t0.0375\tEA'));assert.equal(authorizations,1);
 const field=document.querySelector('[aria-label="Filter text for Product Batch"]');await act(async()=>{field[Object.keys(field).find(k=>k.startsWith('__reactProps$'))].onChange({target:{value:'B44'}});await tick()});await clickCopy();assert.equal(copied.split('\r\n').length,2);assert(copied.includes('p44'));
 blocked=true;await clickCopy();const manual=document.querySelector('textarea[aria-label="Issue-slip copy text"]');assert(manual);assert.equal(manual.value.replace(/\r\n/g,'\n'),copied.replace(/\r\n/g,'\n'));
 const previous=copied;allowed=false;blocked=false;await clickCopy();assert.equal(copied,previous,'Denied live export cannot write clipboard');
 permission=false;await act(async()=>root.render(React.createElement(IssueRequirements,{headers,rows})));assert(![...document.querySelectorAll('button')].some(b=>b.textContent==='Copy filtered rows for Excel'));
 const text=issueSlipText(['Code','Value'],[['=HYPERLINK("bad")',0],['text\tline\nend',null],['normal',-0.125]]);assert(text.includes("'=HYPERLINK"));assert(text.includes('text line end\t'));assert(text.includes('normal\t-0.125'));
 await act(async()=>root.unmount());dom.window.close();console.log('PASS: issue table; all-page and filtered TSV copying; blank orders/full-precision numbers; manual clipboard fallback; live export permissions; safe spreadsheet text.');
})().catch(e=>{console.error(e);process.exitCode=1});

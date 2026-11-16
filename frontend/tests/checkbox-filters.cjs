const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,IS_REACT_ACT_ENVIRONMENT:true});
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),{default:Filter,matchesChoice,normalizeSelection}=require('../src/checkbox-filter.tsx');const root=createRoot(document.getElementById('root')),tick=()=>new Promise(r=>setImmediate(r));let value='all';
function Example(){const [selected,setSelected]=React.useState(value);return React.createElement(Filter,{label:'Materials',value:selected,options:[{value:'A'},{value:'B'},{value:1},{value:'1'},{value:null},{value:''}],onChange:v=>{value=v;setSelected(v)}})}
async function click(index){await act(async()=>{document.querySelectorAll('.checkbox-values input')[index].click();await tick()})}
(async()=>{
 assert.deepEqual(normalizeSelection('Legacy'),['Legacy']);assert(matchesChoice('all','anything'));assert(!matchesChoice([],null));assert(matchesChoice([1],1));assert(!matchesChoice([1],'1'));
 await act(async()=>root.render(React.createElement(Example)));
 await click(0);await click(1);assert.deepEqual(value,['A','B']);assert.equal(document.querySelector('summary').textContent,'2 selected');
 await click(0);assert.deepEqual(value,['B']);await click(4);assert.deepEqual(value,['B',null]);
 await act(async()=>{document.querySelector('.checkbox-actions button:last-child').click();await tick()});assert.deepEqual(value,[]);assert.equal(document.querySelector('summary').textContent,'None selected');
 await act(async()=>{document.querySelector('.checkbox-options fieldset>label input').click();await tick()});assert.equal(value,'all');
 await act(async()=>{const input=document.querySelector('[aria-label="Search Materials"]');Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(input,'A');input.dispatchEvent(new window.Event('input',{bubbles:true}));await tick()});
 await act(async()=>{document.querySelector('.checkbox-actions button').click();await tick()});assert.deepEqual(value,['A',null]);
 const {filterRows,cellKey}=require('../src/grid-utils.ts');assert.deepEqual(filterRows([['A',1],['B',2],['C',3]],{Material:{values:[cellKey('A'),cellKey('B')]}},['Material','Qty']),[['A',1],['B',2]]);
 await act(async()=>root.unmount());console.log('PASS: searchable checkbox multi-selection, all/none, preserved typed/blank values, legacy selections and OR table filtering.');
})().catch(e=>{console.error(e);process.exitCode=1});

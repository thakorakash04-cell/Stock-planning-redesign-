const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const {matchesSegments}=require('../src/segment-selection.ts'),{filterSegments}=require('../src/segments.ts');
assert.equal(matchesSegments(['A','B'],['B','C']),true);assert.equal(matchesSegments(['A','B'],['C']),false);assert.equal(matchesSegments([],['A']),false);assert.equal(matchesSegments('A',['A']),true);assert.equal(matchesSegments('all',[]),true);assert.equal(matchesSegments(['unassigned','A'],[]),true);
const {lookupSegments,segmentIndex}=require('../src/segments.ts');
const names=['Ostomy Care','General Wound Care','Advance Wound Care','Endovascular Solution','Energy Device','Oncology'];
const normalized=segmentIndex([{name:'BOM',headers:['FG Material Code','Component Code','Source.Name'],rows:names.map((s,i)=>[String(1001+i),'RM'+i,' '+s+'.XLSX '])}]);
for(let i=0;i<names.length;i++){assert.deepEqual(lookupSegments(normalized,' '+(1001+i)+'.0 '),[names[i]]);assert.equal(matchesSegments([names[i]],lookupSegments(normalized,' '+(1001+i)+'.0 ')),true);assert.deepEqual(lookupSegments(normalized,' rm'+i+' '),[names[i]])}
assert.deepEqual(lookupSegments({'00123':['A']},'123'),[]);
const {rowSegments}=require('../src/segments.ts');
assert.deepEqual(rowSegments(['Material','Unique Material.Source.Name'],['A','Ostomy Care.XLSX'],{A:['Energy Devices']}),['Ostomy Care']);
assert.deepEqual(rowSegments(['Material','Source.Name'],['A','General Wound Care.xlsx'],{A:['Energy Devices']}),['General Wound Care']);
assert.deepEqual(rowSegments(['SKU Code','Segment'],['A','GWC'],{A:['General Wound Care']},'DP MRP'),['General Wound Care']);
const {segmentChoices}=require('../src/segments.ts');
assert.deepEqual(segmentChoices([{name:'Forecast Data',headers:['Source.Name'],rows:[['Laser System.xlsx']]}],{A:['Energy Devices']}),['Energy Devices','Laser System']);
const tables=[{name:'Stock',headers:['Material'],rows:[['x'],['y'],['z']]}],map={x:['A','B'],y:['B'],z:['C']};
assert.deepEqual(filterSegments(tables,map,['A','B'])[0].rows,[['x'],['y']]);
const dom=new JSDOM('<div id="root"></div>');Object.assign(global,{window:dom.window,document:dom.window.document,IS_REACT_ACT_ENVIRONMENT:true});
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),Select=require('../src/segment-select.tsx').default;let saved='all';
function Test(){const [value,set]=React.useState(saved);return React.createElement(Select,{value,options:['A','B','C'],onChange:v=>{saved=v;set(v)}})}
const root=createRoot(document.getElementById('root'));const click=async text=>act(async()=>{[...document.querySelectorAll('label')].find(l=>l.textContent===text).querySelector('input').click()});
(async()=>{await act(async()=>root.render(React.createElement(Test)));await click('A');await click('B');assert.deepEqual(saved,['A','B']);assert.equal(document.querySelector('summary').textContent,'2 segments selected');await click('A');assert.deepEqual(saved,['B']);await click('All segments');assert.equal(saved,'all');await act(async()=>root.unmount());console.log('Passed: checkbox multi-selection, any-segment matching without duplicate rows, empty/all, legacy and unassigned selections.');})().catch(e=>{console.error(e);process.exitCode=1});

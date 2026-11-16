const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'https://workspace.test'});
Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,localStorage:dom.window.localStorage,IS_REACT_ACT_ENVIRONMENT:true});
let edit=false;const calls=[];
const report={materials:[{code:'A',description:'Product A',type:'ZFGS',unit:'EA'},{code:'S',description:'Semi A',type:'ZSFG',unit:'EA'}],segments:['Wound'],segmentMap:{A:['Wound']},version:'v1',referenceDate:'2026-10-10',referenceBasis:'Worksheet date',ongoingHeaders:['Order','Type','Material','Description','Batch','Qty','Start','Expected end','Expected FG','Basis','Saved by','Saved at'],ongoing:[{id:'order1',revision:0,row:[1,'ZFGS','A','Item','B1',100,'2026-10-01','2026-10-25',85,'History',null,null]}],qc:{headers:['Material','Batch','Latest 101'],rows:[['A','B2','2026-10-04']]},upcomingHeaders:['Product','Description','Batch','Qty','Start','End'],upcoming:[{id:'plan1',revision:1,materialCode:'A',segments:['Wound'],row:['A','Product A','NEXT',100,'2026-11-01','2026-11-10']}]};
const segmentNames=['Ostomy Care','General Wound Care','Advance Wound Care','Endovascular Solution','Energy Device','Oncology'];
report.segments.push(...segmentNames);report.qc.segments=[['Wound']];
for(let i=0;i<segmentNames.length;i++){report.segmentMap[String(1001+i)]=[segmentNames[i]];report.qc.rows.push([' '+(1001+i)+'.0 ','QC-SEG-'+i,'2026-10-04']);report.qc.segments.push([segmentNames[i]]);report.segmentMap[String(1001+i)]=['Wound']}
require.cache[require.resolve('../src/bridge.ts')]={id:'bridge',filename:require.resolve('../src/bridge.ts'),loaded:true,exports:{can:p=>edit&&p.startsWith('edit_'),isAdmin:()=>false,rpc:async(action,payload)=>{calls.push({action,payload});if(action==='production_history')return {headers:['Date & Time (IST)','Username','Changed Field','Previous Value','New Value'],rows:[['17 Oct 2026 11:00:00 IST','viewer','Quantity',50,75]],events:1};if(action==='production_delete')return {...report,upcoming:[]};if(action==='production_availability_all')return {issueHeaders:['Plan Reference','Product Batch','Component','Required Quantity'],issueRows:[['plan1','NEXT','RM',30]],available:false,version:'v1',revision:1,planStatuses:{plan1:'Material shortage'},planHeaders:['Status'],planRows:[['Material shortage']],headers:['Component','Description','Unit','Required','Stock','Need','Status'],rows:[['RM','Raw','EA',30,10,20,'Shortage']],calculationHeaders:['Formula'],calculations:[['100 / 10 × 3 = 30']],explanation:'Current stock only'};return report}}};
const React=require('react'),{act}=React,{createRoot}=require('react-dom/client'),root=createRoot(document.getElementById('root')),Production=require('../src/production.tsx').default;
const tick=()=>new Promise(r=>setImmediate(r));
async function change(key,value){await act(async()=>{const el=document.querySelector('[aria-label="'+key+'"]');Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(el,value);el.dispatchEvent(new window.Event('input',{bubbles:true}));await tick()})}
(async()=>{
 await act(async()=>{root.render(React.createElement(Production,{revision:'v1'},React.createElement('p',null,'Completed table')));await tick()});
 for(const section of ['released','qc','ongoing','upcoming']){
 await act(async()=>{root.render(React.createElement(Production,{revision:'v1',initialReport:report,section},React.createElement('p',null,'Completed table')));await tick()});
 assert.equal(document.querySelectorAll('.production-section:not([hidden])').length,1);
 }
 await act(async()=>{root.render(React.createElement(Production,{revision:'v1',initialReport:report},React.createElement('p',null,'Completed table')));await tick()});
 assert.equal(document.querySelectorAll('.production-section').length,4);assert.ok([...document.querySelectorAll('.production-section')].every(d=>d.tagName==='DETAILS'));
 assert.ok(!document.body.textContent.includes('Add upcoming batch'));
 assert.equal(document.querySelectorAll('.production-section summary[aria-label^="Group "]').length,3,'Each new table has a grouping selector');
 await act(async()=>{const choice=[...document.querySelectorAll('[aria-label="Group ongoing records choices"] .checkbox-values label')].find(l=>l.textContent==='Material');choice.querySelector('input').click();await tick()});
 assert.ok(document.querySelector('.production-section:nth-of-type(2) .group'),'Grouping displays collapsible record groups');
 assert.equal(document.querySelectorAll('summary[aria-label^="Filter "][aria-label$=" by segment"]').length,3,'Each new table has a segment filter');
 await act(async()=>{const control=document.querySelector('[aria-label="Filter qc by segment choices"]');[...control.querySelectorAll("label")].find(x=>x.textContent==='Unassigned').querySelector("input").click();await tick()});
 assert.ok(document.querySelector('.production-section:nth-of-type(3)').textContent.includes('No records match these filters.'));


 await act(async()=>{document.querySelector('[aria-label="Filter qc by segment choices"] input[type="checkbox"]').click();await tick()});
 for(let i=0;i<segmentNames.length;i++){
  await act(async()=>{const c=document.querySelector('[aria-label="Filter qc by segment choices"]');[...c.querySelectorAll('label')].find(l=>l.textContent===segmentNames[i]).querySelector('input').click();await tick()});
  const text=document.querySelector('.production-section:nth-of-type(3)').textContent;
  assert.ok(text.includes('QC-SEG-'+i),'QC release includes '+segmentNames[i]);
  for(let j=0;j<segmentNames.length;j++)if(i!==j)assert.ok(!text.includes('QC-SEG-'+j));
  await act(async()=>{document.querySelector('[aria-label="Filter qc by segment choices"] input[type="checkbox"]').click();await tick()});
 }
 await act(async()=>{document.querySelector('.production-section:nth-of-type(3) .gridcell').click();await tick()});
 assert.ok(document.querySelector('[aria-label="Production record details"]'),'Click a new table value to open full record details');
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Close details').click();await tick()});
 assert.equal([...document.querySelectorAll('button')].filter(b=>b.textContent.startsWith('Check material availability')).length,1);
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Check material availability')).click();await tick()});
 assert.ok(document.querySelector('[aria-label="Material availability details"]'));assert.equal(document.querySelectorAll('[aria-label="Material availability details"] .datagrid').length,3,'Availability opens all three tables');assert(document.querySelector('[aria-label="Batch-wise issue requirements"]').textContent.includes('NEXT'));assert.ok(document.querySelector('.materials-short'));
 assert.ok(document.body.textContent.includes('Combined component requirements'));
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Close availability').click();await tick()});
 edit=true;await act(async()=>{root.render(React.createElement(Production,{revision:'v1'},'Completed table'));await tick()});
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Add upcoming batch').click();await tick()});
 await act(async()=>{const select=document.querySelector('[aria-label="materialCode"]');select.value='A';select.dispatchEvent(new window.Event('change',{bubbles:true}));await tick()});
 assert.equal(document.querySelector('[aria-label="description"]').value,'Product A');
 for(const [k,v] of Object.entries({batch:'NEXT',quantity:'100',startDate:'2026-11-01',endDate:'2026-11-10'}))await change(k,v);
 await act(async()=>{document.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));await tick()});
 const saved=calls.find(c=>c.action==='production_save');assert.equal(saved.payload.value.quantity,100);assert.equal(saved.payload.version,'v1');assert.equal(saved.payload.kind,'upcoming');assert.ok(!Object.hasOwn(saved.payload,'id'),'UI must not replace the RPC request ID');assert.deepEqual(calls.find(c=>c.action==='production_availability_all').payload,{version:'v1'});
 if(![...document.querySelectorAll('button')].some(b=>b.textContent.startsWith('Edit order')))await act(async()=>{document.querySelector('.production-section:nth-of-type(2) .group button').click();await tick()});
 await act(async()=>{const button=[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Edit order'));assert.ok(button.closest('tr').textContent.includes('B1'));button.click();await tick()});
 assert.equal(document.querySelectorAll('.production-form input').length,2,'Only expected quantity and end date may be edited');
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Cancel').click();await tick()});
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Edit history').click();await tick()});
 assert.ok(document.body.textContent.includes('17 Oct 2026 11:00:00 IST'));assert.ok(document.body.textContent.includes('viewer'));
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Plans').click();await tick()});
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Delete A')).click();await tick()});
 assert.ok(document.querySelector('[aria-label="Delete upcoming plan"]'));
 await act(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Delete for everyone').click();await tick()});
 assert.deepEqual(calls.find(c=>c.action==='production_delete').payload,{version:'v1',plan_id:'plan1',revision:1});
 const Dashboard=require('../src/dashboard.tsx').default;
 global.fetch=async()=>Response.json({productCatalogue:{version:'v1',detailsAllowed:false,products:[{id:'p1',name:'Product One',division:'Wound',codes:['A'],url:''}]},accessibleTabs:[3],filename:'master.xlsx',updatedAt:'2026-10-10',sheets:Array.from({length:7},(_,i)=>({name:'Sheet '+i,headers:['Material','Qty'],rows:[['A',5]]}))});
 await act(async()=>{root.render(React.createElement(Dashboard,{user:'viewer'}));await tick()});
 assert.deepEqual([...document.querySelectorAll('nav button')].map(b=>b.textContent),['Production','Floor Level']);
 assert.ok(document.querySelector('.production-workspace'));for(const kind of ['ongoing','qc','upcoming'])assert([...document.querySelectorAll('[aria-label="Group '+kind+' records choices"] .checkbox-values label')].some(l=>l.textContent==='Product Name'));await act(async()=>{const choices=[...document.querySelectorAll('[aria-label="Group ongoing records choices"] .checkbox-values label')];for(const choice of choices)if(choice.querySelector('input').checked)choice.querySelector('input').click();choices.find(l=>l.textContent==='Product Name').querySelector('input').click();await tick()});assert(document.querySelector('.production-section:nth-of-type(2) .group').textContent.includes('Product One'));
 await act(async()=>root.unmount());console.log('Passed: four collapsible production tables, admin-controlled editor, shared save payload and restricted sidebar.');
})().catch(async e=>{await act(async()=>root.unmount());console.error(e);process.exitCode=1});



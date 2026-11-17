const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),{default:Stamp,dataUpToText}=require('../src/source-stamp.tsx');
let html=renderToStaticMarkup(React.createElement(Stamp,{label:'Primary Sales',meta:{filename:'Sales.xlsx',updated_at:Date.parse('2026-11-17T00:00:00Z')/1000,dataUpTo:'2026-11-15',dataDateBasis:'Billing Date'}}));
assert(html.includes('Uploaded on: '));assert(html.includes('IST'));assert(html.includes('Data up to: 15 Nov 2026'));assert(html.includes('Billing Date'));assert(html.includes('Sales.xlsx'));
assert.equal(dataUpToText('2026-11'),'Nov 2026');assert.equal(dataUpToText(null),'Not available in file');assert.equal(renderToStaticMarkup(React.createElement(Stamp,{})),'');
for(const file of ['dashboard.tsx','sales.tsx','pnl.tsx','pending-demand.tsx','upload-center.tsx','meril-stock-records.tsx'])assert(fs.readFileSync(require.resolve('../src/'+file),'utf8').includes('SourceStamp'),file+' shows source dates');
console.log('PASS: separate upload/content dates, exact Data up to label, IST upload time, month precision, unknown dates and source references.');

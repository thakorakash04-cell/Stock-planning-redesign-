const fs=require('fs'),assert=require('node:assert/strict'),ts=require('typescript');
require.extensions['.ts']=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,n);
const {pnlCSV}=require('../src/pnl-export.ts');
const labels=['Sales','Product cost','Product cost %','Manufacturing OHD','Employee cost','SG&A','R&D cost','Total cost','EBITDA','EBITDA %','Interest','Depreciation','Profit before tax','Income tax','PAT','Cash profit','Working capital','Net cash profit','Capex','ROI %'];
const report={sourceVersion:'v1',period:{start:'2026-04-01',end:'2026-08-31'},formulaDrivers:{interestRate:.085,taxRate:.18,yearFraction:5/12},statement:{headers:['Particulars','Selected total','Hidden segment','=unsafe'],rows:labels.map((l,i)=>[l,i===0?500:12,999,i===0?100:5])}};
function parse(csv){return csv.split('\r\n').map(line=>line.match(/"(?:[^"]|"")*"/g)?.map(c=>c.slice(1,-1).replaceAll('""','"'))||[])}
const rows=parse(pnlCSV(report,[0,3,1],'std_dp'));
assert(!rows.flat().includes('Hidden segment'));assert.equal(rows[0][1],"'=unsafe");assert(rows.flat().some(c=>c==='500'));
const starts=rows.findIndex(r=>r[0]==='Formula statement')+1,ref=(label,col='B')=>col+(starts+labels.indexOf(label)+1);
const row=label=>rows[starts+labels.indexOf(label)];
assert.equal(row('EBITDA')[1],`=IFERROR(${ref('Sales')}-${ref('Total cost')},"Unavailable")`);
assert(row('Product cost %')[1].includes(`${ref('Product cost')}/${ref('Sales')}*100`));
assert(row('Total cost')[2].includes(ref('Employee cost','C')));
assert(row('Product cost')[1].includes('B11')); // Captured input cell, independent of selling price.
assert(!pnlCSV(report,[0,1],'revenue').includes('Hidden segment'));
report.statement.rows[8][1]=null;assert.equal(parse(pnlCSV(report,[0,1],'std_dp'))[starts+8][1],'Unavailable');
console.log('Passed: CSV exports visible column order, captured values, drivers and correct formula references; hidden columns and unavailable inputs remain protected.');

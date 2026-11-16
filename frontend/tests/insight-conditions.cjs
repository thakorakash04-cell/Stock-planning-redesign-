const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript');
require.extensions['.ts']=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,n);
const {conditionFilter,restoreConditions}=require('../src/insight-filter-conditions.ts');
assert.deepEqual(conditionFilter('Amount',{op:'number_between',text:'1,000',end:'2000'},'number'),{column:'Amount',op:'number_between',value:[1000,2000]});
assert.deepEqual(conditionFilter('Invoice Date',{op:'date_between',text:'2026-06-01',end:'2026-06-30'},'date'),{column:'Invoice Date',op:'date_between',value:['2026-06-01','2026-06-30']});
assert.throws(()=>conditionFilter('Amount',{op:'number_between',text:'4',end:'2'},'number'));
assert.deepEqual(restoreConditions([{column:'Amount',op:'gte',value:10},{column:'Segment',op:'in',value:['A']}]),{choices:{Segment:['A']},conditions:{Amount:{op:'gte',text:'10',end:''}}});
console.log('PASS: typed numeric/date conditions and checkbox hydration.');

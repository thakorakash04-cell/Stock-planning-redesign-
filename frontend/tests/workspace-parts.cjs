const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript');require.extensions['.ts']=(m,p)=>m._compile(ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,p);
const{financeParts,reusableColumns}=require('../src/workspace-cache.ts');
const previous={id:'f1',versions:{primary:'p1',secondary:'s1',pnl:'n1'},sales:{primary:{rows:[['P']]},secondary:{rows:[['S']]}},pnl:{report:{rows:[['N']]}}};
let parts=financeParts(previous,{primary:'p2',secondary:'s1',pnl:'n2'},true);assert.deepEqual(parts.missing,['primary','pnl']);assert.deepEqual(Object.keys(parts.value.sales),['secondary']);
parts=financeParts(previous,previous.versions,false);assert.deepEqual(parts.missing,['pnl']);assert.deepEqual(Object.keys(parts.value.sales),['primary','secondary']);
const stamp=versions=>JSON.stringify(['master','production','planning','catalogue',Object.entries(versions)]),old=stamp(previous.versions),next=stamp({primary:'p2',secondary:'s1',pnl:'n2'});
const column=(name,sources)=>({key:JSON.stringify(['table','owner',JSON.stringify([{name,plan:{sources}}]),0,[],[]]),columns:[]});
const columns=[column('Arithmetic',[{table:'USER_VIEW'}]),column('BOM lookup',[{}, {table_name:'BOM Cost',source_key:'hash'}]),column('Primary lookup',[{},{table_name:'Primary Sales',source_key:'sales:primary'}]),column('Secondary lookup',[{},{table_name:'Secondary Sales',source_key:'sales:secondary'}]),column('Legacy',[{},{table:'UNKNOWN'}])];
assert.deepEqual(reusableColumns(columns,old,next),[columns[0],columns[1],columns[3]]);console.log('PASS: changed finance parts only, PnL filter independence and precise saved lookup dependency invalidation.');

// A CSV is one sheet: keep captured values first and an editable formula statement below.
// Only application-generated expressions become formulas; imported text stays literal.
export function pnlCSV(report:any,columns:number[],basis:string){
 const cols=columns.filter(c=>c>0),source=report.statement.rows as any[][];
 const literal=(v:any)=>typeof v==='string'&&/^[\s]*[=+@-]/.test(v)?"'"+v:v??'';
 const out:any[][]=[['PnL snapshot',...cols.map(c=>literal(report.statement.headers[c]))],['Statement start',report.period.start],['Statement end',report.period.end],['Sales basis',basis==='std_dp'?'Stock Transfers × Std DP':'Primary Sales'],['Source version',literal(report.sourceVersion||'')],['Note','Snapshot inputs below retain period/segment scope, source signs, admin overrides and unavailable values.'],['Note','Sales uses Std DP × eligible net transfers; COGS uses BOM Grand Total × the same transfers in Std DP mode. Primary Sales uses uploaded cumulative Revenue and production cost.'],['Note','Working capital is captured from the server calculation by segment; the selected total is its sum, not a recalculation using blended days.'],['Captured values',...cols.map(c=>literal(report.statement.headers[c]))]];
 if(report.selectedProducts?.length){out.splice(out.length-1,0,['Selected products',literal(report.selectedProducts.map((p:any)=>p.name).join('; '))],['Allocation rule','Salary/R&D and shared manual overheads use selected products / all products in the working segment.']);}
 const captured=new Map<string,number>();
 for(const r of source){captured.set(r[0],out.length+1);out.push([literal(r[0]),...cols.map(c=>r[c]===null||r[c]===undefined?'Unavailable':literal(r[c]))]);}
 out.push([]);const drivers=report.formulaDrivers||{};const driverRows:Record<string,number>={};
 for(const [key,label] of [['interestRate','Annual interest rate'],['taxRate','Income tax rate'],['yearFraction','Statement year fraction']]){driverRows[key]=out.length+1;out.push([label,...cols.map(()=>typeof drivers[key]==='number'?drivers[key]:'Unavailable')]);}
 out.push([],['Formula statement',...cols.map(c=>literal(report.statement.headers[c]))]);
 const formulaStart=out.length+1,positions=new Map(source.map((r,i)=>[r[0],formulaStart+i]));
 const letter=(i:number)=>{let s='';for(let n=i+2;n>0;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s};
 for(const row of source){const label=row[0];out.push([literal(label),...cols.map((c,i)=>{
  const col=letter(i),ref=(name:string)=>`${col}${positions.get(name)}`,snap=`${col}${captured.get(label)}`;
  // Respect source blockers and explicit product-cost overrides from the loaded statement.
  if(row[c]===null||row[c]===undefined)return 'Unavailable';
  let expr='';
  if(label.endsWith(' %')&&label!=='ROI %')expr=`IF(${ref('Sales')}=0,"Unavailable",${ref(label.slice(0,-2))}/${ref('Sales')}*100)`;
  const derived:Record<string,string>={
   'Total cost':['Product cost','Manufacturing OHD','Employee cost','SG&A','R&D cost'].map(ref).join('+'),
   'EBITDA':`${ref('Sales')}-${ref('Total cost')}`,
   'Interest':`(${ref('Working capital')}+${ref('Capex')})*${col}${driverRows.interestRate}*${col}${driverRows.yearFraction}`,
   'Profit before tax':`${ref('EBITDA')}-${ref('Interest')}-${ref('Depreciation')}`,
   'Income tax':`${ref('Profit before tax')}*${col}${driverRows.taxRate}`,
   'PAT':`${ref('Profit before tax')}-${ref('Income tax')}`,
   'Cash profit':`${ref('PAT')}+${ref('Depreciation')}`,
   'Net cash profit':`${ref('Cash profit')}-${ref('Working capital')}`,
   'ROI %':`IF((${ref('Working capital')}+${ref('Capex')}+${ref('R&D cost')})=0,0,${ref('PAT')}/(${ref('Working capital')}+${ref('Capex')}+${ref('R&D cost')})*100)`
  };
  expr=expr||derived[label]||snap;
  // Older snapshots without drivers retain their captured amounts rather than invented assumptions.
  if((label==='Interest'&&typeof drivers.interestRate!=='number')||(label==='Income tax'&&typeof drivers.taxRate!=='number'))expr=snap;
  return `=IFERROR(${expr},"Unavailable")`;
 })]);}
 return out.map(r=>r.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n');
}

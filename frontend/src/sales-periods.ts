type Cell=string|number|null;
const norm=(v:string)=>v.toLowerCase().replace(/[^a-z0-9]/g,'');
const months=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
function period(year:number,month:number,day=1){return year>=1900&&year<=2200&&month>=1&&month<=12&&day>=1&&day<=new Date(Date.UTC(year,month,0)).getUTCDate()?String(year)+'-'+String(month).padStart(2,'0'):null}
export function datePeriod(value:Cell):string|null{
 if(value===null||value==='')return null;
 if(typeof value==='number'){if(value<1||value>109574)return null;const d=new Date(Date.UTC(1899,11,30)+Math.floor(value)*86400000);return period(d.getUTCFullYear(),d.getUTCMonth()+1)}
 const text=String(value).trim();let m=text.match(/^(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?(?:[T\s].*)?$/);if(m)return period(+m[1],+m[2],m[3]?+m[3]:1);
 m=text.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?:\s.*)?$/);if(m)return period(+m[3],+m[2],+m[1]);
 m=text.match(/^(?:\d{1,2}[-\s/])?([a-z]+)[-\s/](\d{4})$/i);if(m)return period(+m[2],months.indexOf(m[1].toLowerCase().slice(0,3))+1);
 m=text.match(/^(\d{4})[-\s/]([a-z]+)$/i);return m?period(+m[1],months.indexOf(m[2].toLowerCase().slice(0,3))+1):null;
}
export function salesPeriods(headers:string[],rows:Cell[][],dateColumn=''){
 const names=headers.map(norm),aliases=['billingdate','invoicedate','salesdate','documentdate','postingdate','transactiondate','date','period','monthyear','yearmonth'];
 const candidates=headers.filter((_,i)=>aliases.includes(names[i])||names[i].endsWith('date'));
 const chosen=headers.indexOf(dateColumn),automatic=aliases.map(h=>names.indexOf(h)).find(i=>i>=0),di=chosen>=0?chosen:automatic??-1;
 const yi=names.findIndex(h=>['year','years','calendaryear','billingyear'].includes(h)),mi=names.findIndex(h=>['month','months','monthname','billingmonth'].includes(h));
 const values=rows.map(row=>{if(di>=0)return datePeriod(row[di]);if(yi>=0&&mi>=0){const year=Number(row[yi]),raw=String(row[mi]??'').trim(),month=/^\d{1,2}$/.test(raw)?Number(raw):months.indexOf(raw.toLowerCase().slice(0,3))+1;return period(year,month)}return null});
 return {values,options:[...new Set(values.filter((x):x is string=>!!x))].sort().reverse(),candidates,dateColumn:di>=0?headers[di]:''};
}
export const periodLabel=(key:string)=>months[Number(key.slice(5))-1]?.replace(/^./,c=>c.toUpperCase())+' '+key.slice(0,4);

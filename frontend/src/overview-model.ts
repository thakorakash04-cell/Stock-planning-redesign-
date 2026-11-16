import type {Data} from './dashboard';
import {rowSegments} from './segments';
import {salesPeriods} from './sales-periods';
type Cell=string|number|null;
export type StockGroup={name:string;stocked:number;empty:number;unknown:number;total:number};
export function salesActivity(snapshot:{available:boolean;headers:string[];rows:Cell[][]}|null|undefined){
 if(!snapshot?.available)return {available:false,months:[] as {period:string;lines:number}[],undated:0,total:0};
 const dates=salesPeriods(snapshot.headers,snapshot.rows),groups=new Map<string,number>();let undated=0;
 for(const date of dates.values){if(date)groups.set(date,(groups.get(date)||0)+1);else undated++;}
 return {available:true,months:[...groups].sort(([a],[b])=>a.localeCompare(b)).slice(-12).map(([period,lines])=>({period,lines})),undated,total:snapshot.rows.length};
}
export function overviewModel(data:Data|null,segment='all',query='',allowTools=false){
 const allowed=(tab:number)=>!!data&&(![7,8].includes(tab)||allowTools)&&(!data.accessibleTabs||data.accessibleTabs.includes(tab));
 const stock=allowed(0)?data?.sheets[0]:undefined;
 const stockIndex=stock?.headers.findIndex(h=>['currentstock','stockquantity','totalstock','unrestrictedstock'].includes(h.toLowerCase().replace(/[^a-z0-9]/g,'')))??-1;
 const quantityIndex=stockIndex>=0?stockIndex:2;
 const allRows=stock?.rows||[],members=(row:Cell[])=>rowSegments(stock?.headers||[],row,data?.segmentMap||{});
 const segments=[...new Set(allRows.flatMap(members))].sort();
 const rows=allRows.filter(row=>(segment==='all'||members(row).includes(segment))&&(!query||row.some(c=>String(c??'').toLowerCase().includes(query.toLowerCase()))));
 const groups=new Map<string,StockGroup>();
 let stocked=0,empty=0,unknown=0;
 for(const row of rows){const value=row[quantityIndex],known=typeof value==='number'&&Number.isFinite(value),positive=known&&value>0;positive?stocked++:known?empty++:unknown++;
  const names=members(row);for(const name of names.length?names:['Unassigned']){if(!groups.has(name))groups.set(name,{name,stocked:0,empty:0,unknown:0,total:0});const g=groups.get(name)!;g.total++;positive?g.stocked++:known?g.empty++:g.unknown++;}
 }
 const purchasing=allowed(5)?data?.sheets[5]:undefined;
 // This is a count of saved purchasing lines, never a recalculation of quantities.
 const purchaseIndex=purchasing?.headers.findIndex(h=>h.toLowerCase().replace(/[^a-z0-9]/g,'')==='needtoorderquantity')??-1;
 const purchaseLines=purchasing?.rows.filter(r=>typeof r[purchaseIndex>=0?purchaseIndex:7]==='number'&&Number(r[purchaseIndex>=0?purchaseIndex:7])>0).length??null;
 const production=allowed(3)?data?.production:undefined;
 const productionReady=!!production&&!production.error;
 return {allowed,stockAvailable:!!stock,stockLabel:stock?.headers[quantityIndex]||'Saved stock',rows,segments,groups:[...groups.values()].sort((a,b)=>b.total-a.total||a.name.localeCompare(b.name)),stocked,empty,unknown,coverage:stocked+empty?stocked/(stocked+empty)*100:null,purchaseLines,productionAvailable:productionReady,ongoing:productionReady?production.ongoing.length:null,qc:productionReady?production.qc.rows.length:null,upcoming:productionReady?production.upcoming.length:null,stockCount:stock?allRows.length:null,shared:rows.some(r=>members(r).length>1)};
}

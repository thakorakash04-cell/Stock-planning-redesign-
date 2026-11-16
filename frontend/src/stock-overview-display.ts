import type {Cell} from './grid-utils';
export const pendingMaterialKey=(v:unknown)=>String(v??'').normalize('NFKC').replace(/\u200b/g,'').trim().toLowerCase().replace(/^([+-]?\d+)\.0+$/,'$1');
export function stockOverviewDisplay(table:{headers:string[];rows:Cell[][]},pending:any){
 if(!pending?.result)return table;
 return {...table,headers:[...table.headers.slice(0,2),'Unit of Measure','Pack Size','Pending Sales Quantity',...table.headers.slice(2)],rows:table.rows.map(r=>{const found=pending.result.summary[pendingMaterialKey(r[0])];const details=pending.result.productDetails?.[pendingMaterialKey(r[0])];return [...r.slice(0,2),details?.unit??null,details?.packSize??null,found?found.quantity:pending.source&&(!pending.result.visibleStock||pending.result.visibleStock.includes(pendingMaterialKey(r[0])))?0:null,...r.slice(2)]})};
}

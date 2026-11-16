import type {Report} from './production';
import type {Cell} from './grid-utils';
import {pendingMaterialKey} from './stock-overview-display';
export function matchingBatches(report:Report|undefined|null,code:unknown){
 const key=pendingMaterialKey(code),same=(v:unknown)=>!!key&&pendingMaterialKey(v)===key;
 return {ongoing:report?.ongoing?.filter(item=>same(item.materialCode||item.row[2])).map(item=>item.row)||[],qc:report?.qc?.rows?.filter(row=>same(row[0]))||[],upcoming:report?.upcoming?.filter(item=>same(item.materialCode||item.row[0])).map(item=>item.row)||[]};
}
export function knownQuantity(rows:Cell[][],index:number):number|null{
 if(rows.some(row=>typeof row[index]!=='number'||!Number.isFinite(row[index])))return null;
 return rows.reduce((sum,row)=>sum+(row[index] as number),0);
}
export function demandWithBatches(row:Cell[],report?:Report|null){
 const matched=matchingBatches(report,row[0]);
 return [...row,report?knownQuantity(matched.ongoing,8):null,report?knownQuantity(matched.qc,3):null,report?knownQuantity(matched.upcoming,3):null];
}

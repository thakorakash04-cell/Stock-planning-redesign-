import {dateCondition,matchesDateCondition,unaryDateCondition} from '../../frontend/src/date-utils';
export type Cell=string|number|null;
export type ColumnFilter={op?:string;text?:string;end?:string;values?:string[]};
export const cellKey=(v:Cell)=>JSON.stringify(v);
export function filterRows(rows:Cell[][],filters:Record<string,ColumnFilter>,headers:string[]){return rows.filter(r=>headers.every((h,i)=>{const f=filters[h];if(!f)return true;const v=r[i]??null;if(f.values?.length&&!f.values.includes(cellKey(v)))return false;if(dateCondition(f.op))return matchesDateCondition(v,f);if(!f.text)return true;const text=f.text.toLowerCase(),str=String(v??'').toLowerCase();switch(f.op){case 'eq':return str===text;case 'neq':return str!==text;case 'gt':case 'gte':case 'lt':case 'lte':{const x=typeof v==='number'?v:NaN,y=Number(f.text.replaceAll(',',''));return Number.isFinite(x)&&Number.isFinite(y)&&(f.op==='gt'?x>y:f.op==='gte'?x>=y:f.op==='lt'?x<y:x<=y)}default:return str.includes(text)}}))}
export function sumColumn(rows:Cell[][],i:number){return rows.reduce((sum,r)=>sum+(typeof r[i]==='number'&&Number.isFinite(r[i])?r[i] as number:0),0)}

export function calculateColumn(rows:Cell[][],column:number,operation:string):Cell{const values=rows.map(r=>r[column]).filter(v=>typeof v==='number'&&Number.isFinite(v)) as number[];if(operation==='count')return values.length;if(operation==='sum')return values.reduce((a,b)=>a+b,0);if(!values.length)return null;if(operation==='mean')return values.reduce((a,b)=>a+b,0)/values.length;return values.reduce((a,b)=>operation==='min'?Math.min(a,b):Math.max(a,b))}
export function sortRows(rows:Cell[][],column:number,direction:number){if(column<0)return rows;return [...rows].sort((a,b)=>{const x=a[column],y=b[column];return (typeof x==='number'&&typeof y==='number'?x-y:String(x??'').localeCompare(String(y??'')))*direction})}
export function groupRows(rows:Cell[][],column:number){const groups=new Map<string,Cell[][]>();for(const row of rows){const key=String(row[column]??'Blank');if(!groups.has(key))groups.set(key,[]);groups.get(key)!.push(row)}return [...groups.entries()]}
export function sourceRowIndices(rows:Cell[][]){return new Map<Cell[],number>(rows.map((r,i)=>[r,i]))}
export function csvCell(value:Cell){let text=String(value??'');if(typeof value==='string'&&/^[=+\-@\t\r]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"'}

export const activeFilter=(f:ColumnFilter|undefined)=>!!f&&(!!f.text||!!f.values?.length||unaryDateCondition(f.op));

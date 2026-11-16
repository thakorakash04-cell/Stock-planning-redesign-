import {dateHeaders,dateGroupField,dateGroup,dateGroupValue,datePartLabel,DATE_PARTS} from './date-utils';
import type {Cell} from './grid-utils';
export const groupColumns=(value:unknown):string[]=>[...new Set((Array.isArray(value)?value:typeof value==='string'&&value?[value]:[]).filter((v):v is string=>typeof v==='string'&&!!v))];
export const groupingOptions=(headers:string[],rows:Cell[][]=[])=>[...new Set([...headers,'Segment',...dateHeaders(headers,rows).flatMap(h=>DATE_PARTS.map(part=>dateGroupField(h,part)).filter(k=>!headers.includes(k)))])];
export const isGroupingField=(field:string,headers:string[])=>typeof field==='string'&&(field==='Segment'||headers.includes(field)||!!dateGroup(field,headers));
export function groupFieldLabel(field:string){try{if(field.startsWith('@date:')){const [header,part]=JSON.parse(field.slice(6));if(DATE_PARTS.includes(part))return header+' ▸ '+datePartLabel(part)}}catch{}return field}
export const compareGroupValues=(a:Cell,b:Cell)=>a===null?(b===null?0:1):b===null?-1:typeof a==='number'&&typeof b==='number'?a-b:String(a).localeCompare(String(b));
export function groupedRows(rows:Cell[][],columns:string[],headers:string[],segment:(row:Cell[])=>string){
 if(!columns.length)return null;
 const groups=new Map<string,Cell[][]>();
 for(const row of rows){const values=pivotValues(row,columns,headers,segment);const key=JSON.stringify(values);if(!groups.has(key))groups.set(key,[]);groups.get(key)!.push(row)}
 const result=[...groups.entries()];if(columns.some(h=>dateGroup(h,headers)))result.sort((a,b)=>{const x=JSON.parse(a[0]),y=JSON.parse(b[0]);for(let i=0;i<columns.length;i++){const order=compareGroupValues(x[i],y[i]);if(order)return order}return 0});return result;
}
export const groupLabel=(key:string,columns:string[])=>{const values=JSON.parse(key) as Cell[];return values.map((v,i)=>groupFieldLabel(columns[i])+': '+(v===null||v===''?(columns[i]==='Product Name'?'Unmapped product':'Blank'):String(v))).join(' · ')};

export type PivotSettings={filters?:Record<string,string[]>;search?:string;values?:string[];operation?:string;sort?:{column:number;dir:number};layout?:'flat'|'hierarchy';collapsed?:string[];subtotals?:string[]};
export function pivotValues(row:Cell[],columns:string[],headers:string[],segment:(row:Cell[])=>string):Cell[]{return columns.map(h=>{if(h==='Segment')return segment(row);const date=dateGroup(h,headers);return date?dateGroupValue(row[headers.indexOf(date.header)]??null,date.part):row[headers.indexOf(h)]??null})}
export function filterPivotRows(rows:Cell[][],columns:string[],headers:string[],segment:(row:Cell[])=>string,settings:PivotSettings){
 if(!columns.length)return rows;
 return rows.filter(row=>{const values=pivotValues(row,columns,headers,segment);return columns.every((h,i)=>!settings.filters?.[h]?.length||settings.filters[h].includes(JSON.stringify(values[i])))&&(!settings.search||values.some(v=>String(v??'').toLowerCase().includes(settings.search!.toLowerCase())))})
}
export function pivotOutput(groups:[string,Cell[][]][],columns:string[],headers:string[],settings:PivotSettings,statistic:(rows:Cell[][],column:number,operation:string)=>Cell){
 const values=(settings.values||[]).filter(h=>headers.includes(h)&&!columns.includes(h)),operation=settings.operation||'sum';
 const labels:Record<string,string>={sum:'Sum',mean:'Average',count:'Count numbers',min:'Minimum',max:'Maximum'};
 const outputHeaders=[...columns.map(groupFieldLabel),'Record count',...values.map(h=>(labels[operation]||operation)+' '+h)];
 const rows=groups.map(([key,records])=>[...JSON.parse(key),records.length,...values.map(h=>statistic(records,headers.indexOf(h),operation))] as Cell[]);
 const sort=settings.sort;if(sort&&sort.column>=0&&sort.column<outputHeaders.length)rows.sort((a,b)=>{const x=a[sort.column],y=b[sort.column];return (typeof x==='number'&&typeof y==='number'?x-y:String(x??'').localeCompare(String(y??'')))*sort.dir});
 return {headers:outputHeaders,rows};
}

export type PivotNode={key:string;parent:string|null;depth:number;children:PivotNode[];records:Cell[][];row:Cell[]};
export function pivotHierarchy(groups:[string,Cell[][]][],columns:string[],headers:string[],settings:PivotSettings,statistic:(rows:Cell[][],column:number,operation:string)=>Cell){
 const nodes=new Map<string,PivotNode>(),roots:PivotNode[]=[];
 for(const [key,records] of groups){const values=JSON.parse(key) as Cell[];for(let length=1;length<=columns.length;length++){const prefix=values.slice(0,length),id=JSON.stringify(prefix);let node=nodes.get(id);if(!node){const parent=length>1?JSON.stringify(prefix.slice(0,-1)):null;node={key:id,parent,depth:length-1,children:[],records:[],row:[]};nodes.set(id,node);if(parent)nodes.get(parent)!.children.push(node);else roots.push(node)}for(const record of records)node.records.push(record)}}
 const values=(settings.values||[]).filter(h=>headers.includes(h)&&!columns.includes(h)),operation=settings.operation||'sum';
 for(const node of nodes.values()){const prefix=JSON.parse(node.key);node.row=[...prefix,...Array(columns.length-prefix.length).fill(null),node.records.length,...values.map(h=>statistic(node.records,headers.indexOf(h),operation))]}
 const all:PivotNode[]=[];const visit=(siblings:PivotNode[])=>{const sort=settings.sort;if(sort&&sort.column>=0&&sort.column<columns.length+1+values.length)siblings.sort((a,b)=>compareGroupValues(a.row[sort.column],b.row[sort.column])*sort.dir);for(const n of siblings){all.push(n);visit(n.children)}};visit(roots);return {all,nodes};
}

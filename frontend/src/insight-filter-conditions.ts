import {dateCondition,parseCalendarDate,unaryDateCondition} from './date-utils';
import type {ColumnFilter} from './grid-utils';
export type InsightFilter={column:string;op:string;value:unknown};
function numeric(text:string){const value=text.trim().replaceAll(',','');if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value)||!Number.isFinite(Number(value)))throw Error('Enter a valid finite number.');return Number(value);}
export function conditionFilter(column:string,rule:ColumnFilter,kind?:string):InsightFilter|null{
 const op=rule.op||(kind==='date'?'date_on':kind==='number'?'eq':'contains'),text=rule.text?.trim()||'',end=rule.end?.trim()||'';
 if(unaryDateCondition(op))return{column,op,value:null};
 if(!text&&!end)return null;
 if(op==='number_between'){
  if(!text||!end)throw Error('Enter both minimum and maximum for '+column+'.');const a=numeric(text),b=numeric(end);if(a>b)throw Error('Minimum must be on or below maximum for '+column+'.');return{column,op,value:[a,b]};
 }
 if(dateCondition(op)){
  const start=parseCalendarDate(text);if(!start)throw Error('Choose a valid date for '+column+'.');
  if(op==='date_between'){const finish=parseCalendarDate(end);if(!finish||start.ordinal>finish.ordinal)throw Error('Choose valid start/end dates in ascending order for '+column+'.');return{column,op,value:[start.iso,finish.iso]};}
  return{column,op,value:start.iso};
 }
 if(!text)return null;
 if(['gt','gte','lt','lte'].includes(op)||kind==='number'&&['eq','neq'].includes(op))return{column,op:op==='neq'?'ne':op,value:numeric(text)};
 return{column,op:op==='neq'?'ne':op,value:text};
}
export function restoreConditions(filters:InsightFilter[]){
 const choices:Record<string,any>={},conditions:Record<string,ColumnFilter>={};
 for(const f of filters){if(f.op==='in'){choices[f.column]=f.value;continue;}const range=f.op==='number_between'||f.op==='date_between',values=range&&Array.isArray(f.value)?f.value:[];conditions[f.column]={op:f.op==='ne'?'neq':f.op,text:range?String(values[0]??''):f.value===null?'':String(f.value),end:range?String(values[1]??''):''};}
 return{choices,conditions};
}

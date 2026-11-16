// Calendar-date operations for table views only; never alter source cells.
export type DateCell=string|number|null;
export type CalendarDate={year:number;month:number;day:number;iso:string;ordinal:number};
const DAY=86400000,monthNames=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const fullMonths=['january','february','march','april','may','june','july','august','september','october','november','december'];
function calendar(year:number,month:number,day:number):CalendarDate|null{
 if(year<1900||year>9999||month<1||month>12||day<1||day>31)return null;
 const date=new Date(Date.UTC(year,month-1,day));if(date.getUTCFullYear()!==year||date.getUTCMonth()!==month-1||date.getUTCDate()!==day)return null;
 return {year,month,day,iso:String(year).padStart(4,'0')+'-'+String(month).padStart(2,'0')+'-'+String(day).padStart(2,'0'),ordinal:date.getTime()/DAY};
}
export function parseCalendarDate(value:DateCell,allowSerial=false):CalendarDate|null{
 if(typeof value==='number'){
  if(!allowSerial||!Number.isFinite(value)||value<1||value>=2958466)return null;
  const serial=Math.floor(value);if(serial===60)return null; // Excel's fictitious 1900-02-29.
  const d=new Date(Date.UTC(1899,11,serial<60?31:30)+serial*DAY);return calendar(d.getUTCFullYear(),d.getUTCMonth()+1,d.getUTCDate());
 }
 if(typeof value!=='string'||!value.trim())return null;
 let text=value.trim().replace(/ (IST|UTC|GMT)$/i,'');const time=text.match(/[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?$/i);
 if(time){if(+time[1]>23||+time[2]>59||+(time[3]||0)>59)return null;text=text.slice(0,time.index)}
 let m=text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);if(m)return calendar(+m[1],+m[2],+m[3]);
 m=text.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/);if(m)return calendar(+m[3],+m[2],+m[1]); // Day-first workbook dates.
 m=text.match(/^(\d{1,2})[- /]([a-z]+)[- /](\d{4})$/i);if(m){const name=m[2].toLowerCase(),month=fullMonths.findIndex(x=>x===name||x.slice(0,3)===name)+1;return calendar(+m[3],month,+m[1])}
 m=text.match(/^([a-z]+) (\d{1,2}),? (\d{4})$/i);if(m){const name=m[1].toLowerCase(),month=fullMonths.findIndex(x=>x===name||x.slice(0,3)===name)+1;return calendar(+m[3],month,+m[2])}
 return null;
}
export const dateHeader=(header:string)=>/(^|[^a-z])(date|expiry|expiration|timestamp|dob)([^a-z]|$)/i.test(header)||/(date|timestamp)$/.test(header.toLowerCase().replace(/[^a-z]/g,''))||['createdat','updatedat','modifiedat','createdon','updatedon'].includes(header.toLowerCase().replace(/[^a-z]/g,''));
export function dateHeaders(headers:string[],rows:DateCell[][]=[]){return headers.filter((h,i)=>{if(dateHeader(h))return true;let count=0,valid=0;for(const row of rows.slice(0,128)){const v=row[i];if(v===null||v===undefined||v==='')continue;count++;if(parseCalendarDate(v))valid++;if(count===64)break}return count>0&&valid/count>=0.8})}
export const DATE_PARTS=['year','quarter','month','date','day'] as const;
export type DatePart=typeof DATE_PARTS[number];
export const datePartLabel=(part:DatePart)=>({year:'Year',quarter:'Quarter',month:'Month',date:'Date',day:'Day of month'}[part]);
export const dateGroupField=(header:string,part:DatePart)=>'@date:'+JSON.stringify([header,part]);
export function dateGroup(field:string,headers:string[]){
 if(typeof field!=='string'||headers.includes(field)||!field.startsWith('@date:'))return null;
 try{const a=JSON.parse(field.slice(6));return Array.isArray(a)&&a.length===2&&headers.includes(a[0])&&DATE_PARTS.includes(a[1])?{header:a[0] as string,part:a[1] as DatePart}:null}catch{return null}
}
export function dateGroupValue(value:DateCell,part:DatePart):DateCell{const d=parseCalendarDate(value,true);if(!d)return null;return part==='year'?d.year:part==='quarter'?'Q'+Math.ceil(d.month/3):part==='month'?String(d.month).padStart(2,'0')+' '+monthNames[d.month-1]:part==='day'?d.day:d.iso}
export type DateCondition={op?:string;text?:string;end?:string};
export const dateCondition=(op?:string)=>!!op?.startsWith('date_');
export const unaryDateCondition=(op?:string)=>['date_blank','date_not_blank','date_invalid'].includes(op||'');
export function matchesDateCondition(value:DateCell,filter:DateCondition){
 const blank=value===null||value==='',date=parseCalendarDate(value,true);
 if(filter.op==='date_blank')return blank;if(filter.op==='date_not_blank')return !blank;if(filter.op==='date_invalid')return !blank&&!date;
 if(!filter.text||(filter.op==='date_between'&&!filter.end))return true;
 const start=parseCalendarDate(filter.text),end=filter.end?parseCalendarDate(filter.end):null;
 if(!date||!start)return false;
 switch(filter.op){case 'date_on':return date.ordinal===start.ordinal;case 'date_not_on':return date.ordinal!==start.ordinal;case 'date_before':return date.ordinal<start.ordinal;case 'date_on_or_before':return date.ordinal<=start.ordinal;case 'date_after':return date.ordinal>start.ordinal;case 'date_on_or_after':return date.ordinal>=start.ordinal;case 'date_between':return !!end&&date.ordinal>=start.ordinal&&date.ordinal<=end.ordinal;default:return true}
}

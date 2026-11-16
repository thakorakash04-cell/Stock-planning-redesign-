import type {Cell} from './grid-utils';
const xml=(value:unknown)=>String(value??'').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g,'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const column=(i:number)=>{let out='';for(let n=i+1;n;n=Math.floor((n-1)/26))out=String.fromCharCode(65+(n-1)%26)+out;return out};
export async function pivotWorkbook(output:{headers:string[];rows:Cell[][]}){
 const {zipSync,strToU8}=await import('./vendor/fflate.js');
 const rows=[output.headers,...output.rows];
 if(rows.length>1048576||output.headers.length>16384||rows.length*output.headers.length>2000000)throw Error('Narrow the pivot filters before downloading.');
 const sheet='<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData>'+rows.map((row,r)=>'<row r="'+(r+1)+'">'+row.map((v,c)=>{const ref=column(c)+(r+1);return v===null?'<c r="'+ref+'"/>':typeof v==='number'&&Number.isFinite(v)?'<c r="'+ref+'"><v>'+v+'</v></c>':'<c r="'+ref+'" t="inlineStr"><is><t xml:space="preserve">'+xml(v)+'</t></is></c>'}).join('')+'</row>').join('')+'</sheetData><autoFilter ref="A1:'+column(output.headers.length-1)+rows.length+'"/></worksheet>';
 const files={
 '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
 '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
 'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Pivot output" sheetId="1" r:id="rId1"/></sheets></workbook>',
 'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
 'xl/worksheets/sheet1.xml':sheet};
 return zipSync(Object.fromEntries(Object.entries(files).map(([path,data])=>[path,strToU8(data)])));
}
export async function downloadPivot(output:{headers:string[];rows:Cell[][]},filename:string){const bytes=await pivotWorkbook(output);const url=URL.createObjectURL(new Blob([new Uint8Array(bytes)],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}));const link=document.createElement('a');link.href=url;link.download=filename.replace(/[\\/:*?"<>|]/g,'_')+' pivot.xlsx';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}

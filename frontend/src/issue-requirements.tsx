import {useEffect,useState} from 'react';
import DataGrid from './data-grid';
import {can,authorizeExport} from './bridge';
import type {Cell} from './model-data';

export function issueSlipText(headers:string[],rows:Cell[][]){
 const cell=(value:Cell)=>{if(value===null)return '';if(typeof value==='number')return String(value);const text=value.replace(/[\t\r\n]+/g,' ');return /^[\s]*[=+@-]/.test(text)?"'"+text:text;};
 return [headers,...rows].map(row=>row.map(cell).join('\t')).join('\r\n');
}
export default function IssueRequirements({headers,rows,standalone=false}:{headers:string[];rows:Cell[][];standalone?:boolean}){
 const [filtered,setFiltered]=useState(rows),[status,setStatus]=useState(''),[manual,setManual]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{setFiltered(rows);setStatus('');setManual('')},[rows]);
 async function copy(){
  if(busy||!can('download'))return;setBusy(true);setStatus('');setManual('');
  try{
   if(!await authorizeExport())return;
   const text=issueSlipText(headers,filtered);
   try{if(!navigator.clipboard?.writeText)throw Error('Clipboard unavailable');await navigator.clipboard.writeText(text);setStatus('Copied '+filtered.length+' filtered requirement rows with headers.');}
   catch{setManual(text);setStatus('Select and copy the text below, then paste into Excel.');}
  }finally{setBusy(false)}
 }
 return <section aria-label="Batch-wise issue requirements">{!standalone&&<h3>Batch-wise material requirements · Issue slip</h3>}<p className="issue-slip-note">Full BOM quantities for each plan and batch, including shortages. SAP Order stays blank until assigned. Check Plan Readiness and Verification before issuing; this table does not deduct stock.</p><div className="toolbar">{can('download')&&<button className="secondary" disabled={busy||!filtered.length} onClick={copy}>{busy?'Preparing copy…':'Copy filtered rows for Excel'}</button>}<span>{filtered.length.toLocaleString('en-IN')} matching rows · Copy includes all pages</span></div>{status&&<p role="status">{status}</p>}{manual&&<label>Issue-slip copy text<textarea aria-label="Issue-slip copy text" readOnly rows={8} value={manual} onFocus={e=>e.currentTarget.select()} style={{width:'100%'}}/></label>}<DataGrid numberPrecision={12} headers={headers} rows={rows} onFilteredRows={setFiltered} storageKey="availability:issue-requirements" filename="Batch-wise material requirements"/></section>;
}

import {useEffect,useState} from 'react';
import {loadIssueSlip,preparedIssueSlip} from './issue-slip-cache';
import IssueRequirements from './issue-requirements';
import type {Report} from './production';
export default function FloorIssueSlip(){
 const ready=preparedIssueSlip();
 const [result,setResult]=useState<Report['batchAvailability']>(ready?.result??null),[cached,setCached]=useState(!!ready),[busy,setBusy]=useState(!ready),[error,setError]=useState(''),[refresh,setRefresh]=useState(0);
 useEffect(()=>{const changed=()=>setRefresh(v=>v+1);window.addEventListener('stock-data-updated',changed);window.addEventListener('stock-manual-data-updated',changed);return()=>{window.removeEventListener('stock-data-updated',changed);window.removeEventListener('stock-manual-data-updated',changed)}},[]);
 useEffect(()=>{let live=true;const prepared=refresh===0?preparedIssueSlip():undefined;if(prepared){setResult(prepared.result);setCached(true);setBusy(false);return}
  setBusy(true);setError('');loadIssueSlip(refresh>0).then(loaded=>{if(live){setResult(loaded.result);setCached(loaded.cached)}}).catch(e=>{if(live){setResult(null);setError(e instanceof Error?e.message:String(e))}}).finally(()=>{if(live)setBusy(false)});return()=>{live=false}},[refresh]);
 const headers=result?.issueHeaders||[],rows=result?.issueRows||[];
 const count=(name:string)=>{const index=headers.indexOf(name);return index<0?'—':new Set(rows.map(row=>row[index]).filter(value=>value!==null&&value!=='')).size.toLocaleString('en-IN')};
 return <section className="floor-issue-screen" aria-label="Floor Level Issue Slip"><div className="issue-slip-heading"><div><p className="eyebrow">FLOOR LEVEL</p><h1>Issue Slip</h1><p>Material requirements by upcoming plan and product batch.</p></div><button className="secondary" disabled={busy} onClick={()=>setRefresh(v=>v+1)}>{busy?'Updating…':'Refresh issue slips'}</button></div>
 <div className="issue-slip-meta"><span role="status">{busy?'Updating from upcoming production plans…':error?'Update failed':cached?'Ready from cache':'Updated from upcoming plans'}</span>{result?.checkedAt&&<span>Material check: {new Date(result.checkedAt*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})} IST</span>}</div>
 {error&&<p className="error" role="alert">{error} <button onClick={()=>setRefresh(v=>v+1)}>Retry</button></p>}
 {result&&<><div className="issue-slip-summary"><div><span>Upcoming plans</span><strong>{count('Plan Reference')}</strong></div><div><span>Components</span><strong>{count('Component Code')}</strong></div><div><span>Requirement rows</span><strong>{rows.length.toLocaleString('en-IN')}</strong></div></div><div className="panel issue-slip-table"><IssueRequirements standalone headers={headers} rows={rows}/></div></>}
 {!busy&&!error&&!result&&<div className="panel issue-slip-empty">No upcoming production plans are available in your permitted scope.</div>}</section>;
}

import {createContext,useContext,useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {can,canAccessTab,rpc,tableColumnSnapshot,persistViewPreferences} from './bridge';
import {useViewPreference} from './view-preference';
import type {Cell} from './grid-utils';
export type ColumnDefinition={name:string;request:string;plan:{sources:any[];joins:any[];calculations?:any[];columns:string[]}};
type ColumnActions={definitions:ColumnDefinition[];busy:boolean;message:string;add:(question:string,consent:boolean)=>Promise<string>;remove:(name:string)=>void;reset:()=>void;save:()=>Promise<void>;retry:()=>void};
type Result={warnings?:string[];boot?:boolean;key:string;columns:{name:string;values:Cell[]}[]};
const results=new Map<string,Result>();
let sourceEpoch=0,cacheBytes=0;
const sizes=new Map<string,number>();
const clearResults=()=>{results.clear();sizes.clear();cacheBytes=0};
const invalidate=()=>{sourceEpoch++;clearResults()};
window.addEventListener('stock-source-versions',invalidate);
window.addEventListener('stock-data-updated',invalidate);
function forget(key:string){cacheBytes-=sizes.get(key)||0;sizes.delete(key);results.delete(key)}
function remember(value:Result){
 const size=JSON.stringify(value).length;forget(value.key);if(size>32_000_000)return false;
 results.set(value.key,value);sizes.set(value.key,size);cacheBytes+=size;
 while(results.size>32||cacheBytes>128_000_000){const key=results.keys().next().value!;forget(key)}
 return results.has(value.key);
}
export function preparedColumnKey(headers:string[],rows:Cell[][],scope:string,definitions:ColumnDefinition[]){return JSON.stringify([scope,JSON.stringify(tableColumnSnapshot()),JSON.stringify(definitions),sourceEpoch,headers,rows]);}
export async function preloadColumnValues(headers:string[],rows:Cell[][],scope:string,definitions:ColumnDefinition[]){
 const snapshot=tableColumnSnapshot(),owner=JSON.stringify(snapshot),epoch=sourceEpoch;
 const key=preparedColumnKey(headers,rows,scope,definitions);
 const data=await rpc('table_columns_resolve',{scope,headers,rows,definitions,version:snapshot.version});
 if(owner!==JSON.stringify(tableColumnSnapshot())||epoch!==sourceEpoch)throw Error('Data or access changed while loading saved columns. Retry startup.');
 if(!remember({key,columns:data.columns,warnings:data.warnings,boot:true}))throw Error('This added-column result is too large to keep in startup memory.');
 return key;
}
export const hasPreparedColumns=(keys:string[])=>keys.every(key=>results.has(key));
export const TableColumns=createContext<ColumnActions|null>(null);
export function useColumns(headers:string[],rows:Cell[][],scope:string){
 const [preference,setPreference]=useViewPreference('columns:'+scope,{definitions:[] as ColumnDefinition[]});
 const definitions=preference.definitions||[],signature=JSON.stringify(definitions),snapshot:{version?:string;user?:string;accessScope?:string}=typeof tableColumnSnapshot==='function'?tableColumnSnapshot():{};
 const mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[]);
 const owner=JSON.stringify(snapshot),[epoch,setEpoch]=useState(0),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 const [result,setResult]=useState<Result|null>(null),generation=useRef(0);
 const key=useMemo(()=>JSON.stringify([scope,owner,signature,sourceEpoch,headers,rows]),[scope,owner,signature,epoch,headers,rows]);const latest=useRef(key);latest.current=key;
 const permitted=can('use_tools')&&(typeof canAccessTab!=='function'||canAccessTab(7));
 useEffect(()=>{const changed=()=>{setResult(null);setEpoch(n=>n+1)};window.addEventListener('stock-source-versions',changed);window.addEventListener('stock-data-updated',changed);return()=>{window.removeEventListener('stock-source-versions',changed);window.removeEventListener('stock-data-updated',changed)}},[]);
 useEffect(()=>{const current=++generation.current;if(!definitions.length){setResult(null);setBusy(false);return}if(result?.key===key){setBusy(false);return;}if(!permitted){setResult(null);setMessage('Added columns are unavailable because assistant/source access changed.');return}const prepared=results.get(key);if(prepared?.boot){const loaded={key,columns:prepared.columns,warnings:prepared.warnings};remember(loaded);setResult(loaded);setBusy(false);setMessage(prepared.warnings?.join(' ')||'Saved column values ready.');return}let live=true;setBusy(true);setMessage('Loading saved column values…');rpc('table_columns_resolve',{scope,headers,rows,definitions,version:snapshot.version}).then(data=>{if(live&&current===generation.current&&latest.current===key){const next={key,columns:data.columns};remember(next);setResult(next);setMessage(data.warnings?.join(' ')||(data.cached?'Loaded cached column values.':'Saved column values loaded.'))}}).catch(e=>{if(live&&current===generation.current){forget(key);setResult(null);setMessage(e instanceof Error?e.message:String(e))}}).finally(()=>{if(live&&current===generation.current)setBusy(false)});return()=>{live=false}},[key,permitted,epoch]);
 useEffect(()=>{window.dispatchEvent(new window.CustomEvent('stock-table-columns-changed',{detail:{scope,names:definitions.map(d=>d.name)}}))},[scope,signature]);
 const retained=permitted?(result?.key===key?result:results.get(key)):undefined;
 const resolved=retained?.columns??[];
 const table=useMemo(()=>{if(!definitions.length)return {headers,rows};return {headers:[...headers,...definitions.map(d=>d.name)],rows:rows.map((row,index)=>[...row,...definitions.map(d=>resolved.find(c=>c.name===d.name)?.values[index]??null)])}},[headers,rows,signature,retained,key]);
 async function add(question:string,consent:boolean){if(!permitted)throw Error('Assistant access is required to add columns.');if(busy)throw Error('Wait for the current column calculation to finish.');const current=++generation.current,requestKey=key;setBusy(true);setMessage('');try{const data=await rpc('table_column_plan',{scope,headers,rows,definitions,question,consent,version:snapshot.version});if(!mounted.current)return data.saved?'Column saved to your account. Reopen the table to view it.':'The table was closed. Reopen it to check the saved column.';if(typeof tableColumnSnapshot==='function'&&JSON.stringify(tableColumnSnapshot())!==owner)throw Error('The account or workbook changed. Reopen the table.');if(latest.current!==requestKey||current!==generation.current)throw Error('The table or account changed. Add the column again using the current view.');if(data.clarification)return data.clarification;const next=[...definitions,data.definition];setPreference({definitions:next});const value={key:JSON.stringify([scope,owner,JSON.stringify(next),sourceEpoch,headers,rows]),columns:data.columns};remember(value);setResult(value);setMessage(data.warnings?.join(' ')||(data.saved?'Column added and saved to your account.':'Column added. Saving your layout…'));return 'Added '+data.definition.name+'. It is available for filtering, calculations and grouping. '+(data.warnings?.join(' ')||'')}finally{if(mounted.current&&current===generation.current)setBusy(false)}}
 function remove(name:string){clearResults();const removed=new Set([name]);for(const d of definitions){if([...removed].some(n=>JSON.stringify(d.plan).includes(JSON.stringify('s0.'+n))))removed.add(d.name)}generation.current++;setBusy(false);setResult(null);setPreference({definitions:definitions.filter(d=>!removed.has(d.name))});setMessage('Removed '+[...removed].join(', ')+'. Dependent added columns were also removed.');}
 function reset(){clearResults();generation.current++;setBusy(false);setResult(null);setPreference({definitions:[]});setMessage('Original columns restored.');}
 async function save(){if(typeof persistViewPreferences==='function')await persistViewPreferences();setMessage('Table layout saved for future logins.');}
 return {table,actions:{definitions,busy,message,add,remove,reset,save,retry:()=>{forget(key);setResult(null);setEpoch(n=>n+1)}} satisfies ColumnActions};
}
export function ColumnLayoutTools(){const columns=useContext(TableColumns),[saving,setSaving]=useState(false),[status,setStatus]=useState('');if(!columns)return null;return <><button type="button" className="secondary" disabled={saving||columns.busy} onClick={async()=>{setSaving(true);setStatus('');try{await columns.save();setStatus('Layout saved')}catch(e){setStatus(e instanceof Error?e.message:String(e))}finally{setSaving(false)}}}>{saving?'Saving layout…':'Save table layout'}</button>{status&&<span role="status">{status}</span>}{columns.definitions.length>0&&<details className="gridsettings"><summary>Added columns ({columns.definitions.length})</summary><div className="gridsettingspanel">{columns.definitions.map(d=><div key={d.name}><strong>{d.name}</strong><p>{d.request}</p><button type="button" className="secondary" onClick={()=>columns.remove(d.name)}>Delete {d.name}</button></div>)}</div></details>}{columns.definitions.length>0&&!columns.busy&&<button type="button" className="secondary" onClick={columns.retry}>Retry added columns</button>}{columns.definitions.length>0&&columns.message&&<span className="smallnote" role="status">{columns.busy?'Loading added-column values…':columns.message}</span>}</>}

export function preparedColumnSnapshot(keys:string[]){return keys.map(key=>results.get(key)).filter(Boolean);}
export function restorePreparedColumns(values:Result[]){
 const owner=JSON.stringify(tableColumnSnapshot()),keys:string[]=[];
 for(const value of values){
  try{
   const parts=JSON.parse(value.key);
   if(!Array.isArray(parts)||parts.length!==6||parts[1]!==owner||!Array.isArray(parts[4])||!Array.isArray(parts[5])||!Array.isArray(value.columns))return null;
   if(value.columns.some(c=>typeof c.name!=='string'||!Array.isArray(c.values)||c.values.length!==parts[5].length))return null;
   parts[3]=sourceEpoch;const key=JSON.stringify(parts);
   if(!remember({...value,key,boot:true}))return null;keys.push(key);
  }catch{return null}
 }
 return hasPreparedColumns(keys)?keys:null;
}

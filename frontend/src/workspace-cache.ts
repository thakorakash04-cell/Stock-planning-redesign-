// Display snapshots only. A fresh authenticated bridge and current source metadata
// must produce the exact key before a snapshot can be restored. No identity/token
// from this database can sign in or authorize a request.
export type WorkspaceSnapshot={data?:any;contentId?:string;scope?:string;modelKey?:string;sourceStamp?:string;pnlParams?:string;key:string;finance:any;tables:any[]|null;columns:any[]};
const DATABASE='stock-planning-prepared-workspace-v1',STORE='workspace',MAX_BYTES=96*1024*1024;
export async function workspaceCacheKey(args:any,versions:Record<string,string>){
 if(!args.user||!args.accessScope||!args.version||!args.data||!globalThis.crypto?.subtle)return null;
 const preferences=Object.fromEntries(Object.entries(args.preferences||{}).filter(([key])=>key.startsWith('columns:')||key==='pnl:filters').sort(([a],[b])=>a.localeCompare(b)));
 // Include the full authorised display snapshot: covers workbook upload stamps,
 // plan edits, availability, lead time, portal and product-catalogue changes.
 const bytes=new TextEncoder().encode(JSON.stringify([3,args.user,args.role,args.permissions,args.accessScope,args.version,args.modelScope,args.data,preferences,Object.entries(versions).sort(([a],[b])=>a.localeCompare(b))]));
 return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
}
async function database():Promise<IDBDatabase|null>{
 if(typeof indexedDB==='undefined')return null;
 return new Promise(resolve=>{
  let settled=false;const finish=(db:IDBDatabase|null)=>{if(settled){db?.close();return}settled=true;clearTimeout(timer);resolve(db)};
  const timer=setTimeout(()=>finish(null),10000);
  try{const request=indexedDB.open(DATABASE,1);request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains(STORE))request.result.createObjectStore(STORE)};request.onsuccess=()=>finish(request.result);request.onerror=()=>finish(null);request.onblocked=()=>finish(null)}catch{finish(null)}
 });
}
export async function readWorkspaceCache(key:string|null,scope?:string):Promise<WorkspaceSnapshot|null>{
 if(!key)return null;const db=await database();if(!db)return null;
 return new Promise(resolve=>{
  let settled=false;const finish=(value:WorkspaceSnapshot|null)=>{if(settled)return;settled=true;clearTimeout(timer);db.close();resolve(value)};
  const timer=setTimeout(()=>finish(null),10000);
  try{const tx=db.transaction(STORE,'readonly'),request=tx.objectStore(STORE).get('prepared');request.onsuccess=()=>{try{const value=request.result;if(typeof value!=='string'||(value.length>MAX_BYTES||new Blob([value]).size>MAX_BYTES))return finish(null);const snapshot=JSON.parse(value);finish((snapshot?.key===key||Boolean(scope&&snapshot?.scope===scope))&&Array.isArray(snapshot.columns)&&(snapshot.tables===null||Array.isArray(snapshot.tables))?snapshot:null)}catch{finish(null)}};request.onerror=()=>finish(null);tx.onabort=()=>finish(null)}catch{finish(null)}
 });
}
export async function writeWorkspaceCache(snapshot:WorkspaceSnapshot,isCurrent:()=>boolean){
 let value:string;try{value=JSON.stringify(snapshot)}catch{return false}if((value.length>MAX_BYTES||new Blob([value]).size>MAX_BYTES)||!isCurrent())return false;
 const db=await database();if(!db)return false;if(!isCurrent()){db.close();return false}
 return new Promise<boolean>(resolve=>{
  let settled=false;const finish=(saved:boolean)=>{if(settled)return;settled=true;clearTimeout(timer);db.close();resolve(saved)};
  const timer=setTimeout(()=>finish(false),10000);
  try{const tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).put(value,'prepared');tx.oncomplete=()=>finish(true);tx.onabort=tx.onerror=()=>finish(false)}catch{finish(false)}
 });
}

export const modelCacheKey=(args:any)=>JSON.stringify([args.accessScope,args.version,args.modelScope,args.data?.updatedAt]);
export const columnSourceStamp=(args:any,versions:Record<string,string>)=>JSON.stringify([modelCacheKey(args),args.data?.productionRevision,args.data?.planningRevision,args.data?.productCatalogue?.version,Object.entries(versions).sort(([a],[b])=>a.localeCompare(b))]);
export function reusableColumns(columns:any[],previousStamp?:string,currentStamp?:string){
 let old:any[],next:any[];try{old=JSON.parse(previousStamp||'null');next=JSON.parse(currentStamp||'null');if(!Array.isArray(old)||!Array.isArray(next))return [];}catch{return [];}
 const oldVersions=Object.fromEntries(old[4]||[]),nextVersions=Object.fromEntries(next[4]||[]),baseChanged=JSON.stringify(old.slice(0,4))!==JSON.stringify(next.slice(0,4));
 return columns.filter(value=>{try{
  const definitions=JSON.parse(JSON.parse(value.key)[2]);
  return definitions.every((d:any)=>Array.isArray(d.plan?.sources)&&d.plan.sources.slice(1).every((source:any)=>{
   const name=String(source.table_name||''),key=String(source.source_key||'');
   const part=key.startsWith('sales:primary')||/^primary sales$/i.test(name)?'primary':key.startsWith('sales:secondary')||/^secondary sales$/i.test(name)?'secondary':key.startsWith('pnl:')||/p.?&.?l snapshot/i.test(name)?'pnl':null;
   return part?oldVersions[part]===nextVersions[part]:name?!baseChanged:previousStamp===currentStamp;
  }));
 }catch{return false}});
}

export function financeParts(cached:any,versions:Record<string,string>,samePnlParams:boolean){
 const value:any={id:cached?.id,sales:{},pnl:null,errors:[],versions},missing:string[]=[];
 for(const part of ['primary','secondary','pnl'])if(Object.hasOwn(versions,part)){
  const data=part==='pnl'?cached?.pnl:cached?.sales?.[part];
  if(data&&cached?.versions?.[part]===versions[part]&&(part!=='pnl'||samePnlParams)){if(part==='pnl')value.pnl=data;else value.sales[part]=data;}else missing.push(part);
 }
 return{value,missing};
}

// User activity is local; it never renews authentication or authorizes SQL.
let lastUserActivity=Date.now(),lastActivityNotice=0;
export function browserActive(){return typeof document!=='undefined'&&!document.hidden&&Date.now()-lastUserActivity<300000;}
function userActivity(){const now=Date.now(),resuming=now-lastUserActivity>=300000;lastUserActivity=now;
 if(resuming||now-lastActivityNotice>=30000){lastActivityNotice=now;window.parent.postMessage({type:'workspace:user-activity'},window.location?.origin||'*');}}
for(const type of ['pointerdown','pointermove','keydown','scroll','touchstart','wheel'])window.addEventListener(type,userActivity,{passive:true,capture:true});
if(typeof document!=='undefined')document.addEventListener('visibilitychange',()=>{if(!document.hidden){lastActivityNotice=0;userActivity();}});
import {selectDetails} from './detail-rules';
import {segmentIndex,filterSegments,segmentChoices} from './segments';
import {sourceVersions} from './preload-cache';
import {readWorkspaceCache} from './workspace-cache';
import {rememberInsightResponse} from './insight-display-cache';
import type {ModelTable} from './model-data';
type Args={productionStamp?:string;contentId?:string;dataDeferred?:boolean;accessScope?:string;modelScope?:string;tablesDeferred?:boolean;bootstrapId?:string;preload?:any;preferences?:Record<string,any>;version?:string;data?:Record<string,any>|null;tables?:ModelTable[]|null;user:string;role:string;permissions?:Record<string,boolean>;response?:{id:string;body:any;error?:string}};
let state:Args|null=null,parentOrigin='*',lastHeight=0,lastActivity=Date.now()/1000;
for(const name of ['pointerdown','pointermove','keydown','scroll','touchstart','wheel'])window.addEventListener(name,()=>{lastActivity=Date.now()/1000},{passive:true});
function fitFrame(){let height=window.screen.availHeight-140;try{height=window.parent.innerHeight}catch{}height=Math.max(240,height);if(height!==lastHeight){lastHeight=height;send('streamlit:setFrameHeight',{height})}}
const waiting=new Map<string,{resolve:(v:any)=>void;reject:(v:Error)=>void}>();
let navigating=false,navigationId:string|null=null,bootstrapRecovery=false;
let queue:Promise<any>=Promise.resolve();let readyListener:((args:Args)=>void)|null=null;
const send=(type:string,extra:Record<string,unknown>)=>window.parent.postMessage({isStreamlitMessage:true,type,...extra},parentOrigin);
export const isAdmin=()=>state?.role==='admin';
export const canAccessTab=(tab:number)=>!state?.data?.accessibleTabs||state.data.accessibleTabs.includes(tab);
export const can=(permission:string)=>isAdmin()||state?.permissions?.[permission]===true;
export async function authorizeExport(){try{await rpc('export');return true}catch(e){alert(e instanceof Error?e.message:String(e));return false}}
export function rpc(action:string,payload:Record<string,unknown>={}):Promise<any>{if(action!=='preferences_save')flushPreferences();const owner=state?.user,cacheOwner={user:state?.user,accessScope:state?.accessScope};const work=()=>new Promise((resolve,reject)=>{if(navigating){reject(new Error('Opening the selected page.'));return}if(action==='preferences_save'&&state?.user!==owner){resolve({skipped:true});return}const id=crypto.randomUUID();waiting.set(id,{resolve,reject});send('streamlit:setComponentValue',{value:{...payload,id,action,knownBootstrapId:state?.bootstrapId,activity:lastActivity},dataType:'json'});setTimeout(()=>{if(waiting.has(id)){waiting.delete(id);reject(new Error('Request timed out. Please retry.'))}},action==='generate_insights'?240000:120000)});const result=queue.then(work);queue=result.catch(()=>{});return result.then(value=>{rememberInsightResponse(cacheOwner,action,payload,value);if(['production_save','production_delete','pnl_settings'].includes(action)&&state?.user===owner)window.dispatchEvent(new window.Event('stock-manual-data-updated'));return value});}
// Navigation must not wait behind an export, heartbeat or timed-out RPC.
export function openAccount(action:'logout'|'open_admin'|'open_password'|'open_settings'|'open_email'|'open_history'|'open_workbook'|'open_uploads'){
 navigating=true;navigationId=crypto.randomUUID();
 if(preferenceTimer){clearTimeout(preferenceTimer);preferenceTimer=undefined}
 // One component value carries navigation and unsaved preferences. Background
 // RPCs must not overwrite this value while Streamlit switches components.
 const preferences=[...dirtyPreferences].map(([scope,pending])=>({scope,value:pending.value}));
 send('streamlit:setComponentValue',{value:{id:navigationId,action,knownBootstrapId:state?.bootstrapId,activity:lastActivity,preferences,theme:typeof document!=='undefined'&&document.documentElement.dataset.theme==='dark'?'dark':'light'},dataType:'json'});
}
export async function uploadWorkbook(file:File,preview=false){const bytes=new Uint8Array(await file.arrayBuffer());let raw='';for(let i=0;i<bytes.length;i+=32768)raw+=String.fromCharCode(...bytes.subarray(i,i+32768));return rpc(preview?'upload_preview':'upload',{filename:file.name,content:btoa(raw)})}
export function startBridge(onReady:(args:Args)=>void){
 readyListener=onReady;
 window.addEventListener('message',event=>{
  if(event.source!==window.parent||event.data?.type!=='streamlit:render')return;
  parentOrigin=event.origin;
  const args=event.data.args as Args;if(!args?.user)return;
  const changed=Boolean(args.data)&&(args.bootstrapId!==state?.bootstrapId||!state?.data||args.user!==state?.user||args.role!==state?.role||JSON.stringify(args.permissions||{})!==JSON.stringify(state?.permissions||{})||args.data?.productCatalogue?.version!==state?.data?.productCatalogue?.version||args.version!==state.version||args.data?.workspaceRevision!==state?.data?.workspaceRevision||args.data?.planningRevision!==state?.data?.planningRevision||args.data?.productionRevision!==state?.data?.productionRevision||JSON.stringify(args.data?.portal)!==JSON.stringify(state?.data?.portal));
  const userChanged=Boolean(state?.user)&&(state?.user!==args.user||state?.role!==args.role||JSON.stringify(state?.permissions||{})!==JSON.stringify(args.permissions||{})||state?.accessScope!==args.accessScope);
  const contentChanged=Boolean(args.contentId&&state?.contentId&&args.contentId!==state.contentId);
  const modelChanged=userChanged||args.modelScope!==state?.modelScope||args.version!==state?.version;
  if(userChanged){dirtyPreferences.clear();if(preferenceTimer)clearTimeout(preferenceTimer);preferenceTimer=undefined}
  const oldPreferences=JSON.stringify(state?.preferences||{});
  const mergedPreferences={...(args.preferences||state?.preferences||{})};
  for(const [key,pending] of dirtyPreferences)mergedPreferences[key]=pending.value;
  state={...state,...args,preferences:mergedPreferences,data:changed?args.data:userChanged||contentChanged?null:state?.data,tables:modelChanged?(args.tables??null):(args.tables??state?.tables),tablesDeferred:modelChanged?args.tablesDeferred:Boolean(state?.tables?.length)?false:args.tablesDeferred};
  if(changed)window.dispatchEvent(new Event('stock-data-updated'));
  if(userChanged||JSON.stringify(state.preferences)!==oldPreferences)window.dispatchEvent(new Event('stock-preferences-ready'));
  if(args.response?.id===navigationId&&args.response?.error){navigating=false;navigationId=null;alert(args.response.error)}
  if(args.response){const pending=waiting.get(args.response.id);if(pending){waiting.delete(args.response.id);args.response.error?pending.reject(new Error(args.response.error)):pending.resolve(args.response.body)}}
  if(state?.data){bootstrapRecovery=false;readyListener?.(state)}
  else if(args.bootstrapId&&!bootstrapRecovery){
   bootstrapRecovery=true;const owner=state.user,scope=state.accessScope,contentId=state.contentId,bootstrap=state.bootstrapId;
   const recover=()=>rpc('workspace_bootstrap').catch(()=>{bootstrapRecovery=false});
   if(args.dataDeferred&&scope&&contentId){
    void readWorkspaceCache(contentId,scope).then(cached=>{
     if(state?.user!==owner||state?.accessScope!==scope||state?.contentId!==contentId||state?.bootstrapId!==bootstrap)return;
     if(cached?.scope===scope&&cached.contentId===contentId&&cached.data&&Array.isArray(cached.data.sheets)){state={...state,data:cached.data};document.documentElement.dataset.workspaceBaseCache='restored';bootstrapRecovery=false;readyListener?.(state);}
     else void recover();
    }).catch(()=>{void recover()});
   }else void recover();
  }
  fitFrame();
 });
 window.addEventListener('resize',fitFrame);
 (window as any).__portalBoot?.handoff?.();
 send('streamlit:componentReady',{apiVersion:1});
 const handshake=setInterval(()=>{if(state){clearInterval(handshake);return}send('streamlit:componentReady',{apiVersion:1})},1000);
 setInterval(()=>{if(browserActive()&&state?.data&&!waiting.size)rpc('heartbeat').then(result=>{if(result.sourceVersions)sourceVersions(result.sourceVersions)}).catch(()=>{})},60000);
}
const modelRequests=new Map<string,Promise<void>>();
export async function ensureModelTables(){
 if(!state?.tablesDeferred)return;
 const scope=state.modelScope,version=state.version,user=state.user;
 if(!scope)throw Error('Refresh the workspace before opening source records.');
 let pending=modelRequests.get(scope);
 if(!pending){pending=rpc('workspace_model_tables',{modelScope:scope,version}).then(result=>{
  if(state?.modelScope!==scope||state?.user!==user||state?.version!==version||result.modelScope!==scope||result.version!==version)throw Error('The workbook or access changed. Reopen the source records.');
  state={...state,tables:result.tables,tablesDeferred:false};
 }).finally(()=>modelRequests.delete(scope));modelRequests.set(scope,pending);}
 await pending;
}
const originalFetch=window.fetch.bind(window);
window.fetch=async(input:RequestInfo|URL,init?:RequestInit)=>{const path=typeof input==='string'?input:input instanceof URL?input.pathname:input.url;if(path==='/api/data'){if(!state?.data)return Response.json({error:'Loading data'},{status:503});return Response.json(state.data)}if(path==='/api/details'){try{await ensureModelTables()}catch(e){return Response.json({error:e instanceof Error?e.message:String(e)},{status:409})}if(!state?.tables?.length)return Response.json({available:false,message:'Upload a workbook containing an embedded Power Pivot model to see its source records.'});const body=JSON.parse(String(init?.body||'{}'));const index=segmentIndex(state.tables);const sets=filterSegments(selectDetails(state.tables,body.tab,body.row,body.col,body.scope==='all'),index,body.segment||'all');if(body.exportTables)return Response.json({tables:sets});const table=sets.find(t=>t.name===body.table)||sets.find(t=>t.rows.length)||sets[0];const q=String(body.q||'').toLowerCase();const rows=table?.rows.filter(r=>!q||r.some(v=>String(v??'').toLowerCase().includes(q)))||[];return Response.json({available:true,tables:sets.map(t=>({name:t.name,count:t.rows.length})),segments:segmentChoices(state.tables,index),table:table?.name,headers:table?.headers||[],rows:body.exportAll?rows:rows.slice((body.page||0)*50,(body.page||0)*50+50),total:rows.length,totalRelated:sets.reduce((n,t)=>n+t.rows.length,0)})}return originalFetch(input,init)};

export function exportMatchedRows(payload:Record<string,unknown>){return rpc('matched_export',{...payload,version:state?.version,scope:'related'})}

export async function downloadPlanningTable(source:string,headers:string[],rows:unknown[][],plan_id?:string){
 const file=await rpc('planning_table_export',{source,headers,rows,plan_id,version:state?.version});
 const bytes=Uint8Array.from(atob(file.content),c=>c.charCodeAt(0));const url=URL.createObjectURL(new Blob([bytes],{type:file.mime}));
 const link=document.createElement('a');link.href=url;link.download=file.filename;link.click();URL.revokeObjectURL(url);
}

const dirtyPreferences=new Map<string,{value:any;generation:number}>();
let preferenceTimer:ReturnType<typeof setTimeout>|undefined,preferenceGeneration=0;
export function readViewPreference(key:string){return state?.preferences?.[key]}
export function saveViewPreference(key:string,value:any){
 if(!state?.user)return;
 state.preferences={...state.preferences,[key]:value};
 dirtyPreferences.set(key,{value,generation:++preferenceGeneration});
 if(preferenceTimer)clearTimeout(preferenceTimer);
 preferenceTimer=setTimeout(flushPreferences,500);
}
export function flushPreferences(){
 if(preferenceTimer){clearTimeout(preferenceTimer);preferenceTimer=undefined}
 for(const [scope,pending] of dirtyPreferences){
  if((pending as any).sending)continue;
  (pending as any).sending=true;
  const request=rpc('preferences_save',{scope,value:pending.value});(pending as any).promise=request;request.then(()=>{
   if(dirtyPreferences.get(scope)?.generation===pending.generation)dirtyPreferences.delete(scope);
  }).catch(()=>{if(dirtyPreferences.get(scope)?.generation===pending.generation)(pending as any).sending=false;window.dispatchEvent(new Event('stock-preferences-error'))});
 }
}




export function tableColumnSnapshot(){return {version:state?.version,user:state?.user,accessScope:state?.accessScope};}
export async function persistViewPreferences(){flushPreferences();await Promise.all([...dirtyPreferences.values()].map(p=>(p as any).promise).filter(Boolean));}

// Called only after startup has validated an exact authenticated snapshot key.
export function preparedModelTables(){return state?.tablesDeferred?null:state?.tables||[];}
export function restoreModelTables(tables:ModelTable[],scope:string|undefined,version:string|undefined){
 if(!state||state.modelScope!==scope||state.version!==version)return false;
 if(!Array.isArray(tables)||tables.some(t=>!Array.isArray(t.headers)||!Array.isArray(t.rows)))return false;
 state={...state,tables,tablesDeferred:false};return true;
}

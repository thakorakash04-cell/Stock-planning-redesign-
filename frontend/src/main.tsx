import './issue-slip.css';
import {loadIssueSlip} from './issue-slip-cache';
import React from 'react';
import {primeView} from './cached-view';
import WorkspaceBoundary from './workspace-boundary';
import {createRoot} from 'react-dom/client';
import Dashboard,{type Data} from './dashboard';
import {startBridge,rpc,ensureModelTables,preparedModelTables,restoreModelTables} from './bridge';
import './globals.css';
import './theme.css';
import './insights-dashboard.css';
import './checkbox-filter.css';
import './table-controls.css';
import './mint-dashboard.css';
import './mint-sections.css';
import {seedPreload,prepareInsights} from './preload-cache';
import {loadInsightStatus} from './insight-display-cache';
import {preloadColumnValues,hasPreparedColumns,preparedColumnSnapshot,restorePreparedColumns,preparedColumnKey} from './table-columns';
import {startupTables} from './startup-tables';
import {workspaceCacheKey,readWorkspaceCache,writeWorkspaceCache,modelCacheKey,columnSourceStamp,reusableColumns,financeParts} from './workspace-cache';
const root=createRoot(document.getElementById('root')!);
function Loading({percent,label,error,retry,open}:{percent:number;label:string;error?:string;retry?:()=>void;open?:()=>void}){
 return <div className="workspace-connecting workspace-startup"><main><p className="eyebrow">STOCK &amp; PLANNING</p><h1>Loading your saved workspace</h1><p role="status">{label}</p><div className="startup-percentage">{percent}%</div><progress aria-label="Workspace loading" max={100} value={percent}/><p className="smallnote">Progress follows completed data-loading stages.</p>{error&&<div role="alert"><p>{error}</p><button className="primary" onClick={retry}>Retry loading</button> <button className="secondary" onClick={open}>Open available workspace</button></div>}</main></div>;
}
root.render(<Loading percent={0} label="Connecting to your workspace…"/>);
let mountedKey='',preloadId='',current:any=null,generation=0,runningKey='',failedKey='';
const identity=(args:any)=>JSON.stringify([args.user,args.role,args.permissions,args.accessScope]);
const stamp=(args:any)=>JSON.stringify([identity(args),args.bootstrapId,args.version,args.data?.updatedAt,args.data?.productionRevision,args.data?.planningRevision]);
function show(percent:number,label:string,error?:string,retry?:()=>void,open?:()=>void){root.render(<Loading {...{percent,label,error,retry,open}}/>);}
function openWorkspace(args:any){
 const data=args.productionStamp&&args.data?.production?{...args.data,production:{...args.data.production,displayStamp:args.productionStamp}}:args.data;
 if(data?.production)primeView('production_status',data.production,data.production.displayStamp);
 mountedKey=identity(args);runningKey='';root.render(<WorkspaceBoundary key={mountedKey+':'+generation} retry={()=>{if(current){mountedKey='';void loadWorkspace(current)}}}><Dashboard key={mountedKey} user={args.user} initialData={data as Data}/></WorkspaceBoundary>);
 if(args.data?.accessibleTabs?.includes(8)&&(args.role==='admin'||args.permissions?.use_tools)){
  const key=stamp(args);
  const warm=()=>{if(!current||stamp(current)!==key||mountedKey!==identity(args))return;
   void import('./insights').catch(()=>{});
   void prepareInsights(async()=>{const status=await loadInsightStatus(rpc,{user:args.user,accessScope:args.accessScope},args.role==='admin');if(!current||stamp(current)!==key||status.version!==args.version)throw Error('Data or access changed while restoring Insights.');return status}).catch(()=>{});
  };
  if(typeof window.requestAnimationFrame==='function')window.requestAnimationFrame(()=>window.requestAnimationFrame(warm));else setTimeout(warm,0);
 }
}
async function loadWorkspace(args:any){
 document.documentElement.dataset.workspaceCache='checking';
 const token=++generation,key=stamp(args);runningKey=key;failedKey='';let percent=20,label='Workbook and saved preferences loaded.';
 const check=()=>{if(token!==generation||!current||stamp(current)!==key)throw Error('The workbook or account changed. Retry loading the current workspace.');};
 const update=(value:number,text:string)=>{check();percent=value;label=text;show(value,text);};
 const acknowledge=(value:any)=>{if(value?.id&&value.id!==preloadId){preloadId=value.id;void rpc('workspace_preload_ack',{preloadId}).catch(()=>{})}};
 try{
  if(!Array.isArray(args.data?.sheets))throw Error('Workbook tables were incomplete. Retry loading.');
  update(20,label);
  // Authentication has already succeeded. Validate live source metadata before
  // reading any persisted display data; browser storage never restores identity.
  const freshness=await rpc('heartbeat');check();
  const sourceVersions=freshness.sourceVersions;
  const cacheKey=sourceVersions&&typeof indexedDB!=='undefined'?await workspaceCacheKey(args,sourceVersions).catch(()=>null):null;check();
  const cached=await readWorkspaceCache(cacheKey,args.accessScope);check();
  const sameVersions=(a:any,b:any)=>JSON.stringify(Object.entries(a||{}).sort(([a],[b])=>a.localeCompare(b)))===JSON.stringify(Object.entries(b||{}).sort(([a],[b])=>a.localeCompare(b)));
  if(cached&&cached.key===cacheKey&&(!args.preload?.deferred||(cached.finance?.id&&!cached.finance?.errors?.length&&sameVersions(cached.finance.versions,sourceVersions)))&&(!args.tablesDeferred||cached.tables!==null)){
   const keys=restorePreparedColumns(cached.columns);
   const expected=(args.role==='admin'||args.permissions?.use_tools)&&(!args.data?.accessibleTabs||args.data.accessibleTabs.includes(7))?startupTables(args.data,cached.finance,args.preferences||{}):[];
   const expectedKeys=expected.map(table=>preparedColumnKey(table.headers,table.rows,table.scope,args.preferences['columns:'+table.scope].definitions));
   if(keys&&keys.length===expectedKeys.length&&hasPreparedColumns(expectedKeys)&&(!args.tablesDeferred||restoreModelTables(cached.tables!,args.modelScope,args.version))){
    seedPreload(cached.finance,identity(args));
    if(args.data?.accessibleTabs?.includes(12)){update(96,'Preparing cached Issue Slip…');await loadIssueSlip();check();}
    document.documentElement.dataset.workspaceCache='restored';
    update(100,'Restored your cached tables.');
    await new Promise<void>(resolve=>{if(typeof window.requestAnimationFrame==='function')window.requestAnimationFrame(()=>resolve());else setTimeout(resolve,0)});check();openWorkspace(current);return;
   }
  }
  const sameScope=Boolean(cached&&cached.scope===args.accessScope);
  const modelReused=Boolean(sameScope&&cached?.modelKey===modelCacheKey(args)&&cached.tables&&restoreModelTables(cached.tables,args.modelScope,args.version));
  if(sameScope&&cached)restorePreparedColumns(reusableColumns(cached.columns,cached.sourceStamp,columnSourceStamp(args,sourceVersions||{})));
  const parts=financeParts(sameScope?cached?.finance:null,sourceVersions||{},Boolean(sameScope&&cached?.pnlParams===JSON.stringify(args.preferences?.['pnl:filters']||{})));
  let finance=args.preload?.id?args.preload:args.preload?.deferred?parts.value:null;
  if(args.preload?.deferred){
   if(parts.missing.length||!sourceVersions){
   update(20,'Updating changed saved views…');
   const result=await rpc('workspace_preload',sourceVersions?{parts:parts.missing}:{});check();
   if(result.version!==args.version||result.accessScope!==args.accessScope)throw Error('The saved views belong to another workbook or access scope. Retry loading.');
   const incoming=result.preload;finance={...finance,...incoming,sales:{...finance.sales,...incoming?.sales},pnl:incoming?.pnl??finance.pnl,versions:sourceVersions||incoming?.versions};acknowledge(incoming);
   if(finance?.errors?.length)throw Error(finance.errors.join(' '));
   }
   seedPreload(finance,identity(args));
  }
  update(40,'Saved financial views loaded.');
  if(args.tablesDeferred&&!modelReused&&typeof ensureModelTables==='function'){update(40,'Loading permitted source tables…');await ensureModelTables();check();}
  update(55,'Source tables ready.');
  update(65,'Cached table data ready.');
  const columnAccess=(args.role==='admin'||args.permissions?.use_tools)&&(!args.data?.accessibleTabs||args.data.accessibleTabs.includes(7));
  const tables=columnAccess?startupTables(args.data,finance,args.preferences||{}):[],keys:string[]=[];
  for(const [index,table] of tables.entries()){
   update(65+Math.floor(index/Math.max(1,tables.length)*30),'Loading saved column values · '+(index+1)+' of '+tables.length+'…');
   const prepared=preparedColumnKey(table.headers,table.rows,table.scope,args.preferences['columns:'+table.scope].definitions);
   keys.push(hasPreparedColumns([prepared])?prepared:await preloadColumnValues(table.headers,table.rows,table.scope,args.preferences['columns:'+table.scope].definitions));check();
  }
  if(!hasPreparedColumns(keys))throw Error('Some added-column results exceed startup memory capacity. Open the available workspace or retry.');
  update(95,'Preparing cached table interfaces…');
  const modules:Promise<any>[]=[];
  if(args.data?.accessibleTabs?.includes(11))modules.push(import('./sales'));
  if(args.data?.accessibleTabs?.includes(10))modules.push(import('./pnl'));
  await Promise.all(modules);check();
  if(finance?.versions){
   update(95,'Verifying saved source versions…');const result=await rpc('heartbeat');check();
   const versionKey=(value:any)=>JSON.stringify(Object.entries(value||{}).sort(([a],[b])=>String(a).localeCompare(String(b))));
   if(!result.sourceVersions||versionKey(result.sourceVersions)!==versionKey(finance.versions))throw Error('Business sources changed during loading. Retry to open one consistent saved workspace.');
  }
  if(args.data?.accessibleTabs?.includes(12)){update(96,'Preparing cached Issue Slip…');await loadIssueSlip();check();}
  update(97,"Saving prepared workspace…");
  const saved=cacheKey&&typeof preparedModelTables==='function'?await writeWorkspaceCache({data:args.data,contentId:args.contentId,scope:args.accessScope,modelKey:modelCacheKey(args),sourceStamp:columnSourceStamp(args,sourceVersions||{}),pnlParams:JSON.stringify(args.preferences?.['pnl:filters']||{}),key:cacheKey,finance,tables:preparedModelTables(),columns:preparedColumnSnapshot(keys)},()=>token===generation&&Boolean(current)&&stamp(current)===key).catch(()=>false):false;
  document.documentElement.dataset.workspaceCache=saved?'saved':'unavailable';
  check();update(100,saved?'Your cached tables are ready.':'Workspace ready · browser cache unavailable.');
  await new Promise<void>(resolve=>{if(typeof window.requestAnimationFrame==='function')window.requestAnimationFrame(()=>window.requestAnimationFrame(()=>resolve()));else setTimeout(resolve,0)});
  check();
  openWorkspace(current);
 }catch(error){
  if(token!==generation)return;
  runningKey='';failedKey=key;show(percent,label,error instanceof Error?error.message:String(error),()=>{if(current)void loadWorkspace(current)},()=>{if(current){generation++;openWorkspace(current)}});
 }
}
startBridge(args=>{
 const changedIdentity=current&&identity(current)!==identity(args);current=args;
 seedPreload(args.preload,identity(args));
 if(args.preload?.id&&args.preload.id!==preloadId){preloadId=args.preload.id;void rpc('workspace_preload_ack',{preloadId}).catch(()=>{});}
 if(identity(args)===mountedKey)return;
 if(changedIdentity){generation++;runningKey='';failedKey='';mountedKey='';}
 if(runningKey===stamp(args)||failedKey===stamp(args))return;
 // Host replies during startup must not restart the same loading sequence.
 if(runningKey){generation++;runningKey='';}
 void loadWorkspace(args);
});



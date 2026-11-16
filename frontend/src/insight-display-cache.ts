import {seedInsights} from './preload-cache';
type Owner={user?:string;accessScope?:string};
type Entry={owner:string;stamp:string;period:boolean;sections:Record<string,string>;report:any};
const DB='stock-planning-insight-display-v1',MAX=24*1024*1024;
let recent:Entry|null=null,lastStatus:any=null,lastOwner='',lastAdmin=false,currentOwner='',ownerEpoch=0,writes:Promise<unknown>=Promise.resolve();
const ownerKey=(owner:Owner)=>owner.user&&owner.accessScope?JSON.stringify([owner.user,owner.accessScope]):'';
async function database():Promise<IDBDatabase|null>{if(typeof indexedDB==='undefined')return null;return new Promise(resolve=>{let done=false;const finish=(db:IDBDatabase|null)=>{if(done){db?.close();return}done=true;clearTimeout(timer);resolve(db)},timer=setTimeout(()=>finish(null),5000);try{const r=indexedDB.open(DB,1);r.onupgradeneeded=()=>{if(!r.result.objectStoreNames.contains('reports'))r.result.createObjectStore('reports')};r.onsuccess=()=>finish(r.result);r.onerror=r.onblocked=()=>finish(null)}catch{finish(null)}});}
async function read(owner:string):Promise<Entry|null>{if(!owner)return null;if(recent?.owner===owner)return recent;const db=await database();if(!db)return null;return new Promise(resolve=>{let done=false;const finish=(v:Entry|null)=>{if(done)return;done=true;clearTimeout(timer);db.close();resolve(v)},timer=setTimeout(()=>finish(null),5000);try{const r=db.transaction('reports','readonly').objectStore('reports').get('display');r.onsuccess=()=>{try{if(typeof r.result!=='string'||r.result.length>MAX)return finish(null);const value=JSON.parse(r.result);if(value.owner!==owner||typeof value.stamp!=='string'||!Array.isArray(value.report?.sections))return finish(null);recent=value;finish(value)}catch{finish(null)}};r.onerror=()=>finish(null)}catch{finish(null)}});}
async function write(value:Entry){recent=value;let text:string;try{text=JSON.stringify(value)}catch{return false}if(text.length>MAX||new Blob([text]).size>MAX)return false;const db=await database();if(!db)return false;return new Promise<boolean>(resolve=>{let done=false;const finish=(saved:boolean)=>{if(done)return;done=true;clearTimeout(timer);db.close();resolve(saved)},timer=setTimeout(()=>finish(false),5000);try{const tx=db.transaction('reports','readwrite');tx.objectStore('reports').put(text,'display');tx.oncomplete=()=>finish(true);tx.onerror=tx.onabort=()=>finish(false)}catch{finish(false)}});}
export function displayOnly(report:any){const value=JSON.parse(JSON.stringify(report));delete value.report_id;delete value.report_scope;for(const section of value.sections||[])for(const item of [...(section.charts||[]),...(section.kpis||[])])for(const key of ['evidence','comparison_evidence'])if(item[key])for(const field of ['query','source_id','export_id'])delete item[key][field];return value;}
function bind(report:any,binding:string,status:any,admin:boolean){const value=JSON.parse(JSON.stringify(report));value.report_id=binding;value.report_scope=status.report_scope;value.cached=true;for(const section of value.sections)for(const kind of ['charts','kpis'])for(const item of section[kind]||[])for(const part of ['current','previous']){const e=item[part==='previous'?'comparison_evidence':'evidence'];if(!e||!item.id||item.refresh_error)continue;const token=['lazy',binding,section.view,kind,item.id,part].join(':');e.source_id=token;if(admin)e.export_id=token;else delete e.export_id;}return value;}
export async function loadInsightStatus(rpc:(action:string,payload?:any)=>Promise<any>,owner:Owner,admin=false){
 const key=ownerKey(owner);if(currentOwner!==key){currentOwner=key;ownerEpoch++;}const epoch=ownerEpoch;await writes;const cached=await read(key);
 const check=()=>{if(currentOwner!==key||epoch!==ownerEpoch)throw Error('Account or access changed while restoring Insights.');};check();
 let status=await rpc('ai_status',{display_cache:true,load_saved_insights:true,known_report_stamp:cached?.stamp,period_sensitive:cached?.period===true,known_sections:cached?.sections,current_binding:lastOwner===key?lastStatus?.saved_report?.report_id:undefined});
 check();
 if(status.report_not_modified){
  if(!cached||cached.report.version!==status.version)status=await rpc('ai_status',{display_cache:true,load_saved_insights:true});
  else status={...status,saved_report:cached.report,browser_report_cached:true};
 }
 check();
 if(status.report_patch&&cached&&status.saved_report){const current=new Map(cached.report.sections.map((s:any)=>[s.view,s]));for(const section of status.saved_report.sections)current.set(section.view,section);const report={...status.saved_report,sections:status.report_order.map((id:number)=>current.get(id)).filter(Boolean)};status={...status,saved_report:report};}
 if(status.saved_report&&status.report_binding&&!status.active_analysis)status={...status,saved_report:bind(status.saved_report,status.report_binding,status,admin)};
 if(status.saved_report&&status.report_stamp&&!status.active_analysis){const entry={owner:key,stamp:status.report_stamp,period:status.period_sensitive===true,sections:status.section_stamps||cached?.sections||{},report:displayOnly(status.saved_report)};if(!status.report_not_modified)status.browser_report_saved=await write(entry);else recent=entry;}
 lastStatus=status;lastOwner=key;lastAdmin=admin;
 if(typeof document!=='undefined')document.documentElement.dataset.insightDisplayCache=status.browser_report_cached?'restored':status.browser_report_saved?'saved':status.saved_report?'server':'empty';
 return status;
}
export function rememberInsightResponse(owner:Owner,action:string,event:any,response:any){
 const key=ownerKey(owner);if(!key||!response?.report_stamp)return;
 if(!['generate_insights','add_insight_chart','save_insight_item','delete_insight_chart'].includes(action)||response.pending===true)return;
 writes=writes.catch(()=>{}).then(async()=>{
  if(currentOwner&&currentOwner!==key)return;let cached=await read(key);if(currentOwner&&currentOwner!==key)return;const full=response.report||(response.sections?response:null);
  if(full?.cache_generation)cached={owner:key,stamp:response.report_stamp,period:response.period_sensitive===true,sections:response.section_stamps||{},report:displayOnly(full)};
  else if(cached){cached={...cached,report:JSON.parse(JSON.stringify(cached.report))};const section=cached.report.sections.find((s:any)=>s.view===(response.view??event.view));if(!section)return;
   if(action==='add_insight_chart'){const kind=event.item_kind==='kpi'?'kpis':'charts',item=response.kpi||response.chart;if(!item)return;section[kind]=[...(section[kind]||[]).filter((x:any)=>x.id!==item.id),displayOnly({sections:[{[kind]:[item]}]}).sections[0][kind][0]];}
   else{const kind=response.item_kind==='kpi'?'kpis':'charts',id=response.item_id;section[kind]=(section[kind]||[]).filter((item:any)=>!response.deleted||item.id!==id).map((item:any)=>item.id===id?{...item,saved:true,...(response.chart_type?{type:response.chart_type}:{})}:item);}
   cached.stamp=response.report_stamp;cached.period=response.period_sensitive===true;cached.sections=response.section_stamps||{...cached.sections};for(const view of response.invalidated_views||[])delete cached.sections[String(view)];
  }
  if(cached){await write(cached);if(lastOwner===key&&lastStatus){const binding=full?.report_id||event.report_id;lastStatus={...lastStatus,report_stamp:cached.stamp,period_sensitive:cached.period,saved_report:binding?.startsWith('lazy_')?bind(cached.report,binding,lastStatus,lastAdmin):full||{...cached.report,report_id:binding}};seedInsights(binding?.startsWith('lazy_')?lastStatus:null);}}
 }).catch(()=>{});
}

import {rpc,tableColumnSnapshot} from './bridge';
const ENTRY_MAX=16*1024*1024;
const DB='stock-planning-view-cache-v1',STORE='views',MAX=48*1024*1024;
type Entry={key:string;stamp:string;data:any};
const memory=new Map<string,Entry>(),pending=new Map<string,Promise<any>>();
let epoch=0;
window.addEventListener('stock-data-updated',()=>{epoch++;memory.clear()});
window.addEventListener('stock-manual-data-updated',()=>{epoch++;memory.clear()});
async function database():Promise<IDBDatabase|null>{if(typeof indexedDB==='undefined')return null;return new Promise(resolve=>{let done=false;const finish=(db:IDBDatabase|null)=>{if(done){db?.close();return}done=true;clearTimeout(timer);resolve(db)},timer=setTimeout(()=>finish(null),3000);try{const r=indexedDB.open(DB,1);r.onupgradeneeded=()=>{if(!r.result.objectStoreNames.contains(STORE))r.result.createObjectStore(STORE)};r.onsuccess=()=>finish(r.result);r.onerror=r.onblocked=()=>finish(null)}catch{finish(null)}})}
async function disk(key:string,value?:Entry):Promise<Entry|null>{const db=await database();if(!db)return null;return new Promise(resolve=>{let done=false;const finish=(v:Entry|null)=>{if(done)return;done=true;clearTimeout(timer);db.close();resolve(v)},timer=setTimeout(()=>finish(null),3000);try{const tx=db.transaction(STORE,value?'readwrite':'readonly'),store=tx.objectStore(STORE);if(value){const text=JSON.stringify(value);if(new Blob([text]).size>ENTRY_MAX)return finish(null);store.put(text,key);const keys=store.getAllKeys(),values=store.getAll();let ids:IDBValidKey[]|undefined,entries:any[]|undefined;const prune=()=>{if(!ids||!entries)return;let bytes=entries.reduce((n,v)=>n+(typeof v==='string'?new Blob([v]).size:0),0),count=ids.length;for(let i=0;i<ids.length&&(bytes>MAX||count>12);i++){if(ids[i]===key)continue;store.delete(ids[i]);bytes-=typeof entries[i]==='string'?new Blob([entries[i]]).size:0;count--}};keys.onsuccess=()=>{ids=keys.result;prune()};values.onsuccess=()=>{entries=values.result;prune()};tx.oncomplete=()=>finish(value)}else{const r=store.get(key);r.onsuccess=()=>{try{if(typeof r.result!=='string'||r.result.length>MAX)return finish(null);const v=JSON.parse(r.result);finish(v.key===key&&typeof v.stamp==='string'&&v.data&&typeof v.data==='object'?v:null)}catch{finish(null)}}}tx.onerror=tx.onabort=()=>finish(null)}catch{finish(null)}})}
// The authenticated startup snapshot already contains these rows. Prime both
// caches so the first explicit refresh can validate a stamp without re-fetching.
export function primeView(operation:string,data:any,stamp:string|undefined,input:Record<string,unknown>={}){
 if(typeof stamp!=='string'||!stamp||!data||typeof data!=='object'||typeof tableColumnSnapshot!=='function')return;
 const snapshot=tableColumnSnapshot();if(!snapshot.user||!snapshot.accessScope)return;
 const parameters=Object.fromEntries(Object.entries(input).filter(([k])=>k!=='force').sort(([a],[b])=>a.localeCompare(b)));
 const key=JSON.stringify([JSON.stringify(snapshot),operation,parameters]);if(memory.get(key)?.stamp===stamp)return;
 const entry={key,stamp,data};memory.set(key,entry);while(memory.size>12||Array.from(memory.values()).reduce((n,v)=>n+JSON.stringify(v).length,0)>MAX)memory.delete(memory.keys().next().value!);
 void disk(key,entry).catch(()=>{});
}
export function cachedView(operation:string,input:Record<string,unknown>={}):Promise<any>{
 if(typeof tableColumnSnapshot!=='function')return rpc(operation,input);
 const snapshot=tableColumnSnapshot();if(!snapshot.user||!snapshot.accessScope)return rpc(operation,input);const owner=JSON.stringify(snapshot),ticket=epoch;
 const parameters=Object.fromEntries(Object.entries(input).filter(([k])=>k!=='force').sort(([a],[b])=>a.localeCompare(b)));
 const key=JSON.stringify([owner,operation,parameters]),requestKey=JSON.stringify([key,ticket]);const existing=pending.get(requestKey);if(existing)return existing;
 const check=()=>{if(ticket!==epoch||owner!==JSON.stringify(tableColumnSnapshot()))throw Error('Data or access changed while restoring the view. Retry.')};
 const work=(async()=>{const saved=memory.get(key)||await disk(key);check();const response=await rpc(operation,{...input,display_cache:true,known_stamp:saved?.stamp});check();
  if(response.not_modified){if(!saved)throw Error('Saved view unavailable. Refresh and retry.');return saved.data}
  if(typeof response.stamp!=='string')return response; // Older server during deployment.
  if(!response.data||typeof response.data!=='object')throw Error('The saved view response was incomplete. Refresh and retry.');const value={key,stamp:response.stamp,data:response.data};memory.set(key,value);while(memory.size>12||Array.from(memory.values()).reduce((n,v)=>n+JSON.stringify(v).length,0)>MAX)memory.delete(memory.keys().next().value!);await disk(key,value);check();return value.data;
 })().finally(()=>{if(pending.get(requestKey)===work)pending.delete(requestKey)});pending.set(requestKey,work);return work;
}

import {rpc,tableColumnSnapshot} from './bridge';
type Entry={owner:string;stamp:string;result:any};
const DB='stock-planning-issue-slip-v1',STORE='issue',MAX=32*1024*1024;
let memory:Entry|null=null,epoch=0;
const pending=new Map<string,Promise<any>>();
window.addEventListener('stock-data-updated',()=>{epoch++;memory=null});
window.addEventListener('stock-manual-data-updated',()=>{epoch++;memory=null});
function owner(){const s=tableColumnSnapshot();return s.user&&s.accessScope?JSON.stringify([s.user,s.accessScope]):''}
async function database():Promise<IDBDatabase|null>{if(typeof indexedDB==='undefined')return null;return new Promise(resolve=>{let done=false;const finish=(db:IDBDatabase|null)=>{if(done){db?.close();return}done=true;clearTimeout(timer);resolve(db)},timer=setTimeout(()=>finish(null),3000);try{const r=indexedDB.open(DB,1);r.onupgradeneeded=()=>{if(!r.result.objectStoreNames.contains(STORE))r.result.createObjectStore(STORE)};r.onsuccess=()=>finish(r.result);r.onerror=r.onblocked=()=>finish(null)}catch{finish(null)}})}
async function disk(entry?:Entry):Promise<Entry|null>{const db=await database();if(!db)return null;return new Promise(resolve=>{let done=false;const finish=(value:Entry|null)=>{if(done)return;done=true;clearTimeout(timer);db.close();resolve(value)},timer=setTimeout(()=>finish(null),3000);try{const tx=db.transaction(STORE,entry?'readwrite':'readonly'),store=tx.objectStore(STORE);if(entry){const text=JSON.stringify(entry);if(text.length>MAX||new Blob([text]).size>MAX)return finish(null);store.put(text,'display');tx.oncomplete=()=>finish(entry)}else{const r=store.get('display');r.onsuccess=()=>{try{if(typeof r.result!=='string'||r.result.length>MAX||new Blob([r.result]).size>MAX)return finish(null);const v=JSON.parse(r.result);finish(typeof v.owner==='string'&&typeof v.stamp==='string'&&(v.result===null||Array.isArray(v.result?.issueHeaders)&&Array.isArray(v.result?.issueRows))?v:null)}catch{finish(null)}}}tx.onerror=tx.onabort=()=>finish(null)}catch{finish(null)}})}
export function preparedIssueSlip(){return memory?.owner===owner()?{result:memory.result,cached:true}:undefined}
export function loadIssueSlip(force=false):Promise<{result:any;cached:boolean}>{
 if(!force){const ready=preparedIssueSlip();if(ready)return Promise.resolve(ready)}
 const who=owner(),ticket=epoch,key=JSON.stringify([who,ticket,force]);if(pending.has(key))return pending.get(key)!;
 const check=()=>{if(who!==owner()||ticket!==epoch)throw Error('Data or access changed while restoring issue slips. Retry.')};
 const work=(async()=>{const saved=memory?.owner===who?memory:who?await disk():null;check();const cached=saved?.owner===who?saved:null;
  let reply=await rpc('issue_slip_dataset',{known_stamp:cached?.stamp});check();
  if(reply.not_modified&&!cached){reply=await rpc('issue_slip_dataset');check()}
  if(reply.not_modified&&cached){memory=cached;return {result:cached.result,cached:true}}
  if(typeof reply.stamp!=='string'||!(reply.result===null||Array.isArray(reply.result?.issueHeaders)&&Array.isArray(reply.result?.issueRows)))throw Error('Issue-slip data was incomplete. Retry.');
  const entry={owner:who,stamp:reply.stamp,result:reply.result};check();if(who){memory=entry;await disk(entry);check()}return {result:entry.result,cached:false};
 })().finally(()=>{if(pending.get(key)===work)pending.delete(key)});pending.set(key,work);return work;
}

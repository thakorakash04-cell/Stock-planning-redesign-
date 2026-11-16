// User activity is local; it never renews authentication or authorizes SQL.
let lastUserActivity=Date.now(),lastActivityNotice=0;
export function browserActive(){return typeof document!=='undefined'&&!document.hidden&&Date.now()-lastUserActivity<300000;}
function userActivity(){const now=Date.now(),resuming=now-lastUserActivity>=300000;lastUserActivity=now;
 if(resuming||now-lastActivityNotice>=30000){lastActivityNotice=now;window.parent.postMessage({type:'workspace:user-activity'},window.location?.origin||'*');}}
for(const type of ['pointerdown','pointermove','keydown','scroll','touchstart','wheel'])window.addEventListener(type,userActivity,{passive:true,capture:true});
if(typeof document!=='undefined')document.addEventListener('visibilitychange',()=>{if(!document.hidden){lastActivityNotice=0;userActivity();}});
type Waiter={resolve:(x:any)=>void,reject:(e:any)=>void,timer:ReturnType<typeof setTimeout>};
let bootPage="users",bootData:any=null;
export function initialData(){return bootData}
export function initialPage(){return bootPage}
let sequence=0,activeId:string|null=null,connected=false,lastHeight=0;
const pending=new Map<string,Waiter>(),queue:any[]=[];
const post=(x:any)=>parent.postMessage({isStreamlitMessage:true,...x},'*');
let readyResolve:()=>void,readyReject:(e:any)=>void;
export const ready=new Promise<void>((resolve,reject)=>{readyResolve=resolve;readyReject=reject});
function fitFrame(){const height=Math.max(320,window.innerHeight||760);if(height!==lastHeight){lastHeight=height;post({type:'streamlit:setFrameHeight',height})}}
const announce=()=>{post({type:'streamlit:componentReady',apiVersion:1});fitFrame()};
const readyTimer=setTimeout(()=>{clearInterval(handshake);readyReject(Error('The workspace connection did not start. Reload this page to reconnect.'))},30000);
const handshake=setInterval(()=>{if(!connected)announce()},1000);
function sendNext(){if(!connected||activeId||!queue.length)return;const item=queue.shift();activeId=item.id;post({type:'streamlit:setComponentValue',value:item,dataType:'json'});}
export async function call(operation:string,input:any={}){await ready;
 if(operation==='consoleClose'){
  // Leaving must never wait for a workbook, email or AI request.
  queue.length=0;activeId='closing';
  post({type:'streamlit:setComponentValue',value:{id:Date.now()+'-'+(++sequence),operation},dataType:'json'});
  return {ok:true};
 }
return new Promise<any>((resolve,reject)=>{const id=Date.now()+'-'+(++sequence);const timer=setTimeout(()=>{pending.delete(id);const index=queue.findIndex(x=>x.id===id);if(index>=0)queue.splice(index,1);if(activeId===id)activeId=null;reject(Error('The request timed out. Reload the workspace to check whether it completed.'));sendNext()},120000);pending.set(id,{resolve,reject,timer});queue.push({id,operation,...input});sendNext()});}
window.addEventListener('message',e=>{if(e.source!==parent||e.data?.type!=='streamlit:render')return;if(!connected){bootPage=e.data.args?.initialPage||'users';bootData=e.data.args?.bootstrap||null;connected=true;clearTimeout(readyTimer);clearInterval(handshake);readyResolve();}const response=e.data.args?.response;if(response&&pending.has(response.id)){const item=pending.get(response.id)!;clearTimeout(item.timer);pending.delete(response.id);if(activeId===response.id)activeId=null;response.error?item.reject(Error(response.error)):item.resolve(response.body);sendNext()}fitFrame()});
announce();
window.addEventListener('resize',fitFrame);


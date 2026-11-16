// Memory snapshots are seeded by the authenticated bridge or an exact, live-validated browser cache hit.
let boot:any=null,scope='',insights:any=null;
let insightEpoch=0,insightPending:Promise<any>|null=null,insightConsumed=false;
function clearInsights(){insights=null;insightPending=null;insightConsumed=false;insightEpoch++;}
export const insightsBootstrap=()=>insights;
export function seedInsights(value:any){insights=value;}
export function prepareInsights(loader:()=>Promise<any>,consume=false):Promise<any>{
 if(insights&&(!consume||!insightConsumed)){if(consume)insightConsumed=true;return Promise.resolve(insights);}
 if(insightPending){if(consume)insightConsumed=true;return insightPending;}
 const epoch=insightEpoch;insightConsumed=consume;
 const request=loader().then(value=>{if(epoch!==insightEpoch)throw Error('Data or access changed while restoring saved Insights.');insights=value;return value}).finally(()=>{if(insightPending===request)insightPending=null});
 insightPending=request;return request;
}
const sales=new Map<string,any>();
let versions:Record<string,string>={};
export function seedPreload(value:any,identity:string){
 if(scope!==identity){scope=identity;boot=null;clearInsights();sales.clear();versions={};}
 if(!value?.id||boot?.id===value.id)return;
 if(boot)sourceVersions(value.versions||{});
 boot=value;versions=value.versions||{};
 for(const [kind,data] of Object.entries(value.sales||{}))sales.set(kind,data);
 window.dispatchEvent(new window.Event('stock-preload-ready'));
}
export function pnlBootstrap(){return boot?.pnl||null;}
export function salesSnapshot(kind:string){return sales.get(kind);}
export function rememberSales(kind:string,value:any){sales.set(kind,value);}
export function clearSales(kind:string){sales.delete(kind);}
export function sourceVersions(next:Record<string,string>){
 const changed=Object.keys(next).filter(key=>versions[key]!==undefined&&versions[key]!==next[key]);
 versions=next;
 for(const key of changed){if(key==='pnl'){if(boot)boot.pnl=null;}else sales.delete(key);}
 if(changed.length){clearInsights();}
 if(changed.length)window.dispatchEvent(new CustomEvent('stock-source-versions',{detail:changed}));
}

export function financePreloadReady(){return Boolean(boot?.id);}

window.addEventListener('stock-data-updated',()=>{clearInsights()});

window.addEventListener('stock-manual-data-updated',()=>{clearInsights()});

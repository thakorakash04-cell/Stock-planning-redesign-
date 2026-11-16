import {stockOverviewDisplay} from './stock-overview-display';
import {forecastHeaders,forecastSummary} from './forecast';
import type {Cell} from './grid-utils';
export type StartupTable={scope:string;headers:string[];rows:Cell[][]};
export function startupTables(data:any,finance:any,preferences:Record<string,any>={}):StartupTable[]{
 const out:StartupTable[]=[];
 const allowed=(tab:number)=>!data?.accessibleTabs||data.accessibleTabs.includes(tab);
 const add=(scope:string,table:any)=>{if(table?.headers&&Array.isArray(table.rows)&&preferences['columns:'+scope]?.definitions?.length)out.push({scope,headers:table.headers,rows:table.rows})};
 for(const [i,sheet] of (data?.sheets||[]).entries()){
  if(data.accessibleTabs&&!data.accessibleTabs.includes(i))continue;
  add('main:'+sheet.name,i===0?stockOverviewDisplay(sheet,data.pendingSales):sheet);
  if(i===4)add('main:'+sheet.name+':totals',{headers:forecastHeaders,rows:forecastSummary(sheet.rows)});
 }
 const production=data?.production;
 if(production&&allowed(3)){add('production:ongoing',{headers:production.ongoingHeaders,rows:production.ongoing?.map((r:any)=>r.row)||[]});add('production:qc',production.qc);add('production:upcoming',{headers:production.upcomingHeaders,rows:production.upcoming?.map((r:any)=>r.row)||[]})}
 if(allowed(9))add('lead-time:details',data?.leadTime);
 if(allowed(6))add('order-requirements-master',data?.orderRequirements?.summary);
 for(const kind of ['primary','secondary'])if(allowed(11))add('sales:'+kind,finance?.sales?.[kind]);
 const pnl=finance?.pnl;
 if(pnl?.report&&allowed(10)){add('pnl:monthly:'+pnl.params.fy,pnl.report.monthly);add('pnl:product-allocations',pnl.report.productAllocation)}
 return out;
}

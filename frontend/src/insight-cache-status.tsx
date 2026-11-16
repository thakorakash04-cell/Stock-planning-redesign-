import InsightLoadTime from './insight-load-time';
import {tableColumnSnapshot} from './bridge';
export type CacheLoad={phase:'loading'|'rendering'|'ready'|'empty'|'error'|'generating';percent:number;kind:'cached'|'checkpoint'|'saved'|'generated';label:string;startedAt:number;timingMode:'preloaded'|'remote'|'refresh'|'analysis'|'resume'};
type Counts={sections:{charts:unknown[];kpis?:unknown[]}[]};
export default function InsightCacheStatus({state,report,retry}:{state:CacheLoad;report:Counts|null;retry:()=>void}){
 const identity=typeof tableColumnSnapshot==='function'?JSON.stringify(tableColumnSnapshot()):'current-session';
 const loading=state.phase==='loading'||state.phase==='rendering',complete=state.phase==='ready';
 const views=report?.sections.length||0,kpis=report?.sections.reduce((n,s)=>n+(s.kpis?.length||0),0)||0,graphs=report?.sections.reduce((n,s)=>n+s.charts.length,0)||0;
 return <section className={'insight-cache-status '+state.phase} aria-label="Saved report cache status" aria-busy={loading}>
  <div className="insight-cache-heading" role="status" aria-live="polite"><strong>{state.label}</strong>{(loading||complete)&&<span>{state.percent}%</span>}</div>
  {(loading||complete)&&<progress aria-label="Saved report loading" max={100} value={state.percent}/>}
  {(loading||complete||state.phase==='error')&&<InsightLoadTime startedAt={state.startedAt} active={loading} complete={complete} historyKey={identity+':'+state.timingMode}/>}
  {loading&&<p>Checking the saved cache, restoring the dashboard, then displaying it. Progress counts completed loading stages.</p>}
  {complete&&<p>{views} view{views===1?'':'s'} · {kpis} KPI card{kpis===1?'':'s'} · {graphs} graph{graphs===1?'':'s'}{state.kind==='checkpoint'?' · Saved sections restored; resume analysis to finish.':state.kind==='generated'?' · Cache storage has not been confirmed by the server.':''}</p>}
  {state.phase==='empty'&&<p>Run analysis once to save a report for the current data. No AI request has been started.</p>}
  {state.phase==='error'&&<><p>The restore did not finish. Any previous dashboard remains visible; it has not been marked as fully loaded.</p><button type="button" className="secondary" onClick={retry}>Retry loading saved report</button></>}
  {state.phase==='generating'&&<p>New analysis has separate progress below; this is not a cache-loading operation.</p>}
 </section>;
}

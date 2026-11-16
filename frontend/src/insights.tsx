import {loadInsightStatus} from './insight-display-cache';
import FilterCondition from './filter-condition';
import {conditionFilter,restoreConditions,type InsightFilter} from './insight-filter-conditions';
import {dateHeader} from './date-utils';
import type {ColumnFilter} from './grid-utils';
import CheckboxFilter,{type Choice,type ChoiceSelection} from './checkbox-filter';
import AnswerContent from './answer-content';
import RecordGrid from './record-grid';
import {memo,useEffect,useRef,useState} from 'react';
import {useViewPreference} from './view-preference';
import {rpc,isAdmin,tableColumnSnapshot} from './bridge';
import {prepareInsights,insightsBootstrap} from './preload-cache';
import {answerText} from './answer-text';
import {ChartNoAxesCombined,Sparkles,Download,Maximize2,X,Table2,Lightbulb,ClipboardCheck,Info,ChevronLeft,ChevronRight,Plus,Send,Trash2} from 'lucide-react';
import Graphic,{isDatedComparisonLabel} from './insight-graphic';
import {createPortal} from 'react-dom';
import GraphFrame from './graph-frame';
import InsightCacheStatus,{type CacheLoad} from './insight-cache-status';
import InsightLoadTime from './insight-load-time';
type RecordRow=Record<string,unknown>;
type Evidence={source_id?:string;export_id?:string;table:string;matched_records:number;result_rows:number;shown_rows:number;records:RecordRow[]};
type Chart={pending?:boolean;saved?:boolean;refresh_error?:string;id?:string;title:string;mark?:number;custom?:boolean;data_quality?:string;finding?:string;action?:string;attention_id?:string;type?:string;x?:string;label:string;value:string;evidence:Evidence};
type Kpi={pending?:boolean;comparison_result?:{current_month:string;previous_month:string;previous_value:number|null;growth_percent:number|null;note:string};comparison_evidence?:Evidence;saved?:boolean;refresh_error?:string;id?:string;custom?:boolean;title:string;value:number|null;field:string;basis:string;evidence:Evidence};
type Facet={kind?:'number'|'date'|'text';column:string;search_only?:boolean;values:Choice[]};
type Review={findings:string[];actions:string[];data_quality:string[]};
type Attention={id:string;view:number;priority:string;title:string;detail:string;action:string;count:number};
type Report={cache_generation?:string;cached?:boolean;report_id?:string;report_scope?:string;knowledge_revision?:string;planning_revision?:string;referenceDate?:string;attention?:Attention[];scope_notes?:string[];version:string;answer:string;warnings?:string[];overview?:string;generated_at:string;sections:{view:number;title:string;records:number;limitation:string;kpis?:Kpi[];facets?:Facet[];filters?:{column:string;op:string;value:unknown}[];review?:Review;review_mode?:string;charts:Chart[]}[]};
type Source={records:RecordRow[];total:number;page:number;page_size:number;table:string};
const number=(v:unknown)=>typeof v==='number'?v.toLocaleString('en-IN',{maximumFractionDigits:2}):String(v??'—');
const clean=(v:string)=>answerText(v).replace(/^\s{0,3}#{1,6}\s*/gm,'').replace(/\*\*/g,'').replace(/`/g,'');
function RichText({text}:{text:string}){return <div className="review-prose">{answerText(text).split(/\n+/).filter(Boolean).map((line,i)=>{const heading=/^\s*#{1,6}\s+/.test(line);const bullet=/^\s*[-*]\s+/.test(line);const text=clean(line).replace(/^\s*[-*]\s+/,'');return heading?<h3 key={i}>{text}</h3>:<p key={i} className={bullet?'review-bullet':''}>{text}</p>})}</div>}
function ResultTable({records,scope}:{records:RecordRow[];scope:string}){return <RecordGrid records={records} scope={scope}/>;}
// Consent and edit-control changes must not redraw hundreds of unchanged chart marks.
const CachedGraphic=memo(function CachedGraphic({chart,fullScreen,onSelect}:{chart:Chart;fullScreen:boolean;onSelect:(value:Chart)=>void}){return <Graphic chart={chart} fullScreen={fullScreen} onMark={mark=>onSelect({...chart,mark})}/>});
export default function Insights(){
 const statusRef=useRef<any>(null);
 const [sharing,setSharing]=useViewPreference('ai-insights-sharing',{alwaysAllow:false});
 const [restoreAttempt,setRestoreAttempt]=useState(0),[cacheLoad,setCacheLoad]=useState<CacheLoad>({phase:'loading',percent:0,kind:'cached',label:'Checking saved report cache…',startedAt:Date.now(),timingMode:insightsBootstrap()?'preloaded':'remote'});
 const timingIdentity=typeof tableColumnSnapshot==='function'?JSON.stringify(tableColumnSnapshot()):'current-session';
 const cacheLoading=cacheLoad.phase==='loading'||cacheLoad.phase==='rendering';
 const job=useRef<{request_id:string;job_id?:string;step?:number}|null>(null),generation=useRef(0);
 const [editNotice,setEditNotice]=useState<{view:number;text:string;failed?:boolean}|null>(null);
 const [fullGraph,setFullGraph]=useState<string|null>(null);
 const [progress,setProgress]=useState<{label:string;percent:number}|null>(null);
 const [filtering,setFiltering]=useState<number|null>(null);
 const [adding,setAdding]=useState<number|null>(null);
 const [status,setStatus]=useState<any>(null),[report,setReport]=useState<Report|null>(null),[consent,setConsent]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[view,setView]=useState(-1),[expanded,setExpanded]=useState(false),[selected,setSelected]=useState<Chart|null>(null),[source,setSource]=useState<Source|null>(null),[sourceBusy,setSourceBusy]=useState(false),[sourceError,setSourceError]=useState('');
 const allowedToSend=consent||sharing.alwaysAllow===true;
 const workbookReady=status?.workbook_ready??Boolean(status?.tables);
 const sharingAllowed=useRef(allowedToSend);sharingAllowed.current=allowedToSend;
 useEffect(()=>{
  let live=true,sequence=0;
  setCacheLoad({phase:'loading',percent:0,kind:'cached',label:'Checking saved report cache…',startedAt:Date.now(),timingMode:insightsBootstrap()?'preloaded':'remote'});
  const signature=(s:any)=>JSON.stringify([s?.version,s?.knowledge_revision,s?.planning_revision,s?.report_scope,s?.calendar_month,s?.report_stamp]);
  async function load(initial=false){
   const ticket=++sequence,startedAt=Date.now(),timingMode=initial?(insightsBootstrap()?'preloaded':'remote'):'refresh';
   if(!initial)setCacheLoad(current=>({...current,phase:'loading',percent:0,label:'Checking saved report cache…',startedAt,timingMode}));
   try{
    let s=initial?await prepareInsights(()=>loadInsightStatus(rpc,typeof tableColumnSnapshot==='function'?tableColumnSnapshot():{},isAdmin()),true):await loadInsightStatus(rpc,typeof tableColumnSnapshot==='function'?tableColumnSnapshot():{},isAdmin());
    if(!live||ticket!==sequence||job.current)return;
    if(statusRef.current&&signature(statusRef.current)===signature(s)){setStatus(s);const exists=Boolean(s.saved_report||s.active_analysis?.report);setCacheLoad(current=>({...current,phase:exists?'ready':'empty',percent:exists?100:0,label:exists?'Loaded from saved report cache':'No saved report for the current data'}));return;}
    setCacheLoad({phase:'loading',percent:initial?33:0,kind:'cached',label:initial?'Saved cache response received…':'Loading the current saved report…',startedAt,timingMode});
    generation.current++;job.current=null;setFullGraph(null);setBusy(false);setProgress(null);setSelected(null);if(!statusRef.current||statusRef.current.version!==s.version||statusRef.current.report_scope!==s.report_scope)setReport(null);
    statusRef.current=s;setStatus(s);setError('');
    const active=s.active_analysis;
    const restored=active?.report??s.saved_report??null;
    setReport(restored);
    if(initial&&restored)setView(restored.sections.find((section:any)=>section.records>0)?.view??restored.sections[0]?.view??-1);
    setCacheLoad(restored?{phase:'rendering',percent:67,kind:active?.report?'checkpoint':'cached',label:active?.report?'Displaying saved analysis sections…':'Displaying cached KPIs and graphs…',startedAt,timingMode}:{phase:'empty',percent:0,kind:'cached',label:'No saved report for the current data',startedAt,timingMode});
    if(active?.pending){job.current={request_id:active.request_id,job_id:active.job_id,step:active.step};setProgress(active.progress);}
   }catch(e){if(live&&ticket===sequence){setError(e instanceof Error?e.message:String(e));setCacheLoad({phase:'error',percent:0,kind:'cached',label:'Saved report loading failed',startedAt,timingMode});}}
  }
  const refresh=()=>{
   if(job.current){
    const snapshot=typeof tableColumnSnapshot==='function'?tableColumnSnapshot():null;
    if(!snapshot?.version||snapshot.version===statusRef.current?.version)return;
    // A real workbook replacement cancels this run; routine cache/host replies do not.
    generation.current++;job.current=null;setBusy(false);setProgress(null);setReport(null);
   }
   void load(false);
  };
  void load(true);window.addEventListener('stock-data-updated',refresh);window.addEventListener('stock-source-versions',refresh);window.addEventListener('stock-manual-data-updated',refresh);
  return()=>{live=false;sequence++;generation.current++;window.removeEventListener('stock-data-updated',refresh);window.removeEventListener('stock-source-versions',refresh);window.removeEventListener('stock-manual-data-updated',refresh)};
 },[restoreAttempt]);
 useEffect(()=>{
  if(cacheLoad.phase!=='rendering'||!report)return;
  let live=true,first=0,second=0;
  const finish=()=>{if(live)setCacheLoad(current=>current.phase==='rendering'?{...current,phase:'ready',percent:100,label:current.kind==='checkpoint'?'Saved analysis progress loaded':current.kind==='saved'?'Analysis saved to cache':current.kind==='generated'?'Analysis ready':'Loaded from saved report cache'}:current);};
  // Two animation frames allow the restored dashboard to paint before 100%.
  if(typeof window.requestAnimationFrame==='function')first=window.requestAnimationFrame(()=>{second=window.requestAnimationFrame(finish);});
  else queueMicrotask(finish);
  return()=>{live=false;if(typeof window.cancelAnimationFrame==='function'){window.cancelAnimationFrame(first);window.cancelAnimationFrame(second);}};
 },[cacheLoad.phase,report?.report_id]);
 useEffect(()=>{const close=(e:KeyboardEvent)=>{if(e.key==='Escape')setSelected(null)};window.addEventListener('keydown',close);return()=>window.removeEventListener('keydown',close)},[]);
 useEffect(()=>{let live=true;setSource(null);setSourceError('');if(!selected?.evidence.source_id)return;setSourceBusy(true);rpc('insight_records',{source_id:selected.evidence.source_id,version:report?.version,mark:selected.mark,page:0}).then(r=>live&&setSource(r)).catch(e=>live&&setSourceError(e.message)).finally(()=>live&&setSourceBusy(false));return()=>{live=false}},[selected,report?.version]);
 useEffect(()=>{if(view>=0)document.getElementById('insight-view-'+view)?.scrollIntoView?.({block:'start',behavior:'smooth'})},[view]);
 async function page(n:number){if(!selected)return;setSourceBusy(true);setSourceError('');try{const r=await rpc('insight_records',{source_id:selected.evidence.source_id,version:report?.version,mark:selected.mark,page:n});setSource(r)}catch(e){setSourceError(e instanceof Error?e.message:String(e))}finally{setSourceBusy(false)}}
 async function generate(){
  if(busy||cacheLoading||!allowedToSend||!status?.configured||!workbookReady)return;
  const run=++generation.current,resuming=Boolean(job.current);
  if(!job.current)job.current={request_id:crypto.randomUUID()};
  setCacheLoad({phase:'generating',percent:0,kind:'generated',label:resuming?'Resuming analysis':'Generating a new analysis',startedAt:Date.now(),timingMode:resuming?'resume':'analysis'});
  setBusy(true);setError('');setProgress({label:'Preparing business sources',percent:0});
  try{
   while(job.current){
    const payload={version:status.version,consent:allowedToSend,progressive:true,...job.current};
    let response:any;
    for(let attempt=0;;attempt++){
     if(run!==generation.current)return;
     if(!sharingAllowed.current)throw Error('Gemini sharing permission was turned off.');
     try{response=await rpc('generate_insights',payload);break}
     catch(error){
      const message=error instanceof Error?error.message:String(error);
      if(attempt>=2||!/request timed out|failed to fetch|network ?error|connection (?:was )?(?:interrupted|reset|closed)|websocket|disconnected/i.test(message))throw error;
      if(run!==generation.current)return;
      setProgress(current=>({...current,label:'Reconnecting to the same analysis step…',percent:current?.percent??0}));
      await new Promise(resolve=>setTimeout(resolve,attempt===0?1000:2500));
     }
    }
    if(run!==generation.current)return;
    // Accept a complete response from an older server during a rolling update.
    if(response.pending===undefined){setReport(response);setView(response.sections.find((s:any)=>s.records>0)?.view??-1);job.current=null;setCacheLoad(current=>({...current,phase:'rendering',percent:67,kind:response.cache_generation?'saved':'generated',label:'Displaying the completed analysis…'}));break}
    if(response.progress)setProgress(response.progress);
    job.current={request_id:job.current.request_id,job_id:response.job_id,step:response.step};
    if(response.report){setReport(response.report);setView(current=>current===-1?(response.report.sections.find((s:any)=>s.records>0)?.view??-1):current)}
    if(!response.pending){job.current=null;setCacheLoad(current=>({...current,phase:'rendering',percent:67,kind:response.report?.cache_generation?'saved':'generated',label:'Displaying the completed analysis…'}));break}
   }
  }catch(e){if(run===generation.current){const message=e instanceof Error?e.message:String(e);if(/changed|expired|start a new|start analysis again/i.test(message)){job.current=null;setError(message+' Select Run analysis to use the current data.')}else setError('Analysis paused. '+message+' Select Resume analysis to continue the same job.')}}
  finally{if(run===generation.current)setBusy(false)}
 }

 async function addGraph(section:number,question:string,kind:'chart'|'kpi'='chart'):Promise<string>{
  if(!report?.report_id||adding!==null||busy||cacheLoading)return 'Generate the report first, then add a graph.';
  const original=report.report_id;setAdding(section);
  try{const response=await rpc('add_insight_chart',{report_id:original,version:report.version,view:section,question,consent:allowedToSend,...(kind==='kpi'?{item_kind:'kpi'}:{})});
   if(response.clarification)return response.clarification;
   if(response.report){setReport(response.report);return '';}
   if(response.report_id!==original||response.view!==section||!response.chart)throw Error('The graph response did not match this report. Please retry.');
   setReport(current=>{if(!current||current.report_id!==original)return current;const next={...current,sections:current.sections.map(s=>s.view===section?{...s,charts:[...s.charts,response.chart]}:s)};return next});
   return '';
  }finally{setAdding(null)}
 }
 function applyEdit(response:any,expected:string){
  if(response.report){setReport(current=>current?.report_id===expected?response.report:current);return;}
  if(response.report_id!==expected)throw Error('The dashboard changed before the edit completed. Retry with the current report.');
  setReport(current=>current?.report_id!==expected?current:{...current,sections:current.sections.map(section=>section.view!==response.view?section:response.item_kind==='kpi'?{...section,kpis:(section.kpis||[]).filter(k=>!response.deleted||k.id!==response.item_id).map(k=>k.id===response.item_id?{...k,saved:true}:k)}:{...section,charts:section.charts.filter(c=>!response.deleted||c.id!==response.item_id).map(c=>c.id===response.item_id?{...c,saved:true,type:response.chart_type||c.type}:c)})});
 }
 async function saveItem(section:number,item:Chart|Kpi,kind:'chart'|'kpi'){await editReportItem(section,item,kind,true)}
 async function editReportItem(section:number,item:Chart|Kpi,kind:'kpi'|'chart',saving:boolean){
  if(!report?.report_id||!item.id||cacheLoading||busy||filtering!==null||adding!==null)return;
  const collection=kind==='kpi'?'kpis':'charts',noun=kind==='kpi'?'KPI':'Graph';
  const expected=report.report_id,version=report.version,originalIndex=report.sections.find(s=>s.view===section)?.[collection]?.findIndex(k=>k.id===item.id)??0;
  const action=saving?'save_insight_item':'delete_insight_chart';
  setFiltering(section);setError('');setSelected(null);if(!saving&&kind==='chart')setFullGraph(null);
  setEditNotice({view:section,text:saving?'Saving '+noun+' in the background…':noun+' removed from this screen. Saving deletion in the background…'});
  setReport(current=>!current||current.report_id!==expected?current:{...current,sections:current.sections.map(s=>s.view!==section?s:{...s,[collection]:saving?(s[collection]||[]).map(k=>k.id===item.id?{...k,saved:true,pending:true}:k):(s[collection]||[]).filter(k=>k.id!==item.id)})});
  try{
   let response:any;
   for(let attempt=0;;attempt++){
    try{response=await rpc(action,{compact:true,report_id:expected,version,cache_generation:report.cache_generation,view:section,item_kind:kind,...(kind==='kpi'?{kpi_id:item.id}:{chart_id:item.id,...(saving?{chart_type:(item as Chart).type||'bar'}:{})})});break}
    catch(e){const message=e instanceof Error?e.message:String(e);if(attempt>=1||!/request timed out|failed to fetch|network ?error|connection (?:was )?(?:interrupted|reset|closed)|websocket|disconnected/i.test(message))throw e;setEditNotice({view:section,text:'Connection interrupted. Confirming the same '+noun+' change…'});}
   }
   const returned=response.report?.sections?.find((s:any)=>s.view===section)?.[collection]?.find((k:any)=>k.id===item.id);
   if(response.report?(saving?!returned?.saved:Boolean(returned)):(response.report_id!==expected||response.view!==section||response.item_id!==item.id||response.item_kind!==kind||(saving?!response.saved:!response.deleted)))throw Error('The '+noun+' acknowledgement did not match this change.');
   applyEdit(response,expected);
   setReport(current=>!current||current.report_id!==expected?current:{...current,sections:current.sections.map(s=>s.view!==section?s:{...s,[collection]:(s[collection]||[]).map(k=>k.id===item.id?{...k,pending:false}:k)})});
   setEditNotice({view:section,text:saving?noun+' saved for future analysis runs.':noun+' deleted and removed from future runs.'});
  }catch(e){
   const message=e instanceof Error?e.message:String(e);
   setReport(current=>{if(!current||current.report_id!==expected||current.version!==version)return current;return {...current,sections:current.sections.map(s=>{if(s.view!==section)return s;const cards=[...(s[collection]||[])];const at=cards.findIndex(k=>k.id===item.id);if(at>=0)cards[at]=item;else cards.splice(Math.max(0,originalIndex),0,item);return {...s,[collection]:cards}})}});
   const text='Could not confirm the '+noun+' change. The item is restored on screen; retry the same action. '+message;setError(text);setEditNotice({view:section,text,failed:true});
  }finally{setFiltering(null)}
 }
 async function deleteKpi(section:number,kpi:Kpi){await editReportItem(section,kpi,'kpi',false)}
 async function deleteGraph(section:number,chart:Chart){await editReportItem(section,chart,'chart',false)}
 async function filterSection(section:number,filters:{column:string;op:string;value:unknown}[]){
  if(!report?.report_id||cacheLoading)return;
  setFiltering(section);setError('');
  try{const response=await rpc('filter_insights',{report_id:report.report_id,version:report.version,view:section,filters});setReport(current=>{if(!current||current.report_id!==response.report_id)return current;const next={...current,sections:current.sections.map(s=>s.view===section?response.section:s)};return next})}catch(e){setError(e instanceof Error?e.message:String(e));throw e}finally{setFiltering(null)}
 }
 async function download(e:Evidence){setError('');try{const f=await rpc('ai_export',{export_id:e.export_id,version:report?.version,mark:selected?.mark});const u=URL.createObjectURL(new Blob([Uint8Array.from(atob(f.content),c=>c.charCodeAt(0))],{type:f.mime}));const a=document.createElement('a');a.href=u;a.download=f.filename;a.click();URL.revokeObjectURL(u)}catch(e){setError(e instanceof Error?e.message:String(e))}}
 return <div className={'insights-page'+(expanded?' insights-expanded':'')}><div className="titleline"><div><p className="eyebrow">BUSINESS INTELLIGENCE</p><h1><ChartNoAxesCombined size={28}/> Insights & Graphs</h1><p className="subtitle">AI-selected KPIs, connected business findings and interactive graphs. Select a value to explore its evidence.</p></div><button className="secondary" onClick={()=>setExpanded(!expanded)}>{expanded?<X size={16}/>:<Maximize2 size={16}/>} {expanded?'Restore':'Full screen'}</button></div>
 <div className="source"><strong>{status?.filename||'Loading workbook…'}</strong><span>{report?'Generated '+new Date(report.generated_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':'Saved workbook snapshot'}</span></div>
 {editNotice&&<p className={editNotice.failed?'error':'smallnote'} role={editNotice.failed?'alert':'status'}>{editNotice.text}</p>}
 <InsightCacheStatus state={cacheLoad} report={report} retry={()=>{statusRef.current=null;setRestoreAttempt(n=>n+1)}}/>
 <p className="smallnote">Completed dashboards are saved for users with the same access. Save KPI / Save graph keeps an item in future analysis runs while AI can add other comparisons. Regenerate replaces the remaining analysis; deleted graphs stay removed and saved custom graphs recalculate automatically. Changes to saved manual production data update affected KPIs and graphs without another AI run; workbook-based results remain cached until their source changes. Add graph and Add KPI use the full section scope. Graphs retain all comparison categories by default; zoom and scroll change the view, not the calculated data.</p><div className="insights-controls"><label className="aiconsent"><input type="checkbox" checked={allowedToSend} onChange={e=>{setConsent(e.target.checked);if(!e.target.checked)setSharing({alwaysAllow:false})}}/> Allow sharing planning rules, calculation definitions and relevant workbook data with Google Gemini</label><label className="aiconsent"><input type="checkbox" checked={sharing.alwaysAllow===true} onChange={e=>{setSharing({alwaysAllow:e.target.checked});setConsent(false)}}/> Always allow Gemini for my Insights analysis, graphs and KPIs. Saved to my account; turn off anytime.</label><button className="primary" disabled={cacheLoading||busy||adding!==null||filtering!==null||!allowedToSend||!status?.configured||!workbookReady} onClick={generate}><Sparkles size={17}/> {busy?'Analysing planning views…':job.current?'Resume analysis':report?'Regenerate analysis':'Run analysis'}</button></div>
 {!status?.configured&&status&&<p className="error">Add GEMINI_API_KEY in Streamlit Secrets to enable generation.</p>}{error&&<p className="error" role="alert">{error}</p>}{(busy||Boolean(job.current))&&<div className="analysis-progress" role="status"><Sparkles size={20}/><div><strong>{progress?.label||'Building your planning review'}</strong><p>{progress?.percent??0}% complete · {busy?'You can switch workspace tabs while analysis continues.':'Saved sections are restored. Select Resume analysis to continue.'}</p>{cacheLoad.phase==='generating'&&<InsightLoadTime startedAt={cacheLoad.startedAt} active={busy} complete={false} historyKey={timingIdentity+':'+cacheLoad.timingMode}/>}</div></div>}
 {!report&&!busy&&<div className="panel insights-empty"><ChartNoAxesCombined size={42}/><h2>A complete view of your planning data</h2><p>AI designs a dashboard for each section: meaningful KPI cards first, supporting graphs below, and business findings with recommended checks. Connected comparisons use validated joins across permitted sources.</p><p>Uses full saved snapshots. Dashboard filters apply within each section. Select a KPI, bar, slice or point to open its supporting records.</p></div>}
 {report&&<>{!!report.warnings?.length&&<div className="analysis-notice" role="status"><Info size={17}/><div>{report.warnings.map((w,i)=><p key={i}>{clean(w)}</p>)}</div></div>}<div className="insight-summary"><div className="summary-copy"><span className="eyebrow">PLANNING BRIEF</span><h2>Full-snapshot business brief</h2><AnswerContent text={report.overview||report.answer}/></div><div className="report-stats"><div><strong>{report.sections.length}</strong><span>Planning views</span></div><div><strong>{report.sections.reduce((n,s)=>n+s.charts.length,0)}</strong><span>Detailed graphs</span></div></div></div>{report.attention&&report.attention.length>0&&<section className="attention-board" aria-label="Needs attention"><div><h2>Needs attention</h2><p>Calculated checks as of {report.referenceDate||'the workbook snapshot'} · select a finding to focus its planning view.</p></div><div className="attention-cards">{report.attention.map(a=><article className={'attention-card '+a.priority} key={a.id}><span className="attention-label">{a.priority==='high'?'Priority review':'Review'}</span><h3>{a.title}</h3><p>{a.detail}</p><p><strong>Next check:</strong> {a.action}</p><button className="textbutton" onClick={()=>setView(a.view)}>Focus related graphs →</button></article>)}</div></section>}{!!report.scope_notes?.length&&<details className="insight-limits"><summary>Planning scope and calculation limits</summary>{report.scope_notes.map((note,i)=><p key={i}>{note}</p>)}</details>}<p className="smallnote">The business brief and priority findings cover the full saved snapshot. Section filters recalculate the KPI cards and graphs below.</p><div className="insight-view-tabs" role="tablist" aria-label="Planning views"><button role="tab" aria-selected={view===-1} className={view===-1?'active':''} onClick={()=>setView(-1)}>All views</button>{report.sections.map(s=><button role="tab" aria-selected={view===s.view} key={s.view} className={view===s.view?'active':''} onClick={()=>setView(s.view)}>{s.title}<span>{s.charts.length}</span></button>)}</div>
 {report.sections.filter(s=>view===-1||s.view===view).map(s=><section key={s.view} id={'insight-view-'+s.view} className="insights-section"><div className="insight-section-heading"><div><span className="eyebrow">PLANNING VIEW {s.view+1}</span><h2>{s.title}</h2></div><span className="tag">{s.records.toLocaleString()} source records · {s.charts.length} graphs</span></div>
 <SectionFilters initialFilters={s.filters||[]} key={'filters:'+report.report_id+':'+s.view} facets={s.facets||[]} reportId={report.report_id} version={report.version} section={s.view} busy={cacheLoading||filtering===s.view||busy||Boolean(job.current)||adding!==null} apply={filters=>filterSection(s.view,filters)}/>
 {!!s.kpis?.length&&<div className="bi-kpis" aria-label={s.title+' business KPIs'}>{s.kpis.map((k,i)=><div className="bi-kpi-tile" key={k.id||i}><button className="bi-kpi" key={i} disabled={!!k.refresh_error} onClick={()=>setSelected({title:k.title,label:'',value:k.field,evidence:k.evidence})}><span>{k.title}</span><strong>{k.value===null?'Unavailable':number(k.value)}</strong><small>{k.refresh_error||k.basis}</small>{k.comparison_result&&<small>{k.comparison_result.current_month} · Previous ({k.comparison_result.previous_month}): {k.comparison_result.previous_value===null?'Unavailable':number(k.comparison_result.previous_value)} · Growth: {k.comparison_result.growth_percent===null?'Unavailable':number(k.comparison_result.growth_percent)+'%'}<br/>{k.comparison_result.note}</small>}<em>Explore supporting records →</em></button>{k.comparison_evidence&&<button className="textbutton" onClick={()=>setSelected({title:k.title+' · previous month',label:'',value:k.field,evidence:k.comparison_evidence!})}>Previous month records</button>}{k.id&&<button type="button" className="textbutton" aria-label={'Save KPI '+k.title} title="Keep this full-section KPI in future analysis runs" disabled={cacheLoading||!!k.refresh_error||busy||Boolean(job.current)||adding!==null||filtering!==null} onClick={()=>saveItem(s.view,k,'kpi')}>{k.pending?'Saving…':k.saved?'Saved KPI':'Save KPI'}</button>}{k.id&&<button className="textbutton" aria-label={'Delete KPI '+k.title} disabled={cacheLoading||busy||Boolean(job.current)||adding!==null||filtering!==null} onClick={()=>deleteKpi(s.view,k)}>Delete KPI</button>}</div>)}</div>}
 {report.report_id&&<AddGraphForm key={report.report_id+':'+s.view} title={s.title} view={s.view} enabled={allowedToSend&&!cacheLoading&&!busy&&!job.current&&adding===null&&filtering===null} working={adding===s.view} add={question=>addGraph(s.view,question)}/>}
 {report.report_id&&<AddKpiForm title={s.title} enabled={allowedToSend&&!cacheLoading&&!busy&&!job.current&&adding===null&&filtering===null} working={adding===s.view} add={question=>addGraph(s.view,question,'kpi')}/>}
 <div className="insights-grid">{s.charts.map((c,i)=><GraphFrame key={c.id||i} fullScreen={fullGraph===s.view+':'+(c.id||i)} title={c.title} onClose={()=>setFullGraph(null)} toolbar={<>{editNotice?.view===s.view&&<p className={editNotice.failed?'error':'smallnote'} role={editNotice.failed?'alert':'status'}>{editNotice.text}</p>}<SectionFilters initialFilters={s.filters||[]} key={'full-filter:'+report.report_id+':'+s.view} facets={s.facets||[]} reportId={report.report_id} version={report.version} section={s.view} busy={cacheLoading||filtering===s.view||busy||Boolean(job.current)||adding!==null} apply={filters=>filterSection(s.view,filters)}/></>}><article className="panel insight-chart"><div className="chart-heading"><div>{c.refresh_error&&<p role="status">{c.refresh_error}</p>}<h3>{c.title}{c.custom&&<small className="custom-chart-label">Added with AI</small>}</h3><p>{c.evidence.matched_records.toLocaleString()} matching records · {c.evidence.shown_rows} of {c.evidence.result_rows} results displayed</p></div><select className="chart-style" aria-label={'Chart style for '+c.title} value={c.type||'bar'} onChange={e=>setReport(current=>current?{...current,sections:current.sections.map(section=>section.view===s.view?{...section,charts:section.charts.map((chart,j)=>j===i?{...chart,type:e.target.value}:chart)}:section)}:current)}><option value="bar">Horizontal bars</option><option value="column">Vertical columns</option><option value="lollipop">Dot ranking</option>{(c.value.startsWith('count(')||c.value.startsWith('distinct_count('))&&c.evidence.records.length<=30&&c.evidence.records.every(r=>typeof r[c.value]==='number'&&Number(r[c.value])>=0)&&<option value="donut">Donut composition</option>}{c.x&&<option value="scatter">XY comparison</option>}{c.evidence.records.length>0&&c.evidence.records.every(r=>isDatedComparisonLabel(r[c.label]))&&<><option value="line">Line trend</option><option value="area">Area trend</option></>}</select></div><div className="chart-open"><CachedGraphic chart={c} fullScreen={fullGraph===s.view+':'+(c.id||i)} onSelect={setSelected}/></div><label className="bi-value-picker">Explore value<select aria-label={'Explore a value in '+c.title} value="" onChange={e=>{if(e.target.value!=='')setSelected({...c,mark:Number(e.target.value)})}}><option value="">Select category / point…</option>{c.evidence.records.map((r,j)=><option key={j} value={j}>{String(r[c.label]??'Unspecified')} · {number(r[c.value])}</option>)}</select></label>{(c.finding||c.action||c.data_quality)&&<div className="chart-interpretation">{c.finding&&<div><strong>What needs attention</strong><AnswerContent text={c.finding}/></div>}{c.action&&<div><strong>Suggested next check</strong><AnswerContent text={c.action}/></div>}{c.data_quality&&<div className="smallnote"><AnswerContent text={c.data_quality}/></div>}</div>}<div className="chart-footer"><span title={c.value}>{c.type==='scatter'?c.x+' ↔ '+c.value:c.value}</span><div className="graph-actions"><button className="textbutton" disabled={!!c.refresh_error} onClick={()=>setSelected(c)}><Table2 size={14}/> View source data</button><button type="button" className="textbutton" aria-label={'Full screen graph '+c.title} onClick={()=>setFullGraph(fullGraph===s.view+':'+(c.id||i)?null:s.view+':'+(c.id||i))}><Maximize2 size={14}/> Full screen</button>{c.id&&<button type="button" className="textbutton" aria-label={'Save graph '+c.title} title="Keep this full-section graph and style in future analysis runs" disabled={cacheLoading||!!c.refresh_error||busy||Boolean(job.current)||adding!==null||filtering!==null} onClick={()=>saveItem(s.view,c,'chart')}>{c.pending?'Saving…':c.saved?'Saved graph':'Save graph'}</button>}{c.id&&<button className="textbutton" aria-label={'Delete graph '+c.title} disabled={cacheLoading||busy||Boolean(job.current)||adding!==null||filtering!==null} onClick={()=>deleteGraph(s.view,c)}><Trash2 size={14}/> Delete graph</button>}</div></div></article></GraphFrame>)}</div>
 {s.review&&<div className="review-grid" aria-label={s.review_mode==='calculated'?'Calculated review':'AI review'}>{([{key:'findings',title:'Key findings',icon:Lightbulb},{key:'actions',title:'Suggested actions',icon:ClipboardCheck},{key:'data_quality',title:'Data quality & checks',icon:Info}] as const).map(({key,title,icon:Icon})=>s.review?.[key]?.length?<article className={'review-card '+key} key={key}><h3><Icon size={18}/>{key==='findings'?(s.review_mode==='calculated'?'Calculated findings':'AI findings'):title}</h3><ul>{s.review[key].map((t,i)=><li key={i}>{clean(t)}</li>)}</ul></article>:null)}</div>}
 {!s.charts.length&&<p className="panel insights-empty">No supported chart for this view.</p>}{s.limitation&&<details className="insight-limits"><summary><Info size={14}/> Scope & limitations</summary><p>{clean(s.limitation)}</p></details>}</section>)}</>}
 {selected&&createPortal(<div className="insight-data-overlay" onClick={()=>setSelected(null)}><section className="insight-data-dialog" role="dialog" aria-modal="true" aria-label={'Source data: '+selected.title} onClick={e=>e.stopPropagation()}><div className="insight-dialog-heading"><div><span className="eyebrow">GRAPH EVIDENCE</span><h2>{selected.title}</h2><p>{selected.evidence.table}</p></div><button className="secondary" onClick={()=>setSelected(null)} aria-label="Close graph data"><X size={17}/> Close</button></div><div className="insight-dialog-content"><h3>{selected.mark===undefined?'Values used in this graph':'Selected graph value'}</h3><p>{selected.evidence.shown_rows} of {selected.evidence.result_rows} result rows shown. Calculations use all {selected.evidence.matched_records.toLocaleString()} matching source records.</p><ResultTable records={selected.mark===undefined?selected.evidence.records:[selected.evidence.records[selected.mark]]} scope={'insights:result:'+selected.title}/><div className="source-table-heading"><h3>{selected.mark===undefined?'Underlying matching records':'Records contributing to this value'}</h3>{isAdmin()&&selected.evidence.export_id&&<button className="secondary" onClick={()=>download(selected.evidence)}><Download size={14}/> Download matching records (Excel)</button>}</div>{sourceBusy&&<p role="status">Loading source records…</p>}{sourceError&&<p className="error" role="alert">{sourceError}</p>}{!selected.evidence.source_id&&<p>Regenerate the analysis to enable paginated source records for this report.</p>}{source&&<><ResultTable records={source.records} scope={'insights:source:'+selected.evidence.table}/><div className="source-pagination"><span>{source.total?source.page*source.page_size+1:0}–{Math.min((source.page+1)*source.page_size,source.total)} of {source.total.toLocaleString()} matching records</span><button className="secondary" disabled={sourceBusy||source.page===0} onClick={()=>page(source.page-1)}><ChevronLeft size={14}/> Previous</button><button className="secondary" disabled={sourceBusy||(source.page+1)*source.page_size>=source.total} onClick={()=>page(source.page+1)}>Next <ChevronRight size={14}/></button></div></>}</div></section></div>,document.body)}
 </div>
}

function AddKpiForm({title,enabled,working,add}:{title:string;enabled:boolean;working:boolean;add:(question:string)=>Promise<string>}){
 const [question,setQuestion]=useState(''),[feedback,setFeedback]=useState('');
 async function submit(event:React.FormEvent){event.preventDefault();if(!enabled||!question.trim())return;setFeedback('');try{const clarification=await add(question.trim());if(clarification)setFeedback(clarification);else{setQuestion('');setFeedback('KPI added and saved above the graphs.')}}catch(error){setFeedback(error instanceof Error?error.message:String(error))}}
 return <details className="add-graph add-kpi"><summary><Plus size={16}/> Add KPI to {title}</summary><form onSubmit={submit}><label>Describe the KPI<textarea aria-label={'Describe KPI for '+title} value={question} maxLength={2000} rows={2} disabled={working} placeholder="For example: count materials with a shortage, or show the average lead time with its unit." onChange={event=>setQuestion(event.target.value)}/></label><p>Uses all matching records. Source units, period and safe calculation rules apply.</p><button className="primary" disabled={!enabled||!question.trim()}>{working?'Preparing KPI…':'Add KPI with AI'}</button>{feedback&&<p role="status">{feedback}</p>}</form></details>;
}

function AddGraphForm({title,view,enabled,working,add}:{title:string;view:number;enabled:boolean;working:boolean;add:(question:string)=>Promise<string>}){
 const [question,setQuestion]=useState(''),[feedback,setFeedback]=useState(''),[failed,setFailed]=useState(false);
 const example=view===5?'Compare all materials with positive Need to Order Quantity.':view===10?'Show overdue production orders by Days overdue.':view===11?'Show the oldest under-QC batches by Days since 101.':'Compare all materials by a measure in this view, with any filters you need.';
 async function submit(event:React.FormEvent){event.preventDefault();if(!enabled||!question.trim())return;setFeedback('');setFailed(false);try{const clarification=await add(question.trim());if(clarification)setFeedback(clarification);else{setQuestion('');setFeedback('Graph added below with its calculated data and interpretation.')}}catch(error){setFailed(true);setFeedback(error instanceof Error?error.message:String(error))}}
 return <details className="add-graph"><summary><Plus size={16}/> Add graph to {title}</summary><form onSubmit={submit}><label>Describe the graph<textarea aria-label={'Describe graph for '+title} placeholder={example} maxLength={2000} rows={2} value={question} disabled={working} onChange={event=>setQuestion(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();if(enabled&&question.trim())event.currentTarget.form?.requestSubmit()}}}/></label><div><p>Use plain language. Enter adds the graph; Shift+Enter adds a new line. Your sharing consent above applies.</p><button className="primary" type="submit" disabled={!enabled||!question.trim()}><Send size={15}/>{working?'Generating graph and insight…':'Add graph with AI'}</button></div>{feedback&&<p role={failed?'alert':'status'} className={'graph-feedback'+(failed?' error':'')}>{feedback}</p>}</form></details>;
}


function SectionFilters({facets,busy,apply,reportId,version,section,initialFilters=[]}:{initialFilters?:InsightFilter[];facets:Facet[];busy:boolean;apply:(filters:InsightFilter[])=>Promise<void>;reportId?:string;version:string;section:number}){
 const [choices,setChoices]=useState<Record<string,ChoiceSelection>>({}),[conditions,setConditions]=useState<Record<string,ColumnFilter>>({}),[fields,setFields]=useState<string[]>([]),[applied,setApplied]=useState(false),[failed,setFailed]=useState('');
 const suggested=facets.filter(f=>!f.search_only&&/segment|source name|year|month|date|status|uom|unit|material availability|particulars/i.test(f.column)).slice(0,5);
 const preferred=suggested.length?suggested:facets.slice(0,3),others=facets.filter(f=>!preferred.includes(f)),visible=[...preferred,...others.filter(f=>fields.includes(f.column))];
 const signature=JSON.stringify(initialFilters);
 useEffect(()=>{const restored=restoreConditions(initialFilters);setChoices(restored.choices);setConditions(restored.conditions);setApplied(initialFilters.length>0);setFields([...new Set(initialFilters.map(f=>f.column))].filter(column=>!preferred.some(f=>f.column===column)));},[signature]);
 const kind=(f:Facet)=>f.kind||(dateHeader(f.column)?'date':f.values.length&&f.values.every(v=>typeof v==='number')?'number':'text');
 async function submit(reset=false){
  setFailed('');try{
   const filters:InsightFilter[]=reset?[]:Object.entries(choices).filter(([column,v])=>v!=='all'&&visible.some(f=>f.column===column)).map(([column,value])=>({column,op:'in',value}));
   if(!reset)for(const f of visible){const rule=conditions[f.column];if(rule){const condition=conditionFilter(f.column,rule,kind(f));if(condition)filters.push(condition);}}
   await apply(filters);setApplied(filters.length>0);if(reset){setChoices({});setConditions({});setFields([])}
  }catch(e){setFailed(e instanceof Error?e.message:String(e))}
 }
 return <div className="bi-filterbar"><div className="bi-filter-fields">{visible.map(f=><div className="checkbox-field" key={f.column}><span>{f.column}</span><CheckboxFilter label={'Insight '+f.column} maxSelections={500} disabled={busy} value={choices[f.column]??'all'} options={f.values.map(v=>({value:v}))} onChange={values=>setChoices(c=>({...c,[f.column]:values}))} loadOptions={f.search_only&&reportId?async(query,offset)=>rpc('insight_filter_values',{report_id:reportId,version,view:section,column:f.column,query,offset}):undefined}/><details className="insight-condition"><summary aria-label={'Conditions for '+f.column}>Condition</summary><fieldset disabled={busy}><FilterCondition allowNumberRange field={f.column} value={conditions[f.column]||{op:kind(f)==='date'?'date_on':kind(f)==='number'?'eq':'contains'}} onChange={change=>setConditions(current=>({...current,[f.column]:{op:kind(f)==='date'?'date_on':kind(f)==='number'?'eq':'contains',...current[f.column],...change}}))}/><button type="button" className="textbutton" onClick={()=>setConditions(current=>{const next={...current};delete next[f.column];return next})}>Clear condition</button></fieldset></details></div>)}{!!others.length&&<div className="checkbox-field"><span>More filter fields</span><CheckboxFilter label="Additional insight filter fields" showAll={false} maxSelections={8-preferred.length} disabled={busy} value={fields} options={others.map(f=>({value:f.column}))} onChange={values=>setFields(values==='all'?[]:values)}/></div>}</div><div className="bi-filter-actions"><button className="primary" disabled={busy||!facets.length} onClick={()=>submit()}>{busy?'Calculating…':'Apply filters'}</button><button className="secondary" disabled={busy} onClick={()=>submit(true)}>Reset</button><span>{applied?'Filtered calculations · AI narrative hidden':'Full saved section scope'}</span></div><p className="smallnote">Conditions and checked values apply together. Choose up to eight fields.</p>{failed&&<p className="error" role="alert">{failed}</p>}</div>
}


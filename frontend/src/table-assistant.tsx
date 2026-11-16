import {lazy,Suspense,useState,useEffect,useId,useContext} from 'react';
import {createPortal} from 'react-dom';
import {can,canAccessTab} from './bridge';
import {TableColumns} from './table-columns';
const AskAI=lazy(()=>import('./ask-ai'));
export default function TableAssistant({table,view,headers}:{table:string;view:string;headers:string[]}){
 const columnActions=useContext(TableColumns);
 const [open,setOpen]=useState(false),[minimized,setMinimized]=useState(false),id=useId();
 useEffect(()=>{const opened=(event:Event)=>{if((event as CustomEvent).detail!==id)setOpen(false)};window.addEventListener('stock-table-assistant-open',opened);return()=>window.removeEventListener('stock-table-assistant-open',opened)},[id]);
 if(!can('use_tools')||(typeof canAccessTab==='function'&&!canAccessTab(7)))return null;
 return <><button className="secondary" onClick={()=>{window.dispatchEvent(new CustomEvent('stock-table-assistant-open',{detail:id}));setMinimized(false);setOpen(true)}}>Ask Assistant</button>{open&&createPortal(<Suspense fallback={<section className="aiwindow aichat" role="status"><button onClick={()=>setOpen(false)}>Close</button>Opening assistant…</section>}><><aside className={'table-assistant-panel'+(minimized?' is-minimized':'')} hidden={minimized} aria-label="Table Ask Assistant sidebar"><AskAI addColumn={columnActions?.add} context={{kind:'table',table,view,headers}} close={()=>setOpen(false)} minimize={()=>setMinimized(true)}/></aside>{minimized&&<button autoFocus className="secondary table-assistant-restore" aria-label="Restore table assistant" onClick={()=>setMinimized(false)}>Restore Ask Assistant · {table}</button>}</></Suspense>,document.body)}</>;
}

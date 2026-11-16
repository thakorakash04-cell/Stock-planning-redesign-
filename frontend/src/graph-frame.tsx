import {useEffect,useRef,type ReactNode} from 'react';
import {createPortal} from 'react-dom';
export default function GraphFrame({fullScreen,title,onClose,children,toolbar}:{toolbar?:ReactNode;fullScreen:boolean;title:string;onClose:()=>void;children:ReactNode}){
 const panel=useRef<HTMLDivElement>(null),close=useRef(onClose);close.current=onClose;
 useEffect(()=>{
  if(!fullScreen)return;
  const previous=document.activeElement as HTMLElement|null,overflow=document.body.style.overflow;document.body.style.overflow='hidden';panel.current?.focus();
  const key=(event:KeyboardEvent)=>{
   if(document.querySelector('.insight-data-dialog'))return;
   if(event.key==='Escape'){event.preventDefault();close.current();return;}
   if(event.key!=='Tab')return;
   const controls=Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled),select:not(:disabled),input:not(:disabled),[tabindex="0"]')||[]),first=controls[0],last=controls.at(-1);
   if(!first){event.preventDefault();return;}
   if(event.shiftKey&&(document.activeElement===first||document.activeElement===panel.current)){event.preventDefault();last?.focus();}
   else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===panel.current)){event.preventDefault();first.focus();}
  };
  const navigate=()=>close.current();window.addEventListener('keydown',key);window.addEventListener('stock-workspace-navigate',navigate);
  return()=>{document.body.style.overflow=overflow;window.removeEventListener('keydown',key);window.removeEventListener('stock-workspace-navigate',navigate);queueMicrotask(()=>{if(previous?.isConnected&&previous!==document.body)previous.focus();else{const label=previous?.getAttribute('aria-label')||'Full screen graph '+title;if(label)Array.from(document.querySelectorAll<HTMLElement>('[aria-label]')).find(el=>el.getAttribute('aria-label')===label)?.focus();}});};
 },[fullScreen]);
 if(!fullScreen)return <>{children}</>;
 return createPortal(<div ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-label={'Full-screen graph: '+title} className="insights-page graph-fullscreen"><div className="graph-fullscreen-heading"><strong>{title}</strong><button type="button" className="secondary" aria-label="Exit graph full screen" onClick={onClose}>Exit full screen</button></div>{toolbar}{children}</div>,document.body);
}

import {useEffect} from 'react';
import {useViewPreference} from './view-preference';
export function useTableView(scope:string){
 const [view,set]=useViewPreference('table-view:'+scope,{mode:'auto'});
 useEffect(()=>{const sync=(event:Event)=>{const d=(event as CustomEvent).detail;if(d?.scope===scope)set({mode:d.mode})};window.addEventListener('stock-table-view',sync);return()=>window.removeEventListener('stock-table-view',sync)},[scope,set]);
 return [view.mode,(mode:string)=>window.dispatchEvent(new window.CustomEvent('stock-table-view',{detail:{scope,mode}}))] as const;
}
export default function TableViewSwitch({scope,grouped}:{scope:string;grouped:boolean}){
 const [mode,set]=useTableView(scope),pivot=mode==='pivot'||(mode==='auto'&&grouped);
 return <span className="table-view-switch" role="group" aria-label="Table display"><button type="button" className="secondary" aria-pressed={!pivot} onClick={()=>set('table')}>Table View</button><button type="button" className="secondary" aria-pressed={pivot} onClick={()=>set('pivot')}>Pivot View</button></span>;
}

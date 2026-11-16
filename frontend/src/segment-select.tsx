import {useState} from 'react';
import {type SegmentSelection} from './segment-selection';
export {matchesSegments,type SegmentSelection} from './segment-selection';
export default function SegmentSelect({value,options,onChange,label='Filter by segment',unassigned=false}:{value:SegmentSelection;options:string[];onChange:(value:SegmentSelection)=>void;label?:string;unassigned?:boolean}){
 const [query,setQuery]=useState('');
 const all=value==='all'||!value,selected=Array.isArray(value)?value:all?[]:[value];
 const choices=[...new Set([...options,...(unassigned?['unassigned']:[])])];
 return <details className="segment-select" onKeyDown={e=>{if(e.key==='Escape')e.currentTarget.open=false}}><summary aria-label={label}>{all?'All segments':selected.length===1?(selected[0]==='unassigned'?'Unassigned':selected[0]):selected.length+' segments selected'}</summary><div className="segment-options" role="group" aria-label={label+' choices'}><input aria-label={label+' search'} placeholder="Search segments…" value={query} onChange={e=>setQuery(e.target.value)}/><label><input type="checkbox" checked={all} onChange={e=>onChange(e.target.checked?'all':[])}/>All segments</label>{choices.filter(s=>s.toLowerCase().includes(query.toLowerCase())).map(s=><label key={s}><input type="checkbox" checked={selected.includes(s)} onChange={e=>{const next=new Set(selected);if(e.target.checked)next.add(s);else next.delete(s);onChange([...next])}}/>{s==='unassigned'?'Unassigned':s}</label>)}</div></details>;
}

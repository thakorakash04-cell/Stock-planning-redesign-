import {periodLabel} from './sales-periods';
export type PeriodSelection='all'|string[];
export default function SalesMonthFilter({value,options,onChange}:{value:PeriodSelection;options:string[];onChange:(next:PeriodSelection)=>void}){
 const all=value==='all',selected=all?[]:value,years=[...new Set(options.map(x=>x.slice(0,4)))];
 function toggle(values:string[],checked:boolean){const next=new Set(selected);for(const x of values)if(checked)next.add(x);else next.delete(x);onChange([...next])}
 return <details className="segment-select"><summary aria-label="Sales Year and Month">{all?'All years & months':selected.length+' periods selected'}</summary><div className="segment-options" role="group" aria-label="Sales Year and Month choices"><label><input type="checkbox" checked={all} onChange={e=>onChange(e.target.checked?'all':[])}/>All years &amp; months</label>{years.map(year=>{const items=options.filter(x=>x.startsWith(year));return <div key={year}><label><input type="checkbox" checked={!all&&items.every(x=>selected.includes(x))} onChange={e=>toggle(items,e.target.checked)}/><strong>{year}</strong></label>{items.map(month=><label key={month}><input type="checkbox" checked={selected.includes(month)} onChange={e=>toggle([month],e.target.checked)}/>{periodLabel(month)}</label>)}</div>})}{!options.length&&<p>No dated sales records available.</p>}</div></details>
}

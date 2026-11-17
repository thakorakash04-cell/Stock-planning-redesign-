import {useEffect} from 'react';
import DataGrid from './data-grid';
import type {Cell} from './grid-utils';
import {pendingMaterialKey} from './stock-overview-display';
export type MaterialReadiness={status:string;headers:string[];rows:Cell[][];warnings:string[];quantity:number;unit:string};
export type MaterialReadinessIndex=Record<string,Record<string,MaterialReadiness>>;
export const readinessOptions=['Ready','Material Shortage','Material Need to Be Ordered'];
export function readinessFor(index:MaterialReadinessIndex|undefined,row:Cell[]):MaterialReadiness|undefined{return index?.[pendingMaterialKey(row[0])]?.[String(row[3])];}
export function MaterialReadinessDetails({material,value,close}:{material:string;value:MaterialReadiness;close:()=>void}){
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.key==='Escape'&&!document.querySelector('.grid-expanded,.filterdialog'))close()};document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key)},[close]);
 return <div className="overlay record-overlay"><section className="drawer" role="dialog" aria-modal="true" aria-label="Cached material readiness"><div className="detailtopbar"><h2>{material} · {value.status}</h2><button className="secondary" onClick={close}>Close</button></div><p>Required FG quantity: {value.quantity.toLocaleString('en-IN')} {value.unit}. Cached from the uploaded workbook and saved demand snapshot.</p><p>Ready: current component stock including QC covers the requirement. Material Shortage: expected deliveries cover the current shortage. Material Need to Be Ordered: stock plus expected deliveries is insufficient. QC is included once in current stock.</p><p>Each FG is checked independently against its direct BOM. This check does not reserve shared components across products, include future production or guarantee arrival dates.</p>{value.warnings.map((warning,i)=><p className="smallnote" key={i}>{warning}</p>)}<DataGrid headers={value.headers} rows={value.rows} storageKey="demand-material-readiness" filename={material+' material readiness'}/></section></div>;
}

import {dataUpToText,type SourceFile} from './source-stamp';
export type PlanProvenance={origin:string;suggestion:string;materialCode:string;requiredQuantity:number;unit:string;sources:(SourceFile & {label:string;version:string})[]};
export default function PlanOrigin({reason,value}:{reason?:string;value?:PlanProvenance|null}){
 if(!value)return reason?<div className="smallnote"><strong>Planning remark:</strong> {reason}<p>Original source upload dates were not recorded for this plan.</p></div>:null;
 return <div className="smallnote" style={{display:'grid',gap:5,maxWidth:540}}><strong>Suggestion: {value.suggestion}</strong><span>{value.origin} · {value.materialCode} · requirement {value.requiredQuantity.toLocaleString('en-IN')} {value.unit}</span>{reason&&<span>Planning remark: {reason}</span>}{value.sources.map((source,i)=><span key={i}><strong>{source.label}: </strong>{source.filename} · Uploaded on: {typeof source.updated_at==='number'?new Date(source.updated_at*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':'Not recorded'} · Data up to: {dataUpToText(source.dataUpTo)}</span>)}</div>;
}

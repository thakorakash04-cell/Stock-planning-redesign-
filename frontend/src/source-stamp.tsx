export type SourceFile={filename:string;updated_at?:number;dataUpTo?:string|null;dataDateBasis?:string;updated_by?:string};
export function dataUpToText(value?:string|null){
 if(!value)return 'Not available in file';
 const month=/^\d{4}-\d{2}$/.test(value),date=new Date(value+(month?'-01T00:00:00Z':'T00:00:00Z'));
 if(!Number.isFinite(date.getTime()))return 'Not available in file';
 return date.toLocaleDateString('en-IN',{timeZone:'UTC',...(month?{}:{day:'2-digit' as const}),month:'short',year:'numeric'});
}
export default function SourceStamp({meta,label}:{meta?:SourceFile|null;label?:string}){
 if(!meta)return null;
 const date=typeof meta.updated_at==='number'?new Date(meta.updated_at*1000):null;
 return <div className="source" aria-label={(label||'Source file')+' dates'}><strong>{label?label+' · ':''}{meta.filename}</strong><span>Uploaded on: {date&&Number.isFinite(date.getTime())?date.toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':'Not available'}</span><span>Data up to: {dataUpToText(meta.dataUpTo)}</span>{meta.updated_by&&<span>{meta.updated_by}</span>}{meta.dataDateBasis&&<small>{meta.dataDateBasis}</small>}</div>;
}

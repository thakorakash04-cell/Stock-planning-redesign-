export type SegmentSelection=string|string[];
export function matchesSegments(selection:SegmentSelection,values:readonly string[]=[]):boolean{
 if(!selection||selection==='all')return true;
 const selected=Array.isArray(selection)?selection:[selection];
 const key=(v:string)=>v.normalize('NFKC').trim().replace(/\.xlsx?$/i,'').trim().toLowerCase();
 return selected.some(s=>s==='unassigned'?!values.length:values.some(v=>key(v)===key(s)));
}

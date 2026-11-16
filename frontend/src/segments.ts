import {matchesSegments,type SegmentSelection} from './segment-selection';
import type {ModelTable,Cell} from './model-data';
export type SegmentMap=Record<string,string[]>;
export const materialKey=(value:unknown)=>String(value??'').normalize('NFKC').replaceAll('\u200b','').trim().replace(/^([+-]?\d+)\.0+$/,'$1').toLowerCase();
const indexes=new WeakMap<SegmentMap,Map<string,string[]>>();
export function lookupSegments(map:SegmentMap|undefined,value:unknown):string[]{
 if(!map)return [];let index=indexes.get(map);if(!index){index=new Map();for(const [code,values] of Object.entries(map)){const key=materialKey(code);index.set(key,[...new Set([...(index.get(key)||[]),...values])])}indexes.set(map,index)}return index.get(materialKey(value))||[];
}
export const sourceSegment=(value:unknown)=>String(value??'').normalize('NFKC').replaceAll('\u200b','').trim().replace(/\.xlsx?$/i,'').trim();
const headerKey=(v:string)=>v.toLowerCase().replace(/[^a-z0-9]/g,'');
const materials=new Set(['material','materialcode','materialnumber','fgcode','fgmaterial','fgmaterialcode','fgmaterialnumber','sku','skucode']);
const tableIndexes=new WeakMap<ModelTable[],SegmentMap>();
export function segmentIndex(tables:ModelTable[]):SegmentMap{
 const cached=tableIndexes.get(tables);if(cached)return cached;
 const map:Record<string,Set<string>>={},primary=new Set<string>();const ordered=[...tables].sort((a,b)=>Number(!['uniquematerial','bom','bomcost'].includes(headerKey(a.name)))-Number(!['uniquematerial','bom','bomcost'].includes(headerKey(b.name))));for(const t of ordered){const h=t.headers.map(headerKey),mi=h.findIndex(v=>materials.has(v)),si=h.findIndex(v=>v.endsWith('sourcename')||(['uniquematerial','bom','bomcost'].includes(headerKey(t.name))&&v==='segment'));if(mi<0||si<0)continue;for(const r of t.rows){const c=materialKey(r[mi]),s=sourceSegment(r[si]);const authoritative=['uniquematerial','bom','bomcost'].includes(headerKey(t.name));if(c&&s&&(authoritative||!primary.has(c)))(map[c]??=new Set()).add(s);if(c&&s&&authoritative)primary.add(c)}}
 const boms=tables.filter(t=>headerKey(t.name)==='bom').map(t=>({t,h:t.headers.map(headerKey)})).map(({t,h})=>({t,mi:h.findIndex(v=>materials.has(v)),ci:h.findIndex(v=>['component','componentcode','componentmaterial'].includes(v))})).filter(t=>t.mi>=0&&t.ci>=0);
 for(let pass=0;pass<20;pass++){let changed=false;for(const {t,mi,ci} of boms)for(const r of t.rows){const child=materialKey(r[ci]);if(!child)continue;for(const s of map[materialKey(r[mi])]||[]){const values=map[child]??=new Set();if(!values.has(s)){values.add(s);changed=true}}}if(!changed)break}
 const result=Object.fromEntries(Object.entries(map).map(([c,s])=>[c,[...s].sort()]));tableIndexes.set(tables,result);return result;
}
export function rowSegments(headers:string[],row:Cell[],map:SegmentMap,tableName=''):string[]{const source=headers.findIndex(h=>headerKey(h).endsWith('sourcename')),segment=['dpmrp','dpmrpdata'].includes(headerKey(tableName))?-1:headers.findIndex(h=>headerKey(h)==='segment'),i=source>=0?source:segment;if(i>=0){const value=sourceSegment(row[i]);if(value)return [value]}for(let i=0;i<headers.length;i++)if(materials.has(headerKey(headers[i]))||['component','componentcode','componentmaterial'].includes(headerKey(headers[i]))){const values=lookupSegments(map,row[i]);if(values.length)return values}return [];}

export function filterSegments(tables:ModelTable[],map:SegmentMap,segment:SegmentSelection){if(!segment||segment==='all')return tables;const dates=new Set<string>();const filtered=tables.map(t=>{if(t.name==='Calendar')return t;const rows=t.rows.filter(r=>matchesSegments(segment,rowSegments(t.headers,r,map,t.name)));for(const r of rows)for(let i=0;i<t.headers.length;i++)if(/date|attribute|valid from|created on|changed on|last change/i.test(t.headers[i])&&/^\d{4}-\d{2}-\d{2}/.test(String(r[i])))dates.add(String(r[i]).slice(0,10));return {...t,rows}});return filtered.map(t=>t.name==='Calendar'?{...t,rows:t.rows.filter(r=>dates.has(String(r[t.headers.indexOf('Date')]).slice(0,10)))}:t)}


export function segmentChoices(tables:ModelTable[],map:SegmentMap):string[]{
 const values=new Set(Object.values(map).flat());
 for(const t of tables){const i=t.headers.findIndex(h=>headerKey(h).endsWith('sourcename'));if(i>=0)for(const row of t.rows){const value=sourceSegment(row[i]);if(value)values.add(value)}}
 return [...values].sort();
}


import {createContext} from 'react';
import {rowSegments,sourceSegment,lookupSegments,type SegmentMap} from './segments';
import {productColumns} from './product-links';
import type {Cell} from './grid-utils';
export const GroupingSegments=createContext<SegmentMap>({});
export function segmentLabel(headers:string[],row:Cell[],map:SegmentMap){
 const explicit=headers.findIndex(h=>/^(segment|division|source[ _]?name)$/i.test(h));
 if(explicit>=0&&String(row[explicit]??'').trim())return sourceSegment(row[explicit]);
 const direct=rowSegments(headers,row,map);
 const mapped=direct.length?direct:productColumns(headers).keys.flatMap(i=>lookupSegments(map,row[i]));
 const values=[...new Set(mapped)].sort();
 return values.length?values.join(' / '):'Unmapped segment';
}

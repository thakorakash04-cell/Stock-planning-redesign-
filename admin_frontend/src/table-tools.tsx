import React,{Children,createContext,useContext,useId,useMemo,type ReactNode} from 'react';
import DataGrid from './data-grid';
import {call} from './bridge';
import {sourceRowIndices,type Cell} from './grid-utils';
export const GridAccess=createContext<{user:string;canExport:boolean;scope?:string}>({user:'',canExport:false});
export function DataTable({table,onValue,renderCell,storageKey}:{table:any;onValue?:(row:number,column:number)=>void;renderCell?:(row:number,column:number)=>ReactNode|undefined;storageKey?:string}){
 const access=useContext(GridAccess),instance=useId();
 const rowIndices=useMemo(()=>sourceRowIndices(table.rows),[table.rows]);
 const preferenceKey=JSON.stringify([access.user,access.scope||'',storageKey||table.name||instance]);
 return <DataGrid key={preferenceKey} headers={table.headers} rows={table.rows} filename={table.name||'Table'} storageKey={preferenceKey} segmentForRow={table.segmentLabels?row=>table.segmentLabels[rowIndices.get(row)!]||'Unmapped segment':undefined} allowExport={access.canExport} authorizeExport={async()=>{await call('authorizeTableExport',{name:table.name||'Table'});return true}} onCell={onValue?(row,column)=>onValue(rowIndices.get(row)!,column):undefined} renderCell={renderCell?(row,column)=>renderCell(rowIndices.get(row)!,column):undefined}/>;
}
function nodes(value:ReactNode):React.ReactElement[]{return Children.toArray(value).flatMap(n=>React.isValidElement(n)?n.type===React.Fragment?nodes((n.props as any).children):[n]:[])}
function text(value:ReactNode):string{if(value==null||typeof value==='boolean')return '';if(typeof value==='string'||typeof value==='number')return String(value);if(Array.isArray(value))return value.map(text).filter(Boolean).join(' ');if(React.isValidElement(value)){const p=value.props as any;if(value.type==='input'&&p.type==='checkbox')return p.checked?'Allowed':'Not allowed';return text(p.children)}return ''}
export function EnhancedTable({children,name='Table',tableKey}:{children:ReactNode;name?:string;tableKey?:string}){
 const instance=useId();const sections=nodes(children),head=sections.find(n=>n.type==='thead'),body=sections.find(n=>n.type==='tbody');
 const headers=nodes(head?.props&&(head.props as any).children).flatMap(r=>nodes((r.props as any).children)).map((c,i)=>text((c.props as any).children)||'Actions');
 const sourceRows=nodes(body?.props&&(body.props as any).children);const cells=sourceRows.map(r=>nodes((r.props as any).children));
 const rows=cells.map(row=>row.map(c=>{const child=(c.props as any).children;return typeof child==='number'?child:text(child)||null}));
 return <DataTable table={{name,headers,rows}} storageKey={tableKey||name+instance} renderCell={(r,c)=>(cells[r]?.[c]?.props as any)?.children}/>;
}


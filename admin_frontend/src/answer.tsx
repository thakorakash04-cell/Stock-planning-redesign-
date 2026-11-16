import {useEffect,useRef,useState,useId} from 'react';
import {call} from './bridge';
import {DataTable} from './table-tools';
type Scope={division?:string;productId?:string};
function inline(text:string){return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g).map((part,i)=>part.startsWith('**')?<strong key={i}>{part.slice(2,-2)}</strong>:part.startsWith('`')?<code key={i}>{part.slice(1,-1)}</code>:/^\[/.test(part)?<a key={i} href={part.match(/\((.*)\)$/)?.[1]} target="_blank" rel="noopener noreferrer">{part.match(/^\[([^\]]+)/)?.[1]}</a>:part)}
export function Answer({text}:{text:string}){
 const answerId=useId();
 const lines=String(text||'').replace(/\bT\d+:R\d+\b/g,'').split('\n'),blocks:any[]=[];let i=0;
 while(i<lines.length){const line=lines[i].trim();if(!line){i++;continue}const split=(s:string)=>s.replace(/^\s*\||\|\s*$/g,'').split('|').map(c=>c.trim());
  if(line.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-{3}/.test(lines[i+1])){const headers=split(line),rows:string[][]=[];i+=2;while(i<lines.length&&lines[i].includes('|'))rows.push(split(lines[i++]));blocks.push(<DataTable key={i} table={{name:'Answer comparison',headers,rows}} storageKey={'answer:'+answerId+':'+i} renderCell={(row,column)=>inline(rows[row]?.[column]||'')}/>);continue}
  if(/^[-*+]\s+|^\d+[.)]\s+/.test(line)){const ordered=/^\d/.test(line),items=[];while(i<lines.length&&(/^\d+[.)]\s+/.test(lines[i].trim())===ordered)&&/^([-*+]|\d+[.)])\s+/.test(lines[i].trim()))items.push(<li key={i}>{inline(lines[i++].trim().replace(/^([-*+]|\d+[.)])\s+/,''))}</li>);blocks.push(ordered?<ol key={i}>{items}</ol>:<ul key={i}>{items}</ul>);continue}
  if(/^#{1,6}\s/.test(line)){blocks.push(<h3 key={i}>{inline(line.replace(/^#{1,6}\s+/,''))}</h3>);i++;continue}
  blocks.push(<p key={i}>{inline(line)}</p>);i++;
 }
 return <div className="answer-markdown">{blocks}</div>;
}

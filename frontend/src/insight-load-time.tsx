import {useEffect,useRef,useState} from 'react';
const memory=new Map<string,number[]>(),prefix='stock-insight-load-times-v1:';
export function readLoadTimes(key:string):number[]{
 try{const value=JSON.parse(window.localStorage.getItem(prefix+key)||'null');if(Array.isArray(value))return value.filter(n=>typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=600000).slice(-5);}catch{}
 return memory.get(key)||[];
}
export function saveLoadTime(key:string,milliseconds:number){
 if(!Number.isFinite(milliseconds)||milliseconds<0||milliseconds>600000)return;
 const values=[...readLoadTimes(key),milliseconds].slice(-5);memory.set(key,values);
 try{window.localStorage.setItem(prefix+key,JSON.stringify(values));}catch{}
}
export function loadTimeEstimate(history:number[],elapsed:number){
 if(!history.length)return null;
 const sorted=[...history].sort((a,b)=>a-b),middle=Math.floor(sorted.length/2),expected=sorted.length%2?sorted[middle]:(sorted[middle-1]+sorted[middle])/2;
 return Math.max(0,expected-elapsed);
}
export function formatLoadTime(milliseconds:number){
 if(milliseconds<1000)return '<1s';
 const seconds=Math.ceil(milliseconds/1000);return seconds<60?seconds+'s':Math.floor(seconds/60)+'m '+seconds%60+'s';
}
export default function InsightLoadTime({startedAt,active,complete,historyKey}:{startedAt:number;active:boolean;complete:boolean;historyKey:string}){
 const [now,setNow]=useState(Date.now),[history,setHistory]=useState(()=>readLoadTimes(historyKey)),recorded=useRef('');
 useEffect(()=>{setNow(Date.now());setHistory(readLoadTimes(historyKey));if(!active)return;const timer=window.setInterval(()=>setNow(Date.now()),1000);return()=>window.clearInterval(timer);},[startedAt,active,historyKey]);
 useEffect(()=>{const cycle=historyKey+':'+startedAt;if(!complete||recorded.current===cycle)return;recorded.current=cycle;saveLoadTime(historyKey,Math.max(0,Date.now()-startedAt));},[complete,startedAt,historyKey]);
 const elapsed=Math.max(0,now-startedAt),remaining=loadTimeEstimate(history,elapsed);
 return <div className="insight-load-time"><span>Elapsed: {formatLoadTime(elapsed)}</span>{active&&<span>{remaining===null?'Estimated remaining: Calculating estimate…':remaining>0?'Estimated remaining: about '+formatLoadTime(remaining):'Taking longer than earlier loads…'}</span>}{active&&history.length>0&&<small>Estimate based on recent successful loads; it may change.</small>}</div>;
}

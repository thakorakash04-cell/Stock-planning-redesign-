import {useCallback,useEffect,useRef,useState,type SetStateAction} from 'react';
export function useViewPreference<T extends object>(key:string,initial:T):[T,(value:SetStateAction<T>)=>void]{
 const read=()=>{try{return {...initial,...JSON.parse(localStorage.getItem('product360:'+key)||'{}')} as T}catch{return initial}};
 const [stored,setStored]=useState(()=>({key,value:read()}));const value=stored.key===key?stored.value:read();const current=useRef(value);current.current=value;
 useEffect(()=>{setStored({key,value:read()})},[key]);
 const set=useCallback((update:SetStateAction<T>)=>{const next=typeof update==='function'?(update as (v:T)=>T)(current.current):update;current.current=next;setStored({key,value:next});try{localStorage.setItem('product360:'+key,JSON.stringify(next))}catch{}},[key]);return [value,set];
}

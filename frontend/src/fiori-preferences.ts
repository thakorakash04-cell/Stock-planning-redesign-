export type FioriPreferences={favorites:number[];recent:number[]};
const defaults: FioriPreferences={favorites:[0,3,6,8],recent:[]};
const key=(user:string)=>'stock-planning:fiori:'+encodeURIComponent(user);
const ids=(value:unknown)=>Array.isArray(value)?[...new Set(value.filter((id:unknown)=>Number.isInteger(id)&&Number(id)>=0&&Number(id)<=13))] as number[]:[];
export function readFioriPreferences(user:string):FioriPreferences{try{const raw=localStorage.getItem(key(user));if(!raw)return {favorites:[...defaults.favorites],recent:[]};const data=JSON.parse(raw);return {favorites:ids(data.favorites),recent:ids(data.recent).slice(0,6)}}catch{return {favorites:[...defaults.favorites],recent:[]}}}
export function saveFioriPreferences(user:string,value:FioriPreferences){const next={favorites:ids(value.favorites),recent:ids(value.recent).slice(0,6)};try{localStorage.setItem(key(user),JSON.stringify(next))}catch{}window.dispatchEvent(new window.CustomEvent('stock-fiori-preferences',{detail:{user,value:next}}));}
export function recordFioriVisit(user:string,id:number){const prefs=readFioriPreferences(user);saveFioriPreferences(user,{...prefs,recent:[id,...prefs.recent.filter(i=>i!==id)].slice(0,6)});}

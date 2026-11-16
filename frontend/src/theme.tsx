import {useEffect,useState} from 'react';
const KEY="stock-planning:theme",STYLE_KEY="stock-planning:ui-style";
export const UI_STYLES=[['existing','Existing UI'],['glassmorphism','Glassmorphism'],['spatial','Spatial UI'],['neomorphism','Neomorphism'],['liquid-glass','Liquid Glass'],['fiori','Fiori Launchpad']] as const;
function stored(){try{return localStorage.getItem(KEY)==='dark'?'dark':'light'}catch{return 'light'}}
export function readUIStyle(allowFiori=false){try{const value=localStorage.getItem(STYLE_KEY);return UI_STYLES.some(([id])=>id===value)&&(value!=='fiori'||allowFiori)?value!:'existing'}catch{return 'existing'}}
function apply(theme:string,style:string){document.documentElement.dataset.theme=theme;document.documentElement.dataset.uiStyle=style;document.documentElement.style.colorScheme=theme;window.dispatchEvent(new window.CustomEvent('stock-ui-style-changed',{detail:style}))}
function save(key:string,value:string){try{localStorage.setItem(key,value);document.cookie=key.replace(':','-')+'='+value+'; Path=/; Max-Age=31536000; SameSite=Lax'+(location.protocol==='https:'?'; Secure':'')}catch{}}
if(typeof document!=='undefined')apply(stored(),readUIStyle());
export default function ThemeToggle({floating=false,allowFiori=false}:{floating?:boolean;allowFiori?:boolean}){
 const [theme,setTheme]=useState(stored),[style,setStyle]=useState(()=>readUIStyle(allowFiori));
 useEffect(()=>{const sync=()=>{const t=stored(),s=readUIStyle(allowFiori);setTheme(t);setStyle(s);apply(t,s)};sync();window.addEventListener('storage',sync);return()=>window.removeEventListener('storage',sync)},[allowFiori]);
 function toggle(){const next=theme==='dark'?'light':'dark';setTheme(next);apply(next,style);save(KEY,next)}
 return <div className={'portal-appearance-controls'+(floating?' portal-theme-floating':'')}><button type="button" className="portal-theme-toggle" role="switch" aria-checked={theme==='dark'} aria-label="Dark theme" title={theme==='dark'?'Switch to light theme':'Switch to dark theme'} onClick={toggle}><span aria-hidden="true">{theme==='dark'?'☀':'☾'}</span>{theme==='dark'?'Light theme':'Dark theme'}</button><label className="portal-style-control"><span className="portal-style-label">UI style</span><select aria-label="UI style" value={style} onChange={e=>{const next=e.target.value;if(!UI_STYLES.some(([id])=>id===next)||(next==='fiori'&&!allowFiori))return;setStyle(next);apply(theme,next);save(STYLE_KEY,next)}}>{UI_STYLES.filter(([id])=>id!=='fiori'||allowFiori).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label></div>;
}

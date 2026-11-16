import {useContext} from 'react';
import {ProductLinks} from './product-links';
import {isAdmin} from './bridge';
export function syncSettingsUrl(value:string){try{const url=new URL(value);if(url.protocol!=='https:'||url.username||url.password)return '';url.searchParams.set('sync','1');url.hash='';return url.toString()}catch{return ''}}
export default function PlanningSyncLink(){
 const catalogue=useContext(ProductLinks);if(!isAdmin())return null;
 const url=catalogue.products.map(p=>syncSettingsUrl(p.url)).find(Boolean);
 return <button disabled={!url} title={url?'Open the administrator-authorized 02:30 IST refresh settings in Product Status':'Publish the Product Status catalogue once to create this connection'} onClick={()=>{if(url)window.open(url,'_blank','noopener,noreferrer')}} aria-label="Auto refresh"><span aria-hidden="true">⟳</span><span className="navtext">Auto refresh</span></button>;
}

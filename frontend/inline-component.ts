import type {Plugin} from 'vite';

/** Streamlit serves this whole component atomically: no startup asset requests. */
export function inlineComponent():Plugin {
 return {name:'inline-streamlit-component',enforce:'post',generateBundle:{order:'post',handler(_options,bundle){
  const html=bundle['index.html'];
  if(!html||html.type!=='asset')throw Error('Missing component HTML');
  let page=String(html.source);
  page=page.replace(/<script\b[^>]*\bsrc="\.\/([^" ]+)"[^>]*><\/script>/g,(_tag,file)=>{
   const entry=bundle[file];if(!entry||entry.type!=='chunk')throw Error('Missing component entry '+file);
   if(entry.imports.length||entry.dynamicImports.some(name=>name!==file)||/\bimport\s*\(/.test(entry.code))throw Error('Component startup must have no external module dependencies');
   return '<script type="module">'+entry.code.replace(/<\/script/gi,'<\\/script')+'</script>';
  });
  page=page.replace(/<link\b[^>]*\bhref="\.\/([^" ]+\.css)"[^>]*>/g,(_tag,file)=>{
   const css=bundle[file];if(!css||css.type!=='asset')throw Error('Missing component style '+file);
   return '<style>'+String(css.source).replace(/<\/style/gi,'<\\/style')+'</style>';
  });
  if(/<script\b[^>]*\bsrc=|<link\b[^>]*rel="(?:stylesheet|modulepreload)"/i.test(page))throw Error('External component startup dependency remains');
  if(/__VITE_PRELOAD__|__VITE_IS_MODERN__/.test(page))throw Error('Unresolved Vite runtime marker in component HTML');
  html.source=page;
 }}};
}

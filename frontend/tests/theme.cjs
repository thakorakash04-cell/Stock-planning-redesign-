const assert=require('node:assert/strict'),fs=require('fs'),ts=require("typescript"),{JSDOM}=require("jsdom");
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
const dom=new JSDOM('<div id="root"></div>',{url:'https://portal.test'});Object.assign(global,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,location:dom.window.location,IS_REACT_ACT_ENVIRONMENT:true});
const React=require("react"),{act}=React,{createRoot}=require("react-dom/client"),Theme=require("../src/theme.tsx").default;
let root=createRoot(document.getElementById('root'));const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 await act(async()=>{root.render(React.createElement(Theme));await tick()});
 let button=document.querySelector('[role=switch]');assert.equal(button.getAttribute('aria-checked'),'false');
 await act(async()=>{button.click();await tick()});assert.equal(document.documentElement.dataset.theme,'dark');assert.equal(button.getAttribute('aria-checked'),'true');assert.ok(button.textContent.includes('Light theme'));
 const selector=document.querySelector('select[aria-label="UI style"]');assert.equal(selector.options.length,5);
 for(const id of ['existing','glassmorphism','spatial','neomorphism','liquid-glass']){await act(async()=>{selector.value=id;selector.dispatchEvent(new window.Event('change',{bubbles:true}));await tick()});assert.equal(document.documentElement.dataset.uiStyle,id);assert.equal(document.documentElement.dataset.theme,'dark','Style must not change colour mode');}
 await act(async()=>root.unmount());root=createRoot(document.getElementById('root'));
 await act(async()=>{root.render(React.createElement(Theme));await tick()});button=document.querySelector('[role=switch]');assert.equal(button.getAttribute('aria-checked'),'true','Theme must survive remount/login');assert.equal(document.querySelector('select').value,'liquid-glass','UI style must survive remount/login');
 await act(async()=>{button.click();await tick()});assert.equal(document.documentElement.dataset.theme,'light');
 await act(async()=>root.unmount());
 const luminance=hex=>{const rgb=hex.match(/\w\w/g).map(x=>parseInt(x,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]};
 for(const [fg,bg] of [['e5edf5','101821'],['e5edf5','182431'],['b2c0ce','182431'],['88e4d2','182431'],['ffffff','0f766e'],['a1efc5','143c31'],['ffda91','44341d'],['ffc0cb','402731']]){const a=luminance(fg),b=luminance(bg);assert.ok((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,fg+' / '+bg+' must pass normal-text contrast')}
 console.log('PASS: five independent UI styles, light/dark persistence, accessible controls and dark-text contrast palette.');
})().catch(e=>{console.error(e);process.exit(1)});


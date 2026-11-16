const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const html=fs.readFileSync('../frontend_dist/index.html','utf8');
assert(!/<script\b[^>]*\bsrc=|<link\b[^>]*rel="(?:stylesheet|modulepreload)"/i.test(html),'startup must not fetch JS/CSS files');
assert(!/__VITE_PRELOAD__|__VITE_IS_MODERN__/.test(html),'embedded module must use finalized Vite code');
const scripts=[...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)],bootstrap=scripts.find(s=>!s[1].includes('module'))?.[2],moduleCode=scripts.find(s=>s[1].includes('module'))?.[2];
assert(bootstrap&&moduleCode);assert(!/\bimport\s*\(/.test(moduleCode),'no dynamic asset requests');
function environment(){const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test/component/index.html',pretendToBeVisual:true,runScripts:'outside-only'}),messages=[];dom.window.parent.postMessage=m=>messages.push(m);dom.window.fetch=()=>{throw Error('Startup attempted a network fetch')};return{dom,messages,context:dom.getInternalVMContext()}}
(async()=>{
 const {dom,messages,context}=environment();new vm.Script(bootstrap).runInContext(context);assert(messages.some(m=>m.type==='streamlit:componentReady'),'HTML acknowledges before the React module executes');
 const emit=(args,source=dom.window.parent)=>dom.window.dispatchEvent(new dom.window.MessageEvent('message',{data:{type:'streamlit:render',args},origin:'https://workspace.test',source}));
 emit({n:1});emit({n:2});emit({n:999},null);const replay=[];dom.window.addEventListener('message',e=>replay.push(e.data.args));dom.window.__portalBoot.handoff();dom.window.__portalBoot.handoff();assert.deepEqual(replay,[{n:2}],'replay latest trusted render once after bridge attaches');dom.window.close();
 const actual=environment();new vm.Script(bootstrap).runInContext(actual.context);const module=new vm.SourceTextModule(moduleCode,{context:actual.context,initializeImportMeta(meta){meta.url='https://workspace.test/component/index.html'},importModuleDynamically(){throw Error('Unexpected dynamic import')}});assert.equal(module.dependencySpecifiers.length,0);await module.link(()=>{throw Error('Unexpected module request')});await module.evaluate();await new Promise(r=>setTimeout(r,30));assert(actual.dom.window.document.getElementById('root').textContent.includes('Loading your saved workspace'));assert(actual.messages.some(m=>m.type==='streamlit:componentReady'));actual.dom.window.close();
 console.log('PASS: self-contained production HTML executes with all asset requests blocked; early handshake, trusted latest-render replay and React bridge startup pass');
})().catch(e=>{console.error(e);process.exitCode=1});

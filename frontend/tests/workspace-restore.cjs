const assert=require('node:assert/strict'),fs=require('fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);require.extensions['.css']=()=>{};
Object.defineProperty(global,'crypto',{value:require('node:crypto').webcrypto,configurable:true});
// Async IDB contract double. Retains only serialized bytes across fresh runtimes.
let disk=null,blocked=false;
global.indexedDB={open(){if(blocked)throw Error('Storage blocked');const request={};queueMicrotask(()=>{request.result={objectStoreNames:{contains:()=>true},close(){},transaction(){const tx={objectStore(){return{get(){const read={};queueMicrotask(()=>{read.result=disk;read.onsuccess?.()});return read},put(value){disk=value;queueMicrotask(()=>tx.oncomplete?.())}}}};return tx}};request.onsuccess?.()});return request}};
const React=require('react'),{act}=React,tick=()=>new Promise(r=>setImmediate(r));
const definitions=[{name:'Amount',plan:{sources:[],columns:[]}}],headers=['Material','Qty'],rows=[['A',2]];
const base={user:'alice',role:'viewer',permissions:{use_tools:true},accessScope:'alice-scope',version:'v1',modelScope:'model1',tablesDeferred:true,data:{filename:'Master.xlsx',updatedAt:'upload1',accessibleTabs:[0,7],sheets:[{name:'Stock',headers,rows}]},preferences:{'columns:main:Stock':{definitions}},preload:{deferred:true}};
async function boot(args,versions={primary:'sales1'}){
 const dom=new JSDOM('<div id="root"></div>',{url:'https://planning.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,CustomEvent:dom.window.CustomEvent,IS_REACT_ACT_ENVIRONMENT:true});
 const frames=[];window.requestAnimationFrame=fn=>(frames.push(fn),frames.length);const calls=[];let ready,model=null;
 for(const path of ['../src/main.tsx','../src/table-columns.tsx','../src/preload-cache.ts'])delete require.cache[require.resolve(path)];
 require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{startBridge:fn=>ready=fn,can:()=>true,canAccessTab:()=>true,tableColumnSnapshot:()=>({user:args.user,version:args.version,accessScope:args.accessScope}),readViewPreference:k=>args.preferences?.[k],saveViewPreference(){},preparedModelTables:()=>model,restoreModelTables:(tables,scope,version)=>{assert.equal(scope,args.modelScope);assert.equal(version,args.version);model=tables;return true},ensureModelTables:async()=>{calls.push('models');model=[{name:'Stock',headers,rows}]},rpc:async action=>{calls.push(action);if(action==='heartbeat')return{sourceVersions:versions};if(action==='workspace_preload')return{version:args.version,accessScope:args.accessScope,preload:{id:'finance-'+versions.primary,sales:{primary:{rows:[['Sales',9]]}},pnl:null,versions}};if(action==='table_columns_resolve')return{columns:[{name:'Amount',values:[20]}],cached:true};return{}}}};
 const {useColumns}=require('../src/table-columns.tsx');
 require.cache[require.resolve('../src/dashboard.tsx')]={loaded:true,exports:{__esModule:true,default:()=>{const{table}=useColumns(headers,rows,'main:Stock');return React.createElement('div',{'aria-label':'Ready dashboard'},JSON.stringify(table.rows))}}};
 await act(async()=>{require('../src/main.tsx');ready(args);for(let i=0;i<30;i++)await tick()});
 await act(async()=>{while(frames.length){frames.shift()();for(let i=0;i<5;i++)await tick()}});
 await act(async()=>{for(let i=0;i<10;i++)await tick()});
 assert(document.querySelector('[aria-label="Ready dashboard"]'),document.body.textContent);assert(document.body.textContent.includes('20'),'Restored added-column values must appear on first mount');
 const sales=require('../src/preload-cache.ts').salesSnapshot('primary');assert.equal(sales.rows[0][0],'Sales');assert.equal(model[0].rows[0][0],'A');
 const cacheStatus=document.documentElement.dataset.workspaceCache;dom.window.close();calls.cacheStatus=cacheStatus;return calls;
}
(async()=>{
 const first=await boot(base);assert(first.includes('workspace_preload'));assert(first.includes('models'));assert(first.includes('table_columns_resolve'));assert(disk,'Successful startup persists display bytes');assert.equal(first.cacheStatus,'saved');
 const again=await boot({...base,bootstrapId:'different-session'});assert.equal(again.cacheStatus,'restored');assert(again.includes('heartbeat'),'Live server validation always precedes restore');for(const action of ['workspace_preload','models','table_columns_resolve'])assert(!again.includes(action),'Fresh iframe reuses '+action);
 const clock=Date.now;Date.now=()=>clock()+86400000;const nextDay=await boot(base);Date.now=clock;assert(!nextDay.includes('workspace_preload'),'The calendar day alone must not invalidate finance');
 for(const args of [{...base,user:'bob',accessScope:'bob-scope'},{...base,accessScope:'narrower-segments'}]){await boot(base);const calls=await boot(args);assert(calls.includes('workspace_preload'),'Account/access changes cannot reuse prior data');}
 await boot(base);const masterChanged=await boot({...base,data:{...base.data,updatedAt:'upload2'}});assert(masterChanged.includes('models'));assert(!masterChanged.includes('workspace_preload'),'Independent unchanged financial versions are reused');
 await boot(base);const layoutChanged=await boot({...base,preferences:{...base.preferences,'pnl:filters':{fy:2025}}});assert(!layoutChanged.includes('models'));assert(!layoutChanged.includes('workspace_preload'),'Unrelated preferences must not reload Sales');

 await boot(base);const changedSales=await boot(base,{primary:'sales2'});assert(changedSales.includes('workspace_preload'),'New Sales invalidates its portion');assert(!changedSales.includes('models'),'A Sales upload must reuse master model tables');assert(!changedSales.includes('table_columns_resolve'),'Unchanged same-table calculated columns must be retained');
 disk='{broken';assert((await boot(base)).includes('workspace_preload'),'Corruption falls back');
 blocked=true;assert((await boot(base)).includes('workspace_preload'),'Blocked storage falls back without blocking home');blocked=false;
 const cache=require('../src/workspace-cache.ts');assert.equal(await cache.writeWorkspaceCache({key:'stale',finance:null,tables:[],columns:[]},()=>false),false,'Late prior-account writes are rejected');
 console.log('PASS: fresh-runtime workspace/finance/source/column restoration; live validation; upload/account/access/layout/Sales invalidation; corrupt/blocked storage fallback; stale-write isolation.');
})().catch(e=>{console.error(e);process.exitCode=1});

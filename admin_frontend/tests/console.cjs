const assert=require('node:assert/strict'),fs=require('node:fs'),ts=require('typescript'),{JSDOM}=require('jsdom');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,n)=>m._compile(ts.transpileModule(fs.readFileSync(n,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,n);
require.extensions['.css']=()=>{};
const dom=new JSDOM('<div id="root"></div>',{url:'https://workspace.test'});Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true});
const calls=[];const permissions={menu_0:'Open Stock overview',menu_1:'Open BOM cost',download:'Download / export data',update_data:'Upload and replace shared workbook',use_tools:'Use Ask AI'};
const user={allowedSegments:null,username:'viewer',email:'viewer@example.invalid',role:'viewer',active:1,permissions:{menu_0:true,menu_1:true,download:false}};
const tables=[{name:'Summary',headers:['Material','Need to order'],rows:2}];let rules=[],schedule={enabled:true,time:'09:00'};
const automatic={config:{enabled:false,rules:['packaging'],threshold:3000,qcDays:14,packagingWords:['label'],packagingTypes:['ZPAC'],includeMaterials:[],excludeMaterials:[]},version:'n1',rules:[{id:'packaging',title:'1 · Packaging stock below 3,000',trigger:'New master workbook'}],source:{warnings:[]},jobs:[]};
const bootstrap={title:'Stock & Planning',identity:{username:'admin'},portal:'accounts',settings:{},permissions,users:[user],segments:['Red','Blue']};
async function call(operation,input={}){calls.push({operation,...input});switch(operation){case 'consoleInit':return bootstrap;case 'stockNoticeInfo':return automatic;case 'stockNoticePreview':return {...automatic,reports:[{batch:'master:test',recipient:user.email,points:[{rule:'packaging'}],body:'Packaging stock: 2500 EA'}]};case 'stockNoticeSave':automatic.config=input.config;return automatic;case 'emailInfo':return {rules,version:'v1',configured:true,aiConfigured:true,recipients:[{name:'viewer',email:user.email}],tables,operators:['>','=','contains'],schedule,scheduleVersion:'s1',delivery:{error:'',jobs:[]}};case 'emailApplyProposal':rules=input.rules;schedule=input.schedule;return call('emailInfo');case 'emailSchedule':schedule=input.schedule;return call('emailInfo');case 'emailDraft':return {rules:[{id:'draft',name:'Shortage',recipients:[user.email],section:'Summary',column:'Need to order',operator:'>',value:'0',filters:[],enabled:false}],replace_ids:[],schedule:{enabled:true,time:'08:30'},answer:'A draft is ready. Review, enable and save.'};case 'memberSave':user.permissions={...input.permissions};return {ok:true};case 'workbookInfo':return {filename:'Master.xlsx',uploadedBy:'admin',updatedAt:1,tables:[{name:'Summary',rows:2,columns:2}]};case 'history':return {rows:[]};default:return {ok:true}}}
require.cache[require.resolve('../src/bridge.ts')]={loaded:true,exports:{call,ready:Promise.resolve(),initialPage:()=> 'users',initialData:()=>bootstrap}};
const React=require('react'),{act}=React,tick=()=>new Promise(r=>setImmediate(r));
const props=el=>el[Object.keys(el).find(k=>k.startsWith('__reactProps$'))];
async function click(text){const el=[...document.querySelectorAll('button,a')].find(b=>b.textContent.trim()===text||b.textContent.trim().endsWith(text));assert.ok(el,'Missing '+text);await act(async()=>{el.click();await tick()})}
(async()=>{
 await act(async()=>{require('../src/main.tsx');await tick();await tick()});
 assert.equal(calls.length,0,'Opening administration must not issue extra initialization or email RPCs');
 assert.ok(document.querySelector('.console-sidebar'));assert.ok(document.querySelector('table'));assert.ok(document.body.textContent.includes('viewer@example.invalid'));
 await click('Manage rights');assert.ok(document.querySelector('[role="dialog"]'));let checkbox=[...document.querySelectorAll('.console-dialog label')].find(l=>l.textContent.includes('Download / export')).querySelector('input');await act(async()=>{checkbox.click();await tick()});
 assert.equal(document.querySelectorAll('[aria-label="Available segments"] input').length,2,'Existing all-segment users must see segment choices immediately');
 assert.ok([...document.querySelectorAll('[aria-label="Available segments"] input')].every(i=>i.checked));
 await act(async()=>{[...document.querySelectorAll('.console-dialog label')].find(l=>l.textContent.includes('All segments, including future')).querySelector('input').click();await tick()});
 await act(async()=>{[...document.querySelectorAll('.console-dialog label')].find(l=>l.textContent==='Red').querySelector('input').click();await tick()});
 await act(async()=>{document.querySelector('.console-dialog form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));await tick();await tick()});assert.equal(calls.find(x=>x.operation==='memberSave').permissions.download,true);assert.deepEqual(calls.find(x=>x.operation==='memberSave').allowedSegments,['Red']);assert.equal(document.querySelector('[role="dialog"]'),null);
 await click('Email management');
 assert.ok(document.body.textContent.includes('Preview only · no email delivery'));
 await click('Preview automatic reports');assert.ok(document.body.textContent.includes('Packaging stock: 2500 EA'));assert.ok(!calls.some(x=>x.operation==='emailDispatch'||x.operation==='stockNoticeSave'),'Automatic preview cannot save or send');
 const select=document.querySelector('select[aria-label="Recipients for email triggers"]');await act(async()=>{select.options[0].selected=true;select.dispatchEvent(new window.Event('change',{bubbles:true}));await tick()});
 const question=document.querySelector('[aria-label="Describe email trigger rules"]');await act(async()=>{props(question).onChange({target:{value:'Send shortages to this person'}});await tick()});await act(async()=>{question.closest('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));await tick();await tick()});
 assert.equal(calls.find(x=>x.operation==='emailDraft').question,'Send shortages to this person');assert.ok(document.querySelector('.chatmessage.assistant'));assert.ok(document.body.textContent.includes('Draft / paused'));assert.ok(!calls.some(x=>x.operation==='emailSave'||x.operation==='emailDispatch'),'AI must not save or send automatically');
 assert.ok(document.querySelector('[aria-label="Review notification proposal"]'));assert.equal(rules.length,0,'AI must not save its proposal');
 await click('Workbook management');await click('Email management');assert.ok(document.querySelector('[aria-label="Review notification proposal"]'),'Proposal must survive navigation');
 await click('Apply proposal to working draft');assert.equal(rules.length,0,'Applying a proposal must not save it');
 const enable=[...document.querySelectorAll('.email-rule label')].find(l=>l.textContent.includes('Enable this rule')).querySelector('input');await act(async()=>{enable.click();await tick()});
 await click('Save rules');assert.equal(rules.length,1);assert.equal(rules[0].enabled,true);assert.equal(schedule.time,'08:30');assert.ok(calls.some(x=>x.operation==='emailApplyProposal'));assert.ok(!calls.some(x=>x.operation==='emailDispatch'));
 await click('Delete rule');assert.equal(rules.length,1,'Deleting is staged until saved');await click('Save rules');assert.equal(rules.length,0);
 await click('Workbook management');assert.ok(document.body.textContent.includes('Master.xlsx'));assert.ok(document.body.textContent.includes('Saved tables and workbook structure'));
 assert.ok(document.body.textContent.includes('Login logo and text'));
 const purpose=[...document.querySelectorAll('label')].find(l=>l.textContent.includes('Purpose of this website')).querySelector('textarea');
 await act(async()=>{props(purpose).onChange({target:{value:'Track our portal data.\nPlan decisions together.'}});await tick()});
 await click('Save login appearance');assert.equal(calls.filter(x=>x.operation==='settingsSave').at(-1).settings.login_text,'Track our portal data.\nPlan decisions together.');
 await click('Workspace settings');assert.ok(document.querySelector('.sidebar-editor'));assert.equal(document.querySelectorAll('.sidebar-editor>div').length,2);
 console.log('Passed: Product Status-style sidebar, account table/dialog, rights editing, conversational AI drafts without auto-save/send, workbook tables and sidebar editor.');process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});


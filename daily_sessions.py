"""Opaque, revocable browser sessions ending at midnight Asia/Kolkata.

Only token hashes are stored in SQL. Passwords never enter browser storage.
No cached identity or permission is used to authorize a request.
"""
import hashlib,importlib,re,secrets,time,uuid
from dataclasses import replace
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
REVISION=11

def next_midnight(now=None):
    local=datetime.fromtimestamp(time.time() if now is None else now,ZoneInfo('Asia/Kolkata'))
    return (local+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()

def table(store):return ('p360' if hasattr(store,'admin_email') else store.account_table)+'_browser_sessions'
def namespace(store):return getattr(store,'browser_namespace','workspace')
def cookie_name(store):return 'workspace_day_'+namespace(store)
def request_client(legacy=False):
    # The opaque token is the credential. Reverse-proxy/mobile IPs may change
    # between WebSockets, so they must not invalidate a remembered browser.
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is None:return ''
        agent=str(st.context.headers.get('User-Agent',''))
        value=str(st.context.ip_address or '')+'|'+agent if legacy else 'browser-v2|'+agent
        return hashlib.sha256(value.encode()).hexdigest()
    except (ImportError,RuntimeError):return ''

def digest(token,client=''):
    return hashlib.sha256((token+('\0'+client if client else '')).encode()).hexdigest()

def background_active(state,now=None):
    now=time.time() if now is None else now
    actor=state.get('actor')
    expiry=(actor.get('expires_at',0) if isinstance(actor,dict) else getattr(actor,'expires_at',0)) if actor else 0
    if expiry and now>=expiry:return False
    last=state.get('_browser_last_activity',0)
    return bool(actor) and state.get('_browser_visible',False) and 0<=now-last<300

def schema(store):
    with store.transaction() as db:
        store.run(db,f'CREATE TABLE IF NOT EXISTS {table(store)} (token_hash TEXT PRIMARY KEY,username TEXT NOT NULL,version INTEGER NOT NULL,session_id TEXT NOT NULL,issued DOUBLE PRECISION NOT NULL,expires DOUBLE PRECISION NOT NULL)')
        store.run(db,f'CREATE INDEX IF NOT EXISTS {table(store)}_session ON {table(store)}(session_id)')
        store.run(db,f'CREATE INDEX IF NOT EXISTS {table(store)}_expiry ON {table(store)}(expires)')

def issue(store,actor,client=''):
    now=time.time();expiry=next_midnight(now);token=secrets.token_urlsafe(32)
    is_product=isinstance(actor,dict)
    user=actor['email'] if is_product else actor.username
    version=actor['version'] if is_product else actor.version
    sid=uuid.uuid4().hex if is_product else actor.session_id
    with store.transaction() as db:
        store.check(db,actor) if is_product else store.require(db,actor)
        store.run(db,f'DELETE FROM {table(store)} WHERE expires<=?',(now,))
        store.run(db,f'INSERT INTO {table(store)} VALUES(?,?,?,?,?,?)',(digest(token,client),user,version,sid,now,expiry))
    renewed={**actor,'session_id':sid,'expires_at':expiry} if is_product else replace(actor,expires_at=expiry)
    return renewed,token,expiry

def make_store_actor(store,username,version,session_id='',expires_at=0):
    factory=getattr(store,'make_actor',None)
    if factory:return factory(username,version,session_id,expires_at)
    # Compatibility for an already cached pre-factory Store. Use the exact
    # constructor its own login method uses, never a freshly imported module.
    method=getattr(store.login,'__func__',store.login)
    return method.__globals__['Actor'](username,version,session_id,expires_at)

def restore(store,token,client='',legacy_client='',diagnostic=None):
    if diagnostic is not None:diagnostic['validation']='invalid_token'
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):return None
    with store.transaction() as db:
        hashes=list(dict.fromkeys([digest(token,client)]+([digest(token,legacy_client)] if legacy_client else [])))
        row=store.run(db,f'SELECT token_hash,username,version,session_id,issued,expires FROM {table(store)} WHERE token_hash IN ('+','.join('?' for _ in hashes)+') AND expires>?',(*hashes,time.time())).fetchone()
        if not row:
            if diagnostic is not None:diagnostic['validation']='token_not_matched'
            return None
        if diagnostic is not None:diagnostic['validation']='account_not_active'
        if hasattr(store,'admin_email'):
            actor={'email':row['username'],'version':row['version'],'at':row['issued'],'session_id':row['session_id'],'expires_at':row['expires']}
            try:store.check(db,actor)
            except ValueError:return None
        else:
            module=importlib.import_module(type(store).__module__)
            actor=make_store_actor(store,row['username'],row['version'],row['session_id'],row['expires'])
            try:store.require(db,actor)
            except PermissionError as exc:
                if diagnostic is not None:
                    known={'Sign in required.':'actor_type','Your daily session expired. Sign in again.':'expired','This session has expired. Please sign in again.':'account_or_session_version'}
                    diagnostic['denial']=known.get(str(exc),'permission_denied')
                    diagnostic['validator_revision']=getattr(module,'STORE_SCHEMA_REVISION',0)
                    diagnostic['token_version_type']=type(row['version']).__name__
                    account=store.run(db,f'SELECT active,session_version FROM {store.account_table} WHERE username=?',(row['username'],)).fetchone()
                    diagnostic['account_found']=bool(account)
                    if account:
                        diagnostic['account_active']=account['active'] in (1,True,'1','true','t')
                        diagnostic['account_version_type']=type(account['session_version']).__name__
                        diagnostic['raw_versions_equal']=account['session_version']==row['version']
                    diagnostic['matching_session']=bool(store.run(db,f'SELECT 1 FROM {table(store)} WHERE username=? AND version=? AND session_id=? AND expires>?',(row['username'],row['version'],row['session_id'],time.time())).fetchone())
                return None
        if row['token_hash']!=hashes[0]:
            store.run(db,f'UPDATE {table(store)} SET token_hash=? WHERE token_hash=?',(hashes[0],row['token_hash']))
        if diagnostic is not None:diagnostic['validation']='restored'
        return actor

def revoke(store,actor):
    if not actor:return
    sid=actor.get('session_id','') if isinstance(actor,dict) else actor.session_id
    with store.transaction() as db:store.run(db,f'DELETE FROM {table(store)} WHERE session_id=?',(sid,))

def session_valid(store,actor):
    """A denied feature permission does not invalidate an authenticated daily login."""
    if not actor:return False
    try:store.identity(actor)
    except PermissionError:return False
    return True

def restore_candidates(store,tokens,client='',legacy_client='',diagnostic=None):
    """Validate both browser stores; stale local storage must not mask a valid cookie."""
    if not isinstance(tokens,list):return None
    for token in dict.fromkeys(t for t in tokens[:2] if isinstance(t,str)):
        actor=restore(store,token,client,legacy_client,diagnostic)
        if actor:return actor
    return None

def start(store,state,actor):
    actor,token,expiry=issue(store,actor,state.get('_daily_client',request_client()))
    state['actor']=actor;state['login_at']=state['last_active']=time.time()
    state['_daily_restore_checked']=True
    state['_daily_cookie_action']={'name':cookie_name(store),'value':token,'expires':expiry,'nonce':uuid.uuid4().hex}
    return actor

def clear(store,state,reset_state=True):
    revoke(store,state.get('actor'))
    if reset_state:state.clear()
    else:state.pop('actor',None)
    state['_daily_restore_checked']=True
    state['_daily_cookie_action']={'name':cookie_name(store),'value':'','expires':0,'nonce':uuid.uuid4().hex}

def restore_cookie(store,state,cookies):
    # Bind one WebSocket's handshake consistently through form/fragment reruns.
    state.setdefault('_daily_client',request_client())
    state.setdefault('_daily_legacy_client',request_client(legacy=True))
    if state.get('_daily_restore_checked'):return
    token=cookies.get(cookie_name(store))
    state['_daily_diagnostic']={'revision':REVISION,'cookie_present':bool(token),'validation':'no_cookie'}
    if token:
        actor=restore(store,token,state.get('_daily_client',''),state.get('_daily_legacy_client',''),state['_daily_diagnostic'])
        if actor:
            state['actor']=actor;state['login_at']=state['last_active']=time.time()
        # Browser hydration also checks local storage; request cookies can be stale.
    state['_daily_restore_checked']=True

# A v2 component runs in the app document, so storage belongs to this app origin.
# Browser hydration is independent of the initial WebSocket Cookie header.
BROWSER_JS='''export default function(component) {
 const {data,setStateValue}=component;if(!data)return;
 const key=data.name;const registry=window.__workspaceDailyV2||(window.__workspaceDailyV2={});
 let entry=registry[key];
 if(!entry){entry=registry[key]={last:Date.now()/1000,visible:!document.hidden,instance:null,write:null,emit:setStateValue,lastSent:0};
  const signal=()=>{const now=Date.now()/1000;const visible=!document.hidden;
   if(now-entry.lastSent<45&&visible===entry.visible)return;
   entry.visible=visible;entry.lastSent=now;entry.emit('activity',{at:entry.last,visible,nonce:now});};
  const touch=()=>{const idle=Date.now()/1000-entry.last>=300;entry.last=Date.now()/1000;if(idle)entry.lastSent=0;signal();};
  for(const type of ['pointerdown','pointermove','keydown','scroll','touchstart','wheel'])document.addEventListener(type,touch,{passive:true,capture:true});
  window.addEventListener('message',event=>{if(event.origin!==location.origin||!event.source||!Array.from(document.querySelectorAll('iframe')).some(f=>f.contentWindow===event.source)||event.data?.type!=='workspace:user-activity')return;touch();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)entry.last=Date.now()/1000;entry.lastSent=0;signal();});
  // Only a small component event, no SQL or whole-app rerun. Idle timers send nothing.
  entry.timer=setInterval(()=>{if(!document.hidden&&Date.now()/1000-entry.last<300)signal();},45000);
 }
 entry.emit=setStateValue;
 if(entry.protocol!==4){entry.protocol=4;entry.instance=null;entry.write=null;}
 const write=value=>{
  let saved=false;
  const secure=location.protocol==='https:'?'; Secure':'';
  const seconds=value?Math.max(0,Math.ceil(value.expires-Date.now()/1000)):0;
  try{document.cookie=key+'='+encodeURIComponent(value?.token||'')+'; Path=/; SameSite=Strict; Max-Age='+seconds+secure;const cookie=decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith(key+'='))?.slice(key.length+1)||'');saved=value?cookie===value.token:!cookie;}catch{}
  try{if(value)localStorage.setItem(key,JSON.stringify(value));else localStorage.removeItem(key);const actual=JSON.parse(localStorage.getItem(key)||'null');saved=saved||(value?actual?.token===value.token:!actual);}catch{}
  return saved;
 };
 entry.action=data.action?.nonce||null;
 if(data.action&&entry.write!==data.action.nonce){
  const action=data.action;const saved=write(action.value?{token:action.value,expires:action.expires}:null);
  entry.write=action.nonce;entry.receipt={nonce:action.nonce,saved};
  // One atomic receipt prevents a fragment rerun from consuming ack before storage.
  const receipt={instance:data.instance,receipt:entry.receipt};
  setStateValue('session',receipt);
  for(const delay of [500,1500,3500])setTimeout(()=>{if(entry.action===action.nonce)entry.emit('session',receipt)},delay);
 }
 const emitBrowser=attempt=>{
  let saved=null;
  try{saved=JSON.parse(localStorage.getItem(key)||'null');}catch{}
  if(!saved||saved.expires<=Date.now()/1000){saved=null;try{localStorage.removeItem(key);}catch{}}
  let cookie='';try{cookie=decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith(key+'='))?.slice(key.length+1)||'');}catch{}
  const browser={instance:data.instance,token:saved?.token||cookie||'',tokens:[saved?.token,cookie].filter(Boolean),at:entry.last,visible:!document.hidden,attempt};
  setStateValue('session',{instance:data.instance,browser,receipt:entry.receipt||null});
 };
 entry.probing=data.probe===true;
 if(entry.instance!==data.instance){
  entry.instance=data.instance;const instance=data.instance;emitBrowser(0);
  // Bounded startup-only retransmission if a native-form/fragment handoff is lost.
  for(const [attempt,delay] of [[1,500],[2,1500],[3,3500]])setTimeout(()=>{if(entry.instance===instance&&entry.probing)emitBrowser(attempt)},delay);
 }
}'''

def mount(store):
    import streamlit as st
    import streamlit.components.v2 as v2
    state=st.session_state
    state.setdefault('_daily_browser_instance',uuid.uuid4().hex)
    component=v2.component('daily_browser_cookie_v4',js=BROWSER_JS)
    @st.fragment
    def browser_session():
        action=state.get('_daily_cookie_action')
        result=component(data={'name':cookie_name(store),'instance':state['_daily_browser_instance'],'action':action,'probe':not state.get('_daily_browser_checked',False)},
            on_session_change=lambda:None,on_activity_change=lambda:None,
            key='_daily_browser_cookie_v2',height=0)
        session=getattr(result,'session',None)
        session=session if isinstance(session,dict) and session.get('instance')==state['_daily_browser_instance'] else {}
        for value in (session.get('browser'),getattr(result,'activity',None)):
            if isinstance(value,dict):
                at=value.get('at',0)
                if isinstance(at,(int,float)):
                    state['_browser_last_activity']=min(time.time(),at)
                    state['_browser_visible']=value.get('visible') is True
        receipt=session.get('receipt')
        if action and isinstance(receipt,dict) and receipt.get('nonce')==action['nonce']:
            state['_daily_diagnostic']={**state.get('_daily_diagnostic',{}),'revision':REVISION,'write_saved':receipt.get('saved') is True}
            state['_daily_storage_failed']=receipt.get('saved') is not True
            state.pop('_daily_cookie_action',None)
            st.rerun()
        browser=session.get('browser')
        if not state.get('_daily_browser_checked') and isinstance(browser,dict) and browser.get('instance')==state['_daily_browser_instance']:
            already_authenticated=bool(state.get('actor'))
            diagnostic=state.setdefault('_daily_diagnostic',{'revision':REVISION})
            diagnostic.update(browser_token_present=bool(browser.get('token')),candidates=len(browser.get('tokens',[])))
            if not state.get('actor') and not action and browser.get('token'):
                try:actor=restore_candidates(store,browser.get('tokens',[browser['token']]),state.get('_daily_client',''),state.get('_daily_legacy_client',''),diagnostic)
                except Exception:
                    st.warning('The session server is temporarily unavailable. Your browser login has been retained.')
                    if st.button('Reconnect',key='_daily_restore_retry'):st.rerun()
                    st.stop()
                if actor:
                    state['actor']=actor;state['login_at']=state['last_active']=time.time()
                elif st.query_params.get('session_check')!='1':
                    state['_daily_cookie_action']={'name':cookie_name(store),'value':'','expires':0,'nonce':uuid.uuid4().hex}
            state['_daily_browser_checked']=True
            # A validated cookie already opened the UI; activity hydration need not rebuild it.
            if not already_authenticated:st.rerun()
    browser_session()
    if state.get('_daily_storage_failed'):
        st.warning('This browser blocked saving the daily session. You can use this open tab, but refresh may require sign-in. Allow site storage for this portal to enable same-day restore.')
    if st.query_params.get('session_check')=='1':
        with st.expander('Browser sign-in status',expanded=True):st.json(state.get('_daily_diagnostic',{'revision':REVISION}))
    # Do not show a false login or lose the token to a refresh before storage writes.
    if (not state.get('actor') and not state.get('_daily_browser_checked')) or state.get('_daily_cookie_action'):
        st.caption('Restoring your daily browser session…')
        if st.button('Retry browser restore',key='_daily_browser_retry'):
            state['_daily_browser_instance']=uuid.uuid4().hex
            state.pop('_daily_browser_checked',None)
            if isinstance(state.get('_daily_cookie_action'),dict):
                state['_daily_cookie_action']={**state['_daily_cookie_action'],'nonce':uuid.uuid4().hex}
            st.rerun()
        st.stop()



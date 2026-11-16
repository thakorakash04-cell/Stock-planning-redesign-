"""Browser-local theme for Streamlit's login and password forms; no SQL reads."""
import uuid
import streamlit as st
import streamlit.components.v2 as components
REVISION=2
STYLES={'existing':'Existing UI','glassmorphism':'Glassmorphism','spatial':'Spatial UI','neomorphism':'Neomorphism','liquid-glass':'Liquid Glass'}

BROWSER_JS="""export default function(component){
 const {data,setStateValue}=component;if(!data)return;
 const entry=window.__stockAppearance||(window.__stockAppearance={write:null,saved:null});
 const styles=['existing','glassmorphism','spatial','neomorphism','liquid-glass'];
 const read=key=>{try{return localStorage.getItem(key)}catch{return null}};
 const action=data.action;
 if(action&&entry.write!==action.nonce){
  const values={'stock-planning:theme':action.theme==='dark'?'dark':'light','stock-planning:ui-style':styles.includes(action.style)?action.style:'existing'};
  for(const [key,value] of Object.entries(values)){try{localStorage.setItem(key,value);document.cookie=key.replace(':','-')+'='+value+'; Path=/; Max-Age=31536000; SameSite=Lax'+(location.protocol==='https:'?'; Secure':'')}catch{}}
  entry.write=action.nonce;setStateValue('ack',action.nonce);
 }
 const style=read('stock-planning:ui-style');const saved={theme:read('stock-planning:theme')==='dark'?'dark':'light',style:styles.includes(style)?style:'existing'};
 const signature=JSON.stringify(saved);
 if(entry.instance!==data.instance||entry.saved!==signature){entry.instance=data.instance;entry.saved=signature;setStateValue('saved',saved)}
}"""

def controls():
 state=st.session_state
 state.setdefault('_portal_appearance_instance',uuid.uuid4().hex)
 if '_portal_theme_dark' not in state:state['_portal_theme_dark']=st.context.cookies.get('stock-planning-theme')=='dark'
 if '_portal_ui_style' not in state:
  saved=st.context.cookies.get('stock-planning-ui-style','existing')
  state['_portal_ui_style']=saved if saved in STYLES else 'existing'
 component=components.component('stock_appearance_preferences_v2',js=BROWSER_JS)
 action=state.get('_portal_appearance_action')
 result=component(data={'action':action,'instance':state['_portal_appearance_instance']},on_saved_change=lambda:None,on_ack_change=lambda:None,key='_stock_appearance_preferences',height=0)
 saved=getattr(result,'saved',None)
 if not action and isinstance(saved,dict):
  state['_portal_theme_dark']=saved.get('theme')=='dark'
  state['_portal_ui_style']=saved.get('style') if saved.get('style') in STYLES else 'existing'
 if action and getattr(result,'ack',None)==action['nonce']:state.pop('_portal_appearance_action',None)
 def changed():
  state['_portal_appearance_action']={'theme':'dark' if state['_portal_theme_dark'] else 'light','style':state['_portal_ui_style'],'nonce':uuid.uuid4().hex}
 left,right=st.columns([1,2])
 with left:dark=st.toggle('Dark theme',key='_portal_theme_dark',on_change=changed)
 with right:style=st.selectbox('UI style',list(STYLES),format_func=lambda key:STYLES[key],key='_portal_ui_style',on_change=changed)
 if style!='existing':
  background='#101821' if dark else '#edf6f7'
  surface='#182431' if dark else '#ffffff'
  shadow='0 12px 30px #02091155' if dark else '0 12px 30px #24494f22'
  radius='24px' if style=='liquid-glass' else '18px'
  if style=='neomorphism':shadow='6px 6px 16px #0c1520,-6px -6px 16px #2c3d50' if dark else '6px 6px 16px #cad5d7,-6px -6px 16px #ffffff'
  blur='backdrop-filter:blur(12px);' if style in ('glassmorphism','liquid-glass') else ''
  st.markdown('<style>.stApp,[data-testid="stMain"]{background:'+background+'!important}.st-key-portal_signin,[data-testid="stForm"]{background:'+surface+'!important;border-radius:'+radius+';box-shadow:'+shadow+';'+blur+'}</style>',unsafe_allow_html=True)
 if dark:
  st.markdown('''<style>
  html{color-scheme:dark}.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#101821!important;color:#e5edf5!important}
  [data-testid="stForm"],.st-key-portal_signin,[data-testid="stExpander"]{background:#182431!important;border-color:#53667b!important;color:#e5edf5!important}
  .stApp :is(h1,h2,h3,p,label,small,summary,span){color:#dbe6f0!important}
  .stApp input,.stApp textarea,[data-baseweb="input"],[data-baseweb="base-input"]{background:#101b28!important;color:#e5edf5!important;border-color:#53667b!important}
  .stApp button{background:#23384b!important;color:#e5edf5!important;border-color:#71889b!important}
  .stApp button[kind="primary"],.stApp button[kind="primaryFormSubmit"]{background:#0f766e!important;color:white!important}
  </style>''',unsafe_allow_html=True)

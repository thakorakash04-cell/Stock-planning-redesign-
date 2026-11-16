"""Shared account screens. All authorization is repeated by Store operations."""
import os,time,json
from datetime import datetime,timezone
import pandas as pd
import streamlit as st
from .store import Store,AccessDenied

APP_TITLE='Stock & Planning'
from .access import MENU_LABELS
PERMISSION_LABELS={'use_fiori':'Enable Fiori Launchpad UI', 'download': 'Download / export data', 'update_data': 'Upload and replace shared workbook', 'use_tools': 'Use Ask AI and Insights (share relevant records with Gemini)', 'view_product_details':'View imported Product Status details inside Planning', 'edit_production':'Edit ongoing production expected quantity and end date', 'edit_upcoming':'Add, edit and delete shared upcoming production plans', **{'menu_'+str(i):'Open '+label for i,label in enumerate(MENU_LABELS)}}
@st.cache_resource
def initialize(url,username,password,store_revision="2026-10-31-store-actor-v10"):
    # The revision invalidates pre-deployment cached Store instances.
    from .store import Store as CurrentStore
    store=CurrentStore(url);store.bootstrap_admin(username,password);return store

def sign_out(store=None,reason='logout'):
    store=store or st.session_state.get('_account_store')
    if store:
        if st.session_state.get('actor'):
            try:store.log_event(st.session_state.actor,reason)
            except AccessDenied:pass
        from daily_sessions import clear
        clear(store,st.session_state)
    else:st.session_state.clear()
    st.rerun()

def login_page(store):
    import importlib
    from . import portal_ui
    if getattr(portal_ui,'LOGIN_UI_REVISION',0)!=4:portal_ui=importlib.reload(portal_ui)
    return portal_ui.login_page(store,APP_TITLE)

def require_admin(store,actor):
    if store.identity(actor)['role']!='admin':raise AccessDenied('Administrator access required.')

def require_permission(store,actor,permission):
    return store.require_permission(actor,permission)

def format_time(value):
    from .clock import display
    return display(value) if value else 'Not recorded'

def user_page(store,actor):
    from .portal_console import render
    render(store,actor,'users')
    st.stop()

def password_page(store,actor):
    from . import theme as _theme
    if getattr(_theme,'REVISION',0)!=2:
        import importlib
        _theme=importlib.reload(_theme)
    controls=_theme.controls
    controls()
    st.title('Change password')
    st.caption('Enter your current password. After a successful change, all existing sessions are signed out, including this one.')
    with st.form('change_password',clear_on_submit=True):
        current=st.text_input('Current password',type='password',autocomplete='current-password')
        new=st.text_input('New password (at least 12 characters)',type='password',autocomplete='new-password')
        confirm=st.text_input('Confirm new password',type='password',autocomplete='new-password')
        submit=st.form_submit_button('Change password',type='primary')
    if submit:
        if new!=confirm:st.error('The new passwords do not match.')
        else:
            try:store.change_password(actor,current,new)
            except ValueError as exc:st.error(str(exc))
            else:
                from daily_sessions import clear
                clear(store,st.session_state);st.rerun()

def require_workspace():
    try:secrets=dict(st.secrets)
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError):secrets={}
    cfg={key:str(secrets.get(key,os.environ.get(key,''))) for key in ('DATABASE_URL','ADMIN_USERNAME','ADMIN_PASSWORD')}
    if not all(cfg.values()) or len(cfg['ADMIN_PASSWORD'])<12:
        st.title(APP_TITLE+' — setup');st.info('Set DATABASE_URL, ADMIN_USERNAME and ADMIN_PASSWORD in Streamlit Secrets. No default login is enabled.');st.stop()
    try:store=initialize(cfg['DATABASE_URL'],cfg['ADMIN_USERNAME'],cfg['ADMIN_PASSWORD'])
    except Exception:st.error('Cannot connect to the account database. Check Streamlit Secrets.');st.stop()
    from daily_sessions import restore_cookie,mount
    restore_cookie(store,st.session_state,st.context.cookies)
    mount(store)
    actor=st.session_state.get('actor')
    if actor is None:login_page(store)
    now=time.time()
    from daily_sessions import next_midnight
    expiry=getattr(actor,'expires_at',0) or next_midnight(st.session_state.get('login_at',now))
    if now>=expiry:sign_out(store,'session_expired')
    try:identity=store.identity(actor)
    except AccessDenied:sign_out()
    st.session_state.last_active=now
    st.session_state.workspace_role=identity['role'];st.session_state.workspace_permissions=identity['permissions']
    # This context remains server-side, never sent to the component/browser.
    st.session_state._account_store=store
    with st.sidebar:
        st.caption('Signed in as '+identity['username']+' · '+identity['role'])
        if st.button('Sign out',key='workspace_signout'):sign_out(store)
        password=st.toggle('Change password',key='workspace_password')
        manage=st.toggle('Manage users',key='workspace_users') if identity['role']=='admin' else False
    if password:password_page(store,actor);st.stop()
    if manage:user_page(store,actor);st.stop()
    store.record_access(actor,'Workspace')
    return store,actor,identity

def can(permission):
    store=st.session_state.get('_account_store');actor=st.session_state.get('actor')
    if not store or not actor:return False
    try:store.require_permission(actor,permission);return True
    except AccessDenied:return False

def can_export():return can('download')

def admin_download(*args,**kwargs):
    if not can_export():return False
    clicked=st.download_button(*args,**kwargs)
    if clicked:st.session_state._account_store.log_event(st.session_state.actor,'export','File download')
    return clicked

PRODUCTION_ACCESS_REVISION=7


ACCOUNT_SAVE_REVISION=4
THEME_REVISION=2



BROWSER_SESSION_REVISION=2




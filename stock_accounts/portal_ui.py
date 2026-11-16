"""Consistent account, recovery and administrator workspace screens."""
import os,json,time,html
LOGIN_UI_REVISION=4
import streamlit as st

def config():
    try:cfg=dict(st.secrets)
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError):cfg={}
    return {**os.environ,**cfg}

def send_email(to,subject,body,idempotency_key=None):
    from . import mail_transport
    if getattr(mail_transport,'SEND_REVISION',0)!=1:
        import importlib
        mail_transport=importlib.reload(mail_transport)
    return mail_transport.send(config(),to,subject,body,idempotency_key)

def login_page(store,title):
    from .branding import defaults,default_logo,install
    install(store)
    settings={**defaults(title),**store.portal_read(public=True)};title=settings.get('title') or title
    st.markdown("""<style>
    header[data-testid="stHeader"], [data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"]{display:none!important}
    [data-testid="stSidebar"]{background:#143c3d!important;color:white;min-width:48vw!important;max-width:48vw!important;width:48vw!important;transform:none!important;visibility:visible!important;position:sticky!important;top:0;height:100dvh!important}
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding:0 2rem!important}
    .portal-brand{min-height:100dvh;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:3rem 1rem;box-sizing:border-box}
    .portal-brand img{width:min(340px,85%);height:180px;object-fit:contain;margin:0 0 2.5rem}
    .portal-brand h1{font-size:clamp(2rem,3vw,3.5rem);color:white!important;line-height:1.15;margin:0 0 1.5rem}
    .portal-brand p{color:#b3d2d0;font-size:1.08rem;line-height:1.85;white-space:pre-line;max-width:540px;margin:0}
    .portal-brand small{color:#9bc8c3;letter-spacing:.18em;margin-top:2rem;font-size:.7rem}
    .stApp,[data-testid="stMain"]{background:#f4f8f7!important}
    [data-testid="stMainBlockContainer"],.block-container{padding:2.5rem clamp(1.5rem,4vw,5rem)!important;max-width:850px!important}
    .st-key-portal_signin{background:white;border:1px solid #dce7e5;border-radius:18px;padding:clamp(1.5rem,3vw,3.5rem)!important;margin-top:0}
    .st-key-portal_signin h1{color:#17333c!important;font-size:2.15rem!important}
    .st-key-portal_signin [data-testid="stForm"]{border:0!important;padding:0!important}
    .st-key-portal_signin input{min-height:48px}.st-key-portal_signin button[kind="primaryFormSubmit"]{background:#087e7a;border:0;min-height:48px}
    @media(max-width:760px){[data-testid="stAppViewContainer"]{flex-direction:column!important}[data-testid="stSidebar"]{position:relative!important;min-width:100%!important;max-width:100%!important;width:100%!important;height:auto!important}.portal-brand{min-height:0;padding:2rem 1rem}.portal-brand img{height:80px;margin-bottom:1rem}.portal-brand h1{font-size:1.8rem}.portal-brand small{margin-top:1rem}[data-testid="stMainBlockContainer"],.block-container{padding:1rem!important}}
    </style>""",unsafe_allow_html=True)
    from . import theme as _theme
    if getattr(_theme,'REVISION',0)!=2:
        import importlib
        _theme=importlib.reload(_theme)
    controls=_theme.controls
    controls()
    with st.sidebar:
        logo=settings.get('portal_logo') or default_logo(title)
        st.markdown('<div class="portal-brand"><img alt="Portal logo" src="'+html.escape(logo,quote=True)+'"><h1>'+html.escape(title)+'</h1><p>'+html.escape(settings.get('login_text') or defaults(title)['login_text'])+'</p><small>'+html.escape(settings.get('subtitle') or 'PRIVATE WORKSPACE')+'</small></div>',unsafe_allow_html=True)
    with st.container(key='portal_signin'):
        st.caption('PRIVATE / SECURE WORKSPACE')
        st.title(settings.get('signin_heading') or 'Sign in to continue')
        st.write(settings.get('signin_text') or defaults(title)['signin_text'])
        with st.form('login',clear_on_submit=True):
            identifier=st.text_input('Username or email',autocomplete='username',key='login_username')
            password=st.text_input('Password',type='password',autocomplete='current-password',key='login_password')
            submit=st.form_submit_button('Sign in',type='primary',width='stretch')
        if submit:
            actor=store.login(identifier,password)
            if actor:
                from daily_sessions import start
                start(store,st.session_state,actor);st.rerun()
            st.error('Invalid credentials, disabled account, or temporary lock. After repeated failures, wait 15 minutes.')
        with st.expander('Forgot password?'):
            with st.form('request_recovery'):
                who=st.text_input('Registered username or email');request=st.form_submit_button('Send reset code')
            if request:
                try:
                    cfg=config()
                    if not cfg.get('RESET_FROM_EMAIL') or not (cfg.get('RESEND_API_KEY') or all(cfg.get(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD'))):raise ValueError('Email recovery is not configured. Ask the administrator to reset your password.')
                    st.session_state.portal_reset=store.request_recovery(who,lambda email,code:send_email(email,title+' password reset',f'Your reset code is {code}. It expires in 10 minutes and can be used once.'))
                    st.success('If this is an active account with a registered email, a reset code has been sent.')
                except ValueError as exc:st.error(str(exc))
            if st.session_state.get('portal_reset'):
                with st.form('complete_recovery'):
                    code=st.text_input('8-digit reset code',max_chars=8);new=st.text_input('New password (at least 12 characters)',type='password');confirm=st.text_input('Confirm password',type='password');done=st.form_submit_button('Reset password')
                if done:
                    try:
                        if new!=confirm:raise ValueError('Passwords do not match.')
                        store.complete_recovery(*st.session_state.portal_reset,code,new);del st.session_state.portal_reset;st.success('Password changed. Sign in with your new password.')
                    except ValueError as exc:st.error(str(exc))
        st.caption('Accounts are created by your administrator.')
    st.stop()

def email_profiles(store,actor):
    st.subheader('Username and email sign in')
    users=store.users(actor);profiles=store.profiles(actor)
    username=st.selectbox('Account',[u['username'] for u in users])
    with st.form('account_emails'):
        email=st.text_input('Email address',value=profiles.get(username,''),key='profile_email_'+username)
        save=st.form_submit_button('Save email')
    if save:
        try:store.profile_email(actor,username,email);st.success('Email saved. Both username and email can be used with the existing password.');st.rerun()
        except ValueError as exc:st.error(str(exc))
    st.dataframe([{'Username':u['username'],'Email':profiles.get(u['username'],''),'Role':u['role'],'Active':bool(u['active'])} for u in users],hide_index=True,width='stretch')

def workspace_page(store,actor,title):
    store.identity(actor)
    settings=store.portal_read(actor)
    st.title('Workspace settings')
    with st.form('workspace_text'):
        heading=st.text_input('Portal title',settings.get('title',title));subtitle=st.text_input('Sidebar subtitle',settings.get('subtitle','OPERATIONS WORKSPACE'));login=st.text_area('Login sidebar text',settings.get('login_text',''))
        save=st.form_submit_button('Save workspace text')
    if save:store.portal_save(actor,{'title':heading,'subtitle':subtitle,'login_text':login});st.success('Workspace text saved.')
    st.subheader('Sidebar labels and order')
    names=getattr(store,'portal_navigation',[])
    old=settings.get('navigation') or [{'id':str(i),'label':name,'order':i} for i,name in enumerate(names)]
    import pandas as pd
    edited=st.data_editor(pd.DataFrame(old),disabled=['id'],hide_index=True,width='stretch',key='navigation_editor')
    st.caption('Edit labels and order numbers to move sections up or down. Section IDs remain fixed.')
    if st.button('Save sidebar'):
        rows=edited.to_dict('records')
        if any(not str(r['label']).strip() for r in rows):st.error('Every section needs a label.')
        else:
            try:
                for r in rows:r['order']=int(r['order'])
                store.portal_save(actor,{'navigation':rows});st.success('Sidebar updated. Return to the workspace to see changes.')
            except (ValueError,TypeError):st.error('Use whole numbers for sidebar order.')
    st.subheader('Additional segments')
    segments=st.text_area('One segment per line', '\n'.join(settings.get('segments',[])))
    st.caption('Additional labels appear in segment selectors. Rows still require matching Source.Name data; adding a label does not create stock or change calculations.')
    if st.button('Save segments'):store.portal_save(actor,{'segments':list(dict.fromkeys(x.strip() for x in segments.splitlines() if x.strip()))});st.success('Segments saved.')

def email_page(store,actor):
    settings=store.portal_read(actor);st.title('Email management')
    st.caption('Rules for the same recipient are combined into one report. Email credentials stay in Streamlit Secrets.')
    from .scheduled_delivery import DEFAULT_SCHEDULE,status
    from datetime import datetime
    schedule={**DEFAULT_SCHEDULE,**settings.get('email_schedule',{})}
    with st.form('daily_delivery_schedule'):
        st.subheader('Scheduled delivery')
        enabled=st.checkbox('Enable daily delivery',value=schedule['enabled'])
        daily_time=st.time_input('Daily time (IST)',value=datetime.strptime(schedule['time'],'%H:%M').time())
        save_schedule=st.form_submit_button('Save delivery schedule')
    if save_schedule:
        store.portal_save(actor,{'email_schedule':{'enabled':enabled,'time':daily_time.strftime('%H:%M')}})
        st.success('Delivery schedule saved.');st.rerun()
    st.caption('Checks run every minute while the portal is open, including the login screen. If asleep or closed, one latest overdue report per recipient is sent when the portal becomes active. Missed days are combined, using the latest saved data. Default: daily 09:00 IST.')
    delivery=status(store,actor)
    if delivery['error']:st.warning(delivery['error'])
    if delivery['last_slot']:st.caption('Last processed schedule: '+delivery['last_slot'])
    if delivery['jobs']:
        with st.expander('Scheduled delivery history'):st.dataframe(delivery['jobs'],hide_index=True,width='stretch')
    import pandas as pd
    rules=settings.get('email_rules',[])
    base=pd.DataFrame(rules,columns=['enabled','recipient','section','column','operator','value','message'])
    edited=st.data_editor(base,num_rows='dynamic',hide_index=True,width='stretch',column_config={'enabled':st.column_config.CheckboxColumn(default=True),'operator':st.column_config.SelectboxColumn(options=['>','<','=','contains'])},key='email_rules')
    st.caption('Section must match a saved worksheet name. Column must match its header. Operators: >, <, =, contains. All matching rules are grouped by recipient.')
    if st.button('Save email rules'):
        rows=json.loads(edited.to_json(orient='records'))
        if any(not r.get('recipient') or not __import__('re').fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',r['recipient']) or r.get('operator') not in ['>','<','=','contains'] for r in rows):st.error('Check recipient email and operator for every rule.')
        else:store.portal_save(actor,{'email_rules':rows});st.success('Rules saved.')
    if st.button('Preview grouped report'):
        from .portal_alerts import preview
        try:
            grouped=preview(store,actor)
            if not grouped:st.info('No saved rows match enabled rules.')
            for recipient,body in grouped.items():st.subheader(recipient);st.text(body)
        except ValueError as exc:st.error(str(exc))
    st.caption('Manual sending is also available below. Scheduled delivery uses the enabled rules saved above; it does not depend on your account being signed in. Uncertain SMTP outcomes are not resent automatically.')
    if st.button('Send matching reports',type='primary'):
        from .portal_alerts import dispatch
        try:count=dispatch(store,actor,send_email);st.success(f'{count} grouped reports sent.')
        except Exception:st.error('Delivery failed. Check email configuration and preview; no credentials are shown.')

def admin_portal(store,actor,title,page):
    from .portal_console import render
    render(store,actor,page)
    st.stop()


from __future__ import annotations
import stock_accounts.pending_sales as _pending_sales
if getattr(_pending_sales,'REVISION',0)!=3:
    import importlib as _pending_importlib
    _pending_sales=_pending_importlib.reload(_pending_sales)
import notification_format as _notification_format
import importlib as _format_importlib
if getattr(_notification_format,'REVISION',0)!=2:_format_importlib.reload(_notification_format)
import daily_sessions as _daily_sessions
import importlib as _daily_importlib
if getattr(_daily_sessions,'REVISION',0)!=11:_daily_importlib.reload(_daily_sessions)
from stock_accounts import notification_rules as _notification_rules
if getattr(_notification_rules,'REVISION',0)!=8:_daily_importlib.reload(_notification_rules)
from stock_accounts import bom_prices as _bom_prices
if getattr(_bom_prices,'REVISION',0)!=2:_daily_importlib.reload(_bom_prices)
from stock_accounts import product_catalog as _product_catalog
if getattr(_product_catalog,'REVISION',0)!=6:_daily_importlib.reload(_product_catalog)
from stock_accounts import segment_access as _segment_access
if getattr(_segment_access,'REVISION',0)!=2:_daily_importlib.reload(_segment_access)
from stock_accounts import workspace_delivery as _workspace_delivery
if getattr(_workspace_delivery,'REVISION',0)!=11 or getattr(_workspace_delivery,'PRODUCTION_CACHE_REVISION',0)!=2:_daily_importlib.reload(_workspace_delivery)
from stock_accounts import view_cache as _view_cache
if getattr(_view_cache,'REVISION',0)!=2:_daily_importlib.reload(_view_cache)
from stock_accounts import preload as _workspace_preload
if getattr(_workspace_preload,'REVISION',0)!=8:_daily_importlib.reload(_workspace_preload)
from stock_accounts import sales as _sales
if getattr(_sales,'REVISION',0)!=9:_daily_importlib.reload(_sales)
from stock_accounts import pnl_import as _pnl_import
if getattr(_pnl_import,'REVISION',0)!=3:_daily_importlib.reload(_pnl_import)
from stock_accounts import pnl as _pnl
if getattr(_pnl,'REVISION',0)!=9:_daily_importlib.reload(_pnl)
from stock_accounts import scheduled_delivery as _daily_schedule
if getattr(_daily_schedule,'ACTIVITY_REVISION',0)!=8:_daily_importlib.reload(_daily_schedule)
from stock_accounts import portal_alerts as _email_alerts, mail_transport as _email_transport
if getattr(_email_alerts,'EMAIL_FORMAT_REVISION',0)!=1:_daily_importlib.reload(_email_alerts)
if getattr(_email_transport,'SEND_REVISION',0)!=1:_daily_importlib.reload(_email_transport)
import os,time,logging,importlib
from datetime import datetime,timezone
import pandas as pd
import streamlit as st
# Update permission defaults even for Store objects cached before this deployment.
from stock_accounts import store as _account_module
if getattr(_account_module,'STORE_SCHEMA_REVISION',0)!=18:importlib.reload(_account_module)
from stock_accounts.store import Store,Actor,AccessDenied
from stock_accounts import access as _access
if len(_access.MENU_LABELS)!=14 or 'view_product_details' not in _access.PERMISSION_DEFAULTS or 'use_fiori' not in _access.PERMISSION_DEFAULTS:importlib.reload(_access)
from stock_accounts import account_admin as _pnl_account_admin
if getattr(_pnl_account_admin,'PNL_ACCESS_REVISION',0)!=4:importlib.reload(_pnl_account_admin)
from stock_accounts.access import PERMISSION_DEFAULTS
_account_module.DEFAULT_PERMISSIONS.update(PERMISSION_DEFAULTS)
import workbook as _workbook
if getattr(_workbook,'PRODUCTION_REVISION',0)!=1 or getattr(_workbook,'SEGMENT_REVISION',0)!=2:importlib.reload(_workbook)
from workbook import read_upload,TITLES,SPECS,forecast_summary,segment_map,segment_filter,related_tables
from tables import table_controls
# Streamlit may retain helper modules across a source update. Reload only an
# older analysis revision, in dependency order. Account identities survive the
# separate versioned storage reload above.
import importlib
from stock_accounts import lead_time as _lead_time
if getattr(_lead_time,'REVISION',0)!=4:importlib.reload(_lead_time)
import grounded_ai as _grounded_ai
if getattr(_grounded_ai,'TABLE_CONTEXT_REVISION',0)!=1:importlib.reload(_grounded_ai)
if getattr(_grounded_ai,'RESPONSE_STYLE_REVISION',0)!=1 or getattr(_grounded_ai,'QUERY_SCHEMA_REVISION',0)!=5:importlib.reload(_grounded_ai)
from stock_accounts import planning_assistant as _planning_assistant
from stock_accounts import cross_sheet as _cross_sheet
if getattr(_cross_sheet,'REVISION',0)!=5:importlib.reload(_cross_sheet)
if getattr(_planning_assistant,'RESPONSE_STYLE_REVISION',0)!=1 or getattr(_planning_assistant,'KNOWLEDGE_CATALOG_REVISION',0)!=88:importlib.reload(_planning_assistant)
from stock_accounts import calendar_group as _calendar_group
if getattr(_calendar_group,'REVISION',0)!=1:importlib.reload(_calendar_group)
from stock_accounts import monthly_kpi as _monthly_kpi, insight_conditions as _insight_conditions
for _helper in (_monthly_kpi,_insight_conditions):
    if getattr(_helper,'REVISION',0)!=1:importlib.reload(_helper)
import stock_accounts.preferences as _preferences
if getattr(_preferences,'REVISION',0)!=1:importlib.reload(_preferences)
import stock_accounts.table_columns as _table_columns
if getattr(_table_columns,'REVISION',0)!=9:importlib.reload(_table_columns)
from stock_accounts import insights as _insights, assistant_insights as _assistant, workspace_insights as _workspace
for _module in (_grounded_ai,_insights,_assistant,_workspace):
    if getattr(_module,'INSIGHTS_REVISION',0)!=(55 if _module is _workspace else 21 if _module is _assistant else 7 if _module is _insights else 4):
        importlib.reload(_module)
if getattr(_insights,'ATTENTION_REVISION',0)!=1:importlib.reload(_insights)
from stock_accounts import insight_refresh as _insight_refresh
if getattr(_insight_refresh,'REVISION',0)!=4:importlib.reload(_insight_refresh)
from stock_accounts import insight_memory as _insight_memory
if getattr(_insight_memory,'REVISION',0)!=9 or getattr(_insight_memory,'COMPACT_KPI_REVISION',0)!=2:importlib.reload(_insight_memory)
from stock_accounts import insight_kpi_edits as _insight_item_edits
if getattr(_insight_item_edits,'REVISION',0)!=2:importlib.reload(_insight_item_edits)
from stock_accounts import insight_display as _insight_display
if getattr(_insight_display,'REVISION',0)!=3:importlib.reload(_insight_display)
from stock_accounts import insight_jobs as _insight_jobs
if getattr(_insight_jobs,'REVISION',0)!=5:importlib.reload(_insight_jobs)
from stock_accounts import insight_dashboard as _insight_dashboard
if getattr(_insight_dashboard,'REVISION',0)!=10:importlib.reload(_insight_dashboard)
from stock_accounts import custom_insight as _custom_insight
if getattr(_custom_insight,'REVISION',0)!=6:importlib.reload(_custom_insight)
if getattr(_assistant,'INSIGHT_ATTENTION_REVISION',0)!=1 or getattr(_assistant,'CUSTOM_INSIGHT_REVISION',0)!=7:importlib.reload(_assistant)
if getattr(_assistant,'AI_EXPORT_REVISION',0)!=1 or getattr(_assistant,'PLANNING_ASSISTANT_REVISION',0)!=1:importlib.reload(_assistant)
from stock_accounts import branding as _branding
if getattr(_branding,'REVISION',0)!=5:importlib.reload(_branding)
from stock_accounts import portal_console as _console_ui
if getattr(_console_ui,'ADMIN_UI_REVISION',0)!=25:importlib.reload(_console_ui)
from stock_accounts import workspace as _base_workspace
if getattr(_base_workspace,'WORKSPACE_UI_REVISION',0)!=43:importlib.reload(_base_workspace)
# Refresh the dispatcher when an already-running process gains planning RPCs.
if getattr(_workspace,'PLANNING_REVISION',0)!=36:
    importlib.reload(_workspace)
from stock_accounts import planning as _planning, matched_export as _matched_export
for _module in (_planning,_matched_export):
    if getattr(_module,'TABLE_EXPORT_REVISION',0)!=(2 if _module is _matched_export else 4):
        importlib.reload(_module)
from stock_accounts import production_snapshot as _production_snapshot, order_snapshot as _order_snapshot, availability_cache as _availability_cache
if getattr(_production_snapshot,'REVISION',0)!=1:importlib.reload(_production_snapshot)
if getattr(_order_snapshot,'REVISION',0)!=2:importlib.reload(_order_snapshot)
if getattr(_availability_cache,'REVISION',0)!=3:importlib.reload(_availability_cache)
from stock_accounts import batch_availability as _batch_availability
if getattr(_batch_availability,'REVISION',0)!=2:importlib.reload(_batch_availability)
from stock_accounts import production as _production
if getattr(_production,'REVISION',0)!=15 or getattr(_production,'TRANSFER_CACHE_REVISION',0)!=1:importlib.reload(_production)
from stock_accounts.workspace_insights import render_exact_workspace,process_account_navigation,account_page_style
from stock_accounts import auth as _account_auth
if getattr(_account_auth,'BROWSER_SESSION_REVISION',0)!=2:importlib.reload(_account_auth)
if getattr(_account_auth,'THEME_REVISION',0)!=2:importlib.reload(_account_auth)
if getattr(_account_auth,'ACCOUNT_SAVE_REVISION',0)!=4:importlib.reload(_account_auth)
if getattr(_account_auth,'PRODUCTION_ACCESS_REVISION',0)!=7:importlib.reload(_account_auth)
from stock_accounts.auth import user_page as account_admin_page,password_page,initialize as initialize_account_store

st.set_page_config(page_title="Stock & Planning",page_icon="📦",layout="wide")
st.markdown("""<style>.block-container{padding-top:2rem;max-width:1900px}h1,h2,h3{color:#285e4c}div[data-testid='stMetric']{display:none}.stButton>button{border-radius:7px}div[data-testid='stDataFrame']{border:1px solid #e0e8e3;border-radius:8px}</style>""",unsafe_allow_html=True)

@st.cache_resource
def initialize(url,admin_username,admin_password):
    store=Store(url);store.bootstrap_admin(admin_username,admin_password);return store

def configuration():
    try:secrets=dict(st.secrets)
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError):secrets={}
    return {k:str(secrets.get(k,os.environ.get(k,""))) for k in ["DATABASE_URL","ADMIN_USERNAME","ADMIN_PASSWORD"]}

def sign_out():
    from daily_sessions import clear
    store=st.session_state.get('_account_store')
    if store:clear(store,st.session_state)
    else:st.session_state.clear()
    st.rerun()

def login_page(store):
    from stock_accounts import portal_ui
    if getattr(portal_ui,'LOGIN_UI_REVISION',0)!=4:importlib.reload(portal_ui)
    return portal_ui.login_page(store,'Stock & Planning')

def require_admin(store,actor):
    if store.identity(actor)["role"]!="admin":
        raise AccessDenied("Administrator access required.")

def upload_page(store,actor):
    require_admin(store,actor)
    st.title("Update workbook")
    st.write("Refresh All in Excel, save the workbook, then upload it. Saved worksheets and the embedded Power Pivot tables are read together.")
    file=st.file_uploader("Master workbook",type=["xlsx","zip"],help="Up to 25 MB. .xlsx or a previously prepared .stock.zip package.")
    if st.button("Validate and replace shared data",type="primary",disabled=file is None):
        require_admin(store,actor)
        try:
            with st.spinner("Reading worksheets and embedded model…"):
                dataset=read_upload(file.getvalue(),file.name)
                store.save_dataset(actor,file.name,dataset)
            st.success(f"Updated all seven views and {len(dataset['tables'])} model tables. All users see this shared version.")
            if not dataset["tables"]:st.warning("This workbook has no embedded model; only saved worksheet views are available.")
        except (ValueError,KeyError) as exc:
            st.error(str(exc))
        except AccessDenied:raise
        except Exception:
            st.error("The workbook could not be processed or saved. The previous dataset is still available. Confirm the workbook format and database connection.")

def user_page(store,actor):
    require_admin(store,actor)
    st.title("Manage viewer accounts")
    st.caption("Only the configured administrator can create, disable or reset viewer accounts.")
    users=store.users(actor)
    st.table(pd.DataFrame(users)[["username","role","active"]])
    with st.form("create_viewer",clear_on_submit=True):
        st.subheader("Create viewer")
        username=st.text_input("New viewer username")
        password=st.text_input("Initial password (at least 12 characters)",type="password")
        create=st.form_submit_button("Create viewer",type="primary")
    if create:
        try:store.create_viewer(actor,username,password);st.success("Viewer created. Share their credentials privately.")
        except ValueError as exc:st.error(str(exc))
    viewers=[r["username"] for r in users if r["role"]=="viewer"]
    if viewers:
        with st.form("update_viewer",clear_on_submit=True):
            st.subheader("Reset or enable/disable viewer")
            selected=st.selectbox("Viewer",viewers)
            action=st.selectbox("Action",["Reset password","Disable account","Enable account"])
            new_password=st.text_input("New password for reset only",type="password")
            update=st.form_submit_button("Apply change")
        if update:
            try:
                if action=="Reset password":store.update_viewer(actor,selected,password=new_password)
                else:store.update_viewer(actor,selected,active=action=="Enable account")
                st.success("Account updated. Existing sessions for this user have been revoked.")
            except ValueError as exc:st.error(str(exc))


def details_page(dataset,mapping,segment):
    selected=st.session_state.detail
    if st.button("← Back to table"):
        del st.session_state.detail
        st.session_state.grid_revision=st.session_state.get("grid_revision",0)+1
        st.rerun()
    code=selected["code"]
    st.title(str(code))
    st.caption(f"{selected['title']} · {selected['column']}")
    with st.expander("Selected row — all values"):
        st.table(pd.DataFrame([selected["row"]]))
    tables=dataset.get("tables",[])
    if not tables:
        st.info("No embedded model tables are available in this workbook.");return
    entire=st.radio("Record scope",["All related records","Entire workbook"],horizontal=True,key="detail_scope")=="Entire workbook"
    matched=related_tables(tables,code,entire)
    options=[t["name"] for t in matched]
    available=[t["name"] for t in matched if t["rows"]]
    default=options.index(available[0]) if available else 0
    table_name=st.selectbox("Source table",options,index=default,key="detail_table")
    t=next(t for t in matched if t["name"]==table_name)
    segment=st.selectbox("Segment (Source.Name)",["All segments"]+sorted({v for s in mapping.values() for v in s}),key="detail_segment")
    frame=segment_filter(pd.DataFrame(t["rows"],columns=t["headers"]),mapping,segment)
    st.caption("Every source column is available. Related records include components, parent products, batches and periods. The selected value is a saved/calculated worksheet result; DAX is not re-evaluated.")
    table_controls(frame,"detail_"+table_name)


def dashboard_page(store,actor,identity):
    current=store.get_dataset(actor)
    if not current:
        st.title("Stock & Planning")
        st.info("No workbook has been uploaded yet. The administrator must upload the refreshed Excel workbook.")
        return
    dataset=current["data"];mapping=segment_map(dataset.get("tables",[]))
    segment_names=sorted({v for values in mapping.values() for v in values})
    if "detail" in st.session_state:
        details_page(dataset,mapping,"All segments");return
    st.title("Stock & Planning")
    from stock_accounts.clock import display
    date=display(current["updated_at"])
    st.caption(f"{current['filename']} · Updated {date}")
    a,b=st.columns([2,1])
    title=a.selectbox("Worksheet view",TITLES)
    segment=b.selectbox("Segment (Source.Name)",["All segments"]+segment_names,key="main_segment")
    idx=TITLES.index(title);sheet=dataset["sheets"][idx]
    frame=pd.DataFrame(sheet["rows"],columns=sheet["headers"])
    frame=segment_filter(frame,mapping,segment)
    monthly=False
    if idx==4:
        monthly=st.radio("Forecast view",["Product totals","Monthly details"],horizontal=True)=="Monthly details"
        if not monthly:frame=forecast_summary(frame)
        st.caption("Pending quantity = total forecast − total transfers − current stock once per material. Monthly-detail filtered totals recalculate this formula.")
    elif idx in (5,6):st.caption("Source: "+SPECS[idx][0]+". Blanks and negative balances are retained.")
    filtered,selected=table_controls(frame,"main_"+str(idx)+"_"+str(monthly),selectable=True,forecast_monthly=idx==4 and monthly)
    if selected:
        row,column=selected
        code=row.get("Material") or row.get("Component")
        st.session_state.detail={"code":code,"row":row,"column":column,"title":title}
        st.rerun()
    st.caption("This app has no data-download links. Refresh in Excel before updating. Excel Power Query/DAX refresh does not run here.")


def main():
    if not st.get_option("client.disableDataExport"):
        st.error("Deployment requires client.disableDataExport = true in .streamlit/config.toml.");st.stop()
    cfg=configuration()
    if not all(cfg.values()) or len(cfg["ADMIN_PASSWORD"])<12 or cfg["ADMIN_PASSWORD"].startswith(("REPLACE_","CHANGE_")):
        st.title("Stock & Planning — deployment setup")
        st.info("The owner must configure DATABASE_URL, ADMIN_USERNAME and ADMIN_PASSWORD in Streamlit Cloud Secrets. See README.md and secrets.example.toml in the repository. No default password is enabled.")
        st.stop()
    try:store=initialize_account_store(cfg["DATABASE_URL"],cfg["ADMIN_USERNAME"],cfg["ADMIN_PASSWORD"],store_revision="2026-10-31-store-actor-v10");_branding.install(store)
    except Exception:
        st.error("Cannot initialize the account database. Check the database connection and admin settings in Streamlit Secrets.");st.stop()
    # Preserve an explicit connector request through login and query-param resets.
    if st.query_params.get('product360')=='1':
        st.session_state._product360_pending=True
        st.session_state._product360_skus=st.query_params.get('skus','')
    from daily_sessions import restore_cookie,mount
    st.session_state._account_store=store
    restore_cookie(store,st.session_state,st.context.cookies)
    mount(store)
    actor=st.session_state.get("actor")
    if not actor:login_page(store)
    now=time.time()
    event=st.session_state.get("exact_website_ui")
    if isinstance(event,dict) and isinstance(event.get("activity"),(int,float)):
        st.session_state.last_active=max(st.session_state.get("last_active",0),min(now,event["activity"]))
    from daily_sessions import next_midnight
    expiry=getattr(actor,'expires_at',0) or next_midnight(st.session_state.get('login_at',now))
    if now>=expiry:
        store.log_event(actor,"session_expired")
        sign_out()
    identity=store.identity(actor)
    from stock_accounts.scheduled_delivery import mount as mount_scheduled_delivery
    mount_scheduled_delivery(store)
    if isinstance(event,dict) and event.get('action')=='logout' and event.get('id')!=st.session_state.get('_ui_last_request'):
        st.session_state['_ui_last_request']=event['id']
        store.log_event(actor,'logout');sign_out()
    if st.query_params.get('product360')=='1' or st.session_state.get('_product360_pending'):
        from stock_accounts import product360 as _product360
        if getattr(_product360,'AUTH_RETURN_REVISION',0)!=1 or getattr(_product360,'SNAPSHOT_REVISION',0)!=6:importlib.reload(_product360)
        render_product360=_product360.render
        st.session_state.last_active=now
        render_product360(store,actor)
        return
    from stock_accounts.portal_console import process_console_close
    process_console_close(st.session_state)
    process_account_navigation(store,actor)
    if st.session_state.get('_account_page')=='uploads':
        st.session_state.pop('_account_page',None)
    if st.session_state.get('_account_page'):
        st.session_state.last_active=now
        if st.session_state._account_page=='password':
            account_page_style()
            if st.button('← Back to workspace'):
                del st.session_state._account_page;st.rerun()
            with st.container(height=750,border=False,key='account_scroll'):password_page(store,actor)
        else:
            from stock_accounts.portal_console import render
            render(store,actor,st.session_state._account_page)
        return
    # Open the original workspace automatically after authentication/navigation.
    render_exact_workspace(store,actor,identity)

try:
    main()
except AccessDenied as exc:
    from daily_sessions import clear,session_valid
    store=st.session_state.get('_account_store')
    if store and session_valid(store,st.session_state.get('actor')):
        st.error(str(exc))
        if st.button('Return to workspace',key='access_denied_return'):
            st.session_state.pop('_account_page',None);st.session_state.pop('exact_website_ui',None);st.rerun()
        st.stop()
    if store:clear(store,st.session_state)
    else:st.session_state.clear()
    st.warning("Your session is no longer active. Sign in again.")
    st.stop()
except Exception:
    logging.getLogger(__name__).exception("Stock Planning request failed")
    st.error("The server connection was interrupted. Your browser login is retained. Reconnect before retrying a change; it may already have completed.")
    if st.button("Reconnect",key="connection_retry"):st.rerun()
    st.stop()










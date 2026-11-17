"""Serve the original React interface through Streamlit's authenticated session."""
from __future__ import annotations
import base64
from datetime import datetime,timezone
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from .store import AccessDenied
from workbook import read_upload,SPECS,segment_map

_component=components.declare_component("stock_planning_web_ui_session_recovery_v57",path=str(Path(__file__).resolve().parents[1]/"frontend_dist"))
# Keep existing v56 iframe URLs resolvable through the v57 rollout.
_legacy_component=components.declare_component("stock_planning_web_ui_cached_views_v56",path=str(Path(__file__).resolve().parents[1]/"frontend_dist"))


def ui_payload(current,identity=None,overrides=()):
    from .access import allowed
    if current:
        from .model_views import apply as model_views
        dataset=model_views(current["data"])
        from .lead_time import build,purchasing,with_average
        lead,averages=build(dataset)
        purchase=purchasing(dataset,averages,current,overrides)
        dataset={**dataset,'sheets':[purchase if i==5 and purchase else with_average(sheet,dataset,averages) if i==6 else sheet for i,sheet in enumerate(dataset['sheets'])]}
        if identity and not allowed(identity,9):lead={**lead,'rows':[]}
        if identity:
            dataset={**dataset,'sheets':[{**sheet,'rows':sheet['rows'] if allowed(identity,i) else []} for i,sheet in enumerate(dataset['sheets'])]}
        mapping=segment_map(dataset.get("tables",[]))
        return {"accessibleTabs":[i for i in range(14) if not identity or allowed(identity,i)],"filename":current["filename"],"updatedAt":datetime.fromtimestamp(current["updated_at"],tz=timezone.utc).isoformat(),"planningRevision":str([(r["id"],r["revision"],r["updated_at"]) for r in overrides if r["kind"]=="ongoing" ]),"leadTime":lead,"asOf":"Saved Excel results","sheets":dataset["sheets"],"segmentMap":{k:sorted(v) for k,v in mapping.items()}},dataset.get("tables",[]),current["version"]
    return {"accessibleTabs":[i for i in range(14) if not identity or allowed(identity,i)],"filename":"No workbook uploaded yet","updatedAt":None,"asOf":"—","sheets":[{"name":s[0],"headers":["Material","Description"],"rows":[]} for s in SPECS],"segmentMap":{}},[],"empty"

def workspace_payload(store,actor,*,cached_only=False):
    # The deployed insights dispatcher must use the same authenticated bootstrap
    # as the base workspace; do not maintain a second, diverging payload cache.
    from .workspace import workspace_payload as shared_payload
    return shared_payload(store,actor,cached_only=cached_only)


def handle_request(store,actor,event):
    if event.get('display_cache') is True and event.get('action') in ('production_status','planning_status','pnl_report'):
        from . import view_cache
        if getattr(view_cache,'REVISION',0)!=2:
            import importlib
            view_cache=importlib.reload(view_cache)
        clean={k:v for k,v in event.items() if k not in ('display_cache','known_stamp')}
        return view_cache.read(store,actor,event,lambda:_handle_request(store,actor,clean))
    return _handle_request(store,actor,event)

def _handle_request(store,actor,event):
    """Never trust frontend visibility or a client-supplied role."""
    identity=store.identity(actor)
    action=event.get("action")
    if action=="meril_stock_records":
        from .meril_stock import records
        return records(store,actor,event)
    if action in ('table_column_plan','table_columns_resolve','table_column_records'):
        from .table_columns import handle
        return handle(store,actor,event)
    if action=='uploads_status':
        from . import upload_center
        if getattr(upload_center,'REVISION',0)!=2:
            import importlib
            upload_center=importlib.reload(upload_center)
        return upload_center.metadata(store,actor,event.get('include_versions') is True)
    if action in ('pending_sales_read','pending_sales_records','pending_sales_upload'):
        from .pending_sales import read,records,save
        if action=='pending_sales_read':
            from .access import require_menu
            require_menu(store,actor,13)
        return save(store,actor,event) if action=='pending_sales_upload' else records(store,actor,event) if action=='pending_sales_records' else read(store,actor,event)
    if action=='workspace_bootstrap':return {'ok':True}
    if action=='workspace_model_tables':
        from .workspace_delivery import model_tables
        return model_tables(store,actor,event)
    if action=='workspace_preload':
        from .preload import load_after_paint
        return load_after_paint(store,actor,st.session_state,event)
    if action=='product_detail':
        from .product_catalog import read_detail
        return read_detail(store,actor,event)
    if action=='workspace_preload_ack':
        from .preload import acknowledge
        return acknowledge(store,actor,event,st.session_state)
    if action=='heartbeat':
        from .preload import versions
        return {'ok':True,'sourceVersions':versions(store,actor)}
    if isinstance(action,str) and action.startswith('sales_'):
        from .sales import handle
        return handle(store,actor,event)
    if isinstance(action,str) and action.startswith('pnl_'):
        from .pnl import handle
        return handle(store,actor,event)
    if action=="preferences_save":
        from .preferences import save
        return save(store,actor,event)
    from .access import require_menu
    if action=='issue_slip_dataset':
        from . import issue_slip
        if getattr(issue_slip,'REVISION',0)!=3:
            import importlib
            issue_slip=importlib.reload(issue_slip)
        return issue_slip.read(store,actor,event)
    if action=='production_history':
        from .production_history import read as history
        return history(store,actor,event)
    if action=='production_delete':
        from .production import delete
        return delete(store,actor,event)
    if action=='production_availability_all':
        from .batch_availability import check
        return check(store,actor,event)
    if action=='production_availability':
        from .production import check_availability
        return check_availability(store,actor,event)
    if action in ('production_status','production_save'):
        from .production import read,save
        return read(store,actor) if action=='production_status' else save(store,actor,event)
    if action in ('planning_status','planning_calculate'):require_menu(store,actor,6)
    if action=='planning_table_export':require_menu(store,actor,5 if event.get('source')=='forecast_purchasing' else 6)
    if action=='matched_export':
        index=event.get('tab')
        if type(index) is not int or not 0<=index<7:raise ValueError('Invalid section.')
        require_menu(store,actor,index)
    if action in ('ask_ai','ai_clear','ai_export','ai_records'):require_menu(store,actor,7)
    if action=='ai_status':
        from .access import allowed
        if not (allowed(identity,7) or allowed(identity,8)):require_menu(store,actor,7)
    if action in ('filter_dashboard','save_dashboard','generate_insights','insight_records','add_insight_chart','filter_insights','insight_filter_values','delete_insight_chart','save_insight_item'):require_menu(store,actor,8)

    if action=="planning_table_export":
        from .planning import export_planning_table
        return export_planning_table(store,actor,event)
    if action=="matched_export":
        from .matched_export import export_matched
        return export_matched(store,actor,event)
    if action in ("planning_status","planning_calculate"):
        from .planning import handle_planning
        return handle_planning(store,actor,event)
    if action in ('ai_status','ask_ai','ai_clear','ai_export','ai_records','filter_dashboard','save_dashboard','generate_insights','insight_records','add_insight_chart','filter_insights','insight_filter_values','delete_insight_chart','save_insight_item'):
        from .assistant_insights import handle_ai
        return handle_ai(store,actor,event)
    if action in ("heartbeat","refresh","ack"):
        return {"ok":True}
    if action=="logout":
        store.log_event(actor,"logout")
        return {"logout":True}
    if action=="open_password":return {"route":"password"}
    if action=="view":
        index=event.get("tab")
        if type(index) is not int or not 0<=index<len(SPECS):raise ValueError("Unknown view.")
        require_menu(store,actor,index)
        store.record_access(actor,SPECS[index][0]);return {"ok":True}
    if action=="export":
        store.log_event(actor,"export","Table export");return {"ok":True}
    if action=="upload_preview":
        store.require_permission(actor,"update_data")
        content=event.get('content','')
        if not isinstance(content,str) or len(content)>34_000_000:raise ValueError('Choose a workbook under 25 MB.')
        dataset=read_upload(base64.b64decode(content,validate=True),str(event.get('filename','workbook.xlsx'))[:255])
        current=store.get_dataset(actor)
        from .comparison import compare
        return {'comparison':compare(current['data'] if current else None,dataset)}
    if action=="upload":
        store.require_permission(actor,"update_data")
        content=event.get("content","")
        if not isinstance(content,str) or len(content)>34_000_000:raise ValueError("Choose a workbook under 25 MB.")
        raw=base64.b64decode(content,validate=True)
        dataset=read_upload(raw,str(event.get("filename","workbook.xlsx"))[:255])
        store.save_dataset(actor,str(event.get("filename","workbook.xlsx"))[:255],dataset)
        return {"ok":True}
    if identity["role"]!="admin":raise AccessDenied("Administrator access required.")
    if action in ("open_settings","open_email","open_history","open_workbook","open_uploads"):return {"route":action.removeprefix("open_")}
    if action=="open_admin":return {"route":"admin"}
    if action=="list_users":
        return {"users":store.users(actor)}
    if action=="create_viewer":
        store.create_viewer(actor,str(event.get("username","")),str(event.get("password","")))
        return {"ok":True}
    if action=="update_viewer":
        username=str(event.get("username",""));operation=event.get("operation")
        if operation=="reset":store.update_viewer(actor,username,password=str(event.get("password","")))
        elif operation in ("disable","enable"):store.update_viewer(actor,username,active=operation=="enable")
        else:raise ValueError("Unknown account operation.")
        return {"ok":True}
    raise ValueError("Unknown operation.")

def process_account_navigation(store,actor):
    event=st.session_state.get("exact_website_ui")
    if not isinstance(event,dict) or event.get('action') not in ('open_admin','open_password','open_settings','open_email','open_history','open_workbook','open_uploads'):return
    if not isinstance(event.get('id'),str) or event['id']==st.session_state.get('_ui_last_request'):return
    st.session_state._ui_last_request=event['id']
    if event.get('theme') in ('dark','light'):st.session_state['_portal_theme_dark']=event['theme']=='dark'
    try:
        result=handle_request(store,actor,event)
        st.session_state._account_page=result['route']
        st.session_state._ui_response={'id':event['id'],'body':result}
    except AccessDenied as exc:
        st.session_state._ui_response={'id':event['id'],'body':None,'error':str(exc)}

def account_page_style():
    st.markdown("""<style>
    .stAppViewContainer{height:100dvh!important;overflow:hidden!important}
    .stMain{height:100dvh!important;min-height:0!important;overflow-y:auto!important}
    .st-key-account_scroll{max-height:calc(100dvh - 150px)!important;overflow-y:auto!important;overscroll-behavior:contain;scrollbar-gutter:stable}
    .stMainBlockContainer,.block-container{max-width:1500px!important;margin:0 auto!important;padding:2rem!important}
    div[data-testid='stVerticalBlock']{gap:1rem!important}
    header[data-testid='stHeader']{display:block!important}
    </style>""",unsafe_allow_html=True)

def _render_exact_workspace(store,actor,identity):
    identity=store.identity(actor)
    st.session_state.pop('_portal_appearance_instance',None)
    # Login remains Streamlit-native; after sign-in there is only one sidebar:
    # the original website's sidebar inside the full-width component.
    st.markdown("""<style>
    body:has(iframe[title*="stock_planning_web_ui"]) header[data-testid="stHeader"],body:has(iframe[title*="stock_planning_web_ui"]) section[data-testid="stSidebar"],body:has(iframe[title*="stock_planning_web_ui"]) div[data-testid="stToolbar"],body:has(iframe[title*="stock_planning_web_ui"]) #MainMenu,body:has(iframe[title*="stock_planning_web_ui"]) footer{display:none!important}
    body:has(iframe[title*="stock_planning_web_ui"]) .stAppViewContainer,body:has(iframe[title*="stock_planning_web_ui"]) .stMain,body:has(iframe[title*="stock_planning_web_ui"]) .block-container{padding:0!important;margin:0!important;max-width:none!important}
    body:has(iframe[title*="stock_planning_web_ui"]) .stMainBlockContainer{padding:0!important;max-width:none!important}
    body:has(iframe[title*="stock_planning_web_ui"]) .stMain{height:100dvh;overflow:hidden!important}
    body:has(iframe[title*="stock_planning_web_ui"]) div[data-testid="stElementContainer"]:has(iframe){line-height:0}
    body:has(iframe[title*="stock_planning_web_ui"]) div[data-testid="stVerticalBlock"]{gap:0!important}
    body:has(iframe[title*="stock_planning_web_ui"]) div[data-testid="stElementContainer"]:has(iframe){width:100%!important}
    body:has(iframe[title*="stock_planning_web_ui"]) iframe[title*="stock_planning_web_ui"]{width:100%;border:0}
    /* The iframe owns its loading state. Streamlit's stale fade makes a
       live dashboard appear blank during heartbeat, logging and upload RPCs. */
    div[data-testid="stElementContainer"][data-stale="true"]:has(iframe[title*="stock_planning_web_ui"]),div[data-testid="stVerticalBlock"][data-stale="true"]:has(iframe[title*="stock_planning_web_ui"]){opacity:1!important;filter:none!important;transition:none!important}
    </style>""",unsafe_allow_html=True)
    # Read the existing widget value before rendering. A component event already
    # reruns Streamlit; handling it here returns the response in that same run.
    event=st.session_state.get("exact_website_ui")
    if isinstance(event,dict) and isinstance(event.get("id"),str) and event["id"]!=st.session_state.get("_ui_last_request"):
        st.session_state._ui_last_request=event["id"]
        try:
            result=handle_request(store,actor,event)
            if result.get("route"):
                st.session_state._account_page=result["route"];st.rerun()
            if result.get("logout"):
                from daily_sessions import clear
                clear(store,st.session_state);st.rerun()
            st.session_state._ui_response={"id":event["id"],"body":result}
        except (ValueError,AccessDenied) as exc:
            st.session_state._ui_response={"id":event["id"],"body":None,"error":str(exc)}
        except Exception:
            st.session_state._ui_response={"id":event["id"],"body":None,"error":"The request failed. Check the workbook or database connection; your previous data is unchanged."}
    store.record_access(actor,"Workspace")
    startup_meter=st.empty()
    first_start=st.session_state.get('_workspace_startup_meter_done')!=actor.session_id
    if first_start:startup_meter.progress(0,text='Loading your saved workbook · 0%')
    response=st.session_state.get('_ui_response') or {}
    fast_reply=isinstance(event,dict) and event.get('action') in ('save_insight_item','delete_insight_chart','filter_insights','insight_filter_values') and response.get('id')==event.get('id') and not response.get('error')
    data,tables,version=workspace_payload(store,actor,cached_only=True) if fast_reply else workspace_payload(store,actor)
    # Routine replies carry a compact signature. A browser without a retained
    # copy can request an authenticated bootstrap recovery.
    from .preferences import read as read_preferences
    preferences=read_preferences(store,actor)
    from .workspace_delivery import access_scope
    from .access import allowed
    initial={'deferred':allowed(identity,10) or allowed(identity,11),'scope':access_scope(identity)}
    from .workspace_delivery import payload as delivery_payload
    delivery=delivery_payload(st.session_state,event,data,tables,version,identity)
    _component(preferences=preferences,preload=initial,**delivery,version=version,user=identity["username"],role=identity["role"],permissions=identity["permissions"],response=st.session_state.get("_ui_response"),default=None,key="exact_website_ui")
    if first_start:
        st.session_state['_workspace_startup_meter_done']=actor.session_id
        startup_meter.empty()

# Increment with analysis protocol changes to invalidate hot-deployment helpers.
INSIGHTS_REVISION=56

PLANNING_REVISION=36





@st.fragment
def render_exact_workspace(store,actor,identity):
    """Keep normal component RPCs out of the outer login/navigation app rerun."""
    try:_render_exact_workspace(store,actor,identity)
    except AccessDenied:
        from daily_sessions import clear
        clear(store,st.session_state);st.rerun()
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Workspace connection failed')
        st.error('The workspace connection was interrupted. Your browser login is retained. Reconnect before retrying a change; it may already have completed.')
        if st.button('Reconnect workspace',key='workspace_fragment_reconnect'):st.rerun()





"""Serve the original React interface through Streamlit's authenticated session."""
from __future__ import annotations
import base64
from datetime import datetime,timezone
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from .store import AccessDenied
from workbook import read_upload,SPECS,segment_map

_component=components.declare_component("stock_planning_web_ui_business_dashboard_v20",path=str(Path(__file__).resolve().parents[1]/"frontend_dist"))

def ui_payload(current,identity=None,overrides=()):
    from .access import allowed
    if current:
        from .model_views import apply as model_views
        dataset=model_views(current["data"])
        from .lead_time import build,purchasing,with_average
        from .bom_prices import with_prices
        lead,averages=build(dataset)
        purchase=purchasing(dataset,averages,current,overrides)
        dataset={**dataset,'sheets':[with_prices(sheet,dataset) if i==1 else purchase if i==5 and purchase else with_average(sheet,dataset,averages) if i==6 else sheet for i,sheet in enumerate(dataset['sheets'])]}
        if identity and not allowed(identity,9):lead={**lead,'rows':[]}
        if identity:
            dataset={**dataset,'sheets':[{**sheet,'rows':sheet['rows'] if allowed(identity,i) else []} for i,sheet in enumerate(dataset['sheets'])]}
        mapping=segment_map(dataset.get("tables",[]))
        return {"accessibleTabs":[i for i in range(14) if not identity or allowed(identity,i)],"filename":current["filename"],"updatedAt":datetime.fromtimestamp(current["updated_at"],tz=timezone.utc).isoformat(),"planningRevision":str([(r["id"],r["revision"],r["updated_at"]) for r in overrides if r["kind"]=="ongoing" ]),"leadTime":lead,"asOf":"Saved Excel results","sheets":dataset["sheets"],"segmentMap":{k:sorted(v) for k,v in mapping.items()}},dataset.get("tables",[]),current["version"]
    return {"accessibleTabs":[i for i in range(14) if not identity or allowed(identity,i)],"filename":"No workbook uploaded yet","updatedAt":None,"asOf":"—","sheets":[{"name":s[0],"headers":["Material","Description"],"rows":[]} for s in SPECS],"segmentMap":{}},[],"empty"

def workspace_payload(store,actor,*,cached_only=False):
    # Check authorization and the shared version even when a session has cached data.
    # Streamlit can retain a Store instance from before a hot deployment.
    # Use its established database API rather than a newly added class method.
    with store.transaction() as db:
        store.require(db,actor)
        row=store.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
        revision=(row['version'],row['updated_at']) if row else None
    identity=store.identity(actor)
    from .workspace_delivery import retained_get,retained_put,access_scope,REVISION as DELIVERY_REVISION
    if cached_only:
        cached=st.session_state.get('_workspace_payload')
        # Only successful, already version-validated Insight interactions use
        # this branch. Access, session and workbook metadata are still checked.
        if cached and len(cached[0])==9 and cached[0][:4]==(actor.username,actor.session_id,revision,str(identity['permissions'])) and cached[0][4]==28 and cached[0][7]==str(identity.get('allowedSegments')):
            payload,tables,version=cached[1]
            return decorate_workspace(store,actor,payload,identity=identity),tables,version
    from .production import shared
    overrides=shared(store,actor)
    supply_revision=tuple((r['id'],r['revision'],r['updated_at']) for r in overrides if r['kind']=='ongoing')
    production_revision=str([(r['kind'],r['id'],r['revision'],r['updated_at']) for r in overrides])
    from .product_catalog import metadata,read as read_product_catalog
    catalog_version=metadata(store,actor)
    from .access import allowed
    from .availability_cache import revision as availability_revision
    availability_key=availability_revision(store,actor,revision,identity) if allowed(identity,3) else ''
    key=(actor.username,actor.session_id,revision,str(identity['permissions']),28,supply_revision,production_revision,str(identity.get('allowedSegments')),availability_key)
    cached=st.session_state.get('_workspace_payload')
    if not cached or cached[0]!=key:
        retained_key=(DELIVERY_REVISION,access_scope({**identity,'username':actor.username}),revision,supply_revision,production_revision,availability_key)
        retained=retained_get(store,retained_key)
        if retained is not None:
            st.session_state['_workspace_payload']=(key,retained)
            payload,tables,version=retained
            return decorate_workspace(store,actor,payload,catalog_version,identity=identity),tables,version
        current=store.get_dataset(actor)
        if current:
            from .production_snapshot import read as snapshot
            snapshot(store,actor,current)
        from .workspace_delivery import prepared
        payload,tables,version=prepared(store,current,identity,overrides,ui_payload)
        from .access import allowed
        if current and allowed(identity,3):
            from .production import read as production_read
            payload={**payload,'production':production_read(store,actor,current=current,saved=overrides),'productionRevision':production_revision}
        if current and allowed(identity,6):
            from .order_snapshot import read as order_snapshot
            payload={**payload,'orderRequirements':order_snapshot(store,actor,current)}
        cached=(key,(payload,tables,version))
        st.session_state['_workspace_payload']=cached
        retained_put(store,retained_key,cached[1])
    payload,tables,version=cached[1]
    return decorate_workspace(store,actor,payload,catalog_version,identity=identity),tables,version

def decorate_workspace(store,actor,payload,catalog_version=None,identity=None):
    from .product_catalog import metadata,read as read_product_catalog
    if catalog_version is None:catalog_version=metadata(store,actor)
    identity=identity or store.identity(actor)
    from .access import allowed
    # Menu metadata is live even when the expensive rows predate a deployment.
    payload={**payload,'accessibleTabs':[i for i in range(14) if allowed(identity,i)]}
    cached=st.session_state.get('_workspace_payload')
    key=cached[0] if cached else None
    if payload.get('production') and isinstance(key,tuple) and len(key)==9:
        from .view_cache import production_stamp
        stamp=production_stamp(identity,key[2],key[6],key[8])
        payload={**payload,'production':{**payload['production'],'displayStamp':stamp}}
    from .pending_sales import read as pending_read
    pending=pending_read(store,actor) if 0 in payload.get('accessibleTabs',[]) else None
    catalogue=read_product_catalog(store,actor,catalog_version)
    from .product_catalog import enrich_display
    payload,pending=enrich_display(payload,pending,catalogue)
    from .meril_stock import enrich as meril_enrich
    payload=meril_enrich(store,actor,payload,identity)
    return {**payload,'pendingSales':pending,'productCatalogue':catalogue,'workspaceRevision':6,'portal':{k:v for k,v in store.portal_read(actor).items() if k in ('title','subtitle','segments','navigation')}}

def handle_request(store,actor,event):
    """Never trust frontend visibility or a client-supplied role."""
    identity=store.identity(actor)
    action=event.get("action")
    if action=="meril_stock_records":
        from .meril_stock import records
        return records(store,actor,event)
    if action in ('table_column_plan','table_columns_resolve'):
        from .table_columns import handle
        return handle(store,actor,event)
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
    if action in ('open_admin','open_password','open_settings','open_email','open_history','open_workbook'):
        # Preserve the latest table view without delaying navigation behind
        # another component round trip. Invalid preferences never block a page.
        from .preferences import save
        pending=event.get('preferences',[])
        if isinstance(pending,list):
            for preference in pending[:30]:
                if isinstance(preference,dict):
                    try:save(store,actor,preference)
                    except ValueError:pass
    if action=="preferences_save":
        from .preferences import save
        return save(store,actor,event)
    from .access import require_menu
    if action=='production_history':
        from .production_history import read as history
        return history(store,actor,event)
    if action=='production_delete':
        from .production import delete
        return delete(store,actor,event)
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
    if action in ('generate_insights','insight_records','add_insight_chart','filter_insights','insight_filter_values','delete_insight_chart'):require_menu(store,actor,8)

    if action=="planning_table_export":
        from .planning import export_planning_table
        return export_planning_table(store,actor,event)
    if action=="matched_export":
        from .matched_export import export_matched
        return export_matched(store,actor,event)
    if action in ("planning_status","planning_calculate"):
        from .planning import handle_planning
        return handle_planning(store,actor,event)
    if action in ('generate_insights','insight_records','add_insight_chart','filter_insights','insight_filter_values','delete_insight_chart'):
        from .assistant_insights import handle_ai
        return handle_ai(store,actor,event)
    if action in ('ai_status','ask_ai','ai_clear','ai_export','ai_records'):
        from .assistant import handle_ai
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
    if action in ("open_settings","open_email","open_history","open_workbook"):return {"route":action.removeprefix("open_")}
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
    if not isinstance(event,dict) or event.get('action') not in ('open_admin','open_password','open_settings','open_email','open_history','open_workbook'):return
    if not isinstance(event.get('id'),str) or event['id']==st.session_state.get('_ui_last_request'):return
    st.session_state._ui_last_request=event['id']
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

def render_exact_workspace(store,actor,identity):
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
    div[data-testid="stElementContainer"][data-stale="true"]:has(iframe[title*="stock_planning_web_ui"]){opacity:1!important;filter:none!important;transition:none!important}
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
    data,tables,version=workspace_payload(store,actor)
    # Routine replies carry a compact signature. A browser without a retained
    # copy can request an authenticated bootstrap recovery.
    from .preferences import read as read_preferences
    preferences=read_preferences(store,actor)
    from .preload import bundle
    initial=bundle(store,actor,preferences,st.session_state)
    from .workspace_delivery import payload as delivery_payload
    delivery=delivery_payload(st.session_state,event,data,tables,version,identity)
    _component(preferences=preferences,preload=initial,**delivery,version=version,user=identity["username"],role=identity["role"],permissions=identity["permissions"],response=st.session_state.get("_ui_response"),default=None,key="exact_website_ui")


WORKSPACE_UI_REVISION=44





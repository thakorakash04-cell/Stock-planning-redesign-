"""Authenticated, SKU-scoped Product 360 workbook bridge."""
from __future__ import annotations
import re
from .store import AccessDenied
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_REVISION=6
AUTH_RETURN_REVISION=1
HUB='https://product-launch-hub.sweetcoati16.chatgpt.site'

def snapshot(store,actor,request):
    # Moving workbook data to another application is an export. Keep existing
    # download permission and per-menu permissions authoritative on the server.
    identity=store.require_permission(actor,'download')
    if identity['role']!='admin':raise AccessDenied('Planning synchronization requires the planning administrator.')
    from .access import allowed
    if not isinstance(request,dict):raise ValueError('Invalid connection request.')
    nonce=request.get('nonce','')
    if not isinstance(nonce,str) or not re.fullmatch(r'[a-f0-9]{32}',nonce):raise ValueError('Invalid connection nonce.')
    codes=request.get('skus')
    if not isinstance(codes,list) or not codes or len(codes)>5000 or any(not isinstance(x,str) or not x or len(x)>100 for x in codes):raise ValueError('Add confirmed SKU mappings in Product 360 before connecting.')
    wanted=set(codes)
    current=store.get_dataset(actor)
    if not current:raise ValueError('No workbook has been uploaded.')
    sheets=[]
    for i,sheet in enumerate(current['data'].get('sheets',[])):
        if not allowed(identity,i):continue
        if i not in (0,1,2,3):
            labels={re.sub(r'[^a-z0-9]','',str(h).lower()) for h in sheet['headers']}
            if not labels.intersection({'stddp','stddpvalue','stddpprice','stddprate','standarddp','standarddpvalue','standarddistributorprice','standarddealerprice','dp','dpvalue','dpprice','dprate','distributorprice','dealerprice','distributionprice','dpinr','dprs','mrp','mrpvalue','mrpprice','mrprate','maximumretailprice','mrpinr','mrprs'}):continue
        if i==1:
            from .bom_prices import with_prices
            sheet=with_prices(sheet,current['data'])
        headers=sheet['headers']
        key=next((j for j,h in enumerate(headers) if str(h).strip().lower() in ('material','material number','sku','material code','sku code')),None)
        if key is None:continue
        rows=[r for r in sheet['rows'] if len(r)>key and str(r[key]).strip() in wanted]
        sheets.append({'name':sheet['name'],'headers':headers,'rows':rows,'skuColumn':key})
    from .snapshot_sales import snapshot_sales
    sales_sheets,sales_sources=snapshot_sales(store,actor,current['data'],wanted)
    sheets.extend(sales_sheets)
    # Use the source website's production calculations and its shared saved
    # overrides/plans. Never archive or edit source plans during a pull.
    import importlib
    from . import access as production_access
    if not callable(getattr(production_access,'require_menu',None)):
        importlib.reload(production_access)
    from .production import read as read_production
    production=read_production(store,actor,archive=False)
    if str(production['version'])!=str(current['version']):
        raise ValueError('The planning workbook changed during the pull. Retry to capture one consistent version.')
    windows=[
        ('Production · Under QC',production['qc']['headers'],production['qc']['rows'],0),
        ('Production · Ongoing',production['ongoingHeaders'],[x['row'] for x in production['ongoing']],2),
        ('Production · Upcoming',['Material Code',*production['upcomingHeaders']],[[x.get('materialCode'),*x['row']] for x in production['upcoming']],0),
    ]
    for name,headers,rows,key in windows:
        sheets.append({'name':name,'headers':headers,'rows':[r for r in rows if str(r[key] or '').strip() in wanted],'skuColumn':key})
    production_status={'referenceDate':production.get('referenceDate'),'referenceBasis':production.get('referenceBasis'),'error':production.get('error')}
    # Retain matching model records for numeric-cell drill-through. Only the
    # selected FG SKUs and their descendant BOM components leave this app.
    tables=current['data'].get('tables',[])
    linked=set(wanted)
    for _ in range(25):
        previous=len(linked)
        for t in tables:
            h=t['headers']
            if 'Material' not in h or 'Component' not in h:continue
            mi,ci=h.index('Material'),h.index('Component')
            linked.update(str(r[ci]).strip() for r in t['rows'] if str(r[mi]).strip() in linked and r[ci] is not None)
        if len(linked)==previous:break
    source_tables=[]
    keys={'material','component','sku','material code','material number','sku code'}
    for t in tables:
        columns=[i for i,h in enumerate(t['headers']) if str(h).strip().lower() in keys]
        if not columns:continue
        material=next((i for i,h in enumerate(t['headers']) if str(h).strip().lower() in keys-{'component'}),None)
        rows=[r for r in t['rows'] if (str(r[material]).strip() in linked if material is not None else any(str(r[i]).strip() in linked for i in columns))]
        if rows:source_tables.append({'name':t['name'],'headers':t['headers'],'rows':rows})
    result={'type':'p360-workbook','nonce':nonce,'filename':current['filename'],'version':current['version'],'updatedAt':datetime.fromtimestamp(current['updated_at'],tz=timezone.utc).isoformat(),'syncedAt':datetime.now(timezone.utc).isoformat(),'requestedSkus':sorted(wanted),'sheets':sheets,'tables':source_tables,'sourceRole':'admin','productionStatus':production_status,'salesSources':sales_sources}
    import json
    if len(json.dumps(result))>8_000_000:raise ValueError('Too many matching records. Reduce the selected SKU scope.')
    store.log_event(actor,'export','Product 360: SKU-scoped workbook views')
    return result

def render(store,actor):
    import streamlit as st
    import streamlit.components.v1 as components
    identity=store.require_permission(actor,'download')
    if identity['role']!='admin':raise AccessDenied('Planning synchronization requires the planning administrator.')
    st.title('Connect Product 360')
    st.write('Open Product 360, add confirmed SKU codes, then select Fetch latest workbook. Only matching records from your current uploaded workbook are shared. Keep this tab open to refresh.')
    component=components.declare_component('product360_connection',path=str(Path(__file__).parent/'product360_bridge'))
    event=st.session_state.get('product360_connection')
    result=None
    if isinstance(event,dict) and event.get('action')=='fetch':
        try:result=snapshot(store,actor,event)
        except ValueError as exc:result={'type':'p360-error','nonce':event.get('nonce'),'error':str(exc)}
    component(hub=HUB,result=result,key='product360_connection',default=None)
    # Redirect-independent transfer for browsers that clear window.opener at sign-in.
    import json,uuid
    st.subheader('Authorized snapshot')
    codes=st.text_area('SKU codes (one per line)',value=st.session_state.get('_product360_skus','').replace(',', '\n'),key='p360_export_skus')
    if st.button('Prepare authorized snapshot'):
        try:
            request={'nonce':uuid.uuid4().hex,'skus':[x.strip() for x in re.split(r'[,\n]+',codes) if x.strip()]}
            st.session_state._p360_export=json.dumps(snapshot(store,actor,request),allow_nan=False)
        except (ValueError,AccessDenied) as exc:st.error(str(exc))
    if st.session_state.get('_p360_export'):
        st.download_button('Download authorized snapshot',st.session_state._p360_export,file_name='product360-planning.json',mime='application/json')
        st.caption('Return to Product 360 and select Load authorized snapshot. Previously saved records stay available without signing in to planning again.')
    if st.button('Back to Stock & Planning'):
        st.session_state.pop('_product360_pending',None)
        st.session_state.pop('_product360_skus',None)
        st.session_state.pop('_p360_export',None)
        st.query_params.pop('product360',None);st.query_params.pop('skus',None);st.rerun()


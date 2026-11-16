"""Menu and production edit capabilities, independent of broad export rights."""
MENU_LABELS=['Stock overview','BOM cost','Sales & transfers','Production','Forecast planning','Forecast purchasing','Order requirements','Ask AI','Insights & Graphs','Lead time & Consumption','PnL','Sales','Floor Level · Issue Slip','Floor Level · New Production Batch Required']
PERMISSION_DEFAULTS={'download':False,'update_data':False,'use_tools':True,'use_fiori':False,
                     'view_product_details':False,'edit_production':False,'edit_upcoming':False,
                     **{'menu_'+str(i):True for i in range(10)},'menu_10':False,'menu_11':False,'menu_12':True,'menu_13':True}

def allowed(identity,index):
    if identity['role']=='admin':return True
    if index in (12,13):
        return identity['permissions'].get('menu_'+str(index),True) and allowed(identity,3 if index==12 else 0)
    return identity['permissions'].get('menu_'+str(index),False if index>=10 else True) and (index not in (7,8) or identity['permissions'].get('use_tools',False))

def require_menu(store,actor,index):
    from .store import AccessDenied
    if not allowed(store.identity(actor),index):raise AccessDenied('Your administrator has disabled access to this section.')



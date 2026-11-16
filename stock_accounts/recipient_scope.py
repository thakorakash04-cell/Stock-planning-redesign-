"""Re-check registered recipient section rights at preview and dispatch time."""
import hashlib,json

def record(store,email):
    with store.transaction() as db:
        row=store.run(db,f'SELECT a.username,a.role,a.active,a.permissions,a.session_version,a.allowed_segments FROM {store.account_table} a JOIN portal_profiles p ON a.username=p.username WHERE p.email=?',(email,)).fetchone()
    return dict(row) if row else None

def version(store,email):return hashlib.sha256(json.dumps(record(store,email),sort_keys=True).encode()).hexdigest()
def allowed(store,rules):
    result=[];cache={}
    stock=['Summary','BOM Cost','Sales Data','Production Data','Forecast Planning','Forecast Need to Order List','Need to Order Sheet-B.O. PS']
    regulatory=['FDA 510(k)','CDSCO Risk Classification','Approved Devices']
    names=stock if store.account_table=='accounts' else regulatory
    for rule in rules:
        email=rule.get('recipient','')
        if email not in cache:cache[email]=record(store,email)
        user=cache[email]
        # Existing explicitly saved external recipients are preserved. New console
        # rules only choose registered accounts, or those existing saved recipients.
        if user is None:result.append(rule);continue
        if not user['active']:continue
        if user['role']=='admin':result.append(rule);continue
        permissions=json.loads(user['permissions'] or '{}');section=rule.get('section')
        indices=[names.index(section)] if section in names else range(len(names))
        if all(permissions.get('menu_'+str(i),True) for i in indices):result.append(rule)
    return result

"""Private, durable view settings scoped to the authenticated user and table."""
import json,time
REVISION=1

def schema(store,db):
    store.run(db,"""CREATE TABLE IF NOT EXISTS user_view_preferences (
        username TEXT NOT NULL,scope TEXT NOT NULL,payload TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL,
        PRIMARY KEY(username,scope))""")

def read(store,actor):
    with store.transaction() as db:
        store.require(db,actor);schema(store,db)
        from .transfer_cache import read_rows
        return {r['scope']:json.loads(r['payload']) for r in read_rows(store,db,'SELECT scope,payload FROM user_view_preferences WHERE username=?',(actor.username,))}

def validate_scope(scope):
    # Table titles can contain punctuation (%, commas, brackets, etc.). SQL is
    # parameterized; reject control characters rather than valid table names.
    if not isinstance(scope,str) or not 1<=len(scope)<=240 or any(ord(c)<32 or ord(c)==127 for c in scope):raise ValueError('Invalid view settings scope.')

def save(store,actor,event):
    scope=event.get('scope');value=event.get('value')
    validate_scope(scope)
    if not isinstance(value,dict):raise ValueError('Invalid view settings.')
    try:payload=json.dumps(value,allow_nan=False)
    except (TypeError,ValueError):raise ValueError('Invalid view settings.')
    if len(payload)>100_000:raise ValueError('Too many saved filter values. Narrow the selection.')
    with store.transaction() as db:
        store.require(db,actor);schema(store,db)
        store.run(db,'INSERT INTO user_view_preferences(username,scope,payload,updated_at) VALUES(?,?,?,?) ON CONFLICT(username,scope) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',(actor.username,scope,payload,time.time()))
    return {'ok':True}

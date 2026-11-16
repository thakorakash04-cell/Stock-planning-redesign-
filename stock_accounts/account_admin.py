"""Atomic account/profile/access writes using the stable Store database API."""
import json,re,time
from .store import AccessDenied,DEFAULT_PERMISSIONS,normalize_username,password_record,permissions_for
from .segment_access import available,validate

def save_member(store,actor,event):
    with store.transaction() as db:store.require(db,actor,admin=True)
    username=normalize_username(str(event.get('username','')))
    email=str(event.get('email') or '').strip().lower()
    if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):raise ValueError('Enter a valid email address.')
    rights=event.get('permissions',{})
    if not isinstance(rights,dict) or any(k not in DEFAULT_PERMISSIONS or type(v) is not bool for k,v in rights.items()):raise ValueError('Invalid access rights.')
    if 'active' in event and type(event['active']) is not bool:raise ValueError('Choose an active or disabled account status.')
    segments=None
    if 'allowedSegments' in event:
        current=store.get_dataset(actor)
        from .pnl import all_segments
        from .sales import all_segments as sales_segments
        segments=validate(event['allowedSegments'],sorted(set(available(current['data']) if current else [])|set(all_segments(store,actor))|set(sales_segments(store,actor))))
    create=event.get('create') is True
    credentials=password_record(str(event.get('password',''))) if create else None
    with store.transaction() as db:
        store.require(db,actor,admin=True)
        target=store.run(db,'SELECT * FROM accounts WHERE username=?'+('' if store.sqlite else ' FOR UPDATE'),(username,)).fetchone()
        if create and target:raise ValueError('That username already exists.')
        if not create and not target:raise ValueError('Account not found.')
        if target and target['role']=='admin' and username!=actor.username:raise ValueError('Choose a viewer account.')
        clash=store.run(db,'SELECT username FROM portal_profiles WHERE email=? AND username<>?',(email,username)).fetchone() if email else None
        alias=store.run(db,'SELECT username FROM accounts WHERE username=? AND username<>?',(email,username)).fetchone() if email else None
        if clash or alias:raise ValueError('This email is already used by another account.')
        if create and store.run(db,'SELECT username FROM portal_profiles WHERE email=?',(username,)).fetchone():raise ValueError('That username is already a registered email.')
        old_profile=store.run(db,'SELECT email FROM portal_profiles WHERE username=?',(username,)).fetchone()
        old_email=(old_profile['email'] or '') if old_profile else ''
        old_rights=permissions_for(target) if target else dict(DEFAULT_PERMISSIONS)
        old_segments=json.loads(target['allowed_segments']) if target and target['allowed_segments'] is not None else None
        values={**old_rights,**rights};active=event.get('active',bool(target['active']) if target else True)
        if 'allowedSegments' not in event:segments=old_segments
        if target and target['role']=='admin':segments=None;values=old_rights;active=True
        # Every account change below is committed or rolled back together.
        store.run(db,'INSERT INTO portal_profiles(username,email) VALUES(?,?) ON CONFLICT(username) DO UPDATE SET email=excluded.email',(username,email or None))
        store.run(db,'DELETE FROM portal_resets WHERE identifier=?',(username,))
        if create:
            salt,digest=credentials
            store.run(db,'INSERT INTO accounts(username,salt,password_hash,role,active,created_at,permissions,allowed_segments) VALUES(?,?,?,?,?,?,?,?)',(username,salt,digest,'viewer',int(active),time.time(),json.dumps(values),json.dumps(segments) if segments is not None else None))
            store.history_write(db,actor,'User created',None,{'username':username,'email':email})
            store._log(db,actor.username,'user_created',username,actor.session_id)
        elif target['role']=='viewer' and (old_email!=email or old_rights!=values or old_segments!=segments or bool(target['active'])!=active):
            store.run(db,'UPDATE accounts SET permissions=?,allowed_segments=?,active=?,session_version=session_version+1 WHERE username=?',(json.dumps(values),json.dumps(segments) if segments is not None else None,int(active),username))
        if old_email!=email:store.history_write(db,actor,'User email',old_email,email)
        if old_rights!=values:
            store.history_write(db,actor,'User access: '+username,old_rights,values)
            store._log(db,actor.username,'permissions_changed',username,actor.session_id,values)
        if old_segments!=segments:
            store.history_write(db,actor,'User segments: '+username,old_segments,segments)
            store._log(db,actor.username,'segments_changed',username,actor.session_id,{'segments':segments})
        if target and bool(target['active'])!=active:store._log(db,actor.username,'user_enabled' if active else 'user_disabled',username,actor.session_id)
    return {'ok':True}


PNL_ACCESS_REVISION=4


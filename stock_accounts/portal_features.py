"""Shared portal account extensions; all administrative writes are authorized."""
import hashlib,hmac,json,re,secrets,time,uuid

BRANDING_REVISION=5

class PortalFeatures:
    def portal_schema(self):
        with self.transaction() as db:
            self.run(db,'CREATE TABLE IF NOT EXISTS portal_profiles (username TEXT PRIMARY KEY,email TEXT UNIQUE)')
            self.run(db,'CREATE TABLE IF NOT EXISTS portal_settings (id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            self.run(db,'CREATE TABLE IF NOT EXISTS portal_history (id TEXT PRIMARY KEY,occurred_at DOUBLE PRECISION NOT NULL,username TEXT NOT NULL,section TEXT NOT NULL,before_value TEXT NOT NULL,after_value TEXT NOT NULL)')
            self.run(db,'CREATE TABLE IF NOT EXISTS portal_resets (identifier TEXT PRIMARY KEY,challenge TEXT NOT NULL,digest TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL,attempts INTEGER NOT NULL,requested DOUBLE PRECISION NOT NULL,window_start DOUBLE PRECISION NOT NULL,requests INTEGER NOT NULL,version INTEGER NOT NULL)')
    def resolve_login(self,identifier):
        identifier=str(identifier).strip().lower()
        with self.transaction() as db:
            # Exact usernames always retain precedence over email aliases.
            row=self.run(db,f'SELECT username FROM {self.account_table} WHERE username=?',(identifier,)).fetchone()
            if row:return row['username']
            row=self.run(db,'SELECT username FROM portal_profiles WHERE email=?',(identifier,)).fetchone()
            return row['username'] if row else identifier
    def profile_email(self,actor,username,email):
        email=str(email).strip().lower()
        if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):raise ValueError('Enter a valid email address.')
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            if not self.run(db,f'SELECT username FROM {self.account_table} WHERE username=?',(username,)).fetchone():raise ValueError('Account not found.')
            clash=self.run(db,f'SELECT username FROM {self.account_table} WHERE username=? AND username<>?',(email,username)).fetchone()
            other=self.run(db,'SELECT username FROM portal_profiles WHERE email=? AND username<>?',(email,username)).fetchone() if email else None
            if clash or other:raise ValueError('This email is already used by another account.')
            old=self.run(db,'SELECT email FROM portal_profiles WHERE username=?',(username,)).fetchone()
            self.run(db,'INSERT INTO portal_profiles(username,email) VALUES(?,?) ON CONFLICT(username) DO UPDATE SET email=excluded.email',(username,email or None))
            self.run(db,'DELETE FROM portal_resets WHERE identifier=?',(username,))
            self.history_write(db,actor,'User email',old['email'] if old else '',email)
    def profiles(self,actor):
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            return {r['username']:r['email'] or '' for r in self.run(db,'SELECT * FROM portal_profiles').fetchall()}
    def history_write(self,db,actor,section,before,after):
        self.run(db,'INSERT INTO portal_history VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,time.time(),actor.username,section,json.dumps(before),json.dumps(after)))
    def portal_read(self,actor=None,public=False):
        with self.transaction() as db:
            if not public:self.require(db,actor)
            from .transfer_cache import read_rows
            rows=read_rows(self,db,"SELECT payload FROM portal_settings WHERE id='workspace'")
            data=json.loads(rows[0]['payload']) if rows else {}
            if public:return {k:v for k,v in data.items() if k in ('title','subtitle','login_text','portal_logo','signin_heading','signin_text')}
            if data.get('navigation') and not any(str(n.get('id'))=='10' for n in data['navigation']):data['navigation']=[*data['navigation'],{'id':'10','label':'PnL','order':max((n.get('order',0) for n in data['navigation']),default=0)+1}]
            if data.get('navigation') and not any(str(n.get('id'))=='11' for n in data['navigation']):data['navigation']=[*data['navigation'],{'id':'11','label':'Sales','order':max((n.get('order',0) for n in data['navigation']),default=0)+1}]
            identity=self.require(db,actor)
            if identity['role']!='admin':
                data.pop('email_rules',None);data.pop('email_schedule',None)
                if identity.get('allowedSegments') is not None:data['segments']=[s for s in data.get('segments',[]) if s in identity['allowedSegments']]
            return data
    def portal_save(self,actor,data,expected_email_version=None,expected_schedule_version=None):
        if not isinstance(data,dict):raise ValueError('Invalid workspace settings.')
        if 'email_schedule' in data:
            value=data['email_schedule']
            if not isinstance(value,dict) or set(value)!={'enabled','time'} or type(value['enabled']) is not bool or not isinstance(value['time'],str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value['time']):raise ValueError('Choose a valid daily time in IST.')
        if 'navigation' in data:
            nav=data['navigation']
            if not isinstance(nav,list) or len(nav)!=self.navigation_count or {r.get('id') for r in nav}!=set(map(str,range(self.navigation_count))) or any(not isinstance(r.get('label'),str) or not r['label'].strip() or len(r['label'])>100 or type(r.get('order')) is not int for r in nav):raise ValueError('Keep every fixed sidebar section and use valid labels and whole-number order.')
        if 'segments' in data and (not isinstance(data['segments'],list) or len(data['segments'])>200 or any(not isinstance(x,str) or not x.strip() or len(x)>100 for x in data['segments'])):raise ValueError('Use up to 200 segment names of 100 characters each.')
        allowed={'title','subtitle','login_text','portal_logo','signin_heading','signin_text','segments','navigation','email_rules','email_schedule'}
        if not isinstance(data,dict) or set(data)-allowed:raise ValueError('Invalid workspace settings.')
        for key,limit in [('title',150),('subtitle',150),('login_text',1500),('signin_heading',150),('signin_text',1000)]:
            if key in data and (not isinstance(data[key],str) or len(data[key])>limit):raise ValueError('Use valid login text within the field limits.')
        if 'portal_logo' in data:
            from .branding import validate_logo
            validate_logo(data['portal_logo'])
        if len(json.dumps(data))>500000:raise ValueError('Settings are too large.')
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            if not self.sqlite:self.run(db,'SELECT pg_advisory_xact_lock(hashtext(?))',('portal-settings',))
            row=self.run(db,"SELECT payload FROM portal_settings WHERE id='workspace'").fetchone();old=json.loads(row['payload']) if row else {}
            if expected_email_version is not None and hashlib.sha256(json.dumps(old.get('email_rules',[]),sort_keys=True,default=str).encode()).hexdigest()!=expected_email_version:raise ValueError('Email rules changed. Reload before saving.')
            if expected_schedule_version is not None and hashlib.sha256(json.dumps(old.get('email_schedule',{}),sort_keys=True,default=str).encode()).hexdigest()!=expected_schedule_version:raise ValueError('Delivery schedule changed. Reload before saving.')
            new={**old,**data}
            self.run(db,"INSERT INTO portal_settings VALUES('workspace',?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",(json.dumps(new),))
            for key,value in data.items():
                if old.get(key)!=value:self.history_write(db,actor,key,old.get(key),value)
    def portal_history(self,actor,section=None):
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            return [dict(r) for r in self.run(db,'SELECT * FROM portal_history'+(' WHERE section=?' if section else '')+' ORDER BY occurred_at DESC LIMIT 500',(section,) if section else ()).fetchall()]
    def request_recovery(self,identifier,send):
        username=self.resolve_login(identifier);now=time.time();token=secrets.token_urlsafe(32);code=f'{secrets.randbelow(100000000):08d}'
        with self.transaction() as db:
            if not self.sqlite:self.run(db,'SELECT pg_advisory_xact_lock(hashtext(?))',('portal-reset:'+username,))
            prior=self.run(db,'SELECT * FROM portal_resets WHERE identifier=?',(username,)).fetchone()
            if prior and (now-prior['requested']<60 or now-prior['window_start']<3600 and prior['requests']>=5):raise ValueError('Too many requests. Wait before trying again.')
            row=self.run(db,f'SELECT a.*,p.email FROM {self.account_table} a LEFT JOIN portal_profiles p ON a.username=p.username WHERE a.username=?',(username,)).fetchone()
            start=prior['window_start'] if prior and now-prior['window_start']<3600 else now
            count=prior['requests']+1 if prior and start==prior['window_start'] else 1
            self.run(db,'INSERT INTO portal_resets VALUES(?,?,?,?,0,?,?,?,?) ON CONFLICT(identifier) DO UPDATE SET challenge=excluded.challenge,digest=excluded.digest,expires=excluded.expires,attempts=0,requested=excluded.requested,window_start=excluded.window_start,requests=excluded.requests,version=excluded.version',(username,hashlib.sha256(token.encode()).hexdigest(),hashlib.sha256((token+code).encode()).hexdigest(),now+600,now,start,count,row['session_version'] if row else -1))
        if row and row['active'] and row['email']:
            try:send(row['email'],code)
            except Exception:
                with self.transaction() as db:self.run(db,'UPDATE portal_resets SET expires=0 WHERE identifier=? AND challenge=?',(username,hashlib.sha256(token.encode()).hexdigest()))
        return username,token
    def complete_recovery(self,username,token,code,password):
        from importlib import import_module
        module=import_module(self.__class__.__module__);salt,digest=module.password_record(password);valid=False
        with self.transaction() as db:
            if not self.sqlite:self.run(db,'SELECT pg_advisory_xact_lock(hashtext(?))',('portal-reset:'+username,))
            reset=self.run(db,'SELECT * FROM portal_resets WHERE identifier=?',(username,)).fetchone()
            row=self.run(db,f'SELECT * FROM {self.account_table} WHERE username=?',(username,)).fetchone()
            if reset and reset['expires']>time.time() and reset['attempts']<5 and hmac.compare_digest(reset['challenge'],hashlib.sha256(token.encode()).hexdigest()):
                self.run(db,'UPDATE portal_resets SET attempts=attempts+1 WHERE identifier=?',(username,))
                valid=bool(row and row['active'] and row['session_version']==reset['version'] and hmac.compare_digest(reset['digest'],hashlib.sha256((token+str(code)).encode()).hexdigest()))
                if valid:
                    self.run(db,f'UPDATE {self.account_table} SET salt=?,password_hash=?,session_version=session_version+1,failed_attempts=0,locked_until=0 WHERE username=?',(salt,digest,username))
                    self.run(db,'DELETE FROM portal_resets WHERE identifier=?',(username,));self._log(db,username,'password_reset')
        if not valid:raise ValueError('Invalid or expired reset code. Request a new code.')


"""Persistent accounts, administrator-granted capabilities and privacy-safe audit events."""
from __future__ import annotations
import base64, contextlib, gzip, hashlib, hmac, json, os, re, sqlite3, time, uuid
from dataclasses import dataclass
from decimal import Decimal
import math

ITERATIONS = 600_000
DEFAULT_PERMISSIONS = {"download":False,"update_data":False,"use_tools":True,"use_fiori":False,"view_product_details":False,"edit_production":False,"edit_upcoming":False,**{'menu_'+str(i):True for i in range(10)},'menu_10':False,'menu_11':False,'menu_12':True,'menu_13':True}
# Preserve these identity types during a controlled hot reload. Existing sessions
# and exception handlers in other modules must keep using the same classes.
if 'AccessDenied' not in globals():
    class AccessDenied(PermissionError):
        pass
if 'Actor' not in globals() or 'expires_at' not in getattr(Actor,'__dataclass_fields__',{}):
    @dataclass(frozen=True)
    class Actor:
        username: str
        version: int
        session_id: str = ""
        expires_at: float = 0

STORE_SCHEMA_REVISION=18

def session_version(value):
    # Imported account tables can store numeric versions as TEXT while the
    # remembered-session table returns INTEGER. Compare the number, never its
    # driver-specific representation. Invalid revisions must never authorize.
    if type(value) is int:return value if value>0 else None
    if isinstance(value,Decimal):return int(value) if value.is_finite() and value>0 and value==value.to_integral_value() else None
    if type(value) is float:return int(value) if math.isfinite(value) and value>0 and value.is_integer() else None
    if isinstance(value,str) and re.fullmatch(r'[1-9][0-9]{0,18}',value):return int(value)
    return None

def normalize_username(value):
    value=value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.@+-]{2,63}",value):
        raise ValueError("Username must have 3–64 letters, numbers or . _ @ + - characters.")
    return value

def password_record(password):
    if len(password)<12:raise ValueError("Use a password of at least 12 characters.")
    salt=os.urandom(16).hex()
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt),ITERATIONS).hex()
    return salt,digest

def password_matches(password,salt,expected):
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt),ITERATIONS).hex()
    return hmac.compare_digest(digest,expected)

def permissions_for(row):
    if row["role"]=="admin":return {key:True for key in DEFAULT_PERMISSIONS}
    return {**DEFAULT_PERMISSIONS,**json.loads(row["permissions"] or "{}")}

from .portal_features import PortalFeatures

class Store(PortalFeatures):
    browser_namespace="stock"
    navigation_count=12
    account_table='accounts'
    def __init__(self,url):
        if not url.startswith(("postgresql://","postgres://","sqlite:///")):
            raise ValueError("DATABASE_URL must be PostgreSQL, or sqlite:/// for local testing.")
        self.url,self.sqlite=url,url.startswith("sqlite:///")
        self.portal_schema()
        with self.transaction() as db:
            self.run(db,"""CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY,salt TEXT NOT NULL,password_hash TEXT NOT NULL,
                role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,session_version INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0,locked_until DOUBLE PRECISION NOT NULL DEFAULT 0,
                created_at DOUBLE PRECISION NOT NULL)""")
            columns={"allowed_segments":"TEXT", "permissions":"TEXT NOT NULL DEFAULT '{}'", "bootstrap_salt":"TEXT", "bootstrap_hash":"TEXT",
                     "last_login_at":"DOUBLE PRECISION", "last_access_at":"DOUBLE PRECISION"}
            existing={r["name"] for r in self.run(db,"PRAGMA table_info(accounts)").fetchall()} if self.sqlite else set()
            for name,kind in columns.items():
                if self.sqlite:
                    if name not in existing:self.run(db,f"ALTER TABLE accounts ADD COLUMN {name} {kind}")
                else:self.run(db,f"ALTER TABLE accounts ADD COLUMN IF NOT EXISTS {name} {kind}")
            self.run(db,"""CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,payload TEXT NOT NULL,filename TEXT NOT NULL,version TEXT NOT NULL,
                uploaded_by TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL)""")
            self.run(db,"""CREATE TABLE IF NOT EXISTS access_log (
                id TEXT PRIMARY KEY,occurred_at DOUBLE PRECISION NOT NULL,username TEXT NOT NULL,
                action TEXT NOT NULL,resource TEXT NOT NULL,session_id TEXT NOT NULL,details TEXT NOT NULL)""")
            self.run(db,"CREATE INDEX IF NOT EXISTS access_log_user_time ON access_log(username,occurred_at)")
        from daily_sessions import schema as daily_schema
        daily_schema(self)
    @contextlib.contextmanager
    def transaction(self):
        if self.sqlite:
            db=sqlite3.connect(self.url[len("sqlite:///"):],timeout=20);db.row_factory=sqlite3.Row
            db.execute("PRAGMA busy_timeout=20000");db.execute("BEGIN IMMEDIATE")
        else:
            import psycopg
            from psycopg.rows import dict_row
            db=psycopg.connect(self.url,row_factory=dict_row,connect_timeout=15)
        try:yield db;db.commit()
        except Exception:db.rollback();raise
        finally:db.close()
    def run(self,db,sql,args=()):
        return db.execute(sql if self.sqlite else sql.replace("?","%s"),args)
    def _log(self,db,username,action,resource="",session_id="",details=None):
        self.run(db,"INSERT INTO access_log(id,occurred_at,username,action,resource,session_id,details) VALUES(?,?,?,?,?,?,?)",
                 (uuid.uuid4().hex,time.time(),username,action,str(resource)[:200],session_id,json.dumps(details or {},sort_keys=True)))
    def bootstrap_admin(self,username,password):
        username=normalize_username(username)
        with self.transaction() as db:
            row=self.run(db,"SELECT * FROM accounts WHERE username=?",(username,)).fetchone()
            if row and row["role"]!="admin":raise ValueError("The configured administrator ID belongs to a viewer.")
            self.run(db,"UPDATE accounts SET active=0,session_version=session_version+1 WHERE role='admin' AND username<>? AND active=1",(username,))
            if row:
                # Track the configured secret separately, so an in-app admin password
                # change survives cache clears/restarts. A changed secret is recovery.
                salt=row["bootstrap_salt"] or row["salt"];digest=row["bootstrap_hash"] or row["password_hash"]
                if password_matches(password,salt,digest):
                    if not row["bootstrap_hash"]:self.run(db,"UPDATE accounts SET bootstrap_salt=?,bootstrap_hash=? WHERE username=?",(salt,digest,username))
                    if not row["active"]:self.run(db,"UPDATE accounts SET active=1,session_version=session_version+1 WHERE username=?",(username,))
                    return
            salt,digest=password_record(password)
            if row:
                self.run(db,"UPDATE accounts SET salt=?,password_hash=?,bootstrap_salt=?,bootstrap_hash=?,session_version=session_version+1,active=1,failed_attempts=0,locked_until=0 WHERE username=?",(salt,digest,salt,digest,username))
            else:
                self.run(db,"INSERT INTO accounts(username,salt,password_hash,bootstrap_salt,bootstrap_hash,role,created_at) VALUES(?,?,?,?,?,?,?)",(username,salt,digest,salt,digest,"admin",time.time()))
            self._log(db,username,"admin_secret_changed" if row else "admin_created")
    def make_actor(self,username,version,session_id='',expires_at=0):
        # This factory and require share this Store's module globals even when
        # Streamlit evicts/reimports sys.modules while retaining resource caches.
        return Actor(username,version,session_id,expires_at)
    def login(self,username,password):
        try:username=normalize_username(self.resolve_login(username))
        except ValueError:username="invalid_username"
        with self.transaction() as db:
            row=self.run(db,"SELECT * FROM accounts WHERE username=?"+("" if self.sqlite else " FOR UPDATE"),(username,)).fetchone()
            if not row:
                password_matches(password,"00"*16,"00"*32);self._log(db,username,"login_failed");return None
            if row["locked_until"]>time.time():self._log(db,username,"login_locked");return None
            if not password_matches(password,row["salt"],row["password_hash"]) or not row["active"]:
                attempts=row["failed_attempts"]+1
                self.run(db,"UPDATE accounts SET failed_attempts=?,locked_until=? WHERE username=?",(attempts,time.time()+900 if attempts>=5 else 0,username))
                self._log(db,username,"login_failed");return None
            self.run(db,"UPDATE accounts SET failed_attempts=0,locked_until=0,last_login_at=?,last_access_at=? WHERE username=?",(time.time(),time.time(),username))
            actor=self.make_actor(username,row["session_version"],uuid.uuid4().hex)
            self._log(db,username,"login_success",session_id=actor.session_id);return actor
    def require(self,db,actor,admin=False,permission=None):
        if not isinstance(actor,Actor):raise AccessDenied("Sign in required.")
        version=session_version(actor.version)
        if version is None:raise AccessDenied('This session has expired. Please sign in again.')
        from daily_sessions import table as session_table
        expiry=getattr(actor,'expires_at',0)
        if expiry and expiry<=time.time():raise AccessDenied("Your daily session expired. Sign in again.")
        sql="SELECT username,role,active,session_version,permissions,allowed_segments FROM accounts WHERE username=?"
        args=(actor.username,)
        if expiry:
            sql+=f" AND EXISTS(SELECT 1 FROM {session_table(self)} WHERE username=? AND version=? AND session_id=? AND expires>?)"
            args+=(actor.username,version,actor.session_id,time.time())
        row=self.run(db,sql,args).fetchone()
        if not row or not row["active"] or session_version(row["session_version"])!=version:raise AccessDenied("This session has expired. Please sign in again.")
        if admin and row["role"]!="admin":raise AccessDenied("Administrator access required.")
        result={key:row[key] for key in ("username","role","active","session_version")};result["permissions"]=permissions_for(row);result["allowedSegments"]=None if row["role"]=="admin" or row["allowed_segments"] is None else json.loads(row["allowed_segments"])
        if permission and not result["permissions"].get(permission,False):raise AccessDenied("Your administrator has not granted this permission.")
        return result
    def require_permission(self,actor,permission):
        with self.transaction() as db:return self.require(db,actor,permission=permission)
    def identity(self,actor):
        with self.transaction() as db:return self.require(db,actor)
    def users(self,actor):
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            rows=self.run(db,"SELECT username,role,active,created_at,last_login_at,last_access_at,permissions,allowed_segments FROM accounts ORDER BY username").fetchall()
            return [{**dict(r),"permissions":permissions_for(r),"allowedSegments":None if r["role"]=="admin" or r["allowed_segments"] is None else json.loads(r["allowed_segments"])} for r in rows]
    def create_viewer(self,actor,username,password,email=None):
        username=normalize_username(username)
        email=str(email or '').strip().lower()
        if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):raise ValueError('Enter a valid email address.')
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            if self.run(db,"SELECT username FROM portal_profiles WHERE email=?",(username,)).fetchone():raise ValueError("That username is already a registered email.")
            if self.run(db,"SELECT username FROM accounts WHERE username=?",(username,)).fetchone():raise ValueError("That username already exists.")
            if email and (self.run(db,'SELECT username FROM portal_profiles WHERE email=?',(email,)).fetchone() or self.run(db,f'SELECT username FROM {self.account_table} WHERE username=?',(email,)).fetchone()):raise ValueError('Email is already in use.')
            salt,digest=password_record(password)
            self.run(db,"INSERT INTO accounts(username,salt,password_hash,role,created_at) VALUES(?,?,?,?,?)",(username,salt,digest,"viewer",time.time()))
            if email:self.run(db,'INSERT INTO portal_profiles(username,email) VALUES(?,?)',(username,email))
            self.history_write(db,actor,'User created',None,{'username':username,'email':email})
            self._log(db,actor.username,"user_created",username,actor.session_id)
    def update_viewer(self,actor,username,active=None,password=None):
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            row=self.run(db,"SELECT role FROM accounts WHERE username=?",(username,)).fetchone()
            if not row or row["role"]!="viewer":raise ValueError("Select a viewer account. Use Change password for your own password.")
            if active is not None:
                self.run(db,"UPDATE accounts SET active=?,session_version=session_version+1 WHERE username=?",(int(active),username))
                self._log(db,actor.username,"user_enabled" if active else "user_disabled",username,actor.session_id)
            if password is not None:
                salt,digest=password_record(password)
                self.run(db,"UPDATE accounts SET salt=?,password_hash=?,session_version=session_version+1,failed_attempts=0,locked_until=0 WHERE username=?",(salt,digest,username))
                self._log(db,actor.username,"password_reset",username,actor.session_id)
    def update_permissions(self,actor,username,permissions):
        if not isinstance(permissions,dict) or any(k not in DEFAULT_PERMISSIONS or type(v) is not bool for k,v in permissions.items()):raise ValueError("Invalid permissions.")
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            row=self.run(db,"SELECT role,permissions FROM accounts WHERE username=?",(username,)).fetchone()
            if not row or row["role"]!="viewer":raise ValueError("Choose a viewer account.")
            values={**DEFAULT_PERMISSIONS,**json.loads(row["permissions"] or "{}"),**permissions}
            self.run(db,"UPDATE accounts SET permissions=?,session_version=session_version+1 WHERE username=?",(json.dumps(values),username))
            self.history_write(db,actor,'User access: '+username,json.loads(row['permissions'] or '{}'),values)
            self._log(db,actor.username,"permissions_changed",username,actor.session_id,values)
    def update_segments(self,actor,username,segments):
        with self.transaction() as db:self.require(db,actor,admin=True)
        from .segment_access import validate,available
        current=self.get_dataset(actor)
        choices=available(current['data']) if current else []
        segments=validate(segments,choices)
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            row=self.run(db,'SELECT role,allowed_segments FROM accounts WHERE username=?',(username,)).fetchone()
            if not row or row['role']!='viewer':raise ValueError('Choose a viewer account.')
            old=json.loads(row['allowed_segments']) if row['allowed_segments'] is not None else None
            if old==segments:return
            self.run(db,'UPDATE accounts SET allowed_segments=?,session_version=session_version+1 WHERE username=?',(json.dumps(segments) if segments is not None else None,username))
            self.history_write(db,actor,'User segments: '+username,old,segments)
            self._log(db,actor.username,'segments_changed',username,actor.session_id,{'segments':segments})
    def change_password(self,actor,current_password,new_password):
        error=None
        with self.transaction() as db:
            self.require(db,actor)
            row=self.run(db,"SELECT * FROM accounts WHERE username=?"+("" if self.sqlite else " FOR UPDATE"),(actor.username,)).fetchone()
            if row["locked_until"]>time.time():error="Account temporarily locked. Please try later."
            elif not password_matches(current_password,row["salt"],row["password_hash"]):
                attempts=row["failed_attempts"]+1
                self.run(db,"UPDATE accounts SET failed_attempts=?,locked_until=? WHERE username=?",(attempts,time.time()+900 if attempts>=5 else 0,actor.username))
                error="Current password is incorrect."
            elif current_password==new_password:error="Choose a different new password."
            else:
                salt,digest=password_record(new_password)
                self.run(db,"UPDATE accounts SET salt=?,password_hash=?,session_version=session_version+1,failed_attempts=0,locked_until=0 WHERE username=?",(salt,digest,actor.username))
                self._log(db,actor.username,"password_changed",actor.username,actor.session_id)
            if error:self._log(db,actor.username,"password_change_failed",session_id=actor.session_id)
        if error:raise ValueError(error)
    def record_access(self,actor,resource):
        with self.transaction() as db:
            self.require(db,actor)
            prior=self.run(db,"SELECT occurred_at FROM access_log WHERE username=? AND session_id=? AND action='view' AND resource=? ORDER BY occurred_at DESC LIMIT 1",(actor.username,actor.session_id,str(resource)[:200])).fetchone()
            if not prior or time.time()-prior["occurred_at"]>=300:
                self._log(db,actor.username,"view",resource,actor.session_id)
                self.run(db,"UPDATE accounts SET last_access_at=? WHERE username=?",(time.time(),actor.username))
    def log_event(self,actor,action,resource=""):
        if action not in ("logout","session_expired","export","tool_use"):raise ValueError("Invalid event.")
        with self.transaction() as db:
            self.require(db,actor,permission="download" if action=="export" else None)
            self._log(db,actor.username,action,resource,actor.session_id)
    def access_log(self,actor,username=None,limit=500):
        with self.transaction() as db:
            self.require(db,actor,admin=True)
            sql="SELECT occurred_at,username,action,resource,session_id,details FROM access_log";args=[]
            if username:sql+=" WHERE username=? OR resource=?";args.extend([username,username])
            sql+=" ORDER BY occurred_at DESC LIMIT ?";args.append(max(1,min(int(limit),1000)))
            return [dict(r) for r in self.run(db,sql,args).fetchall()]
    def save_dataset(self,actor,filename,dataset):
        payload=base64.b64encode(gzip.compress(json.dumps(dataset,allow_nan=False,separators=(",",":")).encode(),mtime=0)).decode()
        version=hashlib.sha256(payload.encode()).hexdigest()
        uploaded_at=time.time()
        with self.transaction() as db:
            identity=self.require(db,actor,permission="update_data")
            if identity["allowedSegments"] is not None:raise AccessDenied("Full master updates require access to all segments.")
            from .notification_rules import master as capture_notifications
            from .notification_rules import schema as notification_schema
            notification_schema(self,db)
            if not self.run(db,"SELECT id FROM stock_notice_sources WHERE id='master'").fetchone():
                previous=self.run(db,"SELECT version,updated_at,filename FROM datasets WHERE id='current'").fetchone()
                if previous:
                    cached=getattr(self,'_dataset_payload_cache',None)
                    old=cached[1] if cached and cached[0]==(previous['version'],previous['updated_at'],previous['filename']) else self.run(db,"SELECT payload FROM datasets WHERE id='current'").fetchone()
                    old_data=json.loads(gzip.decompress(base64.b64decode(old['payload'])))
                    capture_notifications(self,db,{'version':previous['version'],'updated_at':previous['updated_at'],'data':old_data},baseline=True)
            capture_notifications(self,db,{'version':version,'updated_at':uploaded_at,'data':dataset})
            self.run(db,"INSERT INTO datasets(id,payload,filename,version,uploaded_by,updated_at) VALUES('current',?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,filename=excluded.filename,version=excluded.version,uploaded_by=excluded.uploaded_by,updated_at=excluded.updated_at",(payload,filename,version,actor.username,uploaded_at))
            self.history_write(db,actor,'Workbook upload',None,{'filename':filename,'version':version,'sheets':[{'name':s.get('name'),'rows':len(s.get('rows',[])),'headers':s.get('headers',[])} for s in dataset.get('sheets',[])]})
            self._log(db,actor.username,"data_updated",session_id=actor.session_id)
        # Build source production rows once at master update, outside the upload
        # transaction. Persisted snapshots survive logouts and process restarts.
        from importlib import import_module
        for module in ('production_snapshot','order_snapshot'):
            try:import_module('.'+module,__package__).read(self,actor,{'version':version,'updated_at':uploaded_at,'data':dataset})
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Master snapshot preparation deferred: %s',module)
    def dataset_revision(self,actor):
        with self.transaction() as db:
            self.require(db,actor)
            row=self.run(db,"SELECT version,updated_at,filename FROM datasets WHERE id='current'").fetchone()
            return (row["version"],row["updated_at"]) if row else None
    def get_dataset(self,actor):
        with self.transaction() as db:
            identity=self.require(db,actor);revision=self.run(db,"SELECT version,updated_at,filename FROM datasets WHERE id='current'").fetchone()
            if not revision:return None
            key=(revision['version'],revision['updated_at'],revision['filename'])
            cached=getattr(self,'_dataset_payload_cache',None)
            if cached and cached[0]==key:
                row=cached[1]
            else:
                row=self.run(db,"SELECT * FROM datasets WHERE id='current'").fetchone()
                if row:self._dataset_payload_cache=((row['version'],row['updated_at'],row['filename']),dict(row))
        if not row:return None
        result=dict(row);result["data"]=json.loads(gzip.decompress(base64.b64decode(result.pop("payload"))));
        from .segment_access import current_scope
        return current_scope(result,identity["allowedSegments"])





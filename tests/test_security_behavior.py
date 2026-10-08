import os, sys, tempfile, json, time, uuid, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATE=Path(tempfile.mkdtemp(prefix='tf-audit-fixtures-'))
os.environ.update(TF_DB_PATH=str(STATE/'users.db'),TF_SECRET_KEY='local-review-only-synthetic-signing-key-2026',TF_PRODUCTION='1',TF_ADMIN_EMAIL='',TF_ADMIN_PASSWORD='')
sys.path.insert(0,str(ROOT/'server'))
import config
config.PRIVATE_DATA_DIR=STATE/'data'; config.PRIVATE_DATA_DIR.mkdir()
(config.PRIVATE_DATA_DIR/'manifest.json').write_text(json.dumps({'core':['REVIEW_CORE'],'lazy':[],'live':['REVIEW_LIVE']}))
for n in ['REVIEW_CORE','REVIEW_LIVE']:
 (config.PRIVATE_DATA_DIR/f'{n}.json').write_text('{"fixture":true}')
import refresher
refresher.start=lambda:None # Disable network refresh, not request/auth behavior.
import main, db, auth, security, data
from fastapi.testclient import TestClient
import pytest

@pytest.fixture(autouse=True)
def reset_limits():
 auth._fails.clear(); main._ip_hits.clear(); data._last_live.clear()

def client(): return TestClient(main.app,base_url='https://testserver')
def account():
 c=client(); ident=uuid.uuid4().hex; email=f'{ident}@example.test'; pw='ReviewOnly-password-123'; code='REVIEW-'+ident
 db.seed_invite_code(code,'Synthetic','2026-10-08')
 r=c.post('/api/auth/signup',json={'beta_key':code,'name':'Synthetic reviewer','email':email,'password':pw,'consent':True})
 assert r.status_code==200
 return c,email,pw,r

def csrf(c): return {'X-CSRF-Token':c.cookies.get('tf_csrf')}
def enable_mfa(c):
 r=c.post('/api/auth/mfa/setup',headers=csrf(c)); assert r.status_code==200
 secret=r.json()['secret']; recovery=r.json()['recovery_codes'][0]
 otp=security._hotp(secret,int(time.time()//30))
 assert c.post('/api/auth/mfa/enable',json={'code':otp},headers=csrf(c)).status_code==200
 return secret,recovery

def test_anonymous_data_denied():
 for p in ['/api/data/bundle','/api/data/state','/api/data/live']:
  assert client().get(p).status_code==401

def test_authenticated_data_served():
 c,*_=account(); assert c.get('/api/data/bundle').json()=={'REVIEW_CORE':{'fixture':True}}

def test_direct_dataset_files_blocked():
 for p in ['/js/economy_data.js','/js/news_intel.js','/js/data.js']:
  assert client().get(p).status_code==404

def test_cookie_flags():
 c,e,p,r=account(); cookies=r.headers.get_list('set-cookie'); session=next(x for x in cookies if x.startswith('tf_session='))
 assert 'HttpOnly' in session and 'Secure' in session and 'SameSite=lax' in session

def test_security_headers():
 r=client().get('/app'); assert r.status_code==200
 for h in ['content-security-policy','strict-transport-security','x-frame-options','x-content-type-options']:
  assert h in r.headers

def test_csrf_required():
 c,*_=account(); assert c.post('/api/auth/a11y?on=true').status_code==403
 assert c.post('/api/auth/a11y?on=true',headers=csrf(c)).status_code==200

def test_nonadmin_audit_denied():
 c,*_=account(); assert c.get('/api/auth/admin/audit').status_code==403

def test_admin_audit_allowed():
 c,e,*_=account(); db.set_role(e,'admin'); r=c.get('/api/auth/admin/audit'); assert r.status_code==200 and r.json()['chain_valid']

def test_revoked_cookie_replay_denied():
 c,*_=account(); token=c.cookies.get('tf_session'); assert c.post('/api/auth/logout').status_code==200
 d=client(); d.cookies.set('tf_session',token); assert d.get('/api/auth/me').status_code==401

def test_cross_account_session_revocation_denied():
 a,*_=account(); b,*_=account(); sid=b.get('/api/auth/sessions').json()['sessions'][0]['sid']
 assert a.post('/api/auth/sessions/revoke',headers=csrf(a),json={'sid':sid}).status_code==404
 assert b.get('/api/auth/me').status_code==200

def test_mfa_password_alone_does_not_authenticate():
 c,e,p,*_=account(); enable_mfa(c); d=client(); r=d.post('/api/auth/login',json={'email':e,'password':p})
 assert r.json()=={'mfa_required':True} and not d.cookies.get('tf_session')

def test_mfa_correct_code_authenticates():
 c,e,p,*_=account(); s,_=enable_mfa(c); d=client()
 r=d.post('/api/auth/login',json={'email':e,'password':p,'otp':security._hotp(s,int(time.time()//30))})
 assert r.status_code==200 and d.cookies.get('tf_session')

def test_mfa_recovery_code_single_use():
 c,e,p,*_=account(); _,recovery=enable_mfa(c)
 assert client().post('/api/auth/login',json={'email':e,'password':p,'recovery':recovery}).status_code==200
 assert client().post('/api/auth/login',json={'email':e,'password':p,'recovery':recovery}).status_code==401

def test_login_throttling_same_ip():
 c,e,p,*_=account(); d=client()
 statuses=[d.post('/api/auth/login',json={'email':e,'password':'wrong'}).status_code for _ in range(6)]
 assert statuses==[401]*5+[429]

def test_forwarded_header_cannot_reset_login_throttle():
 c,e,p,*_=account(); d=client()
 for _ in range(6): d.post('/api/auth/login',json={'email':e,'password':'wrong'},headers={'X-Forwarded-For':'198.51.100.1'})
 assert d.post('/api/auth/login',json={'email':e,'password':'wrong'},headers={'X-Forwarded-For':'198.51.100.2'}).status_code==429

def test_mfa_reenrollment_requires_existing_factor():
 c,e,p,*_=account(); enable_mfa(c)
 r=c.post('/api/auth/mfa/setup',headers=csrf(c))
 assert r.status_code in (400,401,403,409), 'Enabled MFA secret can be replaced using session + CSRF alone'

def test_billing_cannot_self_upgrade():
 c,e,*_=account(); db.set_tier(e,'free')
 assert c.post('/api/billing/checkout',headers=csrf(c),json={'tier':'live'}).status_code==501
 assert db.get_user(e)['tier']=='free'

def test_audit_detail_change_detected():
 c,*_=account()
 with sqlite3.connect(config.DB_PATH) as con:
  old=con.execute('SELECT id, detail FROM audit_log ORDER BY id DESC LIMIT 1').fetchone()
  con.execute('UPDATE audit_log SET detail=? WHERE id=?',('tampered',old[0])); con.commit()
 assert not db.verify_audit_chain(security.audit_hash)
 with sqlite3.connect(config.DB_PATH) as con: con.execute('UPDATE audit_log SET detail=? WHERE id=?',(old[1],old[0])); con.commit()

def test_audit_ip_change_detected():
 c,*_=account()
 with sqlite3.connect(config.DB_PATH) as con:
  old=con.execute('SELECT id, ip FROM audit_log ORDER BY id DESC LIMIT 1').fetchone()
  con.execute('UPDATE audit_log SET ip=? WHERE id=?',('tampered',old[0])); con.commit()
 try: assert not db.verify_audit_chain(security.audit_hash), 'IP field is excluded from the hash chain'
 finally:
  with sqlite3.connect(config.DB_PATH) as con: con.execute('UPDATE audit_log SET ip=? WHERE id=?',(old[1],old[0])); con.commit()

def test_configured_proxy_ignores_client_spoofed_prefix():
 from starlette.requests import Request
 import ipaddress
 r=Request({'type':'http','client':('10.0.0.1',1234),'headers':[(b'x-forwarded-for',b'203.0.113.99, 198.51.100.3')]})
 assert security.client_ip(r,(ipaddress.ip_network('10.0.0.0/24'),))=='198.51.100.3'
 assert security.client_ip(r,())=='10.0.0.1'

def test_mfa_confirmation_cannot_enable_replaced_pending_secret():
 c,e,*_=account()
 first=c.post('/api/auth/mfa/setup',headers=csrf(c)).json()['secret']
 c.post('/api/auth/mfa/setup',headers=csrf(c))
 assert not db.confirm_mfa_setup(e,first)
 assert not db.get_user(e)['mfa_enabled']

def test_recovery_consumption_is_atomic():
 from concurrent.futures import ThreadPoolExecutor
 c,e,p,*_=account(); _,code=enable_mfa(c)
 with ThreadPoolExecutor(max_workers=2) as pool:
  results=list(pool.map(lambda _:db.consume_recovery_code(e,security.hash_code(code)),range(2)))
 assert sorted(results)==[False,True]

def test_legacy_audit_rows_remain_verifiable():
 # An isolated old-format database row followed by new v2 events remains valid.
 old_path=db.DB_PATH
 temporary=STATE/'legacy.db'
 try:
  db.DB_PATH=temporary; db.init_db()
  h=security.audit_hash('genesis',1,'','old','detail')
  with sqlite3.connect(temporary) as con:
   con.execute('INSERT INTO audit_log(ts,email,action,detail,ip,prev_hash,row_hash,hash_version) VALUES (1,?,?,?,?,?,?,1)',('', 'old','detail','old-ip','genesis',h))
  db.audit_append(2,'','new','detail','new-ip',security.audit_hash)
  assert db.verify_audit_chain(security.audit_hash)
 finally: db.DB_PATH=old_path

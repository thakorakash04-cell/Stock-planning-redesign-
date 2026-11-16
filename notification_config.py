"""Validate worker configuration without connecting to SQL or exposing values."""
import os,tomllib
ALLOWED=('DATABASE_URL','RESET_FROM_EMAIL','RESEND_API_KEY','SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','GEMINI_API_KEY','GOOGLE_API_KEY','GEMINI_MODEL','ASK_AI_MODEL','ADMIN_EMAIL')

def load_configuration(environment=None):
 environment=os.environ if environment is None else environment
 raw=environment.get('PORTAL_SECRETS','');bundle={}
 if raw:
  try:bundle=tomllib.loads(raw)
  except tomllib.TOMLDecodeError:raise ValueError('PORTAL_SECRETS must contain valid Streamlit-style TOML: NAME = "value", one setting per line.') from None
 result={}
 for key in ALLOWED:
  value=environment.get(key) or bundle.get(key,'')
  if not isinstance(value,(str,int)):raise ValueError('Invalid value type for '+key+'.')
  result[key]=str(value)
 if result.get('SMTP_HOST')=='smtp.gmail.com':result['SMTP_PASSWORD']=''.join(result['SMTP_PASSWORD'].split())
 return result

def validate(configuration,product=False):
 required=['DATABASE_URL','RESET_FROM_EMAIL']+(['ADMIN_EMAIL'] if product else [])
 missing=[key for key in required if not configuration.get(key)]
 if not configuration.get('RESEND_API_KEY'):
  missing.extend(key for key in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD') if not configuration.get(key))
 if missing:raise ValueError('Missing GitHub Actions secrets: '+', '.join(dict.fromkeys(missing)))
 if not configuration['DATABASE_URL'].startswith(('postgresql://','postgres://')):raise ValueError('DATABASE_URL must be the existing portal PostgreSQL connection string.')
 return True

def main(product=False):
 try:validate(load_configuration(),product)
 except ValueError as exc:raise SystemExit(str(exc)) from None
 print('Required notification secrets are configured. No database or email request was made.')

if __name__=='__main__':main(product=False)

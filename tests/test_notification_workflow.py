import importlib.util
from pathlib import Path
import pytest,yaml
from notification_config import validate,load_configuration

CFG={'DATABASE_URL':'postgresql://test.invalid/example','RESET_FROM_EMAIL':'sender@example.invalid','RESEND_API_KEY':'synthetic-test-key','ADMIN_EMAIL':'admin@example.invalid'}

def test_missing_secrets_are_reported_by_name_not_value():
 assert validate(CFG,product=True)
 assert validate({k:v for k,v in CFG.items() if k!='ADMIN_EMAIL'})
 with pytest.raises(ValueError,match='ADMIN_EMAIL'):validate({k:v for k,v in CFG.items() if k!='ADMIN_EMAIL'},product=True)
 with pytest.raises(ValueError) as error:validate({'DATABASE_URL':CFG['DATABASE_URL'],'SMTP_PASSWORD':'do-not-print-this'})
 assert 'do-not-print-this' not in str(error.value)

def test_daily_workflow_schedule_and_permissions():
 workflow=yaml.load(Path('.github/workflows/daily-notifications.yml').read_text(),Loader=yaml.BaseLoader)
 assert workflow['on']['schedule'][0]['cron']=='0 21 * * *'
 assert 'push' not in workflow['on'] and 'pull_request' not in workflow['on']
 assert workflow['permissions']=={'contents':'read'}
 assert workflow['concurrency']['cancel-in-progress']=='false'
 job=workflow['jobs']['daily-report']
 assert job['env']['DATABASE_URL']=='${{ secrets.DATABASE_URL }}'
 assert job['steps'][2]['run']=='python notification_config.py'
 assert job['steps'][-1]['run']=='python notification_worker.py'
 assert not any('upload-artifact' in step.get('uses','') for step in job['steps'])

def test_single_toml_secret_and_individual_override():
 raw='DATABASE_URL = "postgresql://example.invalid/stock"\nRESET_FROM_EMAIL = "sender@example.invalid"\nSMTP_HOST = "smtp.gmail.com"\nSMTP_USER = "sender@example.invalid"\nSMTP_PORT = "587"\nSMTP_PASSWORD = "aaaa bbbb cccc dddd"\nADMIN_PASSWORD = "not-forwarded"\nGOOGLE_API_KEY = "synthetic-key"'
 cfg=load_configuration({'PORTAL_SECRETS':raw,'DATABASE_URL':''})
 assert validate(cfg)
 assert cfg['SMTP_PASSWORD']=='aaaabbbbccccdddd'
 assert cfg['GOOGLE_API_KEY']=='synthetic-key'
 assert 'ADMIN_PASSWORD' not in cfg
 assert load_configuration({'PORTAL_SECRETS':raw,'SMTP_PORT':'465'})['SMTP_PORT']=='465'
 with pytest.raises(ValueError) as error:load_configuration({'PORTAL_SECRETS':'PRIVATE_VALUE = "unclosed'})
 assert 'PRIVATE_VALUE' not in str(error.value)

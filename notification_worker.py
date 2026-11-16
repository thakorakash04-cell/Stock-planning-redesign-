"""Trusted scheduled entry point. No browser session, workbook scan or polling."""
import os
from stock_accounts.store import Store
from stock_accounts.notification_rules import _dispatch
from stock_accounts.mail_transport import send

def main():
 from notification_config import validate,load_configuration
 configuration=load_configuration()
 validate(configuration)
 # Existing Gemini helpers use environment settings. Only allowlisted keys
 # are loaded; bundled administrator passwords are deliberately ignored.
 os.environ.update(configuration)
 store=Store(configuration['DATABASE_URL'])
 sent=0
 for _ in range(50):
  result=_dispatch(store,None,configuration,
   lambda to,subject,body,key:send(configuration,to,subject,body,key))
  sent+=result['sent']
  if result['state']!='checked':break
  with store.transaction() as db:
   remaining=store.run(db,"SELECT count(*) AS n FROM stock_notice_jobs WHERE status='queued'").fetchone()['n']
  if not remaining:break
 else:raise RuntimeError('Notification queue remains pending after the bounded worker run. Inspect delivery history.')
 print('Notification dispatch completed; state:',result['state'],'sent:',sent)

if __name__=='__main__':main()

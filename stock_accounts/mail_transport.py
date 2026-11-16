"""Server-only mail transport with explicit submission uncertainty."""
SEND_REVISION=1
import json,smtplib,ssl
from email.message import EmailMessage
from urllib.request import Request,urlopen
from .scheduled_delivery import DeliveryDeferred,DeliveryUncertain

def send(configuration,to,subject,body,idempotency_key=None):
    markup=getattr(body,'html',None);body=str(body)
    cfg=configuration;sender=cfg.get('RESET_FROM_EMAIL') or cfg.get('ALERT_FROM_EMAIL')
    if not sender:raise DeliveryDeferred('Sender is not configured.')
    if cfg.get('RESEND_API_KEY'):
        headers={'Authorization':'Bearer '+cfg['RESEND_API_KEY'],'Content-Type':'application/json'}
        if idempotency_key:headers['Idempotency-Key']='portal-scheduled-'+idempotency_key
        payload={'from':sender,'to':[to],'subject':subject,'text':body}
        if markup:payload['html']=markup
        request=Request('https://api.resend.com/emails',data=json.dumps(payload).encode(),headers=headers,method='POST')
        try:
            with urlopen(request,timeout=20) as response:
                if response.status not in (200,201,202):raise DeliveryDeferred('Provider rejected delivery.')
        except Exception as exc:
            if idempotency_key:raise DeliveryDeferred('Provider delivery can be retried with the same idempotency key.') from exc
            raise DeliveryUncertain('Inspect provider logs before resending.') from exc
        return
    if not all(cfg.get(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD')):raise DeliveryDeferred('Configure SMTP or Resend.')
    attempted=False;accepted=False
    try:
        msg=EmailMessage();msg['From']=sender;msg['To']=to;msg['Subject']=subject
        if idempotency_key:msg['Message-ID']='<'+idempotency_key+'@workspace-alerts>'
        msg.set_content(body)
        if markup:msg.add_alternative(markup,subtype='html')
        port=int(cfg.get('SMTP_PORT') or 587);context=ssl.create_default_context()
        client=smtplib.SMTP_SSL(cfg['SMTP_HOST'],port,timeout=20,context=context) if port==465 else smtplib.SMTP(cfg['SMTP_HOST'],port,timeout=20)
        with client as smtp:
            if port!=465:smtp.starttls(context=context)
            smtp.login(cfg['SMTP_USER'],cfg['SMTP_PASSWORD']);attempted=True
            refused=smtp.send_message(msg)
            if refused:raise DeliveryDeferred('Recipient was rejected.')
            accepted=True
    except DeliveryDeferred:raise
    except Exception as exc:
        if accepted:return  # SMTP acknowledged delivery; a failed QUIT must not cause a duplicate.
        if attempted:raise DeliveryUncertain('SMTP delivery may already have been accepted.') from exc
        raise DeliveryDeferred('SMTP did not submit the message.') from exc


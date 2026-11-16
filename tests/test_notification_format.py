from unittest.mock import Mock,patch
from notification_format import compose
def sections():
 return [{'title':'Low stock','count':2,'bullets':['2 matching records.'],'tables':[{'title':'Details','headers':['Material','Stock'],'rows':[['<script>unsafe</script>',1234.5],['B',2000]],'count':2}]}]
def test_ai_bullets_and_exact_escaped_source_tables():
 provider=Mock(return_value={'sections':[{'id':'0','intro':['This section covers low stock.','The tables show saved matching details.'],'bullets':['Review the 2 matching records.']}]})
 message=compose('Report','IST',sections(),provider)
 assert '<ul>' in message.html and '<table' in message.html and '<th' in message.html
 assert 'Review the 2 matching records.' in message
 assert '1234.5' in message.html and '2000' in message.html
 assert '<script>' not in message.html and '&lt;script&gt;' in message.html
 assert '<script>' not in str(provider.call_args.args[1])
def test_ai_failure_and_invented_numbers_use_structured_fallback():
 for provider in [Mock(side_effect=TimeoutError()),Mock(return_value={'sections':[{'id':'0','bullets':['There are 999 matching records.']}]})]:
  message=compose('Fallback','IST',sections(),provider)
  assert '2 matching records.' in message and '999' not in message
  assert '<table' in message.html and '<ul>' in message.html
def test_large_tables_show_explicit_sampling_note():
 t={'title':'Rows','headers':['Material'],'rows':[[i] for i in range(60)],'count':70}
 message=compose('Report','IST',[{'title':'Rule','count':70,'tables':[t]}])
 assert 'Showing 50 of 70 records' in message and '<td' in message.html
def test_resend_and_smtp_receive_html_and_plain_alternatives():
 from stock_accounts import mail_transport as transport
 import json
 message=compose('Report','IST',sections())
 cfg={'RESET_FROM_EMAIL':'sender@example.invalid','RESEND_API_KEY':'mock'}
 with patch.object(transport,'urlopen') as http:
  http.return_value.__enter__.return_value.status=200
  transport.send(cfg,'recipient@example.invalid','Subject',message,'id')
  payload=json.loads(http.call_args.args[0].data)
  assert '<table' in payload['html'] and '1234.5' in payload['text']
 cfg={'RESET_FROM_EMAIL':'sender@example.invalid','SMTP_HOST':'mock','SMTP_USER':'mock','SMTP_PASSWORD':'mock'}
 with patch.object(transport.smtplib,'SMTP') as smtp:
  smtp.return_value.__enter__.return_value.send_message.return_value={}
  transport.send(cfg,'recipient@example.invalid','Subject',message,'id')
  sent=smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
  assert {p.get_content_type() for p in sent.iter_parts()}=={'text/plain','text/html'}


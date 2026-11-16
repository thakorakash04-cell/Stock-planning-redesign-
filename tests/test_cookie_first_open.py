"""Exercise the real mount/restore flow with a delayed browser component."""
import importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('daily_under_test',Path(__file__).resolve().parents[1]/'daily_sessions.py')
daily=importlib.util.module_from_spec(spec);spec.loader.exec_module(daily)
class Stopped(Exception):pass
class Rerun(Exception):pass

class CookieFirstOpen(unittest.TestCase):
 def run_mount(self,state,result=None):
  st=types.ModuleType('streamlit');components=types.ModuleType('streamlit.components');v2=types.ModuleType('streamlit.components.v2')
  st.components=components;components.v2=v2;st.session_state=state;st.query_params={};st.fragment=lambda f:f
  st.caption=lambda *a,**k:None;st.warning=lambda *a,**k:None;st.button=lambda *a,**k:False
  st.stop=lambda:(_ for _ in ()).throw(Stopped());st.rerun=lambda:(_ for _ in ()).throw(Rerun())
  mounted=[]
  def component(name,**kwargs):
   def render(**kwargs):mounted.append(kwargs);return result or types.SimpleNamespace()
   return render
  v2.component=component
  with patch.dict(sys.modules,{'streamlit':st,'streamlit.components':components,'streamlit.components.v2':v2}):
   daily.mount(types.SimpleNamespace(browser_namespace='test'))
  return mounted

 def test_validated_cookie_can_open_repeatedly_without_component_response(self):
  for _ in range(3):
   state={}
   with patch.object(daily,'request_client',return_value='client'),patch.object(daily,'restore',return_value={'email':'test@example.invalid'}) as restore:
    daily.restore_cookie(types.SimpleNamespace(browser_namespace='test'),state,{'workspace_day_test':'opaque-token'})
   restore.assert_called_once();self.assertTrue(state['actor']);self.assertEqual(len(self.run_mount(state)),1)
   self.assertNotIn('_daily_browser_checked',state)

 def test_absent_or_rejected_cookie_still_waits_for_browser_validation(self):
  for cookies in ({},{'workspace_day_test':'rejected-token'}):
   state={}
   with patch.object(daily,'request_client',return_value='client'),patch.object(daily,'restore',return_value=None):daily.restore_cookie(types.SimpleNamespace(browser_namespace='test'),state,cookies)
   with self.assertRaises(Stopped):self.run_mount(state)

 def test_pending_token_write_still_requires_receipt(self):
  with self.assertRaises(Stopped):self.run_mount({'actor':object(),'_daily_cookie_action':{'nonce':'write','value':'token'}})

 def test_background_browser_probe_does_not_rerun_authenticated_workspace(self):
  state={'actor':object(),'_daily_browser_instance':'i'}
  browser={'instance':'i','token':'','tokens':[],'at':1,'visible':True}
  self.run_mount(state,types.SimpleNamespace(session={'instance':'i','browser':browser},browser=browser))
  self.assertTrue(state['_daily_browser_checked'])

 def test_first_empty_browser_probe_reruns_to_display_normal_login(self):
  state={'_daily_browser_instance':'i'};browser={'instance':'i','token':'','tokens':[]}
  with self.assertRaises(Rerun):self.run_mount(state,types.SimpleNamespace(session={'instance':'i','browser':browser},browser=browser))
  self.assertTrue(state['_daily_browser_checked']);self.assertNotIn('actor',state)

if __name__=='__main__':unittest.main()

"""Preserve old iframe URLs while the active workspace component is upgraded."""
import ast,types,unittest
from pathlib import Path
from streamlit.components.lib.local_component_registry import LocalComponentRegistry
from streamlit.components.v1.custom_component import CustomComponent

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'stock_accounts/workspace_insights.py'
class WorkspaceRoutes(unittest.TestCase):
 def test_both_routes_resolve_to_current_frontend_and_share_request_key(self):
  tree=ast.parse(MODULE.read_text());registry=LocalComponentRegistry()
  def declare(name,**kwargs):
   registry.register_component(CustomComponent('stock_accounts.workspace_insights.'+name,path=kwargs['path']))
   return name
  scope={'Path':Path,'__file__':str(MODULE),'components':types.SimpleNamespace(declare_component=declare)}
  declarations=[node for node in tree.body if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call) and ast.unparse(node.value.func)=='components.declare_component']
  exec(compile(ast.Module(body=declarations,type_ignores=[]),'<workspace routes>','exec'),scope)
  self.assertEqual(scope['_component'],'stock_planning_web_ui_session_recovery_v57')
  for name in ['stock_planning_web_ui_cached_views_v56','stock_planning_web_ui_session_recovery_v57']:
   path=registry.get_component_path('stock_accounts.workspace_insights.'+name)
   self.assertEqual(path,str(ROOT/'frontend_dist'))
   self.assertTrue((Path(path)/'index.html').is_file())
  calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='_component']
  self.assertEqual(len(calls),1)
  key=next(arg.value.value for arg in calls[0].keywords if arg.arg=='key')
  self.assertEqual(key,'exact_website_ui')
  readers=[]
  for source in [tree,ast.parse((ROOT/'app.py').read_text())]:
   for node in ast.walk(source):
    if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='event' for target in node.targets) and isinstance(node.value,ast.Call) and ast.unparse(node.value.func)=='st.session_state.get':readers.append(node.value.args[0].value)
  self.assertGreaterEqual(len(readers),3);self.assertEqual(set(readers),{key})

if __name__=='__main__':unittest.main()

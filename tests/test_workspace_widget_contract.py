"""Host and component must exchange events through the same session widget."""
import ast
from pathlib import Path
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
class Session(dict):
    __getattr__=dict.__getitem__
    __setattr__=dict.__setitem__

class WorkspaceWidgetContract(unittest.TestCase):
    def setUp(self):
        self.workspace=ast.parse((ROOT/'stock_accounts/workspace_insights.py').read_text())
        self.host=ast.parse((ROOT/'app.py').read_text())
        calls=[n for n in ast.walk(self.workspace) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_component']
        self.assertEqual(len(calls),1)
        self.key=next(k.value.value for k in calls[0].keywords if k.arg=='key')

    def test_rendered_widget_is_read_by_rpc_navigation_activity_and_logout(self):
        readers=[]
        for tree in (self.workspace,self.host):
            for node in ast.walk(tree):
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='event' for t in node.targets):
                    value=node.value
                    if isinstance(value,ast.Call) and ast.unparse(value.func)=='st.session_state.get':
                        readers.append(value.args[0].value)
        self.assertGreaterEqual(len(readers),3)
        self.assertEqual(set(readers),{self.key})

    def test_account_events_after_each_login_are_consumed_once(self):
        fn=next(n for n in self.workspace.body if isinstance(n,ast.FunctionDef) and n.name=='process_account_navigation')
        calls=[];st=types.SimpleNamespace(session_state=Session())
        scope={'st':st,'AccessDenied':ValueError,'handle_request':lambda store,actor,event:calls.append(event['id']) or {'route':'settings'}}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<navigation>','exec'),scope)
        for login in range(3):
            st.session_state=Session({self.key:{'id':str(login),'action':'open_settings'}})
            scope['process_account_navigation'](None,None)
            scope['process_account_navigation'](None,None)
            self.assertEqual(st.session_state['_account_page'],'settings')
        self.assertEqual(calls,['0','1','2'])

if __name__=='__main__':unittest.main()

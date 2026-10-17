import unittest
from types import SimpleNamespace
from wechat_assistant import message_text, session_info, session_changed, listen_chat, MessageWindow, chat_info, reply_window, window_sessions

class RoutingTests(unittest.TestCase):
    def msg(self, text, attr='friend', kind='text'):
        return SimpleNamespace(content=text, attr=attr, type=kind)
    def test_mentions(self):
        self.assertEqual(message_text(self.msg('@贾维斯\u2005/muse 问题'), 'group', '贾维斯'), '/muse 问题')
        self.assertEqual(message_text(self.msg('请 @贾维斯 帮我'), 'group', '贾维斯'), '请  帮我')
        self.assertEqual(message_text(self.msg('@贾维斯\u200b\u2005/help'), 'group', '贾维斯'), '/help')
        self.assertEqual(message_text(self.msg('@贾维斯，帮我'), 'group', '贾维斯'), '，帮我')
        self.assertEqual(message_text(self.msg('你发这个@贾维斯 /status'), 'group', '贾维斯'), '你发这个 /status')
        for text in ('普通群消息','@所有人 你好','@贾维斯2 你好','email@贾维斯 问题'):
            self.assertIsNone(message_text(self.msg(text), 'group', '贾维斯'))
        self.assertIsNone(message_text(self.msg('@贾维斯 帮我', 'self'), 'group', '贾维斯'))
        self.assertIsNone(message_text(self.msg('照片', kind='image'), 'friend', '贾维斯'))
    def test_private(self):
        self.assertEqual(message_text(self.msg('/codex 任务'), 'friend', '贾维斯'), '/codex 任务')
        self.assertIsNone(message_text(self.msg('任务'), 'official', '贾维斯'))
    def test_binary_library_session_fallback(self):
        self.assertEqual(session_info(SimpleNamespace(content='好友甲\n[3条]新消息')), ('好友甲',3,'好友甲\n[3条]新消息'))
    def test_group_registration_only_reads_existing_windows(self):
        chat=SimpleNamespace(ChatInfo=lambda: {'chat_type':'group','chat_name':'项目群'})
        class Client:
            def GetAllSubWindow(self): return [chat]
            def AddListenChat(self, **kwargs): raise AssertionError('不能搜索或打开窗口')
            def GetSubWindow(self, name): raise AssertionError('只允许枚举已有窗口')
            def RemoveListenChat(self, *args, **kwargs): raise AssertionError('不能关闭窗口')
        self.assertIs(listen_chat(Client(), '项目群', lambda *args: None), chat)
    def test_registration_rejects_wrong_destination(self):
        wrong=SimpleNamespace(ChatInfo=lambda: {'chat_type':'friend','chat_name':'项目群'})
        client=SimpleNamespace(GetAllSubWindow=lambda: [wrong])
        with self.assertRaisesRegex(ValueError, '不匹配'):
            listen_chat(client, '项目群', lambda *args: None, 'group')
        client.GetAllSubWindow=lambda: []
        with self.assertRaisesRegex(ValueError, '手动打开'):
            listen_chat(client, '项目群', lambda *args: None)
        client.GetAllSubWindow=lambda: [wrong, wrong]
        with self.assertRaisesRegex(ValueError, '唯一'):
            listen_chat(client, '项目群', lambda *args: None)
    def test_listener_does_not_use_window_mutation_methods(self):
        import ast
        from pathlib import Path
        source=ast.parse(Path(__file__).with_name('wechat_assistant.py').read_text(encoding='utf-8'))
        forbidden={'ChatWith','Show','Close','SwitchToChat'}
        calls={node.func.attr for node in ast.walk(source)
               if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
        self.assertEqual(calls & forbidden,set())
        client=SimpleNamespace(GetSession=lambda: self.fail('主桌面不能读取并切换会话列表'))
        self.assertEqual(window_sessions(client),[])
    def test_window_opening_requires_explicit_isolated_vm_mode(self):
        opened=[]
        chat=SimpleNamespace(ChatInfo=lambda:{'chat_name':'项目群','chat_type':'group'})
        def add(**kwargs):opened.append(kwargs['nickname']);return chat
        client=SimpleNamespace(GetAllSubWindow=lambda:[],AddListenChat=add,GetSession=lambda:[])
        with self.assertRaises(ValueError):listen_chat(client,'项目群',None)
        self.assertEqual(opened,[])
        self.assertIs(listen_chat(client,'项目群',None,allow_open=True),chat)
        self.assertEqual(opened,['项目群'])
    def test_muted_group_mention_is_discovered_without_numeric_badge(self):
        self.assertTrue(session_changed(0,'项目群\n[有人@我] @贾维斯 /help',(0,'项目群\n旧预览'),'贾维斯'))
        self.assertFalse(session_changed(0,'项目群\n普通消息',(0,'项目群\n旧预览'),'贾维斯'))
        self.assertFalse(session_changed(0,'项目群\n[有人@我]',(0,'项目群\n[有人@我]'),'贾维斯'))

    def test_vm_opens_exact_session_row_without_search(self):
        from unittest.mock import Mock, patch
        chat=SimpleNamespace(ChatInfo=lambda:{'chat_name':'项目群','chat_type':'group'})
        row=SimpleNamespace(content='项目群\n[有人@我]',double_click=Mock())
        client=SimpleNamespace(GetAllSubWindow=Mock(side_effect=[[],[chat]]),
                               GetSession=lambda:[row],AddListenChat=Mock())
        with patch('wechat_assistant.time.sleep'):
            self.assertIs(listen_chat(client,'项目群',None,allow_open=True),chat)
        row.double_click.assert_called_once()
        client.AddListenChat.assert_not_called()
    def test_hidden_group_uses_native_identity_without_promoting_friend(self):
        native=SimpleNamespace(AutomationId='ChatSingleWindow123@chatroom',Name='项目群')
        chat=SimpleNamespace(ChatInfo=lambda:{'chat_type':'friend'},_api=SimpleNamespace(control=native))
        self.assertEqual(chat_info(chat),{'chat_type':'group','chat_name':'项目群'})
        native.AutomationId='ChatSingleWindow123'
        self.assertEqual(chat_info(chat),{'chat_type':'friend'})
    def test_reply_rebinds_changed_window_and_refuses_wrong_type(self):
        def window(name,kind):return SimpleNamespace(ChatInfo=lambda:{'chat_name':name,'chat_type':kind})
        chats={'项目群':window('另一个群','group')};removed=[]
        def drop(name):removed.append(name);chats.pop(name,None)
        def add(name,unread,**kwargs):
            self.assertEqual(kwargs['expected_kind'],'group')
            chats[name]=window(name,'group')
        recovered=reply_window(chats,'项目群','group',add,drop)
        self.assertIs(recovered,chats['项目群']);self.assertEqual(removed,['项目群'])
        chats['项目群']=window('项目群','friend')
        def wrong(name,unread,**kwargs):chats[name]=window(name,'friend')
        with self.assertRaisesRegex(ValueError,'拒绝发送'):
            reply_window(chats,'项目群','group',wrong,drop)
    def test_polling_keeps_two_people_and_repeated_identical_requests(self):
        def row(sender,text,id): return SimpleNamespace(sender=sender,content=text,id=id,attr='friend',type='text')
        first=row('甲','@贾维斯 /help','old')
        inbox=MessageWindow([first])
        self.assertEqual(inbox.take_new([]),[])
        redraw=row('甲','@贾维斯 /help','redraw')
        self.assertEqual(inbox.take_new([redraw]),[])
        again=row('甲','@贾维斯 /help','new1')
        other=row('乙','@贾维斯 /status','new2')
        self.assertEqual(inbox.take_new([redraw,again,other]),[again,other])
        nextrow=row('乙','@贾维斯 下一项','new3')
        self.assertEqual(inbox.take_new([other,nextrow]),[nextrow])

if __name__ == '__main__':
    unittest.main()

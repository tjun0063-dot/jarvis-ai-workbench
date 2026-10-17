import io,json,sys,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import wechat_assistant as adapter


class PauseIntegrationTests(unittest.TestCase):
    def test_real_driver_loop_pauses_all_scans_and_sends_then_resumes_without_restart(self):
        events=[];state={'paused':False,'scans':0};resumed_scan=threading.Event()
        deadline=time.time()*1000+10000
        commands=[{'type':'ui_pause','id':'pause','paused':True,'expiresAt':deadline},
                  {'type':'send','id':'text','to':'any','text':'must not send'},
                  {'type':'send_file','id':'file','to':'any','file':{}},
                  {'type':'ui_pause','id':'resume','paused':False,'expiresAt':deadline}]
        class Input:
            def readline(self):return json.dumps({'account':'贾维斯','isolatedVm':True})+'\n'
            def __iter__(self):
                for command in commands:yield json.dumps(command)+'\n'
                resumed_scan.wait(4)
                yield json.dumps({'type':'shutdown'})+'\n'
        def emit(event):
            events.append(event)
            if event['type']=='health':state['paused']=event['uiPaused']
        def session_rows(*args):
            self.assertFalse(state['paused'],'paused driver accessed the WeChat UI')
            state['scans']+=1
            if state['scans']>1:resumed_scan.set()
            return []
        def subwindows():
            self.assertFalse(state['paused'],'paused driver enumerated windows')
            return []
        wx=SimpleNamespace(nickname='贾维斯',GetAllSubWindow=Mock(side_effect=subwindows))
        fake=SimpleNamespace(WeChat=Mock(return_value=wx),WxParam=SimpleNamespace(SPECIAL_SESSION_NAME=()))
        with tempfile.TemporaryDirectory() as temp,patch.dict(sys.modules,{'wxauto4':fake}),\
             patch.object(sys,'stdin',Input()),patch.object(sys,'stdout',io.StringIO()),\
             patch.object(adapter,'__file__',str(Path(temp)/'wechat_assistant.py')),\
             patch.object(adapter,'emit',side_effect=emit),\
             patch.object(adapter,'window_sessions',side_effect=session_rows):
            adapter.main()
        self.assertTrue(resumed_scan.is_set(),'resuming did not restart scanning')
        acks={e['id']:e for e in events if e['type']=='ack'}
        self.assertTrue(acks['pause']['uiPaused']);self.assertFalse(acks['resume']['uiPaused'])
        self.assertIn('已暂停',acks['text']['error']);self.assertIn('已暂停',acks['file']['error'])
        fake.WeChat.assert_called_once()

if __name__=='__main__':unittest.main()

import base64
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import Mock
from muse_artifacts import remote_path, attachment_list, download


class MuseFilesTests(unittest.TestCase):
    def test_explicit_task_scope_only_no_other_thread_or_private_paths(self):
        task=str(uuid.uuid4());prefix='.jarvis-outbox/'+task
        for value in ('/home/hatch/'+prefix+'/图.png',prefix+'/图.png','/'+prefix+'/图.png'):
            self.assertEqual(remote_path(value,task),prefix+'/图.png')
        for value in ('/etc/passwd',prefix+'/../secret',prefix+'/link/../../secret',
                      '.jarvis-outbox/'+str(uuid.uuid4())+'/other.txt','https://example.com/image.png'):
            with self.assertRaises(ValueError):remote_path(value,task)
        raw='完成\n```workbench-artifacts\n{"files":[{"path":"'+prefix+'/图.png","name":"图.png"}]}\n```'
        text,files=attachment_list(raw,task)
        self.assertEqual(text,'完成');self.assertEqual(files,[{'path':prefix+'/图.png','name':'图.png'}])

    def test_binary_read_preserves_exact_bytes_avoids_pdf_export(self):
        raw=b'\x00\xffPPTX bytes';gateway=Mock()
        gateway.call_json.side_effect=[{'kind':'file','size':len(raw)},
            {'offset':0,'len':len(raw),'eof':True,'data_base64':base64.b64encode(raw).decode()}]
        with tempfile.TemporaryDirectory() as temp:
            download(gateway,[{'path':'scope/file','name':'演示.pptx'}],temp)
            self.assertEqual((Path(temp)/'演示.pptx').read_bytes(),raw)
        self.assertEqual([c.args[0] for c in gateway.call_json.call_args_list],['fs.stat','fs.read'])

    def test_bad_or_truncated_chunk_is_never_published(self):
        for reply in ({'offset':1,'len':2,'eof':True,'data_base64':'AAA='},
                      {'offset':0,'len':2,'eof':True,'data_base64':'@@@@'},
                      {'offset':0,'len':0,'eof':False,'data_base64':''}):
            gateway=Mock();gateway.call_json.side_effect=[{'kind':'file','size':4},reply]
            with tempfile.TemporaryDirectory() as temp:
                with self.assertRaises((ValueError,Exception)):
                    download(gateway,[{'path':'scope/file','name':'video.mp4'}],temp)
                self.assertEqual(list(Path(temp).iterdir()),[])

if __name__=='__main__':unittest.main()

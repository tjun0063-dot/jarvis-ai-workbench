import hashlib
import io
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import Mock
from file_transfer import download_file, send_attachment, checked_path


class Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {'Content-Length':str(len(data))}


class TransferTests(unittest.TestCase):
    def command(self, name='演示.pptx', data=b'\x00\xffbinary'):
        return {'type':'send_file','id':str(uuid.uuid4()),'to':'member-A',
                'file':{'name':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()},
                'expiresAt':time.time()*1000+10000}

    def test_exact_bytes_and_group_member_label_then_file(self):
        with tempfile.TemporaryDirectory() as temp:
            command=self.command()
            path=download_file(command,Path(temp),lambda _:Response(b'\x00\xffbinary'))
            chat=Mock()
            send_attachment(chat,command,temp,'group','甲')
            chat.SendMsg.assert_called_once_with('回复 甲：\n附件：演示.pptx')
            chat.SendFiles.assert_called_once_with(str(path))
            self.assertEqual(path.read_bytes(),b'\x00\xffbinary')

    def test_corrupt_truncated_or_expired_file_is_not_sent(self):
        with tempfile.TemporaryDirectory() as temp:
            command=self.command()
            with self.assertRaisesRegex(ValueError,'校验'):
                download_file(command,temp,lambda _:Response(b'\x00\x00binary'))
            with self.assertRaisesRegex(ValueError,'长度'):
                download_file(command,temp,lambda _:Response(b'a'))
            self.assertFalse((Path(temp)/command['id']/command['file']['name']).exists())
            command['expiresAt']=0
            with self.assertRaisesRegex(ValueError,'过期'):
                download_file(command,temp,lambda _:Response(b'\x00\xffbinary'))

    def test_refuse_path_traversal_and_changed_cached_file(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ('../a','a:stream','CON.txt','x\\a.png'):
                with self.assertRaises(ValueError):
                    download_file(self.command(name),temp,lambda _:Response(b'\x00\xffbinary'))
            command=self.command('photo.png')
            path=download_file(command,temp,lambda _:Response(b'\x00\xffbinary'))
            path.write_bytes(b'changed')
            chat=Mock()
            with self.assertRaises(ValueError):send_attachment(chat,command,temp,'friend','乙')
            chat.SendFiles.assert_not_called()

    def test_wechat_failure_remains_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            command=self.command('video.mp4')
            download_file(command,temp,lambda _:Response(b'\x00\xffbinary'))
            chat=Mock();chat.SendFiles.return_value={'status':'失败','message':'微信拒绝该文件'}
            with self.assertRaisesRegex(ValueError,'拒绝'):
                send_attachment(chat,command,temp,'friend','乙')

if __name__=='__main__':unittest.main()

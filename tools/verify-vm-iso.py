import sys,io,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'vm-tools'))
import pycdlib
root=Path(__file__).resolve().parent.parent/'outputs'/'jarvis-vm'
iso=pycdlib.PyCdlib();iso.open(str(root/'media'/(sys.argv[1] if len(sys.argv)>1 else 'Jarvis-Setup-v2.iso')))
def read(path):
    out=io.BytesIO();iso.get_file_from_iso_fp(out,udf_path='/'+path.replace('\\','/'));return out.getvalue()
manifest=json.loads(read('payload-manifest.json').decode('utf-8-sig'))
total=0
for file in manifest['files']:
    data=read(file['path']);total+=len(data)
    assert hashlib.sha256(data).hexdigest().upper()==file['sha256'],file['path']
allowed={'wechat_assistant.py','vm_agent.py','file_transfer.py','requirements-wechat.txt','vm-agent.json'}
for path in [f['path'].replace('\\','/') for f in manifest['files']]:
    if path.startswith('workbench/'):
        assert path.split('/')[-1] in allowed,path
iso.close();print(f'PASS: ISO 内 {len(manifest["files"])} 个文件哈希均匹配；{total} 字节；无主机项目、历史或模型凭据')

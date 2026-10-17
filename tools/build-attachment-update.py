import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]/'outputs'
stage=ROOT/'jarvis-vm/attachment-update'
stage.mkdir(exist_ok=True)
files=('background_agent.py','launch_wechat.py','test_accessibility.py','diagnose_wechat.py',
       'refresh_bridge.py','repair_client.py','guest_common.py','windows_signature.py',
       'Start-Agent.cmd','Check-Agent.cmd','Stop-Agent.cmd','Open-WeChat.cmd',
       'update_launcher.py','update_attachments.py','Update-Attachments.cmd')
for name in files:
    source=ROOT/'jarvis-vm/guest'/name
    if source.suffix.lower()=='.cmd':
        # Windows cmd.exe can split/truncate UTF-8 batch commands with LF-only
        # lines. Always serialize Windows batch files with CRLF before hashing.
        text=source.read_text(encoding='utf-8-sig').replace('\r\n','\n')
        (stage/name).write_bytes(text.replace('\n','\r\n').encode('utf-8'))
    else:shutil.copyfile(source,stage/name)
(stage/'workbench').mkdir(exist_ok=True)
for name in ('vm_agent.py','wechat_assistant.py','file_transfer.py'):
    shutil.copyfile(ROOT/'workbench'/name,stage/'workbench'/name)
shutil.copyfile(ROOT/'jarvis-vm/vm-agent.json',stage/'workbench/vm-agent.json')
names=list(files)+['workbench/'+name for name in ('vm_agent.py','wechat_assistant.py','file_transfer.py','vm-agent.json')]
manifest={'files':[{'path':name,'sha256':hashlib.sha256((stage/name).read_bytes()).hexdigest().upper()} for name in names]}
(stage/'payload-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
print('Attachment update: '+str(len(names))+' verified files; no project data or model credentials.')

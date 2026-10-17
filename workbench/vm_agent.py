"""Run inside the Jarvis VM. Only the dedicated relay can issue send commands."""
import http.client, json, os, queue, subprocess, sys, threading, time, uuid
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
import ipaddress
from file_transfer import download_file, spool_root

root=Path(__file__).resolve().parent
print('正在检查虚拟机环境与连接配置。',flush=True)
import win32com.client
machines=win32com.client.GetObject('winmgmts:').ExecQuery('SELECT Model,Manufacturer FROM Win32_ComputerSystem')
if not any(str(m.Model)=='Virtual Machine' and 'Microsoft' in str(m.Manufacturer) for m in machines):
    raise SystemExit('此连接器只能在 Hyper-V 虚拟机内部启动，主桌面不会执行窗口操作')
config=json.loads((root/'vm-agent.json').read_text(encoding='utf-8-sig'))
base=config['relay'].rstrip('/')
address=urlparse(base)
if (address.scheme!='http' or address.port!=8791 or address.path or address.username
        or address.password or address.query or address.fragment or not config.get('token')
        or not ipaddress.ip_address(address.hostname).is_private):
    raise SystemExit('请使用部署包生成的虚拟机配置')
relay_opener=build_opener(ProxyHandler({}))
run_id=str(uuid.uuid4())
events=queue.Queue(maxsize=200)
adapter_failed=threading.Event()
stopping=threading.Event()
print('正在连接已登录的微信；连接成功后请保持此窗口运行。',flush=True)
child=subprocess.Popen([sys.executable,'-u',str(root/'wechat_assistant.py')],
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW,
    env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
child.stdin.write(json.dumps({'account':config.get('account','贾维斯'),
    'clientPath':str(root.parent/'wechat-assistant-4.1.8.107'/'client'/'Weixin.exe'),
    'listenChats':config.get('listenChats',[]),'isolatedVm':True,
    'uiPaused':os.environ.get('JARVIS_AGENT_START_PAUSED')=='1'},ensure_ascii=False)+'\n')
child.stdin.flush()

def post(endpoint,payload,timeout=25):
    data=json.dumps({'runId':run_id,**payload},ensure_ascii=False).encode('utf-8')
    request=Request(base+endpoint,data=data,headers={
        'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
    with relay_opener.open(request,timeout=timeout) as response:
        return json.loads(response.read())

def open_file(command_id):
    request=Request(base+'/v1/file',data=json.dumps({'runId':run_id,'id':command_id}).encode('utf-8'),
        headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
    return relay_opener.open(request,timeout=120)

def upload_material(event):
    file=Path(event.get('localPath',''))
    meta=event.get('file') or {}
    if not file.is_file() or file.stat().st_size!=meta.get('size'):
        raise ValueError('待上传材料缺失或大小已变化')
    connection=http.client.HTTPConnection(address.hostname,address.port,timeout=180)
    connection.putrequest('POST','/v1/material')
    connection.putheader('Authorization','Bearer '+config['token'])
    connection.putheader('Content-Type','application/octet-stream')
    connection.putheader('Content-Length',str(meta['size']))
    connection.putheader('X-Jarvis-Run-Id',run_id)
    connection.putheader('X-Jarvis-Collection-Id',str(event.get('collectionId','')))
    connection.putheader('X-Jarvis-Material-Id',str(meta.get('id','')))
    connection.putheader('X-Jarvis-Sha256',str(meta.get('sha256','')))
    connection.putheader('X-Jarvis-File-Name',quote(str(meta.get('name','')),safe=''))
    connection.endheaders()
    with file.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):connection.send(block)
    response=connection.getresponse();body=response.read(65536)
    connection.close()
    if response.status!=200:
        try:message=json.loads(body).get('error')
        except Exception:message=None
        raise ValueError(message or '主机拒绝接收材料 HTTP '+str(response.status))
    file.unlink(missing_ok=True)

def read_events():
    had_error=False
    for line in child.stdout:
        try:
            event=json.loads(line)
            if event.get('type') in ('ready','health'):
                event['fileProtocol']=1
                event['materialProtocol']=1
                event['controlProtocol']=1
            if event.get('type') in ('error','warning'):
                print('微信连接器：'+str(event.get('message','')),flush=True)
            if event.get('type')=='error':
                had_error=True;adapter_failed.set()
            if event.get('type')=='ready':
                print('微信窗口已接入，正在确认主机连接。',flush=True)
            if event.get('type')=='material':
                try:upload_material(event)
                except Exception as exc:events.put({'type':'warning','message':'材料上传失败：'+str(exc)[:300]})
                continue
            events.put(event)
        except ValueError: pass
    if not had_error and not stopping.is_set():
        message='虚拟机微信连接器已退出，请查看 Agent-result.txt 中的原始错误。'
        print(message,flush=True);adapter_failed.set()
        events.put({'type':'error','message':message})
    events.put(None)

def read_diagnostics():
    for line in child.stderr:
        print(line.rstrip(),file=sys.stderr,flush=True)

def push_events():
    while True:
        event=events.get()
        if event is None:return
        attempts=0
        while True:
            try:
                post('/v1/events',{'event':event},timeout=5)
                if event.get('type')=='ready':
                    print('已连接主机工作台，窗口操作已暂停；请在主机点击恢复监听。' if event.get('uiPaused') else '已连接主机工作台，正在监听私聊和群内艾特。',flush=True)
                break
            except HTTPError as exc:
                if exc.code in (400,401,403,409):
                    print('主机拒绝连接，请核对配置或停止重复的虚拟机连接器。',flush=True)
                    adapter_failed.set()
                    if child.poll() is None:child.terminate()
                    return
                time.sleep(2)
            except Exception:
                attempts+=1
                if child.poll() is not None and attempts>=2:
                    print('启动错误未能回传主机，请查看本地 Agent-result.txt。',flush=True)
                    return
                time.sleep(2)

reader=threading.Thread(target=read_events,daemon=True)
pusher=threading.Thread(target=push_events,daemon=True)
diagnostics=threading.Thread(target=read_diagnostics,daemon=True)
reader.start();pusher.start();diagnostics.start()
try:
    while child.poll() is None:
        stop_path=os.environ.get('JARVIS_AGENT_STOP_FILE')
        if stop_path and Path(stop_path).is_file():
            stopping.set()
            child.stdin.write(json.dumps({'type':'shutdown'})+'\n');child.stdin.flush()
            child.wait(timeout=5)
            break
        try:
            for command in post('/v1/poll',{}).get('commands',[]):
                if command.get('type') in ('send','send_file','ui_pause','collect_start','collect_stop') and command.get('expiresAt',0)<time.time()*1000:
                    events.put({'type':'ack','id':command.get('id'),'error':'回传命令已过期，未发送'})
                    continue
                if command.get('type')=='send_file':
                    try:
                        download_file(command,spool_root(),open_file)
                    except Exception as exc:
                        events.put({'type':'ack','id':command.get('id'),'error':'附件下载失败：'+str(exc)[:300]})
                        continue
                child.stdin.write(json.dumps(command,ensure_ascii=False)+'\n');child.stdin.flush()
                if command.get('type')=='shutdown':
                    stopping.set()
                    child.wait(timeout=5);raise SystemExit(0)
        except HTTPError as exc:
            if exc.code in (400,401,403,409):raise SystemExit('连接配置被主机拒绝或监听已停止')
            time.sleep(2)
        except Exception: time.sleep(2)
finally:
    if child.poll() is None:child.terminate()
    child.wait(timeout=5)
    reader.join(timeout=3);diagnostics.join(timeout=3);pusher.join(timeout=12)
if adapter_failed.is_set() or child.returncode:
    raise SystemExit(1)

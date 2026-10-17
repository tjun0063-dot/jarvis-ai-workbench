"""Desktop WeChat adapter. JSON lines over stdio; library output stays on stderr."""
import hashlib, json, sys, threading, queue, time, uuid, re
from collections import OrderedDict
from pathlib import Path
protocol = sys.stdout
output_lock = threading.Lock()

def emit(event):
    with output_lock:
        protocol.write(json.dumps(event, ensure_ascii=False) + '\n')
        protocol.flush()

def session_info(session):
    content = str(getattr(session, 'content', ''))
    lines = [s.strip() for s in content.splitlines() if s.strip()]
    name = str(getattr(session, 'name', '') or (lines[0] if lines else ''))
    match = re.search(r'\[(\d+)条\]', content)
    unread = int(getattr(session, 'unread_count', 0) or (match.group(1) if match else 0))
    return name, unread, content

def session_changed(unread, content, old, account):
    # Muted groups can show an @ indicator without a numeric unread badge.
    mentioned = '有人@我' in content or ('@' + account) in content
    return bool((unread or mentioned) and
                (old is None or content != old[1] or unread > old[0]))

def message_text(msg, kind, account):
    if getattr(msg, 'attr', '') != 'friend' or getattr(msg, 'type', '') != 'text':
        return None
    text = str(getattr(msg, 'content', '')).replace('\u200b', '').replace('\ufeff', '').strip()
    if kind == 'group':
        mention = re.compile(r'(?<![A-Za-z0-9_@])@' + re.escape(account) + r'(?=\s|$|[，。！？、,:：!?])')
        if not mention.search(text):
            return None
        text = mention.sub('', text).strip()
    elif kind != 'friend':
        return None
    return text or '/help'

def chat_info(chat):
    info = dict(chat.ChatInfo())
    # Some library reads lose the header count while a group is hidden. Its
    # native window identity still identifies an actual group, independently
    # of the selected main chat. Never use this fallback for friend windows.
    control = getattr(getattr(chat, '_api', None), 'control', None)
    if control is not None:
        try:
            aid = str(getattr(control, 'AutomationId', ''))
            if re.fullmatch(r'ChatSingleWindow\d+@chatroom', aid):
                info['chat_type'] = 'group'
                info['chat_name'] = str(control.Name)
        except Exception:
            pass
    try:
        if int(info.get('group_member_count', 0)) > 1:
            info['chat_type'] = 'group'
    except (TypeError, ValueError):
        pass
    return info

def listen_chat(wx, name, callback, expected_kind=None, allow_open=False):
    # Attach only. AddListenChat can search, activate, open and resize windows.
    # Never call it during discovery or recovery on the user's working desktop.
    candidates = [c for c in wx.GetAllSubWindow()
                  if chat_info(c).get('chat_name') == name]
    if not candidates and allow_open:
        sessions = [s for s in wx.GetSession() if session_info(s)[0] == name]
        if len(sessions) > 1:
            raise ValueError('存在同名会话，拒绝自动选择：' + name)
        if len(sessions) == 1:
            # Open the exact visible session row; avoid search and its focus
            # race with other windows. This path is restricted to the VM.
            sessions[0].double_click()
            time.sleep(0.5)
            candidates = [c for c in wx.GetAllSubWindow()
                          if chat_info(c).get('chat_name') == name]
        if not candidates:
            result = wx.AddListenChat(nickname=name, callback=callback)
        else:
            result = candidates[0]
        if callable(getattr(result, 'ChatInfo', None)):
            candidates = [result]
        else:
            candidates = [c for c in wx.GetAllSubWindow()
                          if chat_info(c).get('chat_name') == name]
    if len(candidates) != 1:
        raise ValueError('请手动打开唯一的独立聊天窗口：' + name)
    chat = candidates[0]
    info = chat_info(chat)
    if (info.get('chat_name') != name or info.get('chat_type') not in ('friend', 'group')
            or expected_kind and info.get('chat_type') != expected_kind):
        raise ValueError('聊天窗口名称或类型不匹配：' + name)
    return chat

def window_sessions(wx, isolated_vm=False):
    return wx.GetSession() if isolated_vm else []

def reply_window(chats, name, kind, add_chat, drop_chat):
    chat = chats.get(name)
    try:
        info = chat_info(chat) if chat else {}
    except Exception:
        info = {}
    if info.get('chat_name') != name or info.get('chat_type') != kind:
        if chat:
            drop_chat(name)
        add_chat(name, 0, capture=False, expected_kind=kind)
        chat = chats[name]
        info = chat_info(chat)
    if info.get('chat_name') != name or info.get('chat_type') != kind:
        raise ValueError('回复目标名称或类型不匹配，拒绝发送')
    return chat

class MessageWindow:
    """Track visible rows across redraws without replaying the startup history."""
    def __init__(self, messages):
        self.keys = [self.key(m) for m in messages]

    @staticmethod
    def key(msg):
        return (str(getattr(msg, 'attr', '')), str(getattr(msg, 'type', '')),
                str(getattr(msg, 'sender', '')), str(getattr(msg, 'content', '')))

    def take_new(self, messages):
        if not messages:
            return []
        keys = [self.key(m) for m in messages]
        end = 0
        # Longest suffix overlap, earliest occurrence: two identical new requests
        # must not collapse into one when rows have identical content.
        for length in range(min(len(self.keys), len(keys)), 0, -1):
            suffix = self.keys[-length:]
            found = next((i + length for i in range(len(keys)-length+1)
                          if keys[i:i+length] == suffix), None)
            if found is not None:
                end = found
                break
        self.keys = keys
        return messages[end:]

def main():
    config = json.loads(sys.stdin.readline())
    isolated_vm = config.get('isolatedVm') is True
    account = str(config.get('account', '贾维斯')).strip()
    if not account:
        raise ValueError('请填写助手号昵称')
    target_path = str(config.get('clientPath', '')).strip()
    if target_path:
        import os, psutil
        expected_path = os.path.normcase(os.path.abspath(target_path))
        found = False
        for process in psutil.process_iter(['name', 'exe']):
            if str(process.info['name']).lower() != 'weixin.exe':
                continue
            actual_path = process.info['exe']
            if not actual_path:
                raise ValueError('无法确认运行中的微信版本，请先手动退出新版微信')
            if os.path.normcase(os.path.abspath(actual_path)) != expected_path:
                raise ValueError('当前运行的是其他目录的微信，请先从托盘退出新版，再打开贾维斯兼容版')
            found = True
        if not found:
            raise ValueError('兼容微信还未打开。请点击“打开兼容微信”，扫码登录贾维斯，再启动助手监听')
    sys.stdout = sys.stderr
    from wxauto4 import WeChat, WxParam
    WxParam.ENABLE_FILE_LOGGER = False
    WxParam.TELEMETRY_ENABLED = False
    WxParam.CHAT_WINDOW_SIZE = (1000, 900)
    try:
        wx = WeChat(resize=False, ads=False)
    except Exception as exc:
        version = ''
        try:
            import psutil, win32api
            for process in psutil.process_iter(['name', 'exe']):
                if str(process.info['name']).lower() == 'weixin.exe' and process.info['exe']:
                    value = win32api.GetFileVersionInfo(process.info['exe'], '\\')
                    high, low = value['FileVersionMS'], value['FileVersionLS']
                    version = '.'.join(str(part) for part in (high >> 16,high & 65535,low >> 16,low & 65535))
                    break
        except Exception:
            pass
        hint = ('当前客户端 ' + version + '；' if version else '') + 'wxauto4 免费版官方支持到微信 4.1.8.107。主窗口不可访问或版本不兼容，无法接收消息。'
        raise ValueError(hint + '\n连接器原始错误：' + str(exc)) from exc
    actual = str(getattr(wx, 'nickname', '')).strip()
    if actual != account:
        raise ValueError('当前微信昵称与“' + account + '”不一致，未启动监听；请打开助手小号微信主窗口')
    outgoing, received = queue.Queue(), queue.Queue()
    chats, routes, seen, collections = OrderedDict(), OrderedDict(), OrderedDict(), OrderedDict()
    inboxes, kinds, session_snapshots, next_attempt = {}, {}, {}, {}
    requested = {item['chat'] for item in config.get('listenChats', [])[:32]
                 if item.get('chat') and item.get('kind') in ('friend','group')}
    diagnostics = {'scans':0,'rows':0,'newRows':0,'accepted':0,'filtered':{},'lastScan':None}
    diagnostic_file = Path(__file__).parent / 'data' / 'assistant-diagnostics.json'
    def callback(msg, chat):
        received.put((msg, chat))
    material_root = Path(__file__).parent / 'data' / 'material-spool'
    material_root.mkdir(parents=True, exist_ok=True)
    def matching_collection(name, kind, sender):
        now=time.time()*1000
        for collection_id, item in list(collections.items()):
            if item['expiresAt'] <= now:
                collections.pop(collection_id, None)
                continue
            if (item['name'],item['kind'],item['sender']) == (name,kind,sender):
                return collection_id,item
        return None,None
    def downloaded_material(msg, collection_id):
        kind=str(getattr(msg,'type',''))
        directory=material_root/collection_id
        directory.mkdir(parents=True,exist_ok=True)
        before={p.resolve() for p in directory.iterdir() if p.is_file()}
        if kind=='image': result=msg.download(dir_path=str(directory),original=True)
        elif kind=='video': result=msg.download(dir_path=str(directory),original=True,timeout=60)
        elif kind=='file': result=msg.download(dir_path=str(directory),timeout=120)
        else: raise ValueError('暂不支持收集此类微信消息：'+kind)
        candidates=[]
        if isinstance(result,(str,Path)):
            value=Path(result);candidates.append(value if value.is_absolute() else directory/value)
        elif isinstance(result,dict):
            for key in ('path','file','filepath','data'):
                if isinstance(result.get(key),(str,Path)):
                    value=Path(result[key]);candidates.append(value if value.is_absolute() else directory/value)
        candidates.extend(p for p in directory.iterdir() if p.is_file() and p.resolve() not in before)
        file=next((p for p in reversed(candidates) if p.is_file()),None)
        if file is None:raise ValueError('微信没有返回已下载材料的路径')
        file=file.resolve();base=directory.resolve()
        if file.parent!=base:raise ValueError('材料下载路径超出临时目录')
        size=file.stat().st_size
        if size>100*1024*1024:raise ValueError('单个材料超过 100MB')
        digest=hashlib.sha256()
        with file.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        return {'type':'material','collectionId':collection_id,'localPath':str(file),
                'file':{'id':str(uuid.uuid4()),'name':file.name,'size':size,'sha256':digest.hexdigest()}}
    def dispatch(msg, chat):
        info = chat_info(chat)
        kind, name = info.get('chat_type'), str(info.get('chat_name', '')).strip()
        text = message_text(msg, kind, account)
        msg_attr,msg_type=str(getattr(msg,'attr','')),str(getattr(msg,'type',''))
        sender = str(getattr(msg, 'sender', '') or name)
        collection_id,collection=matching_collection(name,kind,sender)
        is_material=msg_attr=='friend' and msg_type in ('image','video','file') and collection is not None
        if text is None and not is_material:
            category = str(getattr(msg, 'attr', '')) + ':' + str(getattr(msg, 'type', ''))
            diagnostics['filtered'][category] = diagnostics['filtered'].get(category, 0) + 1
        if (text is None and not is_material) or name not in chats:
            return
        mid = str(getattr(msg, 'id', '') or getattr(msg, 'hash', '') or uuid.uuid4())
        key = (name, mid)
        if key in seen:
            return
        seen[key] = True
        diagnostics['accepted'] += 1
        while len(seen) > 5000:
            seen.popitem(last=False)
        if is_material:
            emit(downloaded_material(msg,collection_id))
            return
        route = str(uuid.uuid4())
        routes[route] = (name, chat, kind, sender)
        while len(routes) > 5000:
            routes.popitem(last=False)
        emit({'type':'message','sender':sender,'id':mid,'text':text,
              'context':{'chat':name,'kind':kind,'route':route}})
    def add_chat(name, unread, capture=True, expected_kind=None):
        if len(chats) >= 32:
            oldest, _ = chats.popitem(last=False)
            inboxes.pop(oldest, None)
            kinds.pop(oldest, None)
        chat = listen_chat(wx, name, callback, expected_kind, allow_open=isolated_vm)
        if isolated_vm:
            wx.RemoveListenChat(name, close_window=False)
        chats[name] = chat
        kinds[name] = chat_info(chat)['chat_type']
        emit({'type':'listening','count':len(chats),
              'groupCount':sum(kinds.get(n) == 'group' for n in chats)})
        messages = chat.GetAllMessage()
        inboxes[name] = MessageWindow(messages)
        if not capture:
            return
        # Registration skips history: deliver only the newly unread tail.
        for msg in messages[-max(1, min(unread, 30)):]:
            dispatch(msg, chat)
    def drop_chat(name):
        chats.pop(name, None)
        inboxes.pop(name, None)
        kinds.pop(name, None)
    def reader():
        for line in sys.stdin:
            try:
                outgoing.put(json.loads(line))
            except ValueError:
                pass
        outgoing.put({'type':'shutdown'})
    threading.Thread(target=reader, daemon=True).start()
    for session in window_sessions(wx, isolated_vm):
        name, unread, content = session_info(session)
        session_snapshots[name] = (unread, content)
    if isolated_vm:
        for name in sorted(requested):
            try:
                add_chat(name, 0, capture=False)
            except Exception as exc:
                next_attempt[name] = time.monotonic() + 30
                emit({'type':'warning','message':'虚拟机聊天接入失败：' + str(exc)})
    # Enumerate existing windows only; do not switch the selected main chat.
    start_paused=config.get('uiPaused') is True
    emit({'type':'ready','account':actual,'mode':'friends-and-mentions',
          'listeningMode':'isolated-vm' if isolated_vm else 'existing-windows','replyNeedsFocus':True,'uiPaused':start_paused})
    last_poll, last_discovery, errors = 0, 0, 0
    ui_paused, last_paused_health = start_paused, 0
    def heartbeat(paused):
        # Paused heartbeats read only cached Python state, never WeChat controls.
        return {'type':'health','account':actual,'count':len(chats),
                'groupCount':sum(kinds.get(n)=='group' for n in chats),
                'retrying':sum(name not in chats for name in next_attempt),
                'waitingWindows':len(requested-set(chats)),
                'listeningMode':'isolated-vm' if isolated_vm else 'existing-windows',
                'replyNeedsFocus':True,'scans':diagnostics['scans'],'uiPaused':paused}
    try:
        while True:
            try:
                command = outgoing.get(timeout=0.2)
            except queue.Empty:
                command = None
            if command and command.get('type') == 'shutdown':
                break
            if command and command.get('type') == 'ui_pause':
                if type(command.get('paused')) is not bool or command.get('expiresAt',0)<time.time()*1000:
                    emit({'type':'ack','id':command.get('id'),'error':'窗口控制命令无效或已过期'})
                else:
                    ui_paused=command['paused']
                    emit(heartbeat(ui_paused))
                    emit({'type':'ack','id':command.get('id'),'uiPaused':ui_paused})
                continue
            if command and command.get('type') in ('collect_start','collect_stop'):
                cid=command.get('id')
                try:
                    collection_id=str(command.get('collectionId',''))
                    if command.get('expiresAt',0)<time.time()*1000 or not re.fullmatch(r'[a-f0-9-]{36}',collection_id):
                        raise ValueError('材料收集命令无效或已过期')
                    if command.get('type')=='collect_stop':
                        collections.pop(collection_id,None)
                    else:
                        destination=routes.get(command.get('to'))
                        if destination is None:raise ValueError('材料收集目标已过期')
                        name,_,kind,sender=destination
                        expires_at=command.get('collectionExpiresAt')
                        if not isinstance(expires_at,(int,float)) or expires_at<=time.time()*1000:
                            raise ValueError('材料会话已过期')
                        collections[collection_id]={'name':name,'kind':kind,'sender':sender,'expiresAt':expires_at}
                    emit({'type':'ack','id':cid})
                except Exception as exc:emit({'type':'ack','id':cid,'error':str(exc)})
                continue
            if ui_paused:
                if command and command.get('type') in ('send','send_file'):
                    emit({'type':'ack','id':command.get('id'),'error':'微信窗口操作已暂停，未发送；恢复后用 /result 取回'})
                if time.monotonic()-last_paused_health>=2:
                    last_paused_health=time.monotonic()
                    emit(heartbeat(True))
                continue
            if command and command.get('type') in ('send','send_file'):
                cid = command.get('id')
                try:
                    destination = routes.get(command.get('to'))
                    if destination is None:
                        raise ValueError('消息回复目标已过期')
                    name, _, kind, sender = destination
                    # A model result can arrive after its window was evicted.
                    # Rebind by the original validated destination, never focus.
                    chat = reply_window(chats, name, kind, add_chat, drop_chat)
                    if command.get('type') == 'send_file':
                        if not isolated_vm:
                            raise ValueError('附件发送请使用虚拟机连接器')
                        from file_transfer import send_attachment, spool_root
                        send_attachment(chat, command, spool_root(), kind, sender)
                        emit({'type':'ack','id':cid})
                        continue
                    text = str(command.get('text', ''))
                    if kind == 'group':
                        text = '回复 ' + sender + '：\n' + text
                    result = chat.SendMsg(text)
                    if isinstance(result, dict) and result.get('status') in ('失败','错误'):
                        raise ValueError(result.get('message') or '微信发送失败')
                    emit({'type':'ack','id':cid})
                except Exception as exc:
                    emit({'type':'ack','id':cid,'error':str(exc)})
            while not received.empty():
                msg, chat = received.get()
                try:
                    dispatch(msg, chat)
                except Exception as exc:
                    emit({'type':'warning','message':'收取微信消息失败：' + str(exc)})
            if time.monotonic() - last_poll >= 2:
                last_poll = time.monotonic()
                try:
                    for name, chat in list(chats.items()):
                        try:
                            info = chat_info(chat)
                            if info.get('chat_name') != name or info.get('chat_type') != kinds.get(name):
                                raise ValueError('原监听窗口已关闭或发生变化')
                            messages = chat.GetAllMessage()
                            diagnostics['rows'] = len(messages)
                            new = inboxes[name].take_new(messages)
                            diagnostics['newRows'] += len(new)
                            for msg in new:
                                dispatch(msg, chat)
                        except Exception as exc:
                            drop_chat(name)
                            emit({'type':'warning','message':'窗口已不可读，请手动重新打开：' + name})
                    diagnostics['scans'] += 1
                    diagnostics['lastScan'] = time.time()
                    diagnostic_file.parent.mkdir(parents=True, exist_ok=True)
                    diagnostic_file.write_text(json.dumps(diagnostics, ensure_ascii=False), encoding='utf-8')
                    if time.monotonic() - last_discovery >= 5:
                        last_discovery = time.monotonic()
                        windows = wx.GetAllSubWindow()
                        names = {}
                        for window in windows:
                            info = chat_info(window)
                            name = info.get('chat_name')
                            if name and info.get('chat_type') in ('friend','group'):
                                names[name] = names.get(name, 0) + 1
                        for name, count in names.items():
                            if count != 1 or name in chats or len(chats) >= 32:
                                continue
                            try:
                                add_chat(name, 0, capture=False)
                            except Exception as exc:
                                emit({'type':'warning','message':'读取已打开窗口失败：' + str(exc)})
                    for session in window_sessions(wx, isolated_vm):
                        name, unread, content = session_info(session)
                        if not name or name in WxParam.SPECIAL_SESSION_NAME:
                            continue
                        old = session_snapshots.get(name)
                        changed = session_changed(unread, content, old, account)
                        if name not in chats and (changed or name in requested) and len(chats) < 32:
                            if time.monotonic() >= next_attempt.get(name, 0):
                                try:
                                    delta = max(1, unread - (old[0] if old else 0))
                                    add_chat(name, delta, capture=bool(changed))
                                except Exception as exc:
                                    next_attempt[name] = time.monotonic() + 30
                                    emit({'type':'warning','message':'虚拟机聊天接入失败：' + str(exc)})
                                    continue
                        session_snapshots[name] = (unread, content)
                    errors = 0
                    emit(heartbeat(False))
                except Exception as exc:
                    errors += 1
                    emit({'type':'warning','message':'微信会话扫描失败：' + str(exc)})
                    if errors >= 5:
                        raise ValueError('无法读取微信会话，请检查助手号窗口及客户端兼容性') from exc
    finally:
        if hasattr(wx, '_listener_thread'):
            wx.StopListening(remove=False)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        emit({'type':'error','message':str(exc)})
        sys.exit(1)


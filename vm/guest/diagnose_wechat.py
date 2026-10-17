"""Read-only diagnostics for the assistant's WeChat window inside its VM."""
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import ipaddress
from urllib.request import build_opener, ProxyHandler
from urllib.error import HTTPError
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import native_query, require_vm


def integrity_level(pid):
    import win32api, win32security, win32con
    process=win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION,False,pid)
    token=None
    try:
        token=win32security.OpenProcessToken(process,win32con.TOKEN_QUERY)
        integrity=win32security.GetTokenInformation(token,win32security.TokenIntegrityLevel)
        if isinstance(integrity,tuple):integrity=integrity[0]
        return integrity.GetSubAuthority(integrity.GetSubAuthorityCount()-1)
    finally:
        if token is not None:token.Close()
        process.Close()


def uia_summary(control, depth=0, budget=None):
    budget=budget if budget is not None else [30]
    if budget[0]<=0:return None
    budget[0]-=1
    row={'type':control.ControlTypeName,'name':control.Name,'class':control.ClassName}
    # Read only shallow container/navigation structure, never message/list rows.
    if (depth<3 and row['type'] in ('PaneControl','WindowControl','GroupControl')
            and not any(word in row['class'].lower() for word in ('chatbox','message','chatcontent'))):
        children=[]
        for child in control.GetChildren()[:12]:
            if budget[0]<=0:break
            summary=uia_summary(child,depth+1,budget)
            if summary is not None:children.append(summary)
        row['children']=children
    return row


def collect(root):
    root = Path(root)
    require_vm(root)
    try:
        config=json.loads((root/'workbench/vm-agent.json').read_text(encoding='utf-8-sig'))
        address=urlparse(config['relay'])
        if (address.scheme!='http' or address.port!=8791 or address.username or address.password
                or address.path or address.query or address.fragment
                or not ipaddress.ip_address(address.hostname).is_private):
            raise ValueError('桥接地址不是部署包中的私网地址')
        try:
            with build_opener(ProxyHandler({})).open(config['relay']+'/v1/events',timeout=5) as response:
                print('主机通信测试 HTTP=' + str(response.status),flush=True)
        except HTTPError as error:
            print('主机通信测试 HTTP=' + str(error.code) + ('（已能到达认证桥）' if error.code==401 else ''),flush=True)
    except Exception as error:
        print('主机通信测试失败：' + str(error),flush=True)
    import psutil, win32api, win32gui, win32process, win32security, win32con
    from wxauto4 import WxParam, uia
    from wxauto4.ui.main import WeChatMainWnd, WeChatLoginWnd
    WxParam.TELEMETRY_ENABLED = False
    WxParam.ENABLE_FILE_LOGGER = False
    print('诊断只读取兼容微信的进程与窗口，不发送消息、不点击窗口。', flush=True)
    print('连接器查找的主窗口：' + str(WeChatMainWnd._ui_cls_name) + ' / ' + str(WeChatMainWnd._ui_name), flush=True)
    expected = Path('C:/Jarvis/wechat-assistant-4.1.8.107/client/Weixin.exe').resolve()
    pids = set()
    for process in psutil.process_iter(['pid','name','exe']):
        if str(process.info.get('name','')).lower() == 'weixin.exe':
            exe = process.info.get('exe')
            if exe and Path(exe).resolve() == expected:
                pids.add(process.pid)
    print('兼容微信进程 PID：' + str(sorted(pids)), flush=True)
    print('当前连接器诊断 PID：' + str(os.getpid()), flush=True)
    processes = native_query(root,
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        "ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process -Filter "
        "(\"Name='Weixin.exe' OR ProcessId=\"+$env:JARVIS_DIAG_PID) -ErrorAction Stop | "
        "Select-Object ProcessId,SessionId) -Compress", JARVIS_DIAG_PID=str(os.getpid()))
    print('进程所在桌面会话：' + json.dumps(processes,ensure_ascii=False), flush=True)
    for pid in sorted(pids | {os.getpid()}):
        try:
            print('进程权限级别 PID=' + str(pid) + ' RID=' + str(integrity_level(pid)), flush=True)
        except Exception as error:
            print('进程权限读取失败 PID=' + str(pid) + '：' + str(error), flush=True)
    windows=[]
    def visit(hwnd, unused):
        _,pid=win32process.GetWindowThreadProcessId(hwnd)
        if pid not in pids:return
        row={'pid':pid,'hwnd':hwnd,'class':win32gui.GetClassName(hwnd),
             'title':win32gui.GetWindowText(hwnd),'visible':bool(win32gui.IsWindowVisible(hwnd)),
             'minimized':bool(win32gui.IsIconic(hwnd))}
        if (row['class'] in (WeChatMainWnd._ui_cls_name,WeChatLoginWnd._ui_cls_name)
                or row['visible'] and (row['title'] in ('微信','Weixin','WeChat') or row['class'].startswith('Qt'))):
            try:
                control=uia.ControlFromHandle(hwnd)
                row['uia']=uia_summary(control)
                row['uia'].update(pid=control.ProcessId,offscreen=bool(control.IsOffscreen))
            except Exception as error:row['uiaError']=str(error)
        windows.append(row)
    win32gui.EnumWindows(visit,None)
    print('兼容微信顶层窗口：\n' + json.dumps(windows,ensure_ascii=False,indent=2), flush=True)
    print('Win32 窗口类与 UI Automation 控件类可以不同；请以上面的 uia 字段判断控件是否可读。',flush=True)
    print('诊断完成。请把这份 WeChat-window-diagnostics.txt 发给工作台。', flush=True)


if __name__ == '__main__':
    report=Path(os.environ['LOCALAPPDATA'])/'JarvisGuest/WeChat-window-diagnostics.txt'
    report.parent.mkdir(parents=True,exist_ok=True)
    from contextlib import redirect_stdout,redirect_stderr
    with report.open('w',encoding='utf-8-sig') as log,redirect_stdout(log),redirect_stderr(log):
        try:collect(Path('C:/Jarvis'))
        except Exception:traceback.print_exc()
    print(report.read_text(encoding='utf-8-sig'),flush=True)
    try:subprocess.Popen(['notepad.exe',str(report)])
    except OSError:print('诊断记录已保存：'+str(report),flush=True)

"""Install file delivery support in the existing isolated WeChat VM."""
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from guest_common import require_vm, verify_manifest, contained
from update_launcher import replace_launcher

FILES=('background_agent.py','launch_wechat.py','test_accessibility.py','diagnose_wechat.py',
       'refresh_bridge.py','repair_client.py','guest_common.py','windows_signature.py',
       'Start-Agent.cmd','Check-Agent.cmd','Stop-Agent.cmd','Open-WeChat.cmd',
       'workbench/vm_agent.py','workbench/wechat_assistant.py','workbench/file_transfer.py',
       'workbench/relay_discovery.py')


def main(root=None,media=None):
    print('材料收集更新 v4（多消息、图片、视频、文件）：正在检查虚拟机环境与部署文件。',flush=True)
    root=Path(root) if root is not None else Path('C:/Jarvis')
    media=Path(media) if media is not None else Path(__file__).resolve().parent
    require_vm(root)
    verify_manifest(media)
    from background_agent import running,main as control
    if running(root):
        print('正在停止旧连接器，微信保持登录，请稍候……',flush=True)
        control('stop',root)
        deadline=time.monotonic()+40
        while running(root) and time.monotonic()<deadline:time.sleep(1)
        if running(root):raise RuntimeError('旧连接器仍在运行，请关闭旧版前台连接器终端后重试。')
    from refresh_bridge import refresh
    refresh(root,media)
    for name in FILES:
        replace_launcher(contained(media,name),contained(root,name))
    print('材料组件已更新。发送 /材料 后可连续发送说明、图片、视频和文件，再用 /开始 提交。',flush=True)
    from test_accessibility import ensure_narrator,scan_main
    ensure_narrator(root)
    if not scan_main(root):
        from test_accessibility import client_processes
        if client_processes(root):
            raise RuntimeError('组件已安装，但微信窗口不可读。请从托盘退出微信，再运行 C:\\Jarvis\\Open-WeChat.cmd；登录展开聊天列表后运行 Start-Agent.cmd。')
        import launch_wechat
        launch_wechat.main(root)
        print('请登录贾维斯并展开聊天列表，检测到窗口后自动启动。',flush=True)
        deadline=time.monotonic()+180
        while not scan_main(root) and time.monotonic()<deadline:time.sleep(2)
    # One-shot startup state: let the user finish operating the guest desktop.
    # Ordinary future Start-Agent launches keep their normal active behavior.
    os.environ['JARVIS_AGENT_START_PAUSED']='1'
    code=control('start',root)
    print('本次更新后窗口操作默认暂停。请回到主机工作台，刷新页面，点击“恢复监听”。',flush=True)
    return code


if __name__=='__main__':
    from test_accessibility import Tee
    from contextlib import redirect_stdout,redirect_stderr
    report=Path(os.environ['LOCALAPPDATA'])/'JarvisGuest/Attachment-update-result.txt'
    report.parent.mkdir(parents=True,exist_ok=True)
    code=1
    with report.open('w',encoding='utf-8-sig') as output:
        with redirect_stdout(Tee(sys.stdout,output)),redirect_stderr(Tee(sys.stderr,output)):
            try:code=main()
            except Exception:traceback.print_exc()
    if code and not os.environ.get('JARVIS_LAUNCHER_REPORT'):
        subprocess.Popen(['notepad.exe',str(report)])
    print('更新记录：'+str(report),flush=True)
    raise SystemExit(code)

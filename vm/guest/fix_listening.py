"""Install a verified startup fix without reinstalling Windows, Python or WeChat."""
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import require_vm, verify_manifest, contained
from update_launcher import replace_launcher

FILES = ('background_agent.py','launch_wechat.py','test_accessibility.py','diagnose_wechat.py',
         'refresh_bridge.py','repair_client.py','guest_common.py','windows_signature.py',
         'Start-Agent.cmd','Check-Agent.cmd','Stop-Agent.cmd','Open-WeChat.cmd')


def main(root=None, media=None):
    root = Path(root) if root is not None else Path('C:/Jarvis')
    media = Path(media) if media is not None else Path(__file__).resolve().parent
    require_vm(root)
    verify_manifest(media)
    from background_agent import running
    from test_accessibility import client_processes, ensure_narrator, scan_main
    if running(root):
        raise RuntimeError('请先运行 C:\\Jarvis\\Stop-Agent.cmd，等待约 20 秒，再运行本修复。')
    if client_processes(root):
        raise RuntimeError('请先在虚拟机右下角微信托盘中选择“退出微信”，再运行本修复。无需卸载。')
    for name in FILES:
        replace_launcher(contained(media, name), contained(root, name))
    print('启动入口已修复。现在先开启讲述人，再打开兼容微信。', flush=True)
    ensure_narrator(root)
    import launch_wechat
    launch_wechat.main(root)
    print('请登录贾维斯并展开聊天列表；检测到可读主窗口后自动启动后台连接器。', flush=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if scan_main(root):
            from background_agent import main as start
            return start('start', root)
        time.sleep(2)
    raise RuntimeError('还未检测到可读的微信主窗口。请保留结果，不要重复启动多个连接器。')


if __name__ == '__main__':
    from test_accessibility import Tee
    from contextlib import redirect_stdout, redirect_stderr
    report = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest/Fix-listening-result.txt'
    report.parent.mkdir(parents=True, exist_ok=True)
    code = 1
    with report.open('w', encoding='utf-8-sig') as output:
        with redirect_stdout(Tee(sys.stdout, output)), redirect_stderr(Tee(sys.stderr, output)):
            try:
                code = main()
            except Exception:
                traceback.print_exc()
    if code:
        subprocess.Popen(['notepad.exe', str(report)])
    print('修复记录：' + str(report), flush=True)
    raise SystemExit(code)

"""Launch the VM connector detached from its temporary console; keep a log."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import require_vm


def running(root):
    import psutil
    expected = (root / 'workbench/vm_agent.py').resolve()
    allowed = {(root / 'python/python.exe').resolve(),
               (root / 'workbench/.wechat-venv/Scripts/python.exe').resolve()}
    matches = []
    for process in psutil.process_iter(['pid', 'exe', 'cmdline']):
        try:
            if process.info['exe'] and Path(process.info['exe']).resolve() in allowed and any(
                    Path(arg).resolve() == expected for arg in (process.info['cmdline'] or [])[1:]):
                matches.append(process.pid)
        except (OSError, ValueError, psutil.Error):
            pass
    return matches


def detached(command, directory, log, stop_file):
    with log.open('wb') as stream:
        return subprocess.Popen(command, cwd=str(directory), stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
                 'JARVIS_AGENT_STOP_FILE': str(stop_file)})


def main(action='start', root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    require_vm(root)
    report_dir = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest'
    report_dir.mkdir(parents=True, exist_ok=True)
    record = report_dir / 'Background-agent.json'
    processes = running(root)
    if action == 'stop':
        if not record.exists():
            raise RuntimeError('没有后台启动记录，请先关闭旧版前台连接器窗口。')
        state = json.loads(record.read_text(encoding='utf-8'))
        stop_file = report_dir / ('agent-stop-' + state['identity'])
        stop_file.write_text('stop', encoding='ascii')
        print('已请求停止后台连接器，通常在 20 秒内停止。', flush=True)
        return 0
    if action == 'status' or processes:
        print('连接器进程正在运行：' + str(processes) if processes else '连接器未运行。', flush=True)
        print('是否已连接、是否收到消息请查看主机工作台。', flush=True)
        if record.exists():
            state = json.loads(record.read_text(encoding='utf-8'))
            log = report_dir / state['logName']
            if log.exists():
                print(log.read_text(encoding='utf-8', errors='replace')[-6000:], flush=True)
        return 0
    from test_accessibility import ensure_narrator, scan_main
    ensure_narrator(root)
    if not scan_main(root):
        raise RuntimeError('微信无障碍主窗口不可读。请先从托盘退出微信，运行 Open-WeChat.cmd，登录并展开聊天列表，再运行 Start-Agent.cmd。')
    identity = uuid.uuid4().hex
    log = report_dir / ('Agent-background-' + identity + '.txt')
    stop_file = report_dir / ('agent-stop-' + identity)
    command = [str(root / 'workbench/.wechat-venv/Scripts/python.exe'), '-u',
               str(root / 'workbench/vm_agent.py')]
    process = detached(command, root / 'workbench', log, stop_file)
    record.write_text(json.dumps({'pid': process.pid, 'identity': identity, 'logName': log.name}), encoding='utf-8')
    print('后台进程已创建，正在确认微信及主机连接；尚未确认收件。', flush=True)
    for _ in range(10):
        if process.poll() is not None:
            raise RuntimeError('后台连接器退出：\n' + log.read_text(encoding='utf-8', errors='replace')[-6000:])
        text = log.read_text(encoding='utf-8', errors='replace')
        if '已连接主机工作台' in text:
            print('已连接主机工作台。关闭本窗口不影响后台监听；微信和虚拟机桌面须保持可用。', flush=True)
            break
        time.sleep(1)
    else:
        print('仍在连接，尚未确认成功。请运行 Check-Agent.cmd 查看后续结果。', flush=True)
    print('日志：' + str(log), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else 'start'))
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)

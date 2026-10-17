"""Try the real Windows screen reader before WeChat, in the guest only.

No registry changes, UI clicks, process-memory writes or client patches.
An empty Qt shell is never treated as a connected assistant.
"""
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import native_query, require_vm, verify_manifest
from diagnose_wechat import uia_summary
import repair_client
import refresh_bridge


def has_main_window(tree):
    if tree.get('class') == 'mmui::MainWindow' and tree.get('name') == '微信':
        return True
    return any(has_main_window(child) for child in tree.get('children', []))


def process_image(pid):
    import ctypes
    from ctypes import wintypes
    import win32api, win32con
    handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    try:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        query = kernel.QueryFullProcessImageNameW
        query.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                          ctypes.POINTER(wintypes.DWORD)]
        query.restype = wintypes.BOOL
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not query(int(handle), 0, buffer, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.value
    finally:
        handle.Close()


def client_processes(root):
    return native_query(root,
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        "ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process -Filter "
        "\"Name='Weixin.exe'\" -ErrorAction Stop | Select-Object ProcessId,ExecutablePath) -Compress")


def scan_main(root):
    import win32gui, win32process
    from wxauto4 import uia, WxParam
    WxParam.TELEMETRY_ENABLED = False
    WxParam.ENABLE_FILE_LOGGER = False
    expected = (root / 'wechat-assistant-4.1.8.107/client/Weixin.exe').resolve()
    pids = {p['ProcessId'] for p in client_processes(root)
            if p.get('ExecutablePath') and Path(p['ExecutablePath']).resolve() == expected}
    found = []
    def visit(hwnd, unused):
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid not in pids or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return
        if win32gui.GetWindowText(hwnd) != '微信':
            return
        try:
            tree = uia_summary(uia.ControlFromHandle(hwnd))
            if tree and has_main_window(tree):
                found.append(hwnd)
        except Exception:
            pass
    win32gui.EnumWindows(visit, None)
    return bool(found)


def ensure_narrator(root):
    def running():
        return native_query(root,
            "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
            "$taskSessionId=(Get-Process -Id $PID).SessionId;"
            "ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process -Filter "
            "\"Name='Narrator.exe'\" -ErrorAction Stop | Where-Object SessionId -eq $taskSessionId | "
            "Select-Object ProcessId,ExecutablePath) -Compress")
    narrator = Path(os.environ['SystemRoot']) / 'System32/Narrator.exe'
    def matches(rows):
        for process in rows:
            path = process.get('ExecutablePath')
            # Narrator can run with UIAccess; CIM may omit its image path.
            if not path:
                try:
                    path = process_image(process['ProcessId'])
                except Exception:
                    continue
            if Path(path).resolve() == narrator.resolve():
                return True
        return False
    if not matches(running()):
        if not narrator.is_file():
            raise RuntimeError('找不到 Windows 自带的讲述人。')
        print('正在启动虚拟机内的 Windows 讲述人，可能会听到朗读声。', flush=True)
        # UIAccess apps must be activated by the Windows shell; CreateProcess
        # can return ERROR_ELEVATION_REQUIRED even for the normal open action.
        try:
            os.startfile(str(narrator), 'open')
        except OSError as error:
            raise RuntimeError('讲述人启动未完成。请在虚拟机内按 Win+Ctrl+Enter 开启讲述人，'
                               '再重新运行本测试。Windows 错误：' + str(error)) from error
    for _ in range(15):
        if matches(running()):
            time.sleep(3)
            print('讲述人已运行；现在启动微信。请暂时保持讲述人开启。', flush=True)
            return
        time.sleep(1)
    raise RuntimeError('讲述人没有持续运行，尚未启动微信。')


def main(root=None, media=None):
    root = Path(root) if root is not None else Path('C:/Jarvis')
    media = Path(media) if media is not None else Path(__file__).resolve().parent
    require_vm(root)
    verify_manifest(media)
    print('无障碍启动测试 v4（桥接地址同步 + 兼容客户端恢复）。', flush=True)
    if client_processes(root):
        raise RuntimeError('请先从虚拟机右下角托盘退出微信，再重新运行 Test-Accessibility.cmd。只关闭聊天窗口不等于退出微信。')
    # Use the validated launcher supplied on this disc, against installed files.
    import launch_wechat
    refresh_bridge.refresh(root, media)
    repair_client.restore(root, media)
    ensure_narrator(root)
    launch_wechat.main(root)
    print('请在虚拟机内扫码或确认登录贾维斯并打开聊天列表。最多检测 3 分钟。', flush=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if scan_main(root):
            print('检测到微信 mmui::MainWindow。正在启动原有连接器；连接是否成功请看后续日志。', flush=True)
            return subprocess.call([sys.executable, '-I', str(root / 'launch_agent.py')], cwd=str(root))
        time.sleep(2)
    print('未检测到可读的微信主界面，连接器尚未启动。下面保留同一次测试的只读诊断。', flush=True)
    from diagnose_wechat import collect
    collect(root)
    raise RuntimeError('无障碍启动测试未通过。请发送 Accessibility-result.txt；不要反复重装或继续启动连接器。')


class Tee:
    def __init__(self, console, log):
        self.console, self.log = console, log
    def write(self, value):
        self.console.write(value)
        self.log.write(value)
        return len(value)
    def flush(self):
        self.console.flush()
        self.log.flush()


def run():
    report = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest/Accessibility-result.txt'
    report.parent.mkdir(parents=True, exist_ok=True)
    from contextlib import redirect_stdout, redirect_stderr
    with report.open('w', encoding='utf-8-sig') as log:
        with redirect_stdout(Tee(sys.stdout, log)), redirect_stderr(Tee(sys.stderr, log)):
            try:
                code = main()
            except Exception as error:
                print('测试未完成：' + str(error), flush=True)
                traceback.print_exc()
                code = 1
    print('测试记录：' + str(report), flush=True)
    try:
        subprocess.Popen(['notepad.exe', str(report)])
    except OSError:
        pass
    return code


if __name__ == '__main__':
    raise SystemExit(run())

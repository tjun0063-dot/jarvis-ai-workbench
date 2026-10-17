"""Install the offline guest package without executing .ps1 files."""
from pathlib import Path
import ipaddress
import json
import os
import shutil
import subprocess
import sys
import uuid
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import require_vm, verify_manifest, verify_publisher

verified_vm = False


class Tee:
    def __init__(self, console, log):
        self.console, self.log = console, log

    def write(self, text):
        self.console.write(text)
        self.log.write(text)
        self.flush()

    def flush(self):
        self.console.flush()
        self.log.flush()


def report_failure(media, message):
    """Send a bounded installer error to the existing authenticated host relay."""
    if not verified_vm:
        return
    try:
        config = json.loads((media / 'workbench/vm-agent.json').read_text(encoding='utf-8-sig'))
        base = config['relay'].rstrip('/')
        address = urlparse(base)
        if address.scheme != 'http' or address.port != 8791 or address.path or not ipaddress.ip_address(address.hostname).is_private:
            return
        event = {'runId': str(uuid.uuid4()), 'event': {'type': 'warning',
                 'message': '虚拟机安装失败：' + message[-6000:]}}
        request = Request(base + '/v1/events', data=json.dumps(event, ensure_ascii=False).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + config['token'], 'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            response.read()
    except Exception:
        pass


def run_checked(args, timeout):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace', timeout=timeout,
        env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
    if result.stdout:
        print(result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError('安装子步骤失败：' + result.stdout[-4000:])


def main():
    global verified_vm
    media = Path(__file__).resolve().parent
    destination = Path('C:/Jarvis')
    require_vm(media)
    verified_vm = True
    if destination.exists():
        raise RuntimeError('C:\\Jarvis 已存在，未覆盖。请保留此窗口的错误信息，以便继续修复。')
    print('1/4 正在核验离线安装文件，请稍候……', flush=True)
    print('正在核对光盘文件清单。', flush=True)
    verify_manifest(media)
    print('正在核对 Python 安装器发布者签名。', flush=True)
    verify_publisher(media, media / 'python-installer.exe', 'Python Software Foundation')
    print('2/4 正在复制到 C:\\Jarvis……', flush=True)
    # Copy file contents without propagating DVD read-only attributes.
    shutil.copytree(media, destination, copy_function=shutil.copyfile)
    print('3/4 正在安装 Python……', flush=True)
    result = subprocess.run([str(destination / 'python-installer.exe'), '/quiet',
        'InstallAllUsers=0', 'PrependPath=0', 'Include_launcher=0', 'Include_test=0',
        'TargetDir=' + str(destination / 'python')], timeout=600)
    if result.returncode not in (0, 3010):
        raise RuntimeError('Python 安装失败，错误码：' + str(result.returncode))
    python = destination / 'python/python.exe'
    environment = destination / 'workbench/.wechat-venv'
    run_checked([str(python), '-m', 'venv', str(environment)], timeout=180)
    print('4/4 正在离线安装微信连接器……', flush=True)
    run_checked([str(environment / 'Scripts/python.exe'), '-m', 'pip', 'install',
        '--no-index', '--find-links', str(destination / 'wheels'), '-r',
        str(destination / 'workbench/requirements-wechat.txt')], timeout=300)
    from repair_runtime import ensure_runtime
    runtime_code = ensure_runtime(media, destination)
    if runtime_code == 3010:
        print('Windows 运行库提示需要重启。请先重启虚拟机，再打开微信与连接器。', flush=True)
    print('安装完成。打开 C:\\Jarvis\\Open-WeChat.cmd，扫码登录贾维斯；再运行 Start-Agent.cmd。', flush=True)


if __name__ == '__main__':
    log_dir = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / 'Install-result.txt'
    console_out, console_err = sys.stdout, sys.stderr
    exit_code = 0
    with log_path.open('w', encoding='utf-8-sig') as log:
        sys.stdout, sys.stderr = Tee(console_out, log), Tee(console_err, log)
        try:
            main()
        except Exception as error:
            message = str(error)
            print('安装失败：' + message, file=sys.stderr, flush=True)
            report_failure(Path(__file__).resolve().parent, message)
            exit_code = 1
        finally:
            sys.stdout, sys.stderr = console_out, console_err
    try:
        subprocess.Popen(['notepad.exe', str(log_path)])
    except OSError:
        print('安装记录已保存：' + str(log_path), flush=True)
    raise SystemExit(exit_code)

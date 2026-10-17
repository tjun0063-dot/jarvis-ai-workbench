"""Update only the installed launcher after verifying the guest media."""
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import require_vm, contained, sha256


def replace_launcher(source, target):
    """Do not copy a DVD's read-only attribute or reuse a failed staging file."""
    backup = target.with_name(target.name + '.before-launcher-update')
    if target.exists() and not backup.exists():
        shutil.copyfile(target, backup)
    handle, name = tempfile.mkstemp(prefix=target.name + '.', suffix='.launcher-update', dir=target.parent)
    os.close(handle)
    staged = Path(name)
    previous_mode = target.stat().st_mode if target.exists() else None
    replaced = False
    try:
        shutil.copyfile(source, staged)
        if previous_mode is not None:
            target.chmod(previous_mode | stat.S_IWRITE)
        staged.replace(target)
        replaced = True
    finally:
        if not replaced and previous_mode is not None and target.exists():
            target.chmod(previous_mode)
        if staged.exists():
            staged.unlink()


def update(media, destination, agent=False, background=False, recovery=False):
    media, destination = Path(media), Path(destination)
    require_vm(destination if background else media)
    if not (destination / 'python/python.exe').is_file():
        raise RuntimeError('没有找到已安装的 C:\\Jarvis\\python。请保留现有安装并反馈。')
    files = (('background_agent.py','Start-Agent.cmd','Check-Agent.cmd','Stop-Agent.cmd',
              'workbench/vm_agent.py','workbench/wechat_assistant.py') if background else
             ('launch_agent.py', 'Start-Agent.cmd', 'check_installation.py', 'workbench/vm_agent.py') if agent
             else ('launch_wechat.py', 'Open-WeChat.cmd'))
    if recovery:
        files += ('launch_wechat.py','Open-WeChat.cmd','repair_client.py','guest_common.py','windows_signature.py')
        files = tuple(dict.fromkeys(files))
    manifest = json.loads((media / 'payload-manifest.json').read_text(encoding='utf-8-sig'))
    for name in files:
        items = [item for item in manifest.get('files', []) if item['path'].replace('\\','/') == name]
        if len(items) != 1 or sha256(contained(media, name)).lower() != items[0]['sha256'].lower():
            raise RuntimeError('启动器文件核验失败：' + name)
    if background:
        import psutil
        expected = (destination / 'workbench/vm_agent.py').resolve()
        for process in psutil.process_iter(['cmdline']):
            try:
                if any(Path(arg).resolve() == expected for arg in (process.info['cmdline'] or [])[1:]):
                    raise RuntimeError('旧连接器仍在运行，请先关闭旧终端窗口或运行 Stop-Agent.cmd，再更新。')
            except (OSError, ValueError, psutil.Error):
                pass
    for name in files:
        target = contained(destination, name)
        replace_launcher(contained(media, name), target)
    print('启动器更新完成。现有微信、Python 和连接配置已保留。', flush=True)


if __name__ == '__main__':
    try:
        update(Path(__file__).resolve().parent, Path('C:/Jarvis'), agent='--agent' in sys.argv[1:], background='--background' in sys.argv[1:])
    except Exception as error:
        print('更新失败：' + str(error), file=sys.stderr, flush=True)
        traceback.print_exc()
        raise SystemExit(1)

"""Keep a verified offline client in the VM and update its normal launchers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import contained, require_vm, sha256, verify_manifest
from repair_client import PACKAGE, core_record, restore
from update_launcher import update


def keep_recovery(root, media):
    root, media = Path(root), Path(media)
    require_vm(root)
    verify_manifest(media)
    source = contained(media, PACKAGE)
    record = json.loads((source / 'preparation.json').read_text(encoding='utf-8-sig'))
    expected = core_record(record)
    recovery = contained(root, 'recovery-media')
    if recovery.exists():
        verify_manifest(recovery)
        saved = json.loads((recovery / PACKAGE / 'preparation.json').read_text(encoding='utf-8-sig'))
        if core_record(saved) != expected:
            raise RuntimeError('已有恢复副本与原始记录不一致，未覆盖。')
        return recovery
    source_manifest = json.loads((media / 'payload-manifest.json').read_text(encoding='utf-8-sig'))
    files = [item for item in source_manifest['files']
             if item['path'].replace('\\','/').startswith(PACKAGE + '/client/')
             or item['path'].replace('\\','/') == PACKAGE + '/preparation.json']
    needed = sum(contained(media,item['path']).stat().st_size for item in files)
    if shutil.disk_usage(root).free < needed + 256*1024*1024:
        raise RuntimeError('虚拟机磁盘空间不足，未留存恢复副本。')
    staged = contained(root, 'recovery-stage-' + uuid.uuid4().hex[:12])
    staged.mkdir()
    print('正在留存原始兼容微信，后续恢复无需再次换光盘……', flush=True)
    for item in files:
        target = contained(staged, item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(contained(media, item['path']), target)
    (staged / 'payload-manifest.json').write_text(json.dumps({'files':files}), encoding='utf-8')
    verify_manifest(staged)
    staged.rename(recovery)
    return recovery


def main(root=None, media=None):
    root = Path(root) if root is not None else Path('C:/Jarvis')
    media = Path(media) if media is not None else Path(__file__).resolve().parent
    require_vm(root)
    verify_manifest(media)
    # The updater rejects a still-running connector before replacing any code.
    update(media, root, background=True, recovery=True)
    restore(root, media)
    keep_recovery(root, media)
    from test_accessibility import ensure_narrator, scan_main
    from launch_wechat import main as open_wechat
    from background_agent import main as start_agent
    ensure_narrator(root)
    open_wechat(root)
    print('请登录贾维斯并展开聊天列表；检测到主界面后自动启动后台连接器。', flush=True)
    deadline = time.monotonic()+180
    while time.monotonic()<deadline:
        if scan_main(root):
            return start_agent('start', root)
        time.sleep(2)
    raise RuntimeError('尚未检测到微信主界面。登录后运行 C:\\Jarvis\\Start-Agent.cmd。')


if __name__ == '__main__':
    from test_accessibility import Tee
    from contextlib import redirect_stdout, redirect_stderr
    report = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest/Recovery-install-result.txt'
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open('w', encoding='utf-8-sig') as log:
        with redirect_stdout(Tee(sys.stdout, log)), redirect_stderr(Tee(sys.stderr, log)):
            try:
                code = main()
            except Exception:
                traceback.print_exc()
                code = 1
    if code:
        subprocess.Popen(['notepad.exe', str(report)])
    print('记录：' + str(report), flush=True)
    raise SystemExit(code)

"""Restore the verified guest client, preserving the entire previous directory."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import contained, native_query, require_vm, sha256, verify_manifest, verify_publisher

VERSION = '4.1.8.107'
PACKAGE = 'wechat-assistant-' + VERSION
CORE_FILES = {'Weixin.exe', VERSION + '/Weixin.dll'}


def running_wechat(root):
    return native_query(root,
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        "ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process -Filter "
        "\"Name='Weixin.exe' OR Name='WeChat.exe'\" -ErrorAction Stop | Select-Object ProcessId) -Compress")


def core_record(record):
    if (not record.get('ready') or record.get('version') != VERSION
            or record.get('entry') != 'Weixin.exe'):
        raise RuntimeError('兼容微信部署记录未通过核验。')
    items = record.get('launchFiles', [])
    if len(items) != 2 or {item['path'] for item in items} != CORE_FILES:
        raise RuntimeError('兼容微信核心文件清单不正确。')
    return {item['path']: item['sha256'].lower() for item in items}


def describe_change(path, relative, actual, expected):
    info = {'path': relative, 'actualSha256': actual, 'expectedSha256': expected}
    if path.is_file():
        try:
            from windows_signature import signed_file_info
            info.update(signed_file_info(path))
        except Exception as error:
            info['signatureError'] = str(error)
    print('客户端差异：' + json.dumps(info, ensure_ascii=False), flush=True)
    return info


def restore(root, media):
    root, media = Path(root).resolve(), Path(media).resolve()
    require_vm(root)
    verify_manifest(media)
    if running_wechat(root):
        raise RuntimeError('请先从虚拟机托盘退出微信，再运行 Test-Accessibility.cmd。')
    source = contained(media, PACKAGE)
    reference_path = contained(source, 'preparation.json')
    reference = json.loads(reference_path.read_text(encoding='utf-8-sig'))
    expected = core_record(reference)
    clean = contained(source, 'client')
    listed = json.loads((media / 'payload-manifest.json').read_text(encoding='utf-8-sig'))['files']
    listed_client = {contained(media, item['path']) for item in listed
                     if item['path'].replace('\\', '/').startswith(PACKAGE + '/client/')}
    actual_client = {p.resolve() for p in clean.rglob('*') if p.is_file()}
    if not actual_client or listed_client != actual_client:
        raise RuntimeError('光盘客户端文件与完整清单不一致，未恢复。')
    for relative, digest in expected.items():
        path = contained(clean, relative)
        if sha256(path).lower() != digest:
            raise RuntimeError('光盘兼容客户端哈希不符：' + relative)
        if verify_publisher(root, path, 'Tencent').get('version') != VERSION:
            raise RuntimeError('光盘兼容客户端版本不符：' + relative)

    destination = contained(root, PACKAGE)
    if not destination.is_dir():
        raise RuntimeError('找不到已安装的微信客户端目录，未恢复。')
    client = contained(destination, 'client')
    record_path = contained(destination, 'preparation.json')
    changes = []
    for relative, digest in expected.items():
        path = contained(client, relative)
        actual = sha256(path).lower() if path.is_file() else '文件缺失'
        if actual != digest:
            changes.append(describe_change(path, relative, actual, digest))
    try:
        record_ok = core_record(json.loads(record_path.read_text(encoding='utf-8-sig'))) == expected
    except Exception:
        record_ok = False
    if not changes and record_ok:
        print('兼容微信核心文件核验通过，无需恢复。', flush=True)
        return None

    needed = sum(p.stat().st_size for p in clean.rglob('*') if p.is_file())
    if shutil.disk_usage(destination).free < needed + 256 * 1024 * 1024:
        raise RuntimeError('虚拟机磁盘空间不足以准备兼容客户端，未替换现有文件。')
    identity = uuid.uuid4().hex[:12]
    stage = contained(destination, 'repair-stage-' + identity)
    backup = contained(destination, 'client-before-repair-' + identity)
    record_backup = contained(destination, 'preparation.before-repair-' + identity + '.json')
    stage.mkdir()
    candidate = contained(stage, 'client')
    print('正在从光盘准备原始兼容客户端，请稍候……', flush=True)
    shutil.copytree(clean, candidate, copy_function=shutil.copyfile)
    shutil.copyfile(reference_path, stage / 'preparation.json')
    # Verify every copied client file, not just the two executable cores.
    for original in clean.rglob('*'):
        if original.is_file():
            copied = contained(candidate, original.relative_to(clean))
            if sha256(original) != sha256(copied):
                raise RuntimeError('复制校验失败，现有客户端尚未替换：' + str(original.relative_to(clean)))
    if running_wechat(root):
        raise RuntimeError('恢复期间微信被打开，现有客户端尚未替换。请退出后重试。')

    moved_client = moved_record = installed_client = installed_record = False
    try:
        if client.exists():
            client.rename(backup)
            moved_client = True
        candidate.rename(client)
        installed_client = True
        if record_path.exists():
            record_path.rename(record_backup)
            moved_record = True
        (stage / 'preparation.json').rename(record_path)
        installed_record = True
    except Exception:
        # Roll back both program and metadata; keep failed replacement files too.
        if installed_record:
            record_path.rename(contained(stage, 'failed-preparation.json'))
        if moved_record:
            record_backup.rename(record_path)
        if installed_client:
            client.rename(contained(stage, 'failed-client'))
        if moved_client:
            backup.rename(client)
        raise
    audit = {'version': VERSION, 'changes': changes,
             'clientBackup': str(backup) if moved_client else None,
             'recordBackup': str(record_backup) if moved_record else None}
    (destination / ('client-repair-' + identity + '.json')).write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8-sig')
    print('已恢复微信 ' + VERSION + '，原客户端备份：' + str(backup), flush=True)
    return audit


if __name__ == '__main__':
    report = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest/Client-repair-result.txt'
    report.parent.mkdir(parents=True, exist_ok=True)
    from contextlib import redirect_stdout, redirect_stderr
    with report.open('w', encoding='utf-8-sig') as log, redirect_stdout(log), redirect_stderr(log):
        try:
            restore(Path('C:/Jarvis'), Path(__file__).resolve().parent)
            code = 0
        except Exception:
            traceback.print_exc()
            code = 1
    print(report.read_text(encoding='utf-8-sig'), flush=True)
    subprocess.Popen(['notepad.exe', str(report)])
    raise SystemExit(code)

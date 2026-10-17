"""Guest deployment checks. Signature verification uses Windows APIs directly."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


def native_query(root, command, timeout=45, **extra_env):
    result = subprocess.run(
        [str(Path(root) / 'powershell' / 'pwsh.exe'), '-NoLogo', '-NoProfile',
         '-NonInteractive', '-Command', command],
        env={**os.environ, **extra_env}, capture_output=True, text=True,
        encoding='utf-8-sig', timeout=timeout,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Windows 核验失败：' + (result.stderr.strip() or str(result.returncode)))
    return json.loads(result.stdout)


def require_vm(root):
    machine = native_query(root,
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        "Get-CimInstance Win32_ComputerSystem -ErrorAction Stop | "
        "Select-Object Model,Manufacturer | ConvertTo-Json -Compress")
    if machine.get('Model') != 'Virtual Machine' or 'Microsoft' not in machine.get('Manufacturer', ''):
        raise RuntimeError('此程序只能在贾维斯 Hyper-V 虚拟机内部运行。')


def contained(root, relative):
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise RuntimeError('部署文件路径越界：' + str(relative))
    return candidate


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root):
    manifest = json.loads((Path(root) / 'payload-manifest.json').read_text(encoding='utf-8-sig'))
    seen = set()
    files = manifest.get('files', [])
    if not files:
        raise RuntimeError('部署清单为空。')
    for item in files:
        path = contained(root, item['path'])
        identity = str(path).casefold()
        if identity in seen:
            raise RuntimeError('部署清单有重复文件。')
        seen.add(identity)
        if sha256(path).lower() != item['sha256'].lower():
            raise RuntimeError('部署文件核验失败：' + item['path'])


def verify_publisher(root, path, publisher):
    from windows_signature import signed_file_info
    info = signed_file_info(path)
    expected = {'Tencent': 'Tencent Technology (Shenzhen) Company Limited'}.get(publisher, publisher)
    if info.get('status') != 'Valid' or info.get('signer', '').casefold() != expected.casefold():
        raise RuntimeError('程序发布者签名核验失败：' + Path(path).name + '（状态：' +
                           str(info.get('status')) + '；发布者：' + str(info.get('signer') or '未识别') + '）')
    return info

"""Bounded VM attachment spool. This module never accepts a host filesystem path."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import time

FILE_LIMIT = 100 * 1024 * 1024


def safe_name(value):
    if (not isinstance(value, str) or not value or len(value) > 180
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', value) or value.endswith(('.', ' '))
            or re.match(r'^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)', value, re.I)
            or value in ('.', '..')):
        raise ValueError('附件文件名无效')
    return value


def metadata(command):
    if not re.fullmatch(r'[a-f0-9-]{36}', str(command.get('id', ''))):
        raise ValueError('附件命令编号无效')
    file = command.get('file', {})
    safe_name(file.get('name'))
    if (type(file.get('size')) is not int or not 0 <= file['size'] <= FILE_LIMIT
            or not re.fullmatch(r'[a-f0-9]{64}', str(file.get('sha256', '')))):
        raise ValueError('附件元数据无效')
    if command.get('expiresAt', 0) < time.time() * 1000:
        raise ValueError('附件发送命令已过期，未发送')
    return file


def spool_root():
    return Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest' / 'attachments'


def checked_path(command, spool):
    file = metadata(command)
    spool = Path(spool)
    target = spool / command['id'] / file['name']
    if (spool.is_symlink() or target.parent.is_symlink() or target.is_symlink()
            or target.resolve().parent != target.parent.absolute()
            or not target.is_file() or target.stat().st_nlink != 1):
        raise ValueError('附件缓存路径无效')
    if target.stat().st_size != file['size']:
        raise ValueError('附件缓存大小不一致')
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(part)
    if digest.hexdigest() != file['sha256']:
        raise ValueError('附件缓存哈希不一致')
    return target


def download_file(command, spool, open_response):
    file = metadata(command)
    spool = Path(spool)
    spool.mkdir(parents=True, exist_ok=True)
    if spool.is_symlink() or spool.resolve() != spool.absolute():
        raise ValueError('附件缓存目录不能重定向')
    # Retain files for 24 hours so WeChat can finish uploading asynchronously.
    for folder in spool.iterdir():
        if (folder.is_dir() and not folder.is_symlink()
                and re.fullmatch(r'[a-f0-9-]{36}', folder.name)
                and time.time() - folder.stat().st_mtime > 86400):
            if folder.resolve().parent == spool.resolve():
                shutil.rmtree(folder)
    used = sum(f.stat().st_size for d in spool.iterdir() if d.is_dir() and not d.is_symlink()
               for f in d.iterdir() if f.is_file() and not f.is_symlink())
    if used + file['size'] > 2 * 1024 * 1024 * 1024:
        raise ValueError('虚拟机附件缓存已满，请清理超过一天的旧附件后重试')
    folder = spool / command['id']
    folder.mkdir(exist_ok=True)
    if folder.is_symlink() or folder.resolve().parent != spool.resolve():
        raise ValueError('附件缓存路径无效')
    target, staged = folder / file['name'], folder / '.download-part'
    digest, size = hashlib.sha256(), 0
    try:
        with open_response(command['id']) as response, staged.open('xb') as stream:
            length = response.headers.get('Content-Length')
            if length is not None and int(length) != file['size']:
                raise ValueError('主机附件长度不一致')
            while True:
                part = response.read(1024 * 1024)
                if not part:
                    break
                size += len(part)
                if size > file['size'] or size > FILE_LIMIT:
                    raise ValueError('主机附件超过声明大小')
                stream.write(part)
                digest.update(part)
        if size != file['size'] or digest.hexdigest() != file['sha256']:
            raise ValueError('附件传输校验失败，未交给微信发送')
        metadata(command)
        staged.replace(target)
        return checked_path(command, spool)
    finally:
        if staged.exists() and not staged.is_symlink():
            staged.unlink()


def send_attachment(chat, command, spool, kind, sender):
    target = checked_path(command, spool)
    label = ('回复 ' + sender + '：\n' if kind == 'group' else '') + '附件：' + command['file']['name']
    result = chat.SendMsg(label)
    check_result(result)
    result = chat.SendFiles(str(target))
    check_result(result)


def check_result(result):
    if isinstance(result, dict) and result.get('status') in ('失败', '错误'):
        raise ValueError(result.get('message') or '微信发送附件失败')

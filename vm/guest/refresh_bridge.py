"""Refresh a changed private relay address without replacing the shared key."""
import ipaddress
import json
from pathlib import Path
import re
import shutil
import stat
import uuid
from urllib.parse import urlparse
from guest_common import require_vm, verify_manifest, contained


def validate(config):
    address = urlparse(config.get('relay', ''))
    if (address.scheme != 'http' or address.port != 8791 or address.username or address.password
            or address.path or address.query or address.fragment
            or not ipaddress.ip_address(address.hostname).is_private
            or config.get('account') != '贾维斯'
            or not re.fullmatch('[0-9a-f]{64}', config.get('token', ''))):
        raise RuntimeError('桥接配置不符合已部署的私网连接要求。')


def refresh(root, media):
    root, media = Path(root), Path(media)
    require_vm(root)
    source = contained(media, 'workbench/vm-agent.json')
    if not source.is_file():
        return False
    verify_manifest(media)
    target = contained(root, 'workbench/vm-agent.json')
    old = json.loads(target.read_text(encoding='utf-8-sig'))
    new = json.loads(source.read_text(encoding='utf-8-sig'))
    validate(old)
    validate(new)
    if old['token'] != new['token']:
        raise RuntimeError('桥接密钥不一致，未覆盖来宾配置。')
    if old['relay'] == new['relay']:
        print('主机桥接地址已同步。', flush=True)
        return False
    identity = uuid.uuid4().hex[:12]
    backup = contained(root, 'workbench/vm-agent.before-address-' + identity + '.json')
    staged = contained(root, 'workbench/vm-agent.address-' + identity + '.json')
    shutil.copyfile(target, backup)
    shutil.copyfile(source, staged)
    mode = target.stat().st_mode
    try:
        target.chmod(mode | stat.S_IWRITE)
        staged.replace(target)
    except Exception:
        if target.exists():
            target.chmod(mode)
        raise
    print('已同步重启后的主机桥接地址，连接密钥保持不变。', flush=True)
    return True

"""Discover the Hyper-V Default Switch host gateway from inside the guest."""
import ipaddress
import json
import subprocess


def select_gateway(records):
    if isinstance(records, dict):
        records = [records]
    matches = []
    for item in records or []:
        try:
            local = ipaddress.ip_address(item['address'])
            gateway = ipaddress.ip_address(item['gateway'])
            prefix = int(item['prefix'])
            network = ipaddress.ip_network(f'{local}/{prefix}', strict=False)
        except (KeyError, TypeError, ValueError):
            continue
        if local.version == 4 and gateway.version == 4 and gateway.is_private and gateway in network:
            matches.append(str(gateway))
    matches = sorted(set(matches))
    if len(matches) != 1:
        raise RuntimeError('未找到唯一的 Hyper-V 私网默认网关')
    return matches[0]


def discover_gateway(timeout=10):
    command = (
        "$items=@(Get-NetIPConfiguration | ForEach-Object {"
        "if($_.IPv4DefaultGateway -and $_.IPv4Address){"
        "[pscustomobject]@{address=$_.IPv4Address[0].IPAddress;"
        "prefix=$_.IPv4Address[0].PrefixLength;gateway=$_.IPv4DefaultGateway[0].NextHop}}});"
        "$items | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True)
    return select_gateway(json.loads(result.stdout or '[]'))


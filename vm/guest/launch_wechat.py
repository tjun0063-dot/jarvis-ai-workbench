"""Validate and open the guest WeChat client without a PowerShell script file."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import contained, native_query, require_vm, sha256, verify_publisher
from test_accessibility import ensure_narrator


def main(root=None, auto_repair=True):
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    require_vm(root)
    ensure_narrator(root)
    source = root / 'wechat-assistant-4.1.8.107'
    manifest = json.loads((source / 'preparation.json').read_text(encoding='utf-8-sig'))
    if not manifest.get('ready') or manifest.get('version') != '4.1.8.107':
        raise RuntimeError('兼容微信部署记录未通过核验。')
    client = source / 'client'
    for item in manifest['launchFiles']:
        binary = contained(client, item['path'])
        actual = sha256(binary) if binary.is_file() else '文件缺失'
        if actual.lower() != item['sha256'].lower():
            print('微信客户端文件已变化：' + item['path'], flush=True)
            try:
                from windows_signature import signed_file_info
                print('当前版本及签名：' + json.dumps(signed_file_info(binary), ensure_ascii=False), flush=True)
            except Exception as error:
                print('无法核验当前签名：' + str(error), flush=True)
            recovery = root / 'recovery-media'
            if auto_repair and recovery.is_dir():
                from repair_client import restore
                print('正在使用本机留存的原始兼容文件恢复。', flush=True)
                restore(root, recovery)
                return main(root, auto_repair=False)
            raise RuntimeError('微信客户端文件已变化：' + item['path'] +
                               '；当前 SHA256=' + actual + '；预期 SHA256=' + item['sha256'])
    entry = contained(client, manifest['entry'])
    info = verify_publisher(root, entry, 'Tencent')
    if info.get('version') != '4.1.8.107':
        raise RuntimeError('微信客户端版本不兼容。')
    processes = native_query(root,
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        "ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process -Filter \"Name='Weixin.exe'\" -ErrorAction Stop | "
        "Select-Object ExecutablePath) -Compress")
    for process in processes:
        path = process.get('ExecutablePath')
        if not path or not Path(path).resolve().is_relative_to(client.resolve()):
            raise RuntimeError('请先手动退出虚拟机中其他版本的微信，再打开贾维斯兼容版。')
    if not processes:
        print('已通过虚拟机、文件和发布者签名检查，正在启动微信。', flush=True)
        subprocess.Popen([str(entry)], cwd=str(client))
        time.sleep(3)
        processes = native_query(root,
            "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
            "ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process -Filter \"Name='Weixin.exe'\" -ErrorAction Stop | "
            "Select-Object ExecutablePath) -Compress")
        if not any(p.get('ExecutablePath') and Path(p['ExecutablePath']).resolve().is_relative_to(client.resolve())
                   for p in processes):
            raise RuntimeError('微信启动后没有持续运行。请把这份启动记录发给工作台，以便检查客户端运行环境。')
    print('微信进程正在运行。请查看虚拟机内的微信窗口，扫码登录贾维斯；登录后运行 C:\\Jarvis\\Start-Agent.cmd。', flush=True)
    print('此结果仅确认微信进程存在，登录和连接器还需继续验证。', flush=True)


def run_with_report():
    report_dir = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest'
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / 'WeChat-launch-result.txt'
    from contextlib import redirect_stdout, redirect_stderr
    exit_code = 0
    with report.open('w', encoding='utf-8-sig') as log, redirect_stdout(log), redirect_stderr(log):
        try:
            main()
        except Exception as error:
            print('启动失败：' + str(error), flush=True)
            traceback.print_exc()
            exit_code = 1
    print(report.read_text(encoding='utf-8-sig'), flush=True)
    try:
        subprocess.Popen(['notepad.exe', str(report)])
    except OSError:
        print('启动记录已保存：' + str(report), flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(run_with_report())

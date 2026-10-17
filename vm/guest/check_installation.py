"""Read-only installation check with a persistent, readable result."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import contained, require_vm, sha256


def check(destination):
    destination = Path(destination)
    if not destination.exists():
        return False, '尚未安装：没有找到 C:\\Jarvis。请重新运行光盘里的 Install-Jarvis.cmd，并保留完整错误信息。'
    required = ['python/python.exe', 'workbench/.wechat-venv/Scripts/python.exe',
                'workbench/vm-agent.json', 'workbench/vm_agent.py',
                'workbench/wechat_assistant.py', 'Open-WeChat.cmd', 'Start-Agent.cmd',
                'wechat-assistant-4.1.8.107/preparation.json']
    missing = [name for name in required if not (destination / name).is_file()]
    if missing:
        return False, '安装未完成，缺少：\n' + '\n'.join(missing) + '\n请把这份结果发给工作台，先不要删除或重新安装。'
    source = destination / 'wechat-assistant-4.1.8.107'
    try:
        config = json.loads((destination / 'workbench/vm-agent.json').read_text(encoding='utf-8-sig'))
        if not config.get('relay') or not config.get('token') or config.get('account') != '贾维斯':
            raise ValueError('连接配置不完整')
        manifest = json.loads((source / 'preparation.json').read_text(encoding='utf-8-sig'))
        if not manifest.get('ready') or manifest.get('version') != '4.1.8.107':
            raise ValueError('微信兼容版本记录不正确')
        for item in manifest['launchFiles']:
            if sha256(contained(source / 'client', item['path'])).lower() != item['sha256'].lower():
                raise ValueError('微信兼容版本文件已变化')
    except Exception as error:
        return False, '安装文件检查未通过：' + str(error)
    try:
        result = subprocess.run([str(destination / 'workbench/.wechat-venv/Scripts/python.exe'),
            '-I', '-c', 'import win32ui, win32gui, win32api, pythoncom, wxauto4, wxauto4.uia, win32com.client; print("OK")'],
            capture_output=True, text=True, encoding='utf-8', timeout=45,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            return False, '微信连接器依赖未安装完整：\n' + result.stderr.strip()
    except Exception as error:
        return False, '无法检查微信连接器：' + str(error)
    return True, ('安装检查通过。Python、微信连接器、兼容客户端和连接配置齐全。\n\n'
                  '下一步：\n1. 打开 C:\\Jarvis\\Open-WeChat.cmd，扫码登录贾维斯。\n'
                  '2. 登录后打开 C:\\Jarvis\\Start-Agent.cmd，并保持运行。\n'
                  '3. 工作台显示已连接后，再测试私聊和群聊回复。\n\n'
                  '此检查确认安装文件和依赖齐全；微信登录与消息收发仍须继续验证。')


def main():
    require_vm(Path(__file__).resolve().parent)
    success, message = check('C:/Jarvis')
    print(message, flush=True)
    report_dir = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest'
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / 'Installation-result.txt'
    report.write_text(message, encoding='utf-8-sig')
    subprocess.Popen(['notepad.exe', str(report)])
    return 0 if success else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('检查失败：' + str(error), file=sys.stderr, flush=True)
        raise SystemExit(1)

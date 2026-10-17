"""Repair native Python GUI dependencies with the signed Microsoft runtime."""
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import contained, native_query, require_vm, sha256, verify_publisher


def probe(destination):
    python = Path(destination) / 'workbench/.wechat-venv/Scripts/python.exe'
    if not python.is_file():
        raise RuntimeError('没有找到已安装的微信连接器 Python 环境。')
    return subprocess.run([str(python), '-I', '-c',
        'import win32ui, win32gui, win32api, pythoncom, win32com.client, wxauto4, wxauto4.uia; print("NATIVE_IMPORTS_OK")'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
        env={**os.environ, 'PYTHONUTF8':'1', 'PYTHONIOENCODING':'utf-8'},
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def ensure_runtime(media, destination):
    media, destination = Path(media), Path(destination)
    before = probe(destination)
    if not before.returncode:
        print('原生依赖检查通过，无需安装运行库。', flush=True)
        return 0
    print('当前依赖错误：\n' + before.stderr.strip(), flush=True)
    installer = contained(media, 'vc_redist.x64.exe')
    manifest = json.loads((media / 'payload-manifest.json').read_text(encoding='utf-8-sig'))
    items = [item for item in manifest.get('files', []) if item['path'] == installer.name]
    if len(items) != 1 or sha256(installer).lower() != items[0]['sha256'].lower():
        raise RuntimeError('微软运行库安装文件哈希核验失败。')
    info = verify_publisher(media, installer, 'Microsoft Corporation')
    print('Microsoft 官方签名核验通过，运行库版本：' + str(info.get('version')), flush=True)
    print('正在安装 x64 Visual C++ 运行库。若出现 Windows 权限确认，请确认发布者为 Microsoft Corporation。', flush=True)
    code = native_query(media,
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        "$ErrorActionPreference='Stop';"
        "$jarvisRuntimeProcess=Start-Process -FilePath $env:JARVIS_RUNTIME_INSTALLER "
        "-ArgumentList @('/install','/passive','/norestart') -Verb RunAs -Wait -PassThru;"
        "ConvertTo-Json -InputObject $jarvisRuntimeProcess.ExitCode -Compress",
        timeout=600, JARVIS_RUNTIME_INSTALLER=str(installer))
    print('运行库安装器退出码：' + str(code), flush=True)
    after = probe(destination)
    if after.returncode:
        raise RuntimeError('运行库安装后依赖仍未通过检查：\n' + after.stderr.strip())
    print('原生依赖检查通过：win32ui、微信连接器及其他 Windows 模块均能导入。', flush=True)
    if code == 3010:
        print('安装器提示需要重启，请只重启贾维斯虚拟机，然后重新登录微信并运行 Start-Agent.cmd。', flush=True)
    elif code not in (0, 1638):
        raise RuntimeError('虽然依赖已能导入，安装器仍返回异常退出码：' + str(code))
    return 3010 if code == 3010 else 0


def main():
    media = Path(__file__).resolve().parent
    require_vm(media)
    result = ensure_runtime(media, Path('C:/Jarvis'))
    from update_launcher import update
    update(media, Path('C:/Jarvis'), agent=True)
    return result


if __name__ == '__main__':
    report = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest/Runtime-repair-result.txt'
    report.parent.mkdir(parents=True, exist_ok=True)
    from contextlib import redirect_stdout, redirect_stderr
    result = 0
    with report.open('w', encoding='utf-8-sig') as log, redirect_stdout(log), redirect_stderr(log):
        try:
            result = main()
        except Exception:
            traceback.print_exc();result = 1
    print(report.read_text(encoding='utf-8-sig'), flush=True)
    try:
        subprocess.Popen(['notepad.exe', str(report)])
    except OSError:
        print('修复记录已保存：' + str(report), flush=True)
    raise SystemExit(result)

"""Keep VM agent startup output visible and persist it after an exit."""
import os
from pathlib import Path
import subprocess
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_common import require_vm


def execute_agent(root, report):
    root, report = Path(root), Path(report)
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open('w', encoding='utf-8-sig') as log:
        try:
            require_vm(root)
            command = [str(root / 'workbench/.wechat-venv/Scripts/python.exe'),
                       '-u', str(root / 'workbench/vm_agent.py')]
            with subprocess.Popen(command, cwd=str(root / 'workbench'),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    encoding='utf-8', errors='replace',
                    env={**os.environ, 'PYTHONUTF8':'1', 'PYTHONIOENCODING':'utf-8'}) as process:
                for line in process.stdout:
                    print(line, end='', flush=True)
                    log.write(line);log.flush()
                result = process.wait()
            message = ('连接器启动失败或异常退出。请把本记录发给工作台。' if result
                       else '连接器已停止运行。')
            log.write(message + '\n');log.flush()
            print(message, flush=True)
            return result
        except Exception:
            message = traceback.format_exc()
            print(message, flush=True);log.write(message);log.flush()
            return 1


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    report = Path(os.environ['LOCALAPPDATA']) / 'JarvisGuest/Agent-result.txt'
    result = execute_agent(root, report)
    try:
        subprocess.Popen(['notepad.exe', str(report)])
    except OSError:
        print('运行记录已保存：' + str(report), flush=True)
    raise SystemExit(result)

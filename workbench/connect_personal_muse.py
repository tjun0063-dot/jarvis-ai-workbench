"""User-approved one-time Chrome session transfer, limited to muse.ai.

This file is not invoked by the worker or server. Its launcher explains the
scope and requires the person at the keyboard to type YES before invoking it.
"""
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
BROWSER = ROOT / 'tools/personal-muse-browser/node_modules/agent-browser/bin/agent-browser-win32-x64.exe'


def muse_cookie_jar(cookies):
    jar = {c['name']: c['value'] for c in cookies
           if isinstance(c, dict) and c.get('domain', '').lower() in ('muse.ai', '.muse.ai')
           and isinstance(c.get('name'), str) and isinstance(c.get('value'), str)}
    if not jar.get('hatch_sess'):
        raise RuntimeError('No logged-in muse.ai session was found; the previous saved login was kept.')
    return {'cookies': jar}


def browser(*args):
    result = subprocess.run([str(BROWSER), '--headed', '--auto-connect', '--session', 'jarvis-muse-auth', *args, '--json'],
                            capture_output=True, text=True, encoding='utf-8', timeout=45)
    try:
        envelope = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError('Chrome connection failed. Check chrome://inspect/#remote-debugging and the approval prompt.') from None
    if result.returncode or envelope.get('success') is False:
        raise RuntimeError('Chrome did not approve the connection. Keep the logged-in Muse tab open and retry.')
    return envelope.get('data', envelope)


def main():
    tabs = browser('tab', 'list').get('tabs', [])
    matching = [t for t in tabs if urlsplit(t.get('url', '')).scheme == 'https'
                and urlsplit(t.get('url', '')).hostname == 'muse.ai']
    if not matching:
        raise RuntimeError('Open the logged-in https://muse.ai/ tab in Chrome first.')
    target = matching[0].get('id') or matching[0].get('tabId')
    if not target:
        raise RuntimeError('Chrome did not return a Muse tab identifier.')
    browser('tab', str(target))
    result = browser('cookies', 'get')
    cookies = result if isinstance(result, list) else result.get('cookies', result.get('items', []))
    jar = muse_cookie_jar(cookies)
    directory = ROOT / 'data/muse-personal'
    if not directory.is_dir():
        raise RuntimeError('Use Connect-Muse.cmd so the private credential directory is prepared first.')
    destination = directory / 'cookies.txt'
    config = directory / 'config.json'
    if not config.exists():
        with config.open('x', encoding='utf-8') as file:
            json.dump({'cookies_file': str(destination), 'node_id': uuid4().hex[:16]}, file)
    temporary = directory / ('.cookies-' + uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as file:
            json.dump(jar, file)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print('Muse login saved locally. No cookie values were printed. Return to the workbench and click Check connection.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error))
        raise SystemExit(1)

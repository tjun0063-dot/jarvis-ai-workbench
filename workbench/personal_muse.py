"""Bounded workbench adapter for the muse.ai personal agent (muse-cli 0.3.2).

Input is JSON on stdin, never a prompt or credential in process arguments.
Authentication is a separate, user-operated step; this worker never exports it.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

from muse_cli import cli

ROOT = Path(__file__).resolve().parent
PRIVATE = Path(os.environ.get('WORKBENCH_DATA_DIR', ROOT / 'data')) / 'muse-personal'
cli.CONFIG_DIR = str(PRIVATE)
cli.CONFIG_FILE = str(PRIVATE / 'config.json')
cli.COOKIES_FILE = str(PRIVATE / 'cookies.txt')


def invoke(fn, **kwargs):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        fn(SimpleNamespace(**kwargs))
    return json.loads(output.getvalue())


def _complete_reply(events, baseline, fallback=''):
    """Return the latest complete assistant text after a send baseline.

    Muse can publish a short prefix first and then replace that event with the
    complete text.  It can also use several assistant bubbles for one turn.
    """
    replies = []
    for event in sorted(events, key=lambda item: item.get('seq', 0)):
        if not cli.is_reply(event, baseline):
            continue
        message = cli.fmt_event(event)
        text = message.get('text')
        if not isinstance(text, str) or not text.strip():
            continue
        text = text.strip()
        if replies and text == replies[-1]:
            continue
        if replies and text.startswith(replies[-1]):
            replies[-1] = text
        elif not replies or not replies[-1].startswith(text):
            replies.append(text)
    return '\n\n'.join(replies).strip() or str(fallback or '').strip()


def _settle_reply(fetch_events, baseline, initial, max_polls=30,
                  stable_polls=6, pause=2):
    """Poll until Muse history has stopped changing for about ten seconds."""
    current = str(initial or '').strip()
    stable = 0
    for _ in range(max_polls):
        try:
            candidate = _complete_reply(fetch_events(), baseline, current)
        except Exception:
            candidate = current
        if candidate and candidate != current:
            current = candidate
            stable = 0
        else:
            stable += 1
        if stable >= stable_polls:
            break
        if pause:
            time.sleep(pause)
    return current


def dispatch(request):
    command = request.get('command')
    if command == 'status':
        invoke(cli.cmd_status)
        return {'ok': True}
    if command == 'library':
        return {'sessions': invoke(cli.cmd_threads, archived=False),
                'goals': invoke(cli.cmd_goals)}
    if command == 'history':
        thread = request.get('thread')
        if not isinstance(thread, str) or not thread or len(thread) > 512:
            raise ValueError('A specific Muse chat must be selected.')
        events = invoke(cli.cmd_history, thread=thread, limit=100, raw=True).get('chat_events', [])
        history = []
        for event in sorted(events, key=lambda item: item.get('seq', 0)):
            message = cli.fmt_event(event)
            role = message.get('role')
            role = {'message.user': 'user', 'message.assistant': 'assistant'}.get(role, role)
            if role in ('user', 'assistant') and isinstance(message.get('text'), str) and message['text']:
                history.append({'role': role, 'content': message['text']})
        return {'history': history}
    if command == 'create':
        return invoke(cli.cmd_session_start, title=str(request.get('title') or '工作台会话')[:120])
    if command == 'send':
        thread, prompt = request.get('thread'), request.get('prompt')
        if not isinstance(thread, str) or not thread or len(thread) > 512:
            raise ValueError('A dedicated Muse side chat is required.')
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 100000:
            raise ValueError('Invalid Muse prompt.')
        before = invoke(cli.cmd_history, thread=thread, limit=1, raw=True).get('chat_events', [])
        baseline = max((event.get('seq', 0) for event in before), default=0)
        reply = invoke(cli.cmd_send, thread=thread, text=prompt, wait=180)
        text = reply.get('reply', {}).get('text')
        if not isinstance(text, str) or not text.strip():
            raise TimeoutError('Muse has not replied yet. The remote task may still be running; avoid resending it.')
        def fetch_events():
            return invoke(cli.cmd_history, thread=thread, limit=100, raw=True).get('chat_events', [])
        text = _settle_reply(fetch_events, baseline, text)
        if request.get('artifactDir'):
            import re
            from muse_artifacts import attachment_list, download
            task_id=request.get('taskId')
            if not isinstance(task_id,str) or not re.fullmatch(r'[a-f0-9-]{36}',task_id):
                raise ValueError('Invalid attachment task ID.')
            text,files=attachment_list(text,task_id)
            if files:
                gateway=cli.connect(cli.load_config())
                try:download(gateway,files,request['artifactDir'])
                finally:gateway.close()
        return {'text': text}
    raise ValueError('Unsupported workbench command.')


if __name__ == '__main__':
    try:
        raw = sys.stdin.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('Request too large.')
        result = dispatch(json.loads(raw))
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        # Network exception strings may contain signed gateway URLs. Keep them local.
        message = str(error) if isinstance(error, (ValueError, TimeoutError)) else 'Muse connection failed; check the saved login and network.'
        print(json.dumps({'error': message, 'kind': type(error).__name__}, ensure_ascii=False))
        sys.exit(1)

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).with_name('personal_muse.py')
SPEC = importlib.util.spec_from_file_location('personal_muse_under_test', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def event(seq, text, *, reply_to=None, ready=True):
    payload = {'display_text': text, 'display_text_ready': ready}
    if reply_to is not None:
        payload['reply_to_message_id'] = reply_to
    return {'seq': seq, 'event_name': 'message.assistant', 'payload': payload}


class SettleReplyTests(unittest.TestCase):
    def test_waits_for_same_event_to_expand(self):
        snapshots = iter([
            [event(11, '这个我没法')],
            [event(11, '这个我没法直接替你付款，但可以把库迪咖啡订单准备到付款前。')],
            [event(11, '这个我没法直接替你付款，但可以把库迪咖啡订单准备到付款前。')],
        ])
        last = []

        def fetch():
            nonlocal last
            try:
                last = next(snapshots)
            except StopIteration:
                pass
            return last

        answer = MODULE._settle_reply(fetch, 10, '这个我没法', max_polls=5,
                                      stable_polls=2, pause=0)
        self.assertEqual(answer, '这个我没法直接替你付款，但可以把库迪咖啡订单准备到付款前。')

    def test_combines_multiple_bubbles_and_ignores_pushes(self):
        events = [
            event(9, '旧回复'),
            event(11, '第一段'),
            event(12, '后台推送', reply_to='self'),
            event(13, '第二段'),
        ]
        self.assertEqual(MODULE._complete_reply(events, 10), '第一段\n\n第二段')


if __name__ == '__main__':
    unittest.main()

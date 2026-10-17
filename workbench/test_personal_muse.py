import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import personal_muse
from connect_personal_muse import muse_cookie_jar

class PersonalMuseTests(unittest.TestCase):
    def test_cookie_scope_is_exact_and_requires_valid_login(self):
        jar = muse_cookie_jar([{'domain':'.muse.ai','name':'hatch_sess','value':'fixture'},
                              {'domain':'muse.ai.evil.example','name':'stolen','value':'fixture'},
                              {'domain':'other.example','name':'other','value':'fixture'}])
        self.assertEqual(jar, {'cookies':{'hatch_sess':'fixture'}})
        with self.assertRaises(RuntimeError):
            muse_cookie_jar([{'domain':'muse.ai.evil.example','name':'hatch_sess','value':'fixture'}])

    def test_missing_thread_never_sends_to_personal_main_chat(self):
        with patch.object(personal_muse, 'invoke') as invoke:
            with self.assertRaises(ValueError):
                personal_muse.dispatch({'command':'send','prompt':'hello'})
            invoke.assert_not_called()

    def test_import_orders_messages_and_drops_non_conversation_events(self):
        events = [{'seq':3,'event_name':'message.assistant','payload':{'display_text':'答'}},
                  {'seq':1,'payload':{'role':'user','content':'问'}},
                  {'seq':2,'payload':{'role':'system','content':'internal'}}]
        with patch.object(personal_muse,'invoke',return_value={'chat_events':events}):
            self.assertEqual(personal_muse.dispatch({'command':'history','thread':'fixture'})['history'],
                             [{'role':'user','content':'问'},{'role':'assistant','content':'答'}])

    def test_no_reply_is_not_success(self):
        with patch.object(personal_muse,'invoke',return_value={'sent':True}):
            with self.assertRaises(TimeoutError):
                personal_muse.dispatch({'command':'send','thread':'fixture','prompt':'hello'})

if __name__ == '__main__':unittest.main()

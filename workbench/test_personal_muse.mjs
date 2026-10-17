import {test} from 'node:test';
import assert from 'node:assert/strict';
import {museThreadId} from './personal_muse.mjs';
test('personal Muse refuses a missing side-chat identifier instead of defaulting to the main chat',()=>{
 assert.equal(museThreadId({session_id:'my-side-chat'}),'my-side-chat');
 for(const response of [{},{session_id:''},{session_id:42},{session_id:'x'.repeat(513)}])assert.throws(()=>museThreadId(response),/避免误发/);
});

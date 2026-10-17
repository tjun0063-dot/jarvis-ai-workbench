import {test} from 'node:test';
import assert from 'node:assert/strict';
import {MuseOutput} from './muse_runner.mjs';
const event=(type,payload)=>JSON.stringify({payload_type:type,payload,stream:{kind:'session',id:'fixture-session'}})+'\n';
test('Muse consumes chunked JSONL without including input echoes or duplicating terminal text',()=>{
 const parser=new MuseOutput(),wire=event('run.input.echo',{text:'private input'})+event('run.output.delta',{text:'你'})+event('run.output.delta',{text:'好'})+event('run.terminal.completed',{terminal:'completed',text:'你好'});
 for(let n=0;n<wire.length;n+=7)parser.push(wire.slice(n,n+7));
 assert.equal(parser.finish(0),'你好');assert.equal(parser.session,'fixture-session');
});
test('Muse rejects an exit without a successful terminal, even if partial output exists',()=>{
 const parser=new MuseOutput();parser.push(event('run.output.delta',{text:'partial'}));assert.throws(()=>parser.finish(0),/完成事件/);
 const failed=new MuseOutput();failed.push(event('run.terminal.failed',{terminal:'failed',reason:'login required'}).trim());assert.throws(()=>failed.finish(1),/login required/);
});

import {test} from 'node:test';
import assert from 'node:assert/strict';
import {assistantHealth} from './assistant_health.mjs';
test('主动暂停窗口时不误报扫描故障，也不报告正在接收消息',()=>{
 const state=assistantHealth({status:'已连接',uiPaused:true,lastScan:'2026-01-01',listening:2,waitingWindows:0});
 assert.equal(state.paused,true);assert.equal(state.stale,false);assert.equal(state.receiving,false);assert.equal(state.windowsUnavailable,false);
});
test('fresh transport heartbeat does not imply receiving when all requested chat windows disappeared',()=>{
 const now=Date.parse('2026-10-16T00:00:00Z');
 const state=assistantHealth({status:'已连接',lastScan:new Date(now).toISOString(),listening:0,waitingWindows:2},now);
 assert.equal(state.stale,false);assert.equal(state.windowsUnavailable,true);assert.equal(state.receiving,false);
 const recovered=assistantHealth({status:'已连接',lastScan:new Date(now).toISOString(),listening:2,waitingWindows:0},now);
 assert.equal(recovered.windowsUnavailable,false);assert.equal(recovered.receiving,true);
});
test('stale or missing scan time cannot report receiving',()=>{
 for(const lastScan of [null,'invalid','2026-10-15T00:00:00Z']){
  const state=assistantHealth({status:'已连接',lastScan,listening:2},Date.parse('2026-10-16T00:00:00Z'));
  assert.equal(state.stale,true);assert.equal(state.receiving,false);
 }
});

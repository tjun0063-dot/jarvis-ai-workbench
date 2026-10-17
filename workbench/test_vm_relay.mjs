import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {createVmRelay} from './vm_relay.mjs';

test('窗口暂停须来宾确认，暂停阻止文字与文件回传，恢复保持原连接器',async()=>{
 const token='e'.repeat(64),events=[],relay=createVmRelay({bind:'127.0.0.1',port:0,token,onEvent:e=>events.push(e),pollMs:20});
 const address=await relay.listen(),runId=randomUUID();
 const post=async(endpoint,body={})=>{const r=await fetch('http://127.0.0.1:'+address.port+endpoint,{method:'POST',headers:{Authorization:'Bearer '+token},body:JSON.stringify({runId,...body})});return r.json();};
 try{
  await post('/v1/events',{event:{type:'ready',account:'贾维斯',fileProtocol:1}});
  await assert.rejects(relay.setUiPaused(true),/先安装/);
  await post('/v1/events',{event:{type:'health',controlProtocol:1,fileProtocol:1,uiPaused:false,listeningMode:'isolated-vm',scans:3,count:2,groupCount:1}});
  const pause=relay.setUiPaused(true);assert.equal(relay.uiPaused,false);assert.equal(relay.uiTransition,true);
  await assert.rejects(relay.send('r','暂不发送'),/暂停/);
  const command=(await post('/v1/poll')).commands[0];assert.equal(command.type,'ui_pause');assert.equal(command.paused,true);
  await post('/v1/events',{event:{type:'health',controlProtocol:1,uiPaused:true,listeningMode:'isolated-vm',scans:3,count:2,groupCount:1}});
  await post('/v1/events',{event:{type:'ack',id:command.id,uiPaused:true}});await pause;
  assert(relay.connected);assert(relay.uiPaused);assert.equal(relay.uiTransition,null);assert(events.at(-1).relayControl);
  await assert.rejects(relay.send('r','暂不发送'),/暂停/);await assert.rejects(relay.sendFile('r',{},'unused'),/暂停/);
  const resume=relay.setUiPaused(false),next=(await post('/v1/poll')).commands[0];assert.equal(next.paused,false);
  await post('/v1/events',{event:{type:'ack',id:next.id,uiPaused:false}});await resume;
  assert(!relay.uiPaused);assert(relay.connected);
  const text=relay.send('r','恢复发送'),last=(await post('/v1/poll')).commands[0];
  await post('/v1/events',{event:{type:'ack',id:last.id}});await text;assert(!events.at(-1).relayControl);
 }finally{await relay.close();}
});

test('authenticated scan heartbeat restores an already-running guest after host restart',async()=>{
 const token='c'.repeat(64),events=[],relay=createVmRelay({bind:'127.0.0.1',port:0,token,onEvent:e=>events.push(e)});
 const address=await relay.listen(),runId=randomUUID();
 const send=async(event,key=token)=>fetch('http://127.0.0.1:'+address.port+'/v1/events',{method:'POST',headers:{Authorization:'Bearer '+key},body:JSON.stringify({runId,event})});
 try{
  const health={type:'health',listeningMode:'isolated-vm',scans:20,count:2,groupCount:1};
  assert.equal((await send(health,'invalid')).status,401);assert(!relay.connected);
  await send({type:'health'});assert(!relay.connected);
  await send(health);assert(relay.connected);assert.equal(events.at(-2).type,'ready');
  relay.stop();assert.equal((await send(health)).status,403);assert(!relay.connected);
 }finally{await relay.close();}
});

test('冷启动即暂停的来宾可在主机重启后恢复连接，须验证昵称和暂停协议',async()=>{
 const relay=createVmRelay({bind:'127.0.0.1',port:0,token:'f'.repeat(64)}),runId=randomUUID();
 const address=await relay.listen();
 const event={type:'health',controlProtocol:1,uiPaused:true,scans:0,count:2,groupCount:1,listeningMode:'isolated-vm'};
 async function post(value){await fetch('http://127.0.0.1:'+address.port+'/v1/events',{method:'POST',headers:{Authorization:'Bearer '+'f'.repeat(64)},body:JSON.stringify({runId,event:value})});}
 try{await post(event);assert(!relay.connected);await post({...event,account:'其他账号'});assert(!relay.connected);await post({...event,account:'贾维斯'});assert(relay.connected);assert(relay.uiPaused);assert(relay.supportsUiControl);}finally{await relay.close();}
});

test('虚拟机桥认证、成员路由、乱序确认、停止后禁止消息',async()=>{
 const token='a'.repeat(64),events=[],relay=createVmRelay({bind:'127.0.0.1',port:0,token,pollMs:50,onEvent:e=>events.push(e)});
 const address=await relay.listen(),url='http://127.0.0.1:'+address.port,runId=randomUUID();
 const post=async(endpoint,data,key=token)=>{const r=await fetch(url+endpoint,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+key},body:JSON.stringify({runId,...data})});return {status:r.status,data:await r.json()};};
 try{
  assert.equal((await post('/v1/events',{event:{type:'ready',account:'贾维斯'}},'invalid')).status,401);
  assert.equal((await post('/v1/events',{event:{type:'ready',account:'另一个号'}})).status,400);
  await post('/v1/events',{event:{type:'ready',account:'贾维斯'}});assert(relay.connected);
  const ctx={chat:'项目群',kind:'group',route:'甲的路由'};
  await post('/v1/events',{event:{type:'message',id:'m1',sender:'甲',text:'/status',context:ctx}});
  assert.deepEqual(events.at(-1).context,ctx);
  const a=relay.send('甲的路由','结果甲'),b=relay.send('乙的路由','结果乙');
  const {data}=await post('/v1/poll',{});assert.deepEqual(data.commands.map(c=>c.to),['甲的路由','乙的路由']);
  await post('/v1/events',{event:{type:'ack',id:data.commands[1].id}});await b;assert.equal(relay.pendingCount,1);
  await post('/v1/events',{event:{type:'ack',id:data.commands[0].id}});await a;assert.equal(relay.pendingCount,0);
  const waiting=relay.send('甲的路由','未发送');const rejected=assert.rejects(waiting,/停止/);relay.stop();await rejected;
  assert.equal((await post('/v1/events',{event:{type:'message',id:'m2',sender:'甲',text:'任务',context:ctx}})).status,403);
  assert.equal((await post('/v1/poll',{})).data.commands[0].type,'shutdown');assert(!relay.connected);
 }finally{await relay.close();}
});
test('桥发送过期后不再派发，拒绝错误路由和另一个连接器',async()=>{
 const token='b'.repeat(64),relay=createVmRelay({bind:'127.0.0.1',port:0,token,timeoutMs:30,pollMs:20});
 const address=await relay.listen(),runId=randomUUID();
 async function post(endpoint,event,run=runId){const r=await fetch('http://127.0.0.1:'+address.port+endpoint,{method:'POST',headers:{Authorization:'Bearer '+token},body:JSON.stringify({runId:run,event})});return {status:r.status,data:await r.json()};}
 try{
  await post('/v1/events',{type:'ready',account:'贾维斯'});
  assert.equal((await post('/v1/events',{type:'message',context:{kind:'shell'}})).status,400);
  assert.equal((await post('/v1/poll',null,randomUUID())).status,409);
  await assert.rejects(relay.send('r','迟到结果'),/超时/);
  assert.deepEqual((await post('/v1/poll')).data.commands,[]);
 }finally{await relay.close();}
});

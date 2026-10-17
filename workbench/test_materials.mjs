import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {createMaterialStore,materialPrompt} from './materials.mjs';
import {createInbound,remoteKey} from './remote.mjs';
import {createVmRelay} from './vm_relay.mjs';

test('材料会话按群和发送人隔离，合并多条说明与文件后只提交一次',async()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'jarvis-materials-'));
 try{
  const state={projects:{default:{id:'default',name:'默认',directory:temp}},sessions:{},tasks:[],contacts:{},seen:[]};let sequence=0,started,stopped,queued,saved=0;
  const materials=createMaterialStore(path.join(temp,'incoming'),state,()=>saved++),sent=[];
  const receive=createInbound({state,materials,save(){saved++;},createProject(name,remoteOwner){const id='p'+(++sequence);return state.projects[id]={id,name,remoteOwner,directory:temp};},createConversation(projectId,engine,title){const id='s'+(++sequence);return state.sessions[id]={id,projectId,engine,title};},enqueue(...args){queued=args;const task={status:'queued',engine:args[1]};state.tasks.push(task);return task;},send:async(channel,to,text)=>sent.push({to,text}),stop:()=>false,startCollection:async(...args)=>{started=args;},stopCollection:async(...args)=>{stopped=args;}});
  const context={chat:'项目群',kind:'group',route:'route-a'},key=remoteKey('wechat-account','甲',context);
  await receive('wechat-account','甲','/材料','m1',context);const draft=materials.get(key);assert(draft);assert.equal(started[1],draft.id);
  await receive('wechat-account','甲','/codex 请根据资料制作摘要','m2',{...context,route:'route-b'});
  const id=randomUUID(),bytes=Buffer.from('material bytes'),target=materials.location(draft.id,id);fs.writeFileSync(target,bytes);
  materials.addFile(draft.id,{id,name:'资料.txt',size:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});
  await receive('wechat-account','乙','/材料状态','m3',{...context,route:'route-other'});assert(sent.at(-1).text.includes('没有材料'));
  await receive('wechat-account','甲','补充：保留数字','m4',{...context,route:'route-c'});
  await receive('wechat-account','甲','/开始','m5',{...context,route:'route-d'});
  assert.equal(stopped[1],draft.id);assert.equal(queued[1],'codex');assert.equal(queued[2],'请根据资料制作摘要\n\n补充：保留数字');assert.equal(queued[6].files[0].name,'资料.txt');assert.equal(materials.get(key),null);
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
});

test('任务材料提示包含真实输入路径，取消会清理临时文件',()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'jarvis-material-clean-'));
 try{
  const state={},store=createMaterialStore(path.join(temp,'incoming'),state),key='owner',context={chat:'我',kind:'friend',route:'r'};
  const draft=store.begin(key,{channel:'wechat-account',sender:'我',context}),id=randomUUID(),data=Buffer.from('x'),file=store.location(draft.id,id);fs.writeFileSync(file,data);
  store.addFile(draft.id,{id,name:'图片.png',size:1,sha256:createHash('sha256').update(data).digest('hex')});
  const finished=store.finish(key,'r2'),out=path.join(temp,'out');fs.mkdirSync(out);const rows=store.stage(finished,out),prompt=materialPrompt('分析',rows);
  assert(prompt.includes(path.resolve(rows[0].path)));assert(!fs.existsSync(path.dirname(file)));assert(fs.existsSync(rows[0].path));
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
});

test('反向桥只接受已授权材料会话，并按声明长度和哈希落盘',async()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'jarvis-material-relay-')),token='e'.repeat(64),events=[];
 const relay=createVmRelay({bind:'127.0.0.1',port:0,token,pollMs:20,incomingDirectory:temp,onEvent:e=>events.push(e)}),address=await relay.listen(),runId=randomUUID(),base='http://127.0.0.1:'+address.port;
 const json=(endpoint,body={})=>fetch(base+endpoint,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({runId,...body})});
 try{
  await json('/v1/events',{event:{type:'ready',account:'贾维斯',materialProtocol:1}});
  const collectionId=randomUUID(),start=relay.startCollection('route-a',collectionId,Date.now()+60000),poll=await json('/v1/poll'),command=(await poll.json()).commands[0];assert.equal(command.type,'collect_start');
  await json('/v1/events',{event:{type:'ack',id:command.id}});await start;
  const bytes=Buffer.from('incoming material'),id=randomUUID(),sha256=createHash('sha256').update(bytes).digest('hex'),headers={Authorization:'Bearer '+token,'Content-Type':'application/octet-stream','Content-Length':String(bytes.length),'X-Jarvis-Run-Id':runId,'X-Jarvis-Collection-Id':collectionId,'X-Jarvis-Material-Id':id,'X-Jarvis-Sha256':sha256,'X-Jarvis-File-Name':encodeURIComponent('资料 1.txt')};
  assert.equal((await fetch(base+'/v1/material',{method:'POST',headers,body:bytes})).status,200);assert.deepEqual(fs.readFileSync(path.join(temp,collectionId,id)),bytes);assert.equal(events.at(-1).file.name,'资料 1.txt');
  const wrong={...headers,'X-Jarvis-Material-Id':randomUUID(),'X-Jarvis-Sha256':'0'.repeat(64)};assert.equal((await fetch(base+'/v1/material',{method:'POST',headers:wrong,body:bytes})).status,400);
  const stopping=relay.stopCollection('route-b',collectionId),stopPoll=await json('/v1/poll'),stopCommand=(await stopPoll.json()).commands[0];await json('/v1/events',{event:{type:'ack',id:stopCommand.id}});await stopping;
  assert.equal((await fetch(base+'/v1/material',{method:'POST',headers:{...headers,'X-Jarvis-Material-Id':randomUUID()},body:bytes})).status,403);
 }finally{await relay.close();fs.rmSync(temp,{recursive:true,force:true});}
});

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {randomUUID,createHash} from 'node:crypto';
import {createArtifactStore,portableFiles,safeFilename,FILE_LIMIT} from './artifacts.mjs';
import {deliverTask} from './task_status.mjs';
import {createVmRelay} from './vm_relay.mjs';
import {createInbound,remoteKey} from './remote.mjs';

test('/result 的文件只回传原群成员，使用新消息的路由，成功后显式取回会重发附件',async()=>{
 const ctx={chat:'群',kind:'group',route:'new-A'},owner=remoteKey('wechat-account','甲',ctx),sent=[];
 const file={id:randomUUID(),taskId:randomUUID(),name:'甲的PPT.pptx',deliveryStatus:'sent'};
 const state={projects:{p:{id:'p',remoteOwner:owner}},sessions:{s:{id:'s',projectId:'p'}},contacts:{[owner]:{id:owner,allowed:true,projectId:'p',currentConversation:'s'}},seen:[],tasks:[{id:file.taskId,remoteOwner:owner,conversationId:'s',status:'completed',deliveryStatus:'sent',result:'甲的正文',attachments:[file]}]};
 const receive=createInbound({state,save(){},createProject(name,remoteOwner){return state.projects.q={id:'q',name,remoteOwner};},send:async(c,to,value)=>sent.push({to,value})});
 await receive('wechat-account','乙','/result','B',{...ctx,route:'new-B'});assert(!sent.some(x=>x.value?.attachment));
 await receive('wechat-account','甲','/result','A',ctx);assert.equal(sent.at(-1).to,'new-A');assert.equal(sent.at(-1).value.attachment,file);assert.equal(file.deliveryStatus,'sent');
});

test('附件收集只取当前任务目录，保留各格式原字节与中文名，副本不受源文件修改影响',()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'jarvis-artifacts-'));
 try{
  const store=createArtifactStore(path.join(temp,'store')),project=path.join(temp,'project');fs.mkdirSync(project);
  const id=randomUUID(),out=store.begin(project,id);fs.writeFileSync(path.join(project,'私人文件.txt'),'不能发送');
  for(const name of ['图片.png','视频.mp4','演示.pptx','表格.xlsx','压缩.zip','未知格式.custom'])fs.writeFileSync(path.join(out,name),Buffer.from([0,255,100,0,25]));fs.mkdirSync(path.join(out,'.jarvis-input'));fs.writeFileSync(path.join(out,'.jarvis-input','原始材料.txt'),'不能回传');
  const files=store.collect(id,out);assert.equal(files.length,6);assert(!files.some(f=>f.name==='私人文件.txt'));
  for(const f of files){assert.deepEqual(fs.readFileSync(store.resolve(f)),Buffer.from([0,255,100,0,25]));assert.equal(f.taskId,id);}
  fs.writeFileSync(path.join(out,'图片.png'),'changed');assert.equal(fs.readFileSync(store.resolve(files.find(f=>f.name==='图片.png'))).length,5);
  assert.throws(()=>store.resolve({...files[0],taskId:randomUUID()}));
  fs.writeFileSync(store.resolve(files[0]),'tampered');assert.throws(()=>store.resolve(files[0]),/校验/);
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
});
test('拒绝越界、链接、过大文件、危险文件名和伪造 Base64，文本内嵌附件无需执行模型代码',()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'jarvis-artifact-guards-'));
 try{
  const store=createArtifactStore(path.join(temp,'store')),out=store.begin(temp,randomUUID());
  for(const n of ['../密码.txt','C:\\Users\\x','CON.txt','a.txt:secret','x.'])assert.throws(()=>safeFilename(n));
  assert.throws(()=>portableFiles('```workbench-files\n{"files":[{"name":"bad.png","base64":"@@@"}]}\n```',out));
  const text=portableFiles('结果\n```workbench-files\n{"files":[{"name":"说明.txt","content":"中文内容"},{"name":"二进制.bin","base64":"AP8="}]}\n```',out);
  assert.equal(text,'结果');assert.equal(fs.readFileSync(path.join(out,'说明.txt'),'utf8'),'中文内容');assert.deepEqual(fs.readFileSync(path.join(out,'二进制.bin')),Buffer.from([0,255]));
  const secret=path.join(temp,'private.txt');fs.writeFileSync(secret,'secret');fs.linkSync(secret,path.join(out,'hardlink.txt'));assert.throws(()=>store.collect(randomUUID(),out),/链接/);fs.unlinkSync(path.join(out,'hardlink.txt'));
  const huge=path.join(out,'huge.mp4');fs.writeFileSync(huge,'');fs.truncateSync(huge,FILE_LIMIT+1);assert.throws(()=>store.collect(randomUUID(),out),/100MB/);
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
});
test('附件部分失败时只重试未完成文件，不重新执行模型，不丢失已发送记录',async()=>{
 const task={result:'正文',attachments:[{id:'a',name:'a'},{id:'b',name:'b'}]},sent=[];
 await assert.rejects(deliverTask(task,async v=>{if(v.attachment?.id==='b')throw new Error('微信断线');sent.push(v);},()=>{}),/断线/);
 assert.equal(task.deliveryStatus,'failed');assert.equal(task.attachments[0].deliveryStatus,'sent');assert.equal(task.attachments[1].deliveryStatus,'failed');
 await deliverTask(task,async v=>sent.push(v),()=>{});
 assert.equal(sent.filter(v=>v.attachment?.id==='a').length,1);assert.equal(sent.filter(v=>v.attachment?.id==='b').length,1);assert.equal(task.deliveryStatus,'sent');
});
test('桥只允许当前连接器读取自己待发送的附件；确认后失效，二进制不经过 JSON',async()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'jarvis-relay-file-')),file=path.join(temp,'demo.pptx'),bytes=Buffer.alloc(200001,185);fs.writeFileSync(file,bytes);
 const token='d'.repeat(64),relay=createVmRelay({bind:'127.0.0.1',port:0,token,pollMs:20});
 const address=await relay.listen(),runId=randomUUID(),url='http://127.0.0.1:'+address.port;
 const post=(endpoint,body={},run=runId,key=token)=>fetch(url+endpoint,{method:'POST',headers:{Authorization:'Bearer '+key},body:JSON.stringify({runId:run,...body})});
 try{
  await post('/v1/events',{event:{type:'ready',account:'贾维斯'}});await assert.rejects(relay.sendFile('r',{},file),/更新|部署光盘/);
  await post('/v1/events',{event:{type:'ready',account:'贾维斯',fileProtocol:1}});
  const pending=relay.sendFile('member-A',{name:'演示.pptx',size:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')},file);
  const c=(await(await post('/v1/poll')).json()).commands[0];assert.equal(c.to,'member-A');assert.equal(c.type,'send_file');assert(!JSON.stringify(c).includes(file));
  assert.equal((await post('/v1/file',{id:c.id},randomUUID())).status,403);
  assert.equal((await post('/v1/file',{id:c.id},runId,'wrong')).status,401);
  assert.equal((await post('/v1/file',{id:randomUUID()})).status,403);
  const download=await post('/v1/file',{id:c.id});assert.equal(download.headers.get('content-type'),'application/octet-stream');assert.deepEqual(Buffer.from(await download.arrayBuffer()),bytes);
  await post('/v1/events',{event:{type:'ack',id:c.id}});await pending;
  assert.equal((await post('/v1/file',{id:c.id})).status,403);
 }finally{await relay.close();fs.rmSync(temp,{recursive:true,force:true});}
});

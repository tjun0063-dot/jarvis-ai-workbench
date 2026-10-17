import http from 'node:http';
import {createHash,randomUUID,timingSafeEqual} from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {pipeline} from 'node:stream/promises';
import {Transform} from 'node:stream';
import {FILE_LIMIT,safeFilename} from './artifacts.mjs';

export function validateEvent(e,account){
 if(!e||!['ready','health','listening','warning','error','message','ack'].includes(e.type))throw new Error('事件类型无效');
 if(e.type==='ready'&&e.account!==account)throw new Error('助手昵称不匹配');
 if(e.type==='message'&&(!e.context||!['friend','group'].includes(e.context.kind)||![e.sender,e.id,e.text,e.context.chat,e.context.route].every(x=>typeof x==='string'&&x.length>0&&x.length<=12000)))throw new Error('消息路由无效');
 return e;
}
export function createVmRelay({bind,port=8791,token,account='贾维斯',incomingDirectory,onEvent=()=>{},onDisconnect=()=>{},timeoutMs=30000,pollMs=15000}){
 if(!/^[a-f0-9]{64}$/.test(token))throw new Error('虚拟机桥密钥无效');
 if(incomingDirectory)fs.mkdirSync(incomingDirectory,{recursive:true});const incomingBase=incomingDirectory?fs.realpathSync(incomingDirectory):null;
 let peer=null,lastSeen=0,ready=false,waiting=null,closed=false,paused=false,fileProtocol=0,materialProtocol=0,controlProtocol=0,uiPaused=false,uiTransition=null;
 const pending=new Map(),queue=[],collections=new Map();
 const authorized=req=>{const supplied=String(req.headers.authorization||'');const expected='Bearer '+token;return supplied.length===expected.length&&timingSafeEqual(Buffer.from(supplied),Buffer.from(expected));};
 function disconnect(reason){ready=false;fileProtocol=0;materialProtocol=0;controlProtocol=0;uiPaused=false;uiTransition=null;for(const p of pending.values()){clearTimeout(p.timer);p.reject(new Error(reason));}pending.clear();collections.clear();queue.length=0;onDisconnect(reason);}
 function take(){return queue.splice(0).filter(c=>c.type==='shutdown'||pending.has(c.id));}
 function flush(){if(waiting&&queue.length){const done=waiting;waiting=null;done(take());}}
 async function body(req){let chunks='',size=0;for await(const part of req){size+=part.length;if(size>128*1024)throw new Error('事件过大');chunks+=part;}return JSON.parse(chunks||'{}');}
 const server=http.createServer(async(req,res)=>{
  const json=(status,data)=>{if(res.destroyed)return;res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
  if(!authorized(req))return json(401,{error:'桥接认证失败'});
  if(req.method!=='POST'||!['/v1/events','/v1/poll','/v1/file','/v1/material'].includes(req.url))return json(404,{error:'接口不存在'});
  try{
   if(req.url==='/v1/material'){
    if(!incomingBase)throw new Error('未配置接收材料目录');
    const runId=String(req.headers['x-jarvis-run-id']||''),collectionId=String(req.headers['x-jarvis-collection-id']||''),id=String(req.headers['x-jarvis-material-id']||''),sha256=String(req.headers['x-jarvis-sha256']||''),length=Number(req.headers['content-length']);
    const collection=collections.get(collectionId);
    if(paused||closed||!ready||peer!==runId||!collection||collection.expiresAt<Date.now())return json(403,{error:'材料接收授权无效或已过期'});
    if(!/^[a-f0-9-]{36}$/.test(collectionId)||!/^[a-f0-9-]{36}$/.test(id)||!/^[a-f0-9]{64}$/.test(sha256)||!Number.isSafeInteger(length)||length<0||length>FILE_LIMIT)throw new Error('材料元数据无效');
    let name;try{name=safeFilename(decodeURIComponent(String(req.headers['x-jarvis-file-name']||'')));}catch{throw new Error('材料文件名无效');}
    const dir=path.join(incomingBase,collectionId),dest=path.join(dir,id),relative=path.relative(incomingBase,dest);if(relative.startsWith('..'+path.sep)||path.isAbsolute(relative))throw new Error('材料路径无效');fs.mkdirSync(dir,{recursive:true});
    let count=0;const hash=createHash('sha256'),limiter=new Transform({transform(chunk,encoding,done){count+=chunk.length;if(count>FILE_LIMIT)return done(new Error('材料超过 100MB'));hash.update(chunk);done(null,chunk);}});
    try{await pipeline(req,limiter,fs.createWriteStream(dest,{flags:'wx'}));if(count!==length||hash.digest('hex')!==sha256)throw new Error('材料大小或校验值不一致');}
    catch(error){fs.rmSync(dest,{force:true});throw error;}
    lastSeen=Date.now();onEvent({type:'material',collectionId,file:{id,name,size:length,sha256}});return json(200,{ok:true});
   }
   const b=await body(req);
   if(typeof b.runId!=='string'||! /^[a-f0-9-]{36}$/.test(b.runId))throw new Error('运行标识无效');
   if(req.url==='/v1/file'){
    // File IDs are short-lived capabilities bound to this live connector and
    // its pending reply command. There is deliberately no arbitrary path/URL API.
    const p=pending.get(b.id);
    if(paused||closed||!ready||peer!==b.runId||!p?.file||p.expiresAt<Date.now())return json(403,{error:'附件回传授权无效或已过期'});
    const stat=fs.statSync(p.file);if(!stat.isFile()||stat.size!==p.artifact.size||stat.size>FILE_LIMIT)throw new Error('附件大小校验失败');
    lastSeen=Date.now();res.writeHead(200,{'Content-Type':'application/octet-stream','Content-Length':stat.size,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
    try{await pipeline(fs.createReadStream(p.file),res);}catch{res.destroy();}return;
   }
   if(peer&&peer!==b.runId&&Date.now()-lastSeen<35000)return json(409,{error:'已有虚拟机连接器在线'});
   if(peer!==b.runId){disconnect('虚拟机连接器已重新启动');peer=b.runId;}
   lastSeen=Date.now();
   if(req.url==='/v1/events'){
    if(paused)return json(403,{error:'主机已停止监听，请先在工作台启动虚拟机连接'});
    const e=validateEvent(b.event,account);
    if(e.type==='ack'){const p=pending.get(e.id);if(p){clearTimeout(p.timer);pending.delete(e.id);if(p.uiControl){uiTransition=null;if(!e.error)uiPaused=p.target;}e.error?p.reject(new Error(e.error)):p.resolve();onEvent({...e,relayAcknowledged:true,relayControl:!!p.control,...(p.uiControl&&!e.error?{uiPaused:p.target}:{})});}return json(200,{ok:true});}
    if(e.type==='ready'){ready=true;fileProtocol=e.fileProtocol===1?1:0;materialProtocol=e.materialProtocol===1?1:0;}
    if(e.type==='health'&&e.fileProtocol===1)fileProtocol=1;
    if(e.type==='health'&&e.materialProtocol===1)materialProtocol=1;
    if(['ready','health'].includes(e.type)&&e.controlProtocol===1){controlProtocol=1;if(typeof e.uiPaused==='boolean')uiPaused=e.uiPaused;}
    if(e.type==='error')ready=false;
    // The authenticated adapter emits scan health only after checking the
    // logged-in nickname. Restore a running guest after a host service restart.
    if(!ready&&e.type==='health'&&e.listeningMode==='isolated-vm'&&Number.isInteger(e.scans)&&(e.scans>0||(e.scans===0&&e.uiPaused===true&&e.controlProtocol===1&&e.account===account))&&Number.isInteger(e.count)&&e.count>=0&&e.count<=32&&Number.isInteger(e.groupCount)&&e.groupCount>=0&&e.groupCount<=e.count){
     ready=true;onEvent({type:'ready',account,listeningMode:e.listeningMode,replyNeedsFocus:e.replyNeedsFocus,...(typeof e.uiPaused==='boolean'?{uiPaused:e.uiPaused}:{})});
    }
    onEvent(e);return json(200,{ok:true});
   }
   if(queue.length)return json(200,{commands:take()});
   if(paused)return json(403,{error:'主机已停止监听'});
   if(waiting)return json(409,{error:'一次只允许一个轮询'});
   let timer;const finish=commands=>{clearTimeout(timer);if(waiting===finish)waiting=null;json(200,{commands});};
   waiting=finish;timer=setTimeout(()=>finish([]),pollMs);
   res.on('close',()=>{clearTimeout(timer);if(waiting===finish)waiting=null;});
  }catch(e){json(400,{error:e.message});}
 });
 const health=setInterval(()=>{if(peer&&Date.now()-lastSeen>35000&&ready)disconnect('虚拟机连接器已离线');},5000);health.unref();
 return {
  get connected(){return ready&&!closed&&Date.now()-lastSeen<=35000;},
  get pendingCount(){return pending.size;},
  get supportsFiles(){return this.connected&&fileProtocol===1;},
  get supportsMaterials(){return this.connected&&materialProtocol===1&&!!incomingBase;},
  get supportsUiControl(){return this.connected&&controlProtocol===1;},
  get uiPaused(){return uiPaused;},
  get uiTransition(){return uiTransition;},
  listen(){return new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,bind,()=>{server.off('error',reject);resolve(server.address());});});},
  send(to,text){return new Promise((resolve,reject)=>{
   if(!this.connected)return reject(new Error('虚拟机微信未连接'));
   if(uiPaused||uiTransition===true)return reject(new Error('微信窗口操作已暂停，结果已保留；恢复监听后发送 /result 取回'));
   if(pending.size>=100)return reject(new Error('虚拟机回传队列已满'));
   const id=randomUUID(),expiresAt=Date.now()+timeoutMs;
   const timer=setTimeout(()=>{pending.delete(id);reject(new Error('虚拟机发送超时，结果已保留'));},timeoutMs);
   pending.set(id,{resolve,reject,timer});queue.push({type:'send',id,to,text,expiresAt});flush();
  });},
  sendFile(to,artifact,file){return new Promise((resolve,reject)=>{
   if(uiPaused||uiTransition===true)return reject(new Error('微信窗口操作已暂停，附件已保留；恢复监听后发送 /result 取回'));
   if(!this.supportsFiles)return reject(new Error('虚拟机附件连接器尚未在线，请运行部署光盘的 Update-Attachments.cmd'));
   if(pending.size>=100)return reject(new Error('虚拟机回传队列已满'));
   try{safeFilename(artifact.name);if(!Number.isSafeInteger(artifact.size)||artifact.size<0||artifact.size>FILE_LIMIT||!/^[a-f0-9]{64}$/.test(artifact.sha256))throw new Error('附件元数据无效');}catch(e){return reject(e);}
   const id=randomUUID(),duration=Math.max(timeoutMs,180000),expiresAt=Date.now()+duration;
   const timer=setTimeout(()=>{pending.delete(id);reject(new Error('虚拟机附件发送超时，文件已保留，可用 /result 重发'));},duration);
   pending.set(id,{resolve,reject,timer,file,artifact,expiresAt});queue.push({type:'send_file',id,to,file:{name:artifact.name,size:artifact.size,sha256:artifact.sha256},expiresAt});flush();
  });},
  startCollection(to,collectionId,expiresAt){return new Promise((resolve,reject)=>{
   if(!this.supportsMaterials)return reject(new Error('请先安装支持接收材料的虚拟机组件'));
   if(!/^[a-f0-9-]{36}$/.test(collectionId)||!Number.isSafeInteger(expiresAt)||expiresAt<=Date.now()||expiresAt>Date.now()+31*60*1000)return reject(new Error('材料会话无效'));
   if(pending.size>=100)return reject(new Error('虚拟机命令队列已满'));
   const id=randomUUID(),commandExpires=Date.now()+Math.max(timeoutMs,45000);collections.set(collectionId,{to,expiresAt});
   const timer=setTimeout(()=>{pending.delete(id);collections.delete(collectionId);reject(new Error('虚拟机未确认材料收集模式'));},Math.max(timeoutMs,45000));
   pending.set(id,{resolve,reject:(error)=>{collections.delete(collectionId);reject(error);},timer,control:true});queue.push({type:'collect_start',id,to,collectionId,collectionExpiresAt:expiresAt,expiresAt:commandExpires});flush();
  });},
  stopCollection(to,collectionId){return new Promise((resolve,reject)=>{
   collections.delete(collectionId);if(!this.connected)return resolve();
   const id=randomUUID(),expiresAt=Date.now()+Math.max(timeoutMs,45000),timer=setTimeout(()=>{pending.delete(id);reject(new Error('虚拟机未确认结束材料收集'));},Math.max(timeoutMs,45000));
   pending.set(id,{resolve,reject,timer,control:true});queue.push({type:'collect_stop',id,to,collectionId,expiresAt});flush();
  });},
  setUiPaused(value){return new Promise((resolve,reject)=>{
   if(typeof value!=='boolean')return reject(new Error('暂停状态无效'));
   if(!this.supportsUiControl)return reject(new Error('请先安装支持窗口暂停的虚拟机组件'));
   if(uiTransition!==null)return reject(new Error('窗口操作状态正在切换，请稍候'));
   if(pending.size)return reject(new Error('有回复正在发送，请等待发送完成后再切换'));
   if(value===uiPaused)return resolve();
   const id=randomUUID(),duration=Math.max(timeoutMs,45000),expiresAt=Date.now()+duration;uiTransition=value;
   const timer=setTimeout(()=>{pending.delete(id);uiTransition=null;reject(new Error('未收到窗口暂停状态确认，请检查连接器日志'));},duration);
    pending.set(id,{resolve,reject,timer,control:true,uiControl:true,target:value});queue.push({type:'ui_pause',id,paused:value,expiresAt});flush();
  });},
  resume(){paused=false;},
  stop(){paused=true;queue.length=0;disconnect('虚拟机监听已停止');queue.push({type:'shutdown'});flush();},
  async close(){closed=true;clearInterval(health);disconnect('桥接服务已关闭');if(waiting){waiting([]);waiting=null;}server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
 };
}

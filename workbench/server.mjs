import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID,randomBytes,createHash} from 'node:crypto';
import os from 'node:os';
import {spawn,spawnSync} from 'node:child_process';
import {parseCommand,validateEngine,allowedHost} from './core.mjs';
import {migrateLibrary,scanNative,loadNative,parseImport} from './library.mjs';
import {createInbound} from './remote.mjs';
import {TaskPool} from './task_pool.mjs';
import {createVmRelay} from './vm_relay.mjs';
import {updateCodexProgress,deliverTask} from './task_status.mjs';
import {codexEnvironment} from './codex_network.mjs';
import {personalMuseRequest,museThreadId} from './personal_muse.mjs';
import {assistantHealth} from './assistant_health.mjs';
import {createArtifactStore,artifactPrompt,portableFiles,FILE_LIMIT,FILE_COUNT} from './artifacts.mjs';
import {requestDeepSeek} from './deepseek.mjs';
import {createMaterialStore,materialPrompt} from './materials.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)), port=Number(process.env.PORT||8790);
const compatibleDirectory=path.resolve(root,'../wechat-assistant-4.1.8.107');
let compatibleHashCache={fingerprint:null,valid:false};
function compatibleClient(){
 const base={directory:compatibleDirectory,repairable:fs.existsSync(path.join(compatibleDirectory,'WeChatWin_4.1.8.107.exe'))};
 try{
  const m=JSON.parse(fs.readFileSync(path.join(compatibleDirectory,'preparation.json'),'utf8').replace(/^\uFEFF/,''));
  const files=m.launchFiles.map(f=>({expected:f.sha256,file:path.join(compatibleDirectory,'client',f.path)}));
  const fingerprint=JSON.stringify(files.map(f=>{const x=fs.statSync(f.file);return [f.file,x.size,x.mtimeMs,f.expected];}));
  if(fingerprint!==compatibleHashCache.fingerprint)compatibleHashCache={fingerprint,valid:files.every(f=>createHash('sha256').update(fs.readFileSync(f.file)).digest('hex').toLowerCase()===f.expected.toLowerCase())};
  const ready=m.ready===true&&compatibleHashCache.valid;
  return {...base,ready,version:m.version,executable:path.join(compatibleDirectory,'client','Weixin.exe'),reason:ready?'':'客户端被更新或文件变化，请先恢复兼容版'};
 }catch{return {...base,ready:false,reason:'兼容客户端文件缺失，请先恢复兼容版'};}
}
let clientRepairing=false;
function restoreCompatibleClient(){
 if(clientRepairing)throw new Error('兼容版正在恢复，请稍候');clientRepairing=true;
 return new Promise((resolve,reject)=>{
  const shell=path.join(os.homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','native','powershell','pwsh.exe');
  const child=spawn(shell,['-NoProfile','-File',path.join(compatibleDirectory,'Restore-Assistant.ps1')],{windowsHide:true});let output='',error='';
  child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');child.stdout.on('data',x=>output=(output+x).slice(-2000));child.stderr.on('data',x=>error=(error+x).slice(-2000));
  child.on('error',reject);child.on('close',code=>{compatibleHashCache.fingerprint=null;code===0?resolve({ok:true,message:output.trim()}):reject(new Error(error.trim()||'恢复兼容客户端失败'));});
 }).finally(()=>{clientRepairing=false;});
}
function openCompatibleClient(){if(!compatibleClient().ready)throw new Error(compatibleClient().reason||'兼容客户端尚未准备完成');return new Promise((resolve,reject)=>{const bundled=path.join(os.homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','native','powershell','pwsh.exe'),shell=fs.existsSync(bundled)?bundled:'pwsh.exe';const child=spawn(shell,['-NoProfile','-File',path.join(compatibleDirectory,'Launch-Assistant.ps1')],{windowsHide:true});let output='',error='';child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');child.stdout.on('data',x=>output=(output+x).slice(-2000));child.stderr.on('data',x=>error=(error+x).slice(-2000));child.on('error',reject);child.on('close',code=>code===0?resolve({ok:true,message:output.trim()}):reject(new Error(error.trim()||'兼容客户端启动失败')));});}
const data=process.env.WORKBENCH_DATA_DIR||path.join(root,'data'),projectBase=process.env.WORKBENCH_PROJECT_DIR||path.join(root,'projects'),workspace=path.join(projectBase,'default');
fs.mkdirSync(data,{recursive:true});fs.mkdirSync(workspace,{recursive:true});
const artifacts=createArtifactStore(path.join(data,'attachments'));
const stateFile=path.join(data,'state.json');
let state=fs.existsSync(stateFile)?JSON.parse(fs.readFileSync(stateFile,'utf8')):{sessions:{},tasks:[],contacts:{},seen:[]};
migrateLibrary(state,workspace);
let native=scanNative();
for(const t of state.tasks) {if(t.status==='completed')delete t.progressError;if(t.deliveryError)t.deliveryStatus='failed';else if(t.deliveryStatus==='sending'){t.deliveryStatus='failed';t.deliveryError='服务重启导致回传中断，可用 /result 取回';}}
for(const t of state.tasks)for(const f of t.attachments||[])if(f.deliveryStatus==='sending'){f.deliveryStatus='failed';f.deliveryError='服务重启中断附件发送，请用 /result 重发';}
for(const t of state.tasks) if(['running','queued'].includes(t.status)){t.status='interrupted';t.error='服务重启，任务已中断，请重新提交';}
const save=()=>{fs.writeFileSync(stateFile+'.tmp',JSON.stringify(state));fs.renameSync(stateFile+'.tmp',stateFile);};
save();
const materials=createMaterialStore(path.join(data,'incoming-materials'),state,save);materials.sweep();
const cookie=randomBytes(32).toString('hex'), active=new Map();
const remotePool=new TaskPool(4,32);
let metaKey=process.env.MODEL_API_KEY||'', metaModel='muse-spark-1.3';
let gptKey=process.env.OPENAI_API_KEY||'',gptModel='gpt-6-astra';
let deepseekKey=process.env.DEEPSEEK_API_KEY||'',deepseekModel='deepseek-flash';
const engineModeFile=path.join(data,'engine-modes.json');
let engineModes={gpt:'chatgpt',muse:'web',...(fs.existsSync(engineModeFile)?JSON.parse(fs.readFileSync(engineModeFile,'utf8').replace(/^\uFEFF/,'')):{} )};
// Muse personal agent is distinct from Muse Code and the Meta model API.
if(engineModes.muse==='account')engineModes.muse='web';
const saveEngineModes=()=>fs.writeFileSync(engineModeFile,JSON.stringify(engineModes));
let personalMuseVerified=false,personalMuseLibrary={sessions:[],goals:[]};
const personalMuseCookies=path.join(data,'muse-personal','cookies.txt');
function museRequest(request,run){return personalMuseRequest({python:path.join(root,'.muse-venv','Scripts','python.exe'),script:path.join(root,'personal_muse.py'),env:codexEnvironment(path.join(data,'codex-network.json')),request,run});}
function createConversation(projectId,engine,title,history=[]){validateEngine(engine);if(!state.projects[projectId])throw new Error('项目不存在');const id=randomUUID();state.sessions[id]={id,projectId,engine,title:title||'新 '+engine.toUpperCase()+' 会话',history,thread:null,updated:new Date().toISOString()};save();return state.sessions[id];}
function createProject(name,remoteOwner){const id=randomUUID(),directory=path.join(projectBase,id);fs.mkdirSync(directory,{recursive:true});const p=state.projects[id]={id,name,directory,...(remoteOwner?{remoteOwner}:{})};save();return p;}
function contextMessages(s,prompt){let budget=60000;const out=[];for(const m of [...s.history].reverse()){if(budget<=0)break;const content=m.content.slice(-budget);out.unshift({role:m.role,content});budget-=content.length;}return [...out,{role:'user',content:prompt}];}
let auth={ok:false,label:'未登录'};
function checkAuth(){const r=spawnSync('codex',['login','status'],{encoding:'utf8',windowsHide:true,timeout:10000});auth={ok:r.status===0,label:r.status===0?'已登录':'未登录'};}
checkAuth();
const channels={wechat:{status:'未连接',qr:null,error:''},whatsapp:{status:'未连接',qr:null,error:''}};
channels['wechat-account']={status:'未启动',qr:null,error:''};
let assistantProcess=null,assistantConfig=fs.existsSync(path.join(data,'assistant.json'))?JSON.parse(fs.readFileSync(path.join(data,'assistant.json'),'utf8')):{account:'贾维斯',mode:'friends-and-mentions'};
const assistantPending=new Map();
let vmRelay=null;
function assistantSend(to,text){if(assistantConfig.transport==='vm')return vmRelay?vmRelay.send(to,text):Promise.reject(new Error('虚拟机桥尚未配置'));return new Promise((resolve,reject)=>{if(!assistantProcess||channels['wechat-account'].status!=='已连接')return reject(new Error('助手微信号未连接'));const id=randomUUID(),timer=setTimeout(()=>{assistantPending.delete(id);reject(new Error('助手号发送超时'));},30000);assistantPending.set(id,{resolve,reject,timer});assistantProcess.stdin.write(JSON.stringify({type:'send',id,to,text})+'\n');});}
function startAssistant(config){if(config.transport==='vm'||assistantConfig.transport==='vm'){if(!vmRelay)throw new Error('请先完成虚拟机桥接部署');if(config.account&&config.account!==assistantConfig.account)throw new Error('请使用部署包中的助手昵称');vmRelay.resume();assistantConfig={account:String(config.account||assistantConfig.account||'贾维斯'),mode:'friends-and-mentions',transport:'vm'};fs.writeFileSync(path.join(data,'assistant.json'),JSON.stringify(assistantConfig));channels['wechat-account']={status:'等待虚拟机连接',error:'',qr:null};return;}if(assistantProcess)throw new Error('请先停止当前助手号连接');const account=String(config.account||'贾维斯').trim();if(!account||account.length>100)throw new Error('请输入助手号昵称');const python=path.join(root,'.wechat-venv','Scripts','python.exe');if(!fs.existsSync(python))throw new Error('微信连接器的隔离 Python 环境尚未安装');const client=compatibleClient();if(!client.ready)throw new Error(client.reason);assistantConfig={account,mode:'friends-and-mentions',...(client.ready?{clientPath:client.executable}:{})};fs.writeFileSync(path.join(data,'assistant.json'),JSON.stringify(assistantConfig));channels['wechat-account']={status:'正在核对助手号',error:'',qr:null};
 const child=spawn(python,['-u',path.join(root,'wechat_assistant.py')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8',PYTHONUTF8:'1'}});assistantProcess=child;const startupTimer=setTimeout(()=>{if(channels['wechat-account'].status==='正在核对助手号'){channels['wechat-account'].status='连接失败';channels['wechat-account'].error='微信窗口连接超时，请打开助手号主窗口检查客户端版本';child.kill();}},30000);const listenChats=[...new Map(Object.values(state.contacts).filter(c=>c.channel==='wechat-account'&&c.allowed&&c.chat&&['friend','group'].includes(c.kind)).map(c=>[JSON.stringify([c.chat,c.kind]),{chat:c.chat,kind:c.kind}])).values()].slice(0,32);child.stdin.write(JSON.stringify({...assistantConfig,listenChats})+'\n');let buffer='';
 child.stdout.setEncoding('utf8');child.stderr.on('data',()=>{});child.stdout.on('data',data=>{buffer+=data;let i;while((i=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,i);buffer=buffer.slice(i+1);let e;try{e=JSON.parse(line);}catch{continue;}handleAssistantEvent(e,startupTimer);}});
 child.on('error',e=>{channels['wechat-account'].error=e.message;channels['wechat-account'].status='连接失败';});child.on('close',()=>{clearTimeout(startupTimer);assistantProcess=null;if(channels['wechat-account'].status!=='连接失败')channels['wechat-account']={status:'未启动',qr:null,error:'',listening:0,groups:0,listenerError:''};for(const p of assistantPending.values()){clearTimeout(p.timer);p.reject(new Error('助手号连接已停止'));}assistantPending.clear();});
}
function handleAssistantEvent(e,startupTimer){const channel=channels['wechat-account'];if(e.type==='material'){let draft;try{draft=materials.addFile(e.collectionId,e.file);channel.received=(channel.received||0)+1;channel.lastReceived=new Date().toISOString();vmRelay?.send(draft.context.route,`已收集文件：${e.file.name}（当前 ${draft.files.length} 个）。还可继续发送，完成后发送 /开始。`).catch(error=>{channel.error=error.message;});}catch(error){try{fs.rmSync(materials.location(e.collectionId,e.file?.id),{force:true});}catch{}const active=Object.values(state.materialDrafts||{}).find(d=>d.id===e.collectionId);if(active)vmRelay?.send(active.context.route,'材料接收失败：'+error.message).catch(()=>{});}return;}if(typeof e.uiPaused==='boolean')channel.uiPaused=e.uiPaused;if(e.type==='ready'&&channel.status!=='正在停止'){clearTimeout(startupTimer);channel.status='已连接';channel.connectedAt=new Date().toISOString();channel.error='';channel.listeningMode=e.listeningMode;channel.replyNeedsFocus=e.replyNeedsFocus;}if(e.type==='listening'){channel.listening=e.count;channel.groups=e.groupCount;}if(e.type==='health'){channel.lastHeartbeat=new Date().toISOString();if(!e.uiPaused)channel.lastScan=channel.lastHeartbeat;channel.listening=e.count;channel.groups=e.groupCount;channel.retrying=e.retrying;channel.waitingWindows=e.waitingWindows;channel.listeningMode=e.listeningMode;channel.replyNeedsFocus=e.replyNeedsFocus;if(!e.retrying&&!e.waitingWindows)channel.listenerError='';}if(e.type==='warning')channel.listenerError=e.message;if(e.type==='error'){channel.status='连接失败';channel.error=e.message;}if(e.type==='ack'){if(e.relayAcknowledged&&!e.error&&!e.relayControl){channel.sent=(channel.sent||0)+1;channel.lastSent=new Date().toISOString();}const pending=assistantPending.get(e.id);if(pending){clearTimeout(pending.timer);assistantPending.delete(e.id);if(e.error)pending.reject(new Error(e.error));else{channel.sent=(channel.sent||0)+1;channel.lastSent=new Date().toISOString();pending.resolve();}}}if(e.type==='message'&&channel.status==='已连接'){channel.received=(channel.received||0)+1;if(e.context?.kind==='group')channel.groupReceived=(channel.groupReceived||0)+1;channel.lastReceived=new Date().toISOString();inbound('wechat-account',e.sender,e.text,e.id,e.context).catch(error=>{channel.error=error.message;});}}
const vmConfigFile=path.join(data,'vm-relay.json');
if(fs.existsSync(vmConfigFile)){
 try{
  const cfg=JSON.parse(fs.readFileSync(vmConfigFile,'utf8').replace(/^\uFEFF/,''));
  if(cfg.enabled){
   const dedicated=Object.entries(os.networkInterfaces()).some(([name,addresses])=>name.startsWith('vEthernet (')&&addresses.some(a=>a.address===cfg.bind&&!a.internal));
   if(!dedicated)throw new Error('虚拟机桥只能绑定当前 Hyper-V 虚拟网络地址');
   if(assistantProcess)throw new Error('请先停止主桌面监听');
   assistantConfig={...assistantConfig,transport:'vm'};
   fs.writeFileSync(path.join(data,'assistant.json'),JSON.stringify(assistantConfig));
   vmRelay=createVmRelay({bind:cfg.bind,port:8791,token:cfg.token,account:assistantConfig.account,incomingDirectory:path.join(data,'incoming-materials'),
    onEvent:e=>handleAssistantEvent(e),onDisconnect:reason=>{channels['wechat-account']={status:'虚拟机未连接',error:reason,qr:null};}});
   vmRelay.listen().then(()=>{channels['wechat-account']={status:'等待虚拟机连接',error:'',qr:null};}).catch(e=>{channels['wechat-account']={status:'桥接启动失败',error:e.message,qr:null};vmRelay=null;});
  }
 }catch(e){channels['wechat-account']={status:'桥接配置无效',error:e.message,qr:null};}
}
let wxAccount=fs.existsSync(path.join(data,'wechat.json'))?JSON.parse(fs.readFileSync(path.join(data,'wechat.json'),'utf8')):null;
let wxPolling=false,wxLogin=false,wa=null;
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function fetchJSON(url,options={}) {const r=await fetch(url,{signal:AbortSignal.timeout(40000),...options});if(!r.ok) throw new Error('服务请求失败 HTTP '+r.status);const j=await r.json();if(j.ret) throw new Error('微信接口错误 '+j.ret);return j;}
function wechatBase(value){const u=new URL(value.startsWith('https://')?value:'https://'+value);if(u.protocol!=='https:' || !u.hostname.endsWith('.weixin.qq.com')) throw new Error('微信返回了不受支持的服务地址');return u.origin;}
async function wxPost(endpoint,body){return fetchJSON(wxAccount.base+'/ilink/bot/'+endpoint,{method:'POST',headers:{'Content-Type':'application/json',AuthorizationType:'ilink_bot_token',Authorization:'Bearer '+wxAccount.token},body:JSON.stringify({...body,base_info:{channel_version:'0.1.0'}})});}
async function send(channel,to,text,context){
  if(text&&typeof text==='object'&&text.attachment){
    const file=text.attachment,local=artifacts.resolve(file);
    if(channel==='wechat-account'){
      if(assistantConfig.transport!=='vm')throw new Error('请更新虚拟机附件连接器后发送文件');
      if(!vmRelay)throw new Error('虚拟机微信未连接');
      return vmRelay.sendFile(to,file,local);
    }
    if(channel==='whatsapp'){if(!wa)throw new Error('WhatsApp 未连接');return wa.sendMessage(to,{document:{url:local},fileName:file.name,mimetype:'application/octet-stream'});}
    throw new Error('当前 iLink 入口未接入文件发送，请通过贾维斯个人微信号接收，或在本机工作台下载附件');
  }
  text=String(text||'');
  for(let i=0;i<text.length;i+=3000){const part=text.slice(i,i+3000);if(channel==='wechat-account')await assistantSend(to,part);else if(channel==='wechat') await wxPost('sendmessage',{msg:{from_user_id:'',to_user_id:to,client_id:randomUUID(),message_type:2,message_state:2,context_token:context,item_list:[{type:1,text_item:{text:part}}]}});else await wa.sendMessage(to,{text:part});}
}
function session(id,engine='codex'){return state.sessions[id]??=( {id,engine,history:[],thread:null});}
function stop(id){const run=active.get(id);if(run){run.cancelled=true;if(run.ticket?.cancel())return true;run.abort?.abort();run.process?.kill();if(run.process&&process.platform==='win32')spawn('taskkill',['/PID',String(run.process.pid),'/T','/F'],{windowsHide:true});}return !!run;}
function runCodex(s,prompt,run){return new Promise((resolve,reject)=>{
  const cwd=s.engine==='gpt'?run.artifactDir:state.projects[s.projectId||'default'].directory;
  const args=['exec','-s','workspace-write','-C',cwd,'-c','approval_policy="never"','--json','--skip-git-repo-check'];
  if(s.thread)args.push('resume',s.thread,'-');else {args.push('-');if(s.history.length)prompt='以下是此前会话记录，作为继续任务的参考资料：\n'+JSON.stringify(contextMessages(s,'').slice(0,-1))+'\n当前任务：\n'+prompt;}
  const child=spawn('codex',args,{cwd,windowsHide:true,env:codexEnvironment(path.join(data,'codex-network.json'))});run.process=child;
  let buffer='',answer='',err='',failed=false;
  child.stdin.end(prompt);child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');
  child.stderr.on('data',x=>{err=(err+x).slice(-3000);});
  child.stdout.on('data',x=>{buffer+=x;let i;while((i=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,i);buffer=buffer.slice(i+1);try{const e=JSON.parse(line);if(e.type==='thread.started')s.thread=e.thread_id;if(e.type==='item.completed'&&e.item?.type==='agent_message')answer+=e.item.text+'\n';if(e.type==='turn.failed'){failed=true;err=e.error?.message||e.message||'Codex 执行失败';}if(e.type==='error'){err=e.message||e.error?.message||'Codex 请求重试中';}updateCodexProgress(run.task,e);save();}catch{}}});
  child.on('error',reject);child.on('close',code=>code===0&&!failed?resolve(answer.trim()||'任务完成，无文本输出'):reject(new Error(err||'Codex 进程退出 '+code)));
});}
async function runMuse(s,prompt,run){
 if(engineModes.muse==='web'){
  if(!s.personalMuseThread){const created=await museRequest({command:'create',title:s.title||'工作台会话'},run);s.personalMuseThread=museThreadId(created);save();if(s.history.length)prompt='以下是工作台保存的此前会话资料：\n'+JSON.stringify(contextMessages(s,'').slice(0,-1))+'\n当前请求：\n'+prompt;}
  if(run.cancelled)throw new Error('任务已停止');
  const result=await museRequest({command:'send',thread:s.personalMuseThread,prompt,artifactDir:run.artifactDir,taskId:run.task.id},run);personalMuseVerified=true;return result.text;
 }
 if(!metaKey)throw new Error('请在连接设置中配置 Meta Model API 密钥');const r=await fetch('https://api.meta.ai/v1/chat/completions',{method:'POST',signal:run.abort.signal,headers:{Authorization:'Bearer '+metaKey,'Content-Type':'application/json'},body:JSON.stringify({model:metaModel,messages:contextMessages(s,prompt)})});if(!r.ok)throw new Error('Meta API 返回 HTTP '+r.status+'，请检查密钥、模型权限和额度');const j=await r.json();const answer=j.choices?.[0]?.message?.content;if(!answer)throw new Error('Meta API 未返回文本');return answer;
}
async function runGPT(s,prompt,run){if(engineModes.gpt==='chatgpt')return runCodex(s,prompt,run);const r=await fetch('https://api.openai.com/v1/responses',{method:'POST',signal:run.abort.signal,headers:{Authorization:'Bearer '+gptKey,'Content-Type':'application/json'},body:JSON.stringify({model:gptModel,store:false,input:contextMessages(s,prompt)})});if(!r.ok)throw new Error('GPT API 返回 HTTP '+r.status+'，请检查密钥和模型权限');const j=await r.json();const answer=(j.output||[]).filter(x=>x.type==='message').flatMap(x=>x.content||[]).filter(x=>x.type==='output_text').map(x=>x.text).join('\n');if(!answer)throw new Error('GPT 未返回文本');return answer;}
async function runDeepSeek(s,prompt,run){return requestDeepSeek({key:deepseekKey,model:deepseekModel,messages:contextMessages(s,prompt),signal:run.abort.signal});}
function enqueue(id,engine,prompt,source='web',reply=null,conversationId=null,materialDraft=null){validateEngine(engine);const sid=conversationId||id+':'+engine,s=session(sid,engine);if(conversationId&&s.engine!==engine)throw new Error('会话工具不匹配');s.projectId??='default';s.title??=prompt.slice(0,50);const runId=conversationId||id;if(active.has(runId))throw new Error('当前会话正在执行，请等待或使用 /stop');if(engine==='codex'&&!auth.ok)throw new Error('Codex CLI 尚未登录：在终端运行 codex login 后点击刷新登录状态');if(engine==='muse'&&engineModes.muse==='web'&&!fs.existsSync(personalMuseCookies))throw new Error('muse.ai 登录尚未连接到工作台，请先在主机完成一次性会话授权。');if(engine==='muse'&&engineModes.muse!=='web'&&!metaKey)throw new Error('请先配置 Meta 模型 API 密钥；此模式不控制 muse.ai 个人智能体');if(engine==='gpt'&&(engineModes.gpt==='chatgpt'?!auth.ok:!gptKey))throw new Error(engineModes.gpt==='chatgpt'?'请先通过 codex login 登录 ChatGPT 账号':'请先配置 OpenAI API 密钥');if(engine==='deepseek'&&!deepseekKey)throw new Error('请先在本机工作台配置 DeepSeek API 密钥');if(materialDraft?.files?.length&&!(engine==='codex'||engine==='gpt'&&engineModes.gpt==='chatgpt'))throw new Error('当前 '+engine+' 模式不能读取本机文件材料；请发送 /agent codex 或切换到 ChatGPT 账号模式后重新收集。分段文字材料不受影响。');
  const pooled=source==='wechat-account';if(pooled&&remotePool.full)throw new Error('等待队列已满，请稍后重试');
   const task={id:randomUUID(),session:runId,conversationId:sid,projectId:s.projectId,engine,prompt,source,status:'queued',created:new Date().toISOString(),result:'',error:''};const run={task,abort:new AbortController(),cancelled:false};run.artifactDir=artifacts.begin(state.projects[s.projectId].directory,task.id);run.materialFiles=materialDraft?materials.stage(materialDraft,run.artifactDir):[];state.tasks.push(task);active.set(runId,run);save();
  const deliver=async()=>{s.updated=new Date().toISOString();active.delete(runId);save();if(reply)try{await deliverTask(task,reply,save);}catch{if(task.attachments?.length)try{await reply('附件发送未完成：'+task.deliveryError+'。文件已保留，可用 /result 重试，也可在本机工作台下载。');}catch{}}};
  const execute=async()=>{task.status='running';task.started=new Date().toISOString();save();const deadline=setTimeout(()=>stop(runId),15*60*1000);try{
    const remoteMuse=engine==='muse'&&engineModes.muse==='web';
    const modelPrompt=materialPrompt(prompt,run.materialFiles)+artifactPrompt(remoteMuse?'.jarvis-outbox/'+task.id:run.artifactDir,{remote:remoteMuse});
    const raw=engine==='codex'?await runCodex(s,modelPrompt,run):engine==='gpt'?await runGPT(s,modelPrompt,run):engine==='deepseek'?await runDeepSeek(s,modelPrompt,run):await runMuse(s,modelPrompt,run);
    if(run.cancelled)throw new Error('任务已停止');
    const answer=portableFiles(raw,run.artifactDir);task.attachments=artifacts.collect(task.id,run.artifactDir);
    task.result=answer||(task.attachments.length?'文件已生成，见附件。':'任务完成');task.status='completed';delete task.progressError;
    s.history.push({role:'user',content:prompt},{role:'assistant',content:task.result,attachments:task.attachments});
  }catch(e){task.status=run.cancelled?'interrupted':'failed';task.error=e.message;}finally{clearTimeout(deadline);}void deliver();};
  if(pooled)run.ticket=remotePool.submit(execute,async()=>{task.status='interrupted';task.error='排队任务已取消';await deliver();});else void execute();return task;
}
const inbound=createInbound({state,save,createProject,createConversation,enqueue,send,stop,materials,startCollection:(...args)=>vmRelay?vmRelay.startCollection(...args):Promise.reject(new Error('虚拟机微信未连接')),stopCollection:(...args)=>vmRelay?vmRelay.stopCollection(...args):Promise.resolve()});
async function pollWx(){if(wxPolling||!wxAccount)return;wxPolling=true;channels.wechat.status='已连接';let cursor=wxAccount.cursor||'';
  while(wxAccount){try{const r=await wxPost('getupdates',{get_updates_buf:cursor});channels.wechat.error='';for(const m of r.msgs||[]){const text=(m.item_list||[]).map(i=>i.text_item?.text||i.voice_item?.text||'').filter(Boolean).join('\n');if(m.from_user_id&&m.message_type!==2)await inbound('wechat',m.from_user_id,text||'/help',String(m.message_id||m.client_id||''),m.context_token);}
  cursor=r.get_updates_buf||cursor;wxAccount.cursor=cursor;fs.writeFileSync(path.join(data,'wechat.json'),JSON.stringify(wxAccount));await wait(300);}catch(e){channels.wechat.error=e.message;await wait(5000);}}wxPolling=false;
}
async function connectWechat(){if(wxLogin)throw new Error('微信扫码正在进行');wxLogin=true;channels.wechat={status:'获取二维码',qr:null,error:''};
  try{const QR=(await import('qrcode')).default;let base='https://ilinkai.weixin.qq.com';const r=await fetchJSON(base+'/ilink/bot/get_bot_qrcode?bot_type=3',{headers:{'iLink-App-ClientVersion':'1'}});if(!r.qrcode)throw new Error('未获取到微信二维码');channels.wechat.qr=await QR.toDataURL(r.qrcode_img_content||r.qrcode_url||r.qrcode);channels.wechat.status='等待扫码';
  (async()=>{try{const deadline=Date.now()+480000;while(Date.now()<deadline){const s=await fetchJSON(base+'/ilink/bot/get_qrcode_status?qrcode='+encodeURIComponent(r.qrcode),{headers:{'iLink-App-ClientVersion':'1'}});if(s.redirect_host)base=wechatBase(s.redirect_host);if(['confirmed','connected'].includes(s.status)||s.connected){if(!s.bot_token)throw new Error('登录未返回凭据');wxAccount={token:s.bot_token,base:wechatBase(s.baseurl||s.base_url||base)};fs.writeFileSync(path.join(data,'wechat.json'),JSON.stringify(wxAccount));channels.wechat.qr=null;pollWx();return;}if(s.status==='expired')break;channels.wechat.status=s.status==='scaned'?'已扫码，请在手机确认':'等待扫码';await wait(2000);}throw new Error('二维码已过期，请重新连接');}catch(e){channels.wechat.status='连接失败';channels.wechat.error=e.message;}finally{wxLogin=false;}})();
  }catch(e){wxLogin=false;channels.wechat.status='连接失败';channels.wechat.error=e.message;throw e;}
}
async function connectWhatsApp(){if(wa)throw new Error('WhatsApp 已启动，请等待连接或重启工作台');channels.whatsapp.status='连接中';try{
  const B=await import('@whiskeysockets/baileys'),QR=(await import('qrcode')).default,pino=(await import('pino')).default;
  const {state:creds,saveCreds}=await B.useMultiFileAuthState(path.join(data,'whatsapp'));let version;try{version=(await B.fetchLatestBaileysVersion()).version;}catch{}const sock=B.default({auth:creds,version,logger:pino({level:'silent'}),printQRInTerminal:false,connectTimeoutMs:30000});wa=sock;
  sock.ev.on('creds.update',saveCreds);sock.ev.on('connection.update',async u=>{if(u.qr){channels.whatsapp.qr=await QR.toDataURL(u.qr);channels.whatsapp.status='等待扫码';}if(u.connection==='open'){channels.whatsapp.status='已连接';channels.whatsapp.qr=null;}if(u.connection==='close'){wa=null;channels.whatsapp.status='连接断开';channels.whatsapp.error='连接失败（'+(u.lastDisconnect?.error?.output?.statusCode||'未知')+'）：'+(u.lastDisconnect?.error?.message||'请检查网络后重新连接');}});
  sock.ev.on('messages.upsert',async({messages,type})=>{if(type!=='notify')return;for(const m of messages){const to=m.key.remoteJid;if(m.key.fromMe||!to||to.endsWith('@g.us')||to==='status@broadcast')continue;const text=m.message?.conversation||m.message?.extendedTextMessage?.text;if(text)try{await inbound('whatsapp',to,text,m.key.id);}catch(e){channels.whatsapp.error=e.message;}}});
  }catch(e){wa=null;channels.whatsapp.status='连接失败';channels.whatsapp.error=e.message;throw e;}}
function publicState(){return {auth,workspace,assistant:assistantConfig,vmRelay:{configured:!!vmRelay,connected:!!vmRelay?.connected,supportsFiles:!!vmRelay?.supportsFiles,supportsMaterials:!!vmRelay?.supportsMaterials,supportsUiControl:!!vmRelay?.supportsUiControl,uiPaused:!!vmRelay?.uiPaused,uiTransition:vmRelay?.uiTransition??null},attachmentLimits:{perFile:FILE_LIMIT,count:FILE_COUNT},compatibleClient:compatibleClient(),personalMuseLibrary,meta:{configured:engineModes.muse==='web'?personalMuseVerified:!!metaKey,savedLogin:fs.existsSync(personalMuseCookies),mode:engineModes.muse,model:engineModes.muse==='web'?'muse.ai 个人智能体':metaModel,url:'https://muse.ai/'},gpt:{configured:engineModes.gpt==='chatgpt'?auth.ok:!!gptKey,model:engineModes.gpt==='chatgpt'?'账号默认模型':gptModel,mode:engineModes.gpt},deepseek:{configured:!!deepseekKey,model:deepseekModel,url:'https://platform.deepseek.com/'},projects:Object.values(state.projects),conversations:Object.values(state.sessions).map(({history,...s})=>({...s,messageCount:history.length})),native,channels,execution:{limit:remotePool.limit,running:remotePool.running,queued:remotePool.waiting.length,maxWaiting:remotePool.maxWaiting,pendingReplies:assistantPending.size+(vmRelay?.pendingCount||0)},assistantHealth:assistantHealth(channels['wechat-account']),contacts:Object.values(state.contacts),tasks:state.tasks.slice(-300).reverse()};}
async function body(req){let s='';for await(const x of req){s+=x;if(s.length>5*1024*1024)throw new Error('请求超过 5MB');}return JSON.parse(s||'{}');}
const server=http.createServer(async(req,res)=>{const json=(status,obj)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(obj));};
  try{if(!allowedHost(req.headers.host,port))return json(403,{error:'不允许的主机'});
  res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'");
  if(req.method==='GET'&&['/','/app.js'].includes(req.url)){if(req.url==='/')res.setHeader('Set-Cookie',`wb=${cookie}; HttpOnly; SameSite=Strict; Path=/`);res.setHeader('Content-Type',req.url==='/'?'text/html; charset=utf-8':'text/javascript; charset=utf-8');return res.end(fs.readFileSync(path.join(root,req.url==='/'?'index.html':'app.js')));}
  if(!req.headers.cookie?.split(';').some(x=>x.trim()==='wb='+cookie))return json(401,{error:'请先打开本机工作台页面'});
  if(req.method==='GET'&&req.url==='/api/state')return json(200,publicState());
  if(req.method==='GET'&&req.url?.startsWith('/api/attachments/')){
    const match=req.url.match(/^\/api\/attachments\/([a-f0-9-]{36})\/([a-f0-9-]{36})$/);
    const task=match&&state.tasks.find(t=>t.id===match[1]),file=task?.attachments?.find(f=>f.id===match[2]&&f.taskId===task.id);
    if(!file)return json(404,{error:'附件不存在'});
    const local=artifacts.resolve(file);res.writeHead(200,{'Content-Type':'application/octet-stream','Content-Length':file.size,'Content-Disposition':"attachment; filename*=UTF-8''"+encodeURIComponent(file.name),'Cache-Control':'no-store'});
    const stream=fs.createReadStream(local);stream.on('error',()=>res.destroy());res.on('close',()=>stream.destroy());return stream.pipe(res);
  }
  if(req.method!=='POST')return json(404,{error:'未找到接口'});
  if(!['http://127.0.0.1:'+port,'http://localhost:'+port].includes(req.headers.origin)||!req.headers['content-type']?.startsWith('application/json'))return json(403,{error:'请求来源不允许'});
  const b=await body(req);
  if(req.url==='/api/assistant/client/restore')return json(200,await restoreCompatibleClient());
  if(req.url==='/api/assistant/client/open')return json(200,await openCompatibleClient());
  if(req.url==='/api/assistant/start'){startAssistant(b);return json(200,{ok:true});}
  if(req.url==='/api/assistant/pause'){if(assistantConfig.transport!=='vm'||!vmRelay)throw new Error('此功能需要虚拟机连接器');await vmRelay.setUiPaused(b.paused);return json(200,{ok:true,paused:vmRelay.uiPaused,message:vmRelay.uiPaused?'窗口操作已暂停，可以使用虚拟机其他窗口；任务结果会保留。':'已恢复微信监听，可发送 /result 取回暂停期间的结果。'});}
  if(req.url==='/api/assistant/stop'){if(vmRelay){vmRelay.stop();channels['wechat-account']={status:'未启动',qr:null,error:''};}if(assistantProcess){channels['wechat-account'].status='正在停止';assistantProcess.stdin.write(JSON.stringify({type:'shutdown'})+'\n');const processToStop=assistantProcess;setTimeout(()=>{if(assistantProcess===processToStop)processToStop.kill();},3000);}return json(200,{ok:true});}
  if(req.url==='/api/task'){const c=parseCommand(b.prompt);if(c.action!=='task')throw new Error('请在任务框输入任务内容');const selected=b.conversationId?state.sessions[b.conversationId]:null;if(b.conversationId&&!selected)throw new Error('会话不存在');return json(200,enqueue('web',selected?.engine||c.engine||b.engine||'codex',c.prompt,'web',null,selected?.id));}
  if(req.url==='/api/stop')return json(200,{stopped:stop(b.conversationId||'web')});
  if(req.url==='/api/project'){const name=String(b.name||'').trim();if(!name||name.length>80)throw new Error('请输入 1–80 字的项目名称');return json(200,createProject(name));}
  if(req.url==='/api/conversation')return json(200,createConversation(b.projectId||'default',b.engine||'codex',String(b.title||'').slice(0,120)));
  if(req.url==='/api/conversation/get'){const s=state.sessions[b.id];if(!s)throw new Error('会话不存在');return json(200,s);}
  if(req.url==='/api/conversation/rename'){const s=state.sessions[b.id];if(!s||!String(b.title||'').trim())throw new Error('请输入会话名称');s.title=String(b.title).trim().slice(0,120);save();return json(200,{ok:true});}
  if(req.url==='/api/native/scan'){native=scanNative();return json(200,{count:native.length});}
  if(req.url==='/api/native/import'){const n=native.find(n=>n.id===b.id);if(!n)throw new Error('原会话不存在');const existing=Object.values(state.sessions).find(s=>s.nativeId===n.id&&s.projectId===(b.projectId||'default'));if(existing)return json(200,existing);const s=createConversation(b.projectId||'default','codex',n.title,loadNative(n.id));s.nativeId=n.id;s.importSource='本机 Codex 历史副本';save();return json(200,s);}
  if(req.url==='/api/import'){const imported=parseImport(b.content,b.engine||'gpt');if(imported.length>200)throw new Error('一次最多导入 200 个会话');for(const c of imported){validateEngine(c.engine);if(!c.history.length)throw new Error('没有找到可导入的文字消息');}return json(200,{conversations:imported.map(c=>createConversation(b.projectId||'default',c.engine,c.title,c.history))});}
  if(req.url==='/api/new'){if(active.has('web'))throw new Error('请先停止当前任务');delete state.sessions['web:codex'];delete state.sessions['web:muse'];save();return json(200,{ok:true});}
  if(req.url==='/api/auth'){checkAuth();return json(200,auth);}
  if(req.url==='/api/muse/connect'){const shell=path.join(process.env.SystemRoot||'C:\\Windows','System32','WindowsPowerShell','v1.0','powershell.exe');await new Promise((resolve,reject)=>{const child=spawn(shell,['-NoProfile','-File',path.join(root,'Launch-Personal-Muse.ps1')],{windowsHide:true});child.on('error',reject);child.on('close',code=>code===0?resolve():reject(new Error('Muse 授权窗口未能打开')));});return json(200,{ok:true});}
  if(req.url==='/api/muse/check'){await museRequest({command:'status'});personalMuseVerified=true;return json(200,{ok:true});}
  if(req.url==='/api/muse/library'){personalMuseLibrary=await museRequest({command:'library'});personalMuseVerified=true;return json(200,{count:personalMuseLibrary.sessions.length});}
  if(req.url==='/api/muse/import'){const native=personalMuseLibrary.sessions.find(x=>x.session_id===b.id);if(!native)throw new Error('请先刷新 Muse 目录并选择会话');const existing=Object.values(state.sessions).find(s=>s.engine==='muse'&&s.personalMuseThread===native.session_id&&s.projectId===(b.projectId||'default'));if(existing)return json(200,existing);const imported=await museRequest({command:'history',thread:native.session_id});const s=createConversation(b.projectId||'default','muse',native.title||'Muse 会话',imported.history);s.personalMuseThread=native.session_id;s.importSource='muse.ai 原会话';save();return json(200,s);}
  if(req.url==='/api/meta/login')throw new Error('你选择的是 muse.ai 个人智能体，请使用页面中的 muse.ai 网站入口；Muse Code 登录不等同于连接该账号。');
  if(req.url==='/api/gpt/account'){checkAuth();if(!auth.ok)throw new Error('请先通过 codex login 登录 ChatGPT 账号');if(engineModes.gpt!=='chatgpt')for(const s of Object.values(state.sessions))if(s.engine==='gpt')s.thread=null;engineModes.gpt='chatgpt';saveEngineModes();save();return json(200,{ok:true});}
  if(req.url==='/api/meta/account'){engineModes.muse='web';saveEngineModes();return json(200,{ok:true,connected:false});}
  if(req.url==='/api/meta'){if(typeof b.key!=='string'||!b.key.trim())throw new Error('请输入密钥');metaKey=b.key.trim();metaModel=b.model?.trim()||'muse-spark-1.3';engineModes.muse='api';saveEngineModes();return json(200,{ok:true});}
  if(req.url==='/api/gpt'){if(typeof b.key!=='string'||!b.key.trim())throw new Error('请输入 OpenAI API 密钥');gptKey=b.key.trim();gptModel=b.model?.trim()||'gpt-6-astra';engineModes.gpt='api';saveEngineModes();return json(200,{ok:true});}
  if(req.url==='/api/deepseek'){if(typeof b.key!=='string'||!b.key.trim()||b.key.length>4096)throw new Error('请输入有效的 DeepSeek API 密钥');const model=String(b.model||'deepseek-flash').trim();if(!model||model.length>100)throw new Error('请输入有效的 DeepSeek 模型名称');deepseekKey=b.key.trim();deepseekModel=model;return json(200,{ok:true});}
  if(req.url==='/api/contact'){const c=state.contacts[b.id];if(!c)throw new Error('联系人不存在');if(Object.hasOwn(b,'allowed'))c.allowed=b.allowed===true;if(Object.hasOwn(b,'privateAccess')){if(c.channel!=='wechat-account'||c.kind!=='friend')throw new Error('私人项目只能绑定到助手号的好友私聊');c.privateAccess=b.privateAccess===true;if(!c.privateAccess) {c.projectId=null;c.currentConversation=null;}}save();return json(200,{ok:true});}
  if(req.url==='/api/connect'){if(b.channel==='wechat')await connectWechat();else if(b.channel==='whatsapp')await connectWhatsApp();else throw new Error('未知消息平台');return json(200,{ok:true});}
  return json(404,{error:'未找到接口'});
  }catch(e){json(400,{error:e.message});}});
server.listen(port,'127.0.0.1',()=>console.log('工作台 http://127.0.0.1:'+port));
if(wxAccount)pollWx();

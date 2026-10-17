import test from 'node:test';import assert from 'node:assert/strict';
import {parseCommand,validateEngine,allowedHost} from './core.mjs';
import {migrateLibrary,parseImport} from './library.mjs';
import {createInbound,remoteKey} from './remote.mjs';
import {TaskPool} from './task_pool.mjs';
import {updateCodexProgress,deliverTask,taskMessage} from './task_status.mjs';

test('网络恢复后清除旧错误，回传失败保留模型结果，成功重发清除失败状态',async()=>{
 const t={engine:'codex',status:'completed',result:'已保存的结果'},sent=[];
 updateCodexProgress(t,{type:'error',message:'request timed out'});assert(t.progressError);
 updateCodexProgress(t,{type:'item.completed'});assert(!t.progressError);
 await assert.rejects(deliverTask(t,async()=>{throw new Error('窗口暂时失效');},()=>{}),/窗口/);
 assert.equal(t.result,'已保存的结果');assert.equal(t.deliveryStatus,'failed');assert(taskMessage(t).includes('/result'));
 await deliverTask(t,async(text)=>sent.push(text),()=>{});assert.equal(t.deliveryStatus,'sent');assert(!t.deliveryError);assert.deepEqual(sent,['已保存的结果']);
});
test('/result 只能取回自己的结果，主号显式授权后可以取回私人项目结果',async()=>{
 const a={chat:'项目群',kind:'group',route:'new-a'},b={...a,route:'new-b'},other={chat:'另一个群',kind:'group',route:'other'};
 const owner=remoteKey('wechat-account','甲',a),state={projects:{p:{id:'p',name:'甲工作区',remoteOwner:owner},default:{id:'default',name:'私人项目'}},sessions:{mine:{id:'mine',projectId:'p',engine:'codex'},private:{id:'private',projectId:'default',engine:'codex'}},tasks:[{id:'secret',status:'completed',engine:'codex',conversationId:'private',result:'私人结果'},{id:'result-a',status:'completed',engine:'codex',remoteOwner:owner,conversationId:'mine',result:'甲的结果',deliveryError:'旧窗口失败'}],contacts:{[owner]:{id:owner,channel:'wechat-account',allowed:true,projectId:'p',currentConversation:'mine'}},seen:[]},sent=[];let n=0;
 const receive=createInbound({state,save(){},createProject(name,remoteOwner){const id='p'+(++n);return state.projects[id]={id,name,remoteOwner};},createConversation(){throw new Error('取回结果不应创建模型任务');},enqueue(){throw new Error('取回结果不应调用模型');},send:async(c,to,text)=>sent.push({to,text}),stop:()=>false});
 await receive('wechat-account','乙','/result','1',b);assert(!sent.at(-1).text.includes('甲的结果'));
 await receive('wechat-account','甲','/result','2',other);assert(!sent.at(-1).text.includes('甲的结果'));
 await receive('wechat-account','甲','/result','3',a);assert.deepEqual(sent.at(-1),{to:'new-a',text:'甲的结果'});assert(!state.tasks[1].deliveryError);
 const personal={chat:'本人',kind:'friend',route:'main'};await receive('wechat-account','本人','/result','4',personal);assert(!sent.at(-1).text.includes('私人结果'));
 const me=state.contacts[remoteKey('wechat-account','本人',personal)];me.privateAccess=true;me.projectId='default';me.currentConversation='private';
 await receive('wechat-account','本人','/result','5',personal);assert.equal(sent.at(-1).text,'私人结果');
});

test('群内多人并发、超额排队、乱序完成仍回复原发起人，排队可以取消',async()=>{
 const pool=new TaskPool(4,32),state={projects:{},sessions:{},tasks:[],contacts:{},seen:[]},sent=[],gates=new Map();let n=0;
 const receive=createInbound({state,save(){},createProject(name,remoteOwner){const id='p'+(++n);return state.projects[id]={id,name,remoteOwner};},createConversation(projectId,engine,title){const id='s'+(++n);return state.sessions[id]={id,projectId,engine,title};},enqueue(key,engine,prompt,source,reply,id){const task={conversationId:id,engine,prompt,source,status:'queued'};state.tasks.push(task);task.ticket=pool.submit(async()=>{task.status='running';await new Promise(resolve=>gates.set(prompt,resolve));task.status='completed';await reply('结果:'+prompt);},async()=>{task.status='interrupted';await reply('已取消:'+prompt);});return task;},send:async(channel,to,text)=>{sent.push({to,text});},stop(id){return state.tasks.find(t=>t.conversationId===id)?.ticket.cancel()||false;}});
 await Promise.all(Array.from({length:6},(_,i)=>receive('wechat-account','成员'+i,'/codex 任务'+i,'message'+i,{chat:'项目群',kind:'group',route:'route'+i})));
 assert.equal(pool.running,4);assert.equal(pool.waiting.length,2);assert.equal(state.tasks.filter(t=>t.status==='running').length,4);
 assert(sent.find(x=>x.to==='route4'&&x.text.includes('排队')));assert.equal(new Set(state.tasks.map(t=>t.conversationId)).size,6);
 await receive('wechat-account','成员5','/stop','stop5',{chat:'项目群',kind:'group',route:'stop-route5'});
 await new Promise(resolve=>setImmediate(resolve));assert.equal(pool.waiting.length,1);assert.equal(state.tasks[5].status,'interrupted');
 gates.get('任务2')();await new Promise(resolve=>setImmediate(resolve));assert.equal(state.tasks[4].status,'running');assert.equal(pool.running,4);
 assert(sent.find(x=>x.to==='route2'&&x.text==='结果:任务2'));assert(!sent.some(x=>x.to!=='route2'&&x.text==='结果:任务2'));
 for(const [prompt,resolve]of gates)if(prompt!=='任务2')resolve();await new Promise(resolve=>setImmediate(resolve));assert.equal(pool.running,0);
 assert.equal(state.tasks.filter(t=>t.status==='completed').length,5);assert(!gates.has('任务5'));
});
test('任务失败释放并发槽位，队列达到上限时明确拒绝',async()=>{
 const pool=new TaskPool(1,1);let release;pool.submit(()=>new Promise(resolve=>{release=resolve;}),()=>{});
 let started=false;pool.submit(()=>{started=true;throw new Error('模拟模型失败');},()=>{});
 assert.throws(()=>pool.submit(()=>{},()=>{}),/队列已满/);release();await new Promise(resolve=>setImmediate(resolve));assert(started);assert.equal(pool.running,0);
});
test('旧任务迁移到原会话，不混合不同工具',()=>{const s={sessions:{'web:codex':{engine:'codex',history:[{role:'user',content:'项目一'}]},'web:muse':{engine:'muse',history:[]}},tasks:[{session:'web',engine:'codex',prompt:'项目一'},{session:'web',engine:'muse',prompt:'分析'}]};migrateLibrary(s,'test');assert.equal(s.tasks[0].conversationId,'web:codex');assert.equal(s.tasks[1].conversationId,'web:muse');assert.equal(s.sessions['web:codex'].title,'项目一');});
test('ChatGPT 导入只保留当前分支，并过滤系统消息',()=>{const result=parseImport({title:'旧项目',current_node:'b',mapping:{a:{parent:null,message:{author:{role:'user'},content:{parts:['问题']}}},b:{parent:'a',message:{author:{role:'assistant'},content:{parts:['答案']}}},other:{parent:'a',message:{author:{role:'assistant'},content:{parts:['别的分支']}}}}},'gpt');assert.deepEqual(result[0].history,[{role:'user',content:'问题'},{role:'assistant',content:'答案'}]);assert.equal(parseImport({messages:[{role:'system',content:'不可导入'},{role:'user',content:'历史'}]},'muse')[0].history.length,1);});
test('手机命令路由和多行任务',()=>{assert.deepEqual(parseCommand('/muse 分析\n这个方案'),{action:'task',engine:'muse',prompt:'分析\n这个方案'});assert.deepEqual(parseCommand('/deepseek 分析\n这个方案'),{action:'task',engine:'deepseek',prompt:'分析\n这个方案'});assert.deepEqual(parseCommand('/stop'),{action:'stop'});assert.equal(parseCommand('整理项目').prompt,'整理项目');assert.throws(()=>parseCommand('/unknown'));assert.throws(()=>parseCommand(''));});
test('拒绝未知引擎和 DNS 重绑定主机',()=>{assert.throws(()=>validateEngine('shell'));assert.equal(allowedHost('evil.example:8790',8790),false);assert.equal(allowedHost('127.0.0.1:8790',8790),true);});
test('开放微信的目录和任务仅归属对应私聊 / 群成员，重复消息不执行',async()=>{
 const state={projects:{default:{id:'default',name:'私人项目'}},sessions:{secret:{id:'secret',projectId:'default',title:'私人记录',engine:'codex'}},tasks:[],contacts:{},seen:[]},sent=[];let count=0;
 const receive=createInbound({state,save(){},createProject(name,remoteOwner){const id='p'+(++count);return state.projects[id]={id,name,remoteOwner};},createConversation(projectId,engine,title){const id='s'+(++count);return state.sessions[id]={id,projectId,engine,title};},enqueue(key,engine,prompt,source,reply,id){const t={conversationId:id,engine,prompt,status:'running'};state.tasks.push(t);return t;},send:async(c,to,text)=>sent.push({to,text}),stop:()=>true});
 const a={chat:'项目群',kind:'group',route:'route-a'},b={...a,route:'route-b'},other={chat:'另一个群',kind:'group',route:'route-c'};
 await receive('wechat-account','甲','/projects','1',a);assert(!sent.at(-1).text.includes('私人项目'));
 await receive('wechat-account','甲','/codex 甲的任务','2',a);await receive('wechat-account','甲','/codex 甲的任务','2',a);assert.equal(state.tasks.length,1);
 await receive('wechat-account','乙','/sessions','3',b);assert(!sent.at(-1).text.includes('甲的任务'));assert.equal(sent.at(-1).to,'route-b');
 await receive('wechat-account','甲','/status','4',other);assert.equal(sent.at(-1).text,'暂无任务');
 await receive('wechat-account','乙','/use S1','5',b);assert.equal(sent.at(-1).text,'会话编号不存在');
 const key=remoteKey('wechat-account','甲',a);state.contacts[key].allowed=false;const before=sent.length;await receive('wechat-account','甲','/help','6',a);assert.equal(sent.length,before);
 assert.notEqual(remoteKey('wechat-account','甲',a),remoteKey('wechat-account','甲',{...a,kind:'friend'}));
 const personal={chat:'我的主号',kind:'friend',route:'route-me'};
 await receive('wechat-account','本人','/projects','7',personal);assert(!sent.at(-1).text.includes('私人项目'));
 const me=state.contacts[remoteKey('wechat-account','本人',personal)];me.privateAccess=true;
 await receive('wechat-account','本人','/projects','8',personal);assert(sent.at(-1).text.includes('私人项目'));
 await receive('wechat-account','本人','/project P1','9',personal);
 await receive('wechat-account','本人','/sessions','10',personal);assert(sent.at(-1).text.includes('私人记录'));
 state.contacts[remoteKey('wechat-account','乙',b)].privateAccess=true;
 await receive('wechat-account','乙','/projects','11',b);assert(!sent.at(-1).text.includes('私人项目'));
});

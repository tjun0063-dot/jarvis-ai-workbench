import {parseCommand} from './core.mjs';
import {taskMessage,friendlyError,deliverTask} from './task_status.mjs';

// Desktop account conversations always get their own project, including group members.
export function remoteKey(channel,sender,context){
  return channel==='wechat-account'?channel+':'+JSON.stringify([context.chat,context.kind,sender]):channel+':'+sender;
}
export function createInbound({state,save,createProject,createConversation,enqueue,send,stop,materials,startCollection,stopCollection}){
  materials??={get:()=>null,status:()=>null,begin:()=>{throw new Error('材料收集组件未启用');},addText:()=>{},finish:()=>null,cancel:()=>false,dispose:()=>{}};
  startCollection??=()=>Promise.reject(new Error('材料收集组件未启用'));stopCollection??=()=>Promise.resolve();
  const chains=new Map();
  return async function inbound(channel,sender,text,messageId,context){
    const publicAccount=channel==='wechat-account';
    if(publicAccount&&(!context?.chat||!['friend','group'].includes(context.kind)||!context.route))return;
    const key=remoteKey(channel,sender,context);
    const previous=chains.get(key)||Promise.resolve();
    const operation=previous.catch(()=>{}).then(async()=>{
      if(messageId){const seen=key+':'+messageId;if(state.seen.includes(seen))return;state.seen.push(seen);state.seen=state.seen.slice(-3000);}
      let contact=state.contacts[key];
      if(!contact){contact=state.contacts[key]={id:key,channel,sender,allowed:publicAccount,public:publicAccount};}
      if(publicAccount){contact.public=true;contact.chat=context.chat;contact.kind=context.kind;}
      save();if(!contact.allowed)return;
      const reply=t=>send(channel,publicAccount?context.route:sender,t,context);
      let pendingMaterial=null;
      try{
        const selectedProject=state.projects[contact.projectId];
        const privateAccess=publicAccount&&context.kind==='friend'&&contact.privateAccess===true;
        if(publicAccount&&selectedProject?.remoteOwner!==key&&!(privateAccess&&selectedProject&&!selectedProject.remoteOwner)){
          const p=createProject('微信 · '+context.chat+(context.kind==='group'?' / '+sender:''),key);
          contact.projectId=p.id;contact.currentConversation=null;save();
        }
        const projects=Object.values(state.projects).filter(p=>publicAccount?(p.remoteOwner===key||privateAccess&&!p.remoteOwner):!p.remoteOwner);
        const conversations=Object.values(state.sessions).filter(s=>s.projectId===(contact.projectId||'default'));
        if(text.trim()==='/projects')return await reply(projects.map((p,i)=>`P${i+1} · ${p.name}`).join('\n')+'\n用 /project P1 选择项目');
        if(text.trim()==='/sessions')return await reply((conversations.map((s,i)=>`S${i+1} · ${s.engine} · ${s.title}`).join('\n')||'暂无会话')+'\n用 /use S1 继续会话');
        let m=text.trim().match(/^\/project P(\d+)$/i);if(m){const p=projects[Number(m[1])-1];if(!p)throw new Error('项目编号不存在');contact.projectId=p.id;contact.currentConversation=null;save();return await reply('已切换项目：'+p.name);}
        m=text.trim().match(/^\/use S(\d+)$/i);if(m){const s=conversations[Number(m[1])-1];if(!s)throw new Error('会话编号不存在');contact.currentConversation=s.id;contact.engine=s.engine;save();return await reply('继续会话：'+s.title+' · '+s.engine);}
        m=text.trim().match(/^\/agent (codex|gpt|muse|deepseek)$/i);if(m){contact.engine=m[1].toLowerCase();contact.currentConversation=null;save();return await reply('默认工具已切换为 '+contact.engine);}
        const current=conversations.find(s=>s.id===contact.currentConversation);
        const running=state.tasks.find(t=>['running','queued'].includes(t.status)&&t.remoteOwner===key);
        const ownedTasks=state.tasks.filter(t=>{
          if(current&&t.conversationId!==current.id)return false;
          return publicAccount?t.remoteOwner===key||(privateAccess&&current&&!state.projects[current.projectId]?.remoteOwner):current?true:t.session===key;
        });
        const command=text.trim();let materialDraft=null;
        if(command==='/材料'){
          if(!publicAccount)throw new Error('材料收集模式目前用于贾维斯个人微信号');
          if(running)throw new Error('你的任务正在执行或排队，请等待或使用 /stop');
          const draft=materials.begin(key,{channel,sender,context});
          try{await startCollection(context.route,draft.id,draft.expiresAt);}catch(error){materials.cancel(key);throw error;}
          return await reply('材料收集已开始（30 分钟有效）。请连续发送说明、图片、视频或文件；完成后发送 /开始，放弃请发送 /取消材料。群聊中的文字仍需 @贾维斯，文件会按发送人单独归集。');
        }
        const activeDraft=materials.get(key);
        if(command==='/材料状态'){
          const status=materials.status(key);return await reply(status?`已收集：${status.textCount} 条说明、${status.fileCount} 个文件（${(status.total/1048576).toFixed(1)}MB）。发送 /开始 提交。`:'当前没有材料收集会话，请先发送 /材料');
        }
        if(command==='/取消材料'){
          if(!activeDraft)return await reply('当前没有材料收集会话');
          materials.cancel(key);try{await stopCollection(context.route,activeDraft.id);}catch{}
          return await reply('本次材料已取消并清理。');
        }
        if(activeDraft&&command!='/开始'){
          const draft=materials.addText(key,text,context.route);
          return await reply(`已收集第 ${draft.texts.length} 条说明；还可继续发送材料，完成后发送 /开始。`);
        }
        if(command==='/开始'){
          if(!activeDraft)return await reply('当前没有材料收集会话，请先发送 /材料');
          materialDraft=materials.finish(key,context.route);pendingMaterial=materialDraft;try{await stopCollection(context.route,materialDraft.id);}catch{}
          text=materialDraft.texts.join('\n\n').trim()||'请查看并处理我提供的材料。';
        }
        const c=parseCommand(text);
        if(c.action==='help')return await reply('/codex 任务内容\n/gpt 问题内容\n/muse 问题内容\n/deepseek 问题内容\n/材料 开始收集多条说明和文件\n/开始 合并材料并执行\n/材料状态 查看已收集数量\n/取消材料 清理本次材料\n/agent deepseek 切换默认工具\n/projects 列出自己的项目\n/project P1 切换项目\n/sessions 列出自己的会话\n/use S1 继续会话\n/status 查看最近任务\n/result 取回自己的最近结果\n/new 新会话\n/stop 停止当前任务'+(publicAccount?'\n群里每次请 @贾维斯；群回复会被群成员看到。':''));
        if(c.action==='status')return await reply(taskMessage(running||ownedTasks.at(-1)));
        if(c.action==='result'){
          const task=ownedTasks.filter(t=>t.status==='completed'&&(t.result||t.attachments?.length)).at(-1);
          if(!task)return await reply('暂无已完成的结果，可用 /status 查看当前任务');
          if(task.deliveryStatus==='sending')return await reply('结果正在回传，请稍候');
          if(task.deliveryStatus==='sent')for(const file of task.attachments||[])file.deliveryStatus='pending';
          await deliverTask(task,reply,save);
          return;
        }
        if(c.action==='stop')return await reply(stop(running?.conversationId||current?.id)?'已请求停止':'没有正在运行的任务');
        if(c.action==='new'){if(running)throw new Error('请先等待当前任务结束或使用 /stop');contact.currentConversation=null;save();return await reply('下一条消息将开启新会话');}
        if(running)throw new Error('你的任务正在执行或排队，请等待或使用 /stop');
        const engine=c.engine||current?.engine||contact.engine||'codex';let s=current;
        if(!s||s.engine!==engine)s=createConversation(contact.projectId||'default',engine,c.prompt.slice(0,50));
        // Only remember the selection once dispatch has passed auth/key validation.
        const task=enqueue(key,engine,c.prompt,channel,reply,s.id,materialDraft);pendingMaterial=null;task.remoteOwner=key;
        contact.currentConversation=s.id;contact.engine=engine;save();await reply(task.status==='queued'?'已接收，正在排队：'+engine+'。轮到后自动执行，可用 /status 查看或 /stop 取消。':'已接收，正在执行：'+engine+'。');
      }catch(e){if(pendingMaterial)materials.dispose(pendingMaterial);await reply(friendlyError(e.message));}
    });
    chains.set(key,operation);try{await operation;}finally{if(chains.get(key)===operation)chains.delete(key);}
  };
}

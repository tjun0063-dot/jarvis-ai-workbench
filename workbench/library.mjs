import fs from 'node:fs';import path from 'node:path';import os from 'node:os';
export function migrateLibrary(state,workspace){
  state.projects??={default:{id:'default',name:'默认项目',directory:workspace}};
  for(const [id,s] of Object.entries(state.sessions)){s.projectId??='default';s.title??=s.history?.find(m=>m.role==='user')?.content?.slice(0,50)||'历史 '+s.engine+' 会话';s.updated??=new Date().toISOString();}
  for(const t of state.tasks){t.conversationId??=t.session+':'+t.engine;t.projectId??='default';if(state.sessions[t.conversationId]&&!state.sessions[t.conversationId].history?.length)state.sessions[t.conversationId].title=t.prompt.slice(0,50);}
}
export function normalizeHistory(messages){if(!Array.isArray(messages))throw new Error('历史记录应为消息数组');return messages.filter(m=>['user','assistant'].includes(m.role)&&typeof m.content==='string').map(m=>({role:m.role,content:m.content}));}
export function chatgptMessages(c){const out=[],seen=new Set();let n=c.current_node;while(n&&c.mapping?.[n]&&!seen.has(n)){seen.add(n);const node=c.mapping[n],m=node.message;if(m&&['user','assistant'].includes(m.author?.role)){const text=(m.content?.parts||[]).filter(p=>typeof p==='string').join('\n');if(text)out.unshift({role:m.author.role,content:text});}n=node.parent;}return out;}
export function parseImport(input,engine){
  if(Array.isArray(input)&&input[0]?.mapping)return input.map(c=>({title:c.title||'ChatGPT 导入会话',engine:'gpt',history:chatgptMessages(c)})).filter(c=>c.history.length);
  if(input?.mapping)return [{title:input.title||'ChatGPT 导入会话',engine:'gpt',history:chatgptMessages(input)}];
  return [{title:input.title||'导入会话',engine,history:normalizeHistory(Array.isArray(input)?input:input.messages)}];
}
const codexRoot=path.join(process.env.CODEX_HOME||path.join(os.homedir(),'.codex'));
let nativeFiles=new Map();
export function scanNative(){nativeFiles=new Map();const index=new Map();try{for(const line of fs.readFileSync(path.join(codexRoot,'session_index.jsonl'),'utf8').split('\n')){try{const v=JSON.parse(line);index.set(v.id,v);}catch{}}}catch{}
  const out=[];for(const folder of ['sessions','archived_sessions']){const dir=path.join(codexRoot,folder);if(!fs.existsSync(dir))continue;for(const file of fs.readdirSync(dir,{recursive:true}).filter(x=>x.endsWith('.jsonl'))){const full=path.join(dir,file);let fd;try{fd=fs.openSync(full,'r');const buffer=Buffer.alloc(65536),n=fs.readSync(fd,buffer,0,buffer.length,0);const line=buffer.subarray(0,n).toString('utf8').split('\n')[0],meta=JSON.parse(line).payload;if(!meta?.id)continue;const name=index.get(meta.id);nativeFiles.set(meta.id,full);out.push({id:meta.id,title:name?.thread_name||'Codex 会话 '+meta.id.slice(0,8),cwd:meta.cwd||'',updated:name?.updated_at||meta.timestamp,engine:'codex'});}catch{}finally{if(fd!==undefined)fs.closeSync(fd);}}}
  return out.sort((a,b)=>String(b.updated).localeCompare(String(a.updated)));
}
export function loadNative(id){const file=nativeFiles.get(id);if(!file)throw new Error('请选择目录中已扫描的 Codex 会话');if(fs.statSync(file).size>40*1024*1024)throw new Error('会话超过 40MB，请导出所需聊天后导入');const history=[];
  for(const line of fs.readFileSync(file,'utf8').split('\n')){try{const r=JSON.parse(line),p=r.payload;if(r.type!=='response_item'||p.type!=='message'||!['user','assistant'].includes(p.role))continue;if(p.phase==='commentary')continue;const text=(p.content||[]).filter(x=>['input_text','output_text','text'].includes(x.type)).map(x=>x.text||'').join('\n');if(text&&!/^<(environment_context|external_codex_apps_open_page|send_user_message_question_reply)/.test(text.trim()))history.push({role:p.role,content:text});}catch{}}
  return history;
}

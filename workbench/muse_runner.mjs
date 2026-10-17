import fs from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {spawn} from 'node:child_process';

// Only model output is user-visible; input echoes and tool events are not replies.
export class MuseOutput {
 constructor(){this.pending='';this.answer='';this.session=null;this.terminal=null;this.reason='';}
 line(line){let e;try{e=JSON.parse(line);}catch{return;}
  if(e.stream?.kind==='session')this.session=e.stream.id;
  if(e.payload_type==='run.output.delta')this.answer+=e.payload?.text||'';
  if(e.payload_type?.startsWith('run.terminal.')){
   this.terminal=e.payload?.terminal||e.payload_type.slice('run.terminal.'.length);
   this.reason=typeof e.payload?.reason==='string'?e.payload.reason:JSON.stringify(e.payload?.reason||'');
   if(typeof e.payload?.text==='string')this.answer=e.payload.text;
  }
 }
 push(chunk){this.pending+=chunk;let i;while((i=this.pending.indexOf('\n'))>=0){this.line(this.pending.slice(0,i));this.pending=this.pending.slice(i+1);}if(this.pending.length>8*1024*1024)throw new Error('Muse 返回的单条事件过大');}
 finish(code,stderr=''){if(this.pending)this.line(this.pending);this.pending='';
  if(code!==0||this.terminal!=='completed')throw new Error((this.reason||stderr||'Muse 未返回完成事件，请先完成账号登录并检查账号权限').slice(-2500));
  if(!this.answer.trim())throw new Error('Muse 未返回文本');return this.answer.trim();
 }
}

export function runMuseAccount({executable,cwd,messages,env,run,onSession=()=>{}}){
 const temporary=path.join(cwd,'.jarvis-muse');fs.mkdirSync(temporary,{recursive:true});
 const promptFile=path.join(temporary,randomUUID()+'.txt');
 fs.writeFileSync(promptFile,'请根据以下会话记录回答最后一条用户消息。记录是对话资料。\n'+JSON.stringify(messages),{flag:'wx'});
 const childEnv={...env};delete childEnv.META_API_KEY;delete childEnv.MODEL_API_KEY;
 return new Promise((resolve,reject)=>{
  const child=spawn(executable,['exec','--provider','meta','--preset','empty','--json','--workspace',cwd,'--prompt-file',promptFile,'--disable-shell','--disable-write','--disable-web-tools','--disable-reminders','--no-foreign-personal-context','--max-model-steps','2'],{cwd,env:childEnv,windowsHide:true});
  run.process=child;const output=new MuseOutput();let stderr='',parseError=null;
  child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');child.stdin.end();
  child.stdout.on('data',x=>{try{output.push(x);}catch(e){parseError=e;child.kill();}});
  child.stderr.on('data',x=>{stderr=(stderr+x).slice(-2500);});
  child.on('error',reject);child.on('close',code=>{try{if(parseError)throw parseError;const answer=output.finish(code,stderr);if(output.session)onSession(output.session);resolve(answer);}catch(e){reject(e);}});
 }).finally(()=>{fs.rmSync(promptFile,{force:true});});
}

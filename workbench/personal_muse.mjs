import {spawn} from 'node:child_process';

export function personalMuseRequest({python,script,env,request,run,timeout=request?.artifactDir?720000:300000}){
 return new Promise((resolve,reject)=>{
  const child=spawn(python,['-u',script],{windowsHide:true,env:{...env,PYTHONUTF8:'1',PYTHONIOENCODING:'utf-8',MUSE_NO_UPDATE_CHECK:'1'}});
  if(run)run.process=child;
  let output='',oversized=false,timedOut=false;
  const timer=setTimeout(()=>{timedOut=true;child.kill();},timeout);
  child.stdin.end(JSON.stringify(request));child.stdout.setEncoding('utf8');child.stderr.resume();
  child.stdout.on('data',x=>{output+=x;if(output.length>2*1024*1024){oversized=true;child.kill();}});
  child.on('error',error=>{clearTimeout(timer);reject(error);});
  child.on('close',code=>{clearTimeout(timer);try{
   if(oversized)throw new Error('Muse 返回内容超过 2MB');
   if(timedOut)throw new Error('等待 Muse 超时，远端任务可能仍在运行，请先检查原会话再重发');
   let result;try{result=JSON.parse(output);}catch{throw new Error('Muse 连接器没有返回有效结果');}
   if(code!==0||result.error)throw new Error(result.error||'Muse 连接失败');resolve(result);
  }catch(error){reject(error);}});
 });
}

export function museThreadId(result){
 const id=result?.session_id||result?.session?.session_id;
 if(typeof id!=='string'||!id||id.length>512)throw new Error('Muse 未返回独立会话 ID，已停止发送，避免误发到主聊天');
 return id;
}

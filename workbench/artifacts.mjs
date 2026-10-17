import fs from 'node:fs';
import path from 'node:path';
import {createHash,randomUUID} from 'node:crypto';

export const FILE_LIMIT=100*1024*1024, FILE_COUNT=20, TASK_FILE_LIMIT=300*1024*1024;
const uuid=/^[a-f0-9-]{36}$/;
export function safeFilename(value){
 const name=String(value||'').normalize('NFC');
 if(!name||name.length>180||/[<>:"/\\|?*\x00-\x1f]/.test(name)||/[. ]$/.test(name)||/^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)/i.test(name)||name==='.'||name==='..')throw new Error('附件文件名无效');
 return name;
}
export function containedFile(base,file){
 const root=fs.realpathSync(base),target=fs.realpathSync(file),relative=path.relative(root,target);
 if(!relative||relative.startsWith('..'+path.sep)||relative==='..'||path.isAbsolute(relative))throw new Error('附件路径超出本次任务输出目录');
 // Also reject links whose target happens to remain inside the directory.
 let next=root;for(const part of path.relative(path.resolve(base),path.resolve(file)).split(path.sep)){
  if(!part||part==='..')throw new Error('附件路径无效');next=path.join(next,part);if(fs.lstatSync(next).isSymbolicLink())throw new Error('附件不能是符号链接');
 }
 const stat=fs.statSync(target);if(!stat.isFile()||stat.nlink!==1)throw new Error('附件必须是普通文件，不能是链接或目录');
 if(stat.size>FILE_LIMIT)throw new Error('单个附件超过工作台当前 100MB 上限');
 return {file:target,size:stat.size};
}
export function artifactPrompt(directory,{remote=false}={}){
 return '\n\n[工作台附件能力]\n需要交付文件时，必须实际生成文件，不能只声称已发送。图片、视频、PPT、PDF、表格、压缩包等均可作为附件交付；不要把本机或云端路径当成手机可下载链接。'+
 (remote?`请把本次交付文件保存在云端文件工作区 /home/hatch/ 下的目录 ${directory} 内（保存绝对路径为 /home/hatch/${directory}），最终回复附加以下清单（path 使用相对于 /home/hatch/ 的路径，只列本次交付文件）：\n\`\`\`workbench-artifacts\n{"files":[{"path":"${directory}/报告.pptx","name":"报告.pptx"}]}\n\`\`\`\n`:
 `请把本次交付文件写入目录 ${directory} 。工作台会收集目录里的普通文件作为附件。该目录必须只放交付文件；已有项目文件需发送时请复制进去，不要创建符号或硬链接。\n`)+
 '如果没有文件工具，小型文本文件可在最终回复使用以下格式（content 是实际文本，二进制用 base64 字段，不能伪造空文件）：\n```workbench-files\n{"files":[{"name":"说明.txt","content":"文件内容"}]}\n```\n单个附件最多 100MB，每次最多 20 个，总计最多 300MB。不要生成附件则正常回复文字。不得读取或导出凭据。[/工作台附件能力]';
}
export function portableFiles(text,directory){
 let count=0;
 const cleaned=String(text||'').replace(/```workbench-files\s*\n([\s\S]*?)```/g,(_,raw)=>{
  if(raw.length>3*1024*1024)throw new Error('内嵌附件过大，请用文件输出目录');
  const files=JSON.parse(raw).files;if(!Array.isArray(files)||!files.length)throw new Error('附件清单无效');
  for(const f of files){
   if(++count>FILE_COUNT)throw new Error('每次最多 20 个附件');
   const name=safeFilename(f.name);let bytes;
   if(typeof f.content==='string'&&f.base64===undefined)bytes=Buffer.from(f.content,'utf8');
   else if(typeof f.base64==='string'&&f.content===undefined&&/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(f.base64))bytes=Buffer.from(f.base64,'base64');
   else throw new Error('附件缺少有效的文本或 Base64 内容');
   fs.writeFileSync(path.join(directory,name),bytes,{flag:'wx'});
  }
  return '';
 }).trim();
 if(cleaned.includes('```workbench-files'))throw new Error('附件清单未完整返回');
 return cleaned;
}
export function createArtifactStore(directory){
 fs.mkdirSync(directory,{recursive:true});const base=fs.realpathSync(directory);
 function location(taskId,id){if(!uuid.test(taskId)||!uuid.test(id))throw new Error('附件编号无效');return path.join(base,taskId,id);}
 return {
  begin(project,taskId){if(!uuid.test(taskId))throw new Error('任务编号无效');const out=path.join(project,'.jarvis-outbox',taskId);fs.mkdirSync(out,{recursive:true});if(fs.realpathSync(out)!==path.resolve(out))throw new Error('任务输出目录不能重定向');return out;},
  collect(taskId,out){
   const entries=[];function walk(dir,depth){if(depth>5)throw new Error('附件目录层级过深');for(const ent of fs.readdirSync(dir,{withFileTypes:true})){if(depth===0&&ent.name==='.jarvis-input')continue;const f=path.join(dir,ent.name);if(ent.isDirectory()){if(fs.lstatSync(f).isSymbolicLink())throw new Error('附件目录不能是链接');walk(f,depth+1);}else{if(entries.length>=FILE_COUNT)throw new Error('每次最多 20 个附件');entries.push({...containedFile(out,f),name:safeFilename(ent.name)});}}}walk(out,0);
   if(entries.reduce((sum,f)=>sum+f.size,0)>TASK_FILE_LIMIT)throw new Error('本次附件总计超过 300MB');
   return entries.map(f=>{const id=randomUUID(),dest=location(taskId,id);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.copyFileSync(f.file,dest,fs.constants.COPYFILE_EXCL);const sha256=createHash('sha256').update(fs.readFileSync(dest)).digest('hex');return {id,taskId,name:f.name,size:f.size,sha256};});
  },
  resolve(artifact){const f=location(artifact.taskId,artifact.id),checked=containedFile(base,f);if(checked.size!==artifact.size||createHash('sha256').update(fs.readFileSync(f)).digest('hex')!==artifact.sha256)throw new Error('已保存附件缺失或校验失败');return f;}
 };
}

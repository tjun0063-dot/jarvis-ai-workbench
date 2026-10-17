import fs from 'node:fs';
import path from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {FILE_LIMIT,FILE_COUNT,TASK_FILE_LIMIT,safeFilename,containedFile} from './artifacts.mjs';

export const MATERIAL_TTL=30*60*1000;
const uuid=/^[a-f0-9-]{36}$/;

export function createMaterialStore(directory,state,save=()=>{}){
 fs.mkdirSync(directory,{recursive:true});
 const base=fs.realpathSync(directory);
 state.materialDrafts??={};
 const drafts=state.materialDrafts;
 function location(collectionId,fileId){
  if(!uuid.test(collectionId)||!uuid.test(fileId))throw new Error('材料编号无效');
  return path.join(base,collectionId,fileId);
 }
 function removeDirectory(id){
  if(!uuid.test(id))return;
  const target=path.join(base,id),relative=path.relative(base,target);
  if(relative&&!relative.startsWith('..'+path.sep)&&!path.isAbsolute(relative))fs.rmSync(target,{recursive:true,force:true});
 }
 function expired(draft){return !draft||!Number.isSafeInteger(draft.expiresAt)||draft.expiresAt<=Date.now();}
 function sweep(){
  let changed=false;
  for(const [key,draft] of Object.entries(drafts))if(expired(draft)){removeDirectory(draft?.id);delete drafts[key];changed=true;}
  if(changed)save();
 }
 function get(key){sweep();return drafts[key]||null;}
 function begin(key,{channel,sender,context}){
  const old=drafts[key];if(old)removeDirectory(old.id);
  const draft={id:randomUUID(),key,channel,sender,context:{chat:context.chat,kind:context.kind,route:context.route},createdAt:Date.now(),expiresAt:Date.now()+MATERIAL_TTL,texts:[],files:[]};
  drafts[key]=draft;fs.mkdirSync(path.join(base,draft.id),{recursive:true});save();return draft;
 }
 function touch(draft,route){draft.expiresAt=Date.now()+MATERIAL_TTL;if(route)draft.context.route=route;}
 function addText(key,text,route){
  const draft=get(key);if(!draft)throw new Error('材料收集尚未开始，请先发送 /材料');
  text=String(text||'').trim();if(!text)return draft;
  if(draft.texts.reduce((n,x)=>n+x.length,0)+text.length>20000)throw new Error('材料说明累计超过 20000 字，请发送 /开始 或 /取消材料');
  draft.texts.push(text);touch(draft,route);save();return draft;
 }
 function addFile(collectionId,file){
  sweep();const draft=Object.values(drafts).find(x=>x.id===collectionId);if(!draft)throw new Error('材料会话已结束或过期');
  if(draft.files.length>=FILE_COUNT)throw new Error('一次最多收集 20 个文件');
  const name=safeFilename(file.name),target=location(collectionId,file.id),checked=containedFile(base,target);
  if(checked.size!==file.size||file.size>FILE_LIMIT||!/^[a-f0-9]{64}$/.test(file.sha256)||createHash('sha256').update(fs.readFileSync(target)).digest('hex')!==file.sha256)throw new Error('接收材料校验失败');
  if(draft.files.reduce((n,x)=>n+x.size,0)+file.size>TASK_FILE_LIMIT)throw new Error('本次材料总计超过 300MB');
  draft.files.push({id:file.id,name,size:file.size,sha256:file.sha256});touch(draft);save();return draft;
 }
 function status(key){const d=get(key);return d?{id:d.id,textCount:d.texts.length,fileCount:d.files.length,total:d.files.reduce((n,x)=>n+x.size,0),expiresAt:d.expiresAt,route:d.context.route}:null;}
 function finish(key,route){const d=get(key);if(!d)return null;touch(d,route);delete drafts[key];save();return d;}
 function cancel(key){const d=drafts[key];if(!d)return false;delete drafts[key];removeDirectory(d.id);save();return true;}
 function dispose(draft){if(draft?.id)removeDirectory(draft.id);}
 function stage(draft,target){
  if(!draft||!uuid.test(draft.id))throw new Error('材料会话无效');
  const input=path.join(target,'.jarvis-input');fs.mkdirSync(input,{recursive:true});
  const rows=[];
  try{
   for(const [index,file] of draft.files.entries()){
    const source=location(draft.id,file.id),checked=containedFile(base,source);
    if(checked.size!==file.size||createHash('sha256').update(fs.readFileSync(source)).digest('hex')!==file.sha256)throw new Error('材料文件缺失或校验失败');
    const name=String(index+1).padStart(2,'0')+'-'+safeFilename(file.name),dest=path.join(input,name);
    fs.copyFileSync(source,dest,fs.constants.COPYFILE_EXCL);rows.push({name:file.name,path:dest,size:file.size});
   }
   return rows;
  }finally{removeDirectory(draft.id);}
 }
 return {begin,get,addText,addFile,status,finish,cancel,dispose,stage,sweep,location};
}

export function materialPrompt(text,files){
 const body=String(text||'').trim()||'请查看并处理我提供的材料。';
 if(!files?.length)return body;
 return body+'\n\n[本次用户材料]\n'+files.map((f,i)=>`${i+1}. ${f.name}\n   本机绝对路径：${f.path}`).join('\n')+'\n请实际打开并读取这些文件，再完成任务；不要只根据文件名猜测内容。[/本次用户材料]';
}

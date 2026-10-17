export const taskLabels={queued:'排队中',running:'执行中',completed:'已完成',failed:'失败',interrupted:'已停止'};
export function taskMessage(t){
  if(!t)return '暂无任务';
  const delivery=t.deliveryStatus||(t.deliveryError?'failed':null);
  const extra=delivery==='failed'?'\n任务已保存，但回传失败；发送 /result 可取回。':delivery==='sending'?'\n结果正在回传。':'';
  return `${t.engine} · ${taskLabels[t.status]||t.status}${extra}\n${t.result||friendlyError(t.error)||t.prompt}`;
}
export function friendlyError(value){
  const text=String(value||'');
  if(/hit your usage limit/i.test(text))return 'Codex 返回额度已用尽，请等待额度恢复后再提交，或切换已配置的 GPT / Muse。';
  if(/request timed out|stream disconnected|os error 11001|不知道这样的主机/i.test(text))return '模型连接暂时失败，请检查这台电脑的网络后重试。';
  return text;
}
export function updateCodexProgress(task,event){
  task.progress=event.type;task.updated=new Date().toISOString();
  if(event.type==='error')task.progressError=event.message||event.error?.message||'Codex 请求重试中';
  else if(['thread.started','turn.started','item.started','item.completed','turn.completed'].includes(event.type))delete task.progressError;
}
export async function deliverTask(task,reply,save){
  task.deliveryStatus='sending';save();
  try{
    await reply(task.result||friendlyError(task.error)||(task.attachments?.length?'任务已完成，正在发送附件。':'任务完成'));
    for(const file of task.attachments||[]){
      if(file.deliveryStatus==='sent')continue;
      file.deliveryStatus='sending';save();
      try{await reply({attachment:file});file.deliveryStatus='sent';file.delivered=new Date().toISOString();delete file.deliveryError;}
      catch(e){file.deliveryStatus='failed';file.deliveryError=e.message;throw e;}
      finally{save();}
    }
    task.deliveryStatus='sent';task.delivered=new Date().toISOString();delete task.deliveryError;
  }
  catch(e){task.deliveryStatus='failed';task.deliveryError=e.message;throw e;}
  finally{save();}
}

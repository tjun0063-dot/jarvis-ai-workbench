export function deepSeekOutput(response){
 const text=(response?.output||[])
  .filter(item=>item?.type==='message')
  .flatMap(item=>item.content||[])
  .filter(item=>item?.type==='output_text'&&typeof item.text==='string')
  .map(item=>item.text)
  .join('\n').trim();
 if(!text)throw new Error('DeepSeek 未返回文本');
 return text;
}

export async function requestDeepSeek({key,model,messages,signal,fetchImpl=fetch}){
 if(typeof key!=='string'||!key)throw new Error('请先配置 DeepSeek API 密钥');
 const response=await fetchImpl('https://api.deepseek.com/responses',{
  method:'POST',signal,
  headers:{Authorization:'Bearer '+key,'Content-Type':'application/json'},
  body:JSON.stringify({model:model||'deepseek-flash',input:messages})
 });
 if(!response.ok)throw new Error('DeepSeek API 返回 HTTP '+response.status+'，请检查密钥、模型权限和额度');
 return deepSeekOutput(await response.json());
}

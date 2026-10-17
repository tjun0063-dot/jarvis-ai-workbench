import test from 'node:test';
import assert from 'node:assert/strict';
import {deepSeekOutput,requestDeepSeek} from './deepseek.mjs';

test('DeepSeek Responses API 提取完整的多段文本',()=>{
 const response={output:[{type:'reasoning',content:[]},{type:'message',content:[{type:'output_text',text:'第一段'},{type:'output_text',text:'第二段'}]}]};
 assert.equal(deepSeekOutput(response),'第一段\n第二段');
 assert.throws(()=>deepSeekOutput({output:[]}),/未返回文本/);
});

test('DeepSeek 请求使用官方 Responses API 且不泄漏密钥到正文',async()=>{
 let seen;
 const answer=await requestDeepSeek({key:'secret-key',model:'deepseek-flash',messages:[{role:'user',content:'你好'}],fetchImpl:async(url,options)=>{seen={url,options};return {ok:true,json:async()=>({output:[{type:'message',content:[{type:'output_text',text:'你好'}]}]})};}});
 assert.equal(answer,'你好');
 assert.equal(seen.url,'https://api.deepseek.com/responses');
 assert.equal(seen.options.headers.Authorization,'Bearer secret-key');
 assert(!seen.options.body.includes('secret-key'));
});

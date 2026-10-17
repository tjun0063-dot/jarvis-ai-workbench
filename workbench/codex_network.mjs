import fs from 'node:fs';

export function codexEnvironment(file,env=process.env){
 if(!fs.existsSync(file))return {...env};
 const config=JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));
 if(!config.proxy)return {...env};
 const proxy=new URL(config.proxy);
 if(proxy.protocol!=='http:'||!['127.0.0.1','localhost','[::1]'].includes(proxy.hostname)||!proxy.port||proxy.username||proxy.password||proxy.search||proxy.hash||proxy.pathname!=='/')throw new Error('Codex 代理须使用已配置的本机 HTTP 代理地址');
 const noProxy=[...new Set(String(env.NO_PROXY||'').split(',').filter(Boolean).concat(['localhost','127.0.0.1','::1']))].join(',');
 return {...env,HTTP_PROXY:config.proxy,HTTPS_PROXY:config.proxy,ALL_PROXY:config.proxy,NO_PROXY:noProxy};
}

import os from 'node:os';

function privateV4(value){
 const parts=String(value||'').split('.').map(Number);
 if(parts.length!==4||parts.some(x=>!Number.isInteger(x)||x<0||x>255))return false;
 return parts[0]===10||(parts[0]===172&&parts[1]>=16&&parts[1]<=31)||(parts[0]===192&&parts[1]===168);
}

export function discoverVmBind(interfaces=os.networkInterfaces()){
 const entries=Object.entries(interfaces).filter(([name])=>name.toLowerCase()==='vethernet (default switch)');
 const candidates=entries.flatMap(([,addresses])=>(addresses||[]).filter(a=>(a.family==='IPv4'||a.family===4)&&!a.internal&&privateV4(a.address)).map(a=>a.address));
 if(candidates.length!==1)throw new Error('未找到唯一的 Hyper-V Default Switch IPv4 地址');
 return candidates[0];
}


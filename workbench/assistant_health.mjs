export function assistantHealth(channel,now=Date.now()){
 const connected=channel.status==='已连接';
 const paused=connected&&channel.uiPaused===true;
 const lastScan=channel.lastScan||null;
 const lastActivity=Date.parse(lastScan||channel.connectedAt||'');
 const stale=connected&&!paused&&(!Number.isFinite(lastActivity)||now-lastActivity>15000);
 const windowsUnavailable=connected&&!paused&&channel.listening===0&&channel.waitingWindows>0;
 return {lastScan,stale,paused,windowsUnavailable,receiving:connected&&!paused&&!stale&&channel.listening>0};
}

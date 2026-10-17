export function parseCommand(text) {
  text=String(text||'').trim();
  if(!text || text.length>20000) throw new Error('请输入 1–20000 字的任务');
  const m=text.match(/^\/(codex|gpt|muse|deepseek)\s+([\s\S]+)$/i);
  if(m) return {action:'task',engine:m[1].toLowerCase(),prompt:m[2]};
  if(/^\/(codex|gpt|muse|deepseek)$/i.test(text))throw new Error('请在命令后写任务内容，例如 /deepseek 只回复“连接成功”');
  if(/^\/(help|status|result|new|stop)$/.test(text)) return {action:text.slice(1)};
  if(text.startsWith('/')) throw new Error('未知命令；使用 /help 查看命令');
  return {action:'task',prompt:text};
}
export function validateEngine(engine) {if(!['codex','gpt','muse','deepseek'].includes(engine)) throw new Error('未知执行工具'); return engine;}
export function allowedHost(host,port) {return [`127.0.0.1:${port}`,`localhost:${port}`].includes(host);}

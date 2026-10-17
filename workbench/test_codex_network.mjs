import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {codexEnvironment} from './codex_network.mjs';

test('local proxy is scoped to child environment and preserves localhost exclusions',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'jarvis-network-')),file=path.join(dir,'network.json');
 try{
  const env={OTHER:'preserved',NO_PROXY:'example.internal'};
  assert.deepEqual(codexEnvironment(file,env),env);
  fs.writeFileSync(file,JSON.stringify({proxy:'http://127.0.0.1:7897'}));
  const result=codexEnvironment(file,env);
  assert.equal(result.HTTPS_PROXY,'http://127.0.0.1:7897');assert.equal(result.OTHER,'preserved');
  assert(result.NO_PROXY.includes('127.0.0.1'));assert(!env.HTTPS_PROXY);
  for(const proxy of ['http://external.example:7897','http://user:secret@localhost:7897','http://localhost:7897/path']){
   fs.writeFileSync(file,JSON.stringify({proxy}));assert.throws(()=>codexEnvironment(file,env),/本机/);
  }
 }finally{const resolved=path.resolve(dir);assert.equal(path.dirname(resolved),path.resolve(os.tmpdir()));assert(path.basename(resolved).startsWith('jarvis-network-'));fs.rmSync(resolved,{recursive:true});}
});

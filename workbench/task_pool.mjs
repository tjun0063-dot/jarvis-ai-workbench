// Model work runs concurrently; the desktop adapter serializes UI sends.
export class TaskPool {
  constructor(limit=4,maxWaiting=32){this.limit=limit;this.maxWaiting=maxWaiting;this.running=0;this.waiting=[];}
  get full(){return this.running>=this.limit&&this.waiting.length>=this.maxWaiting;}
  submit(run,cancelled){
    if(this.full)throw new Error('等待队列已满，请稍后重试');
    const job={run,cancelled,state:'queued'};
    const ticket={cancel:()=>{
      if(job.state!=='queued')return false;
      job.state='cancelled';this.waiting.splice(this.waiting.indexOf(job),1);
      Promise.resolve().then(cancelled).catch(()=>{});return true;
    }};
    this.waiting.push(job);this.drain();return ticket;
  }
  drain(){
    while(this.running<this.limit&&this.waiting.length){
      const job=this.waiting.shift();job.state='running';this.running++;
      let result;try{result=job.run();}catch(e){result=Promise.reject(e);}
      Promise.resolve(result).catch(()=>{}).finally(()=>{job.state='done';this.running--;this.drain();});
    }
  }
}

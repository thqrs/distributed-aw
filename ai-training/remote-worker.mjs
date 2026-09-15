#!/usr/bin/env node
import {Worker,isMainThread,parentPort,workerData} from 'node:worker_threads';
import os from 'node:os';
import crypto from 'node:crypto';

if(!isMainThread){
  (0,eval)(workerData.engine);(0,eval)(workerData.shared);
  const suitePack=JSON.parse(workerData.suites);
  const suites=suitePack.suites,engineBuild=suitePack.engineBuild;
  parentPort.on('message',m=>{
    if(!m||m.type!=='run')return;
    try{
      if(m.campaign.engine_build&&m.campaign.engine_build!==engineBuild)throw new Error(`Engine mismatch campaign=${m.campaign.engine_build} client=${engineBuild}`);
      const suite=suites[m.campaign.suite];
      if(!suite)throw new Error('Unknown suite '+m.campaign.suite);
      const result=globalThis.AITrainingSim.runSeed({campaign:m.campaign,seed:m.seed,suite});
      parentPort.postMessage({id:m.id,ok:true,result});
    }catch(e){parentPort.postMessage({id:m.id,ok:false,error:e?.stack||String(e)});}
  });
}else{
  const args={};
  for(let i=2;i<process.argv.length;i++){
    const a=process.argv[i];if(!a.startsWith('--'))continue;
    const k=a.slice(2),v=process.argv[i+1]&&!process.argv[i+1].startsWith('--')?process.argv[++i]:true;args[k]=v;
  }
  const base=String(args.url||process.env.AI_TRAINING_URL||'').replace(/\/$/,'');
  const key=String(args.key||process.env.AI_TRAINING_KEY||'');
  const campaignId=String(args.campaign||process.env.AI_TRAINING_CAMPAIGN||'');
  if(!base||!key||!campaignId){console.error('Usage: AI_TRAINING_URL=https://site/ai-training AI_TRAINING_KEY=... node remote-worker.mjs --campaign ID --workers 4 --limit 0');process.exit(2);}

  const avail=os.availableParallelism?.()||os.cpus().length;
  const workers=Math.max(1,Math.min(64,args.workers==='auto'||!args.workers?Math.max(1,Math.min(8,avail-1)):Number(args.workers)||1));
  const rawLimit=Number(args.limit??100);
  const continuous=Number.isFinite(rawLimit)&&rawLimit===0;
  const limit=continuous?Infinity:Math.max(1,Number.isFinite(rawLimit)?rawLimit:100);
  const targetLabel=continuous?'∞':String(limit);
  const maxMinutes=Math.max(1,Number(args['max-minutes']||330));
  const claimMinutes=Math.max(1,Math.min(30,Number(args['claim-minutes']||12)));
  const submitBatch=Math.max(1,Math.min(128,Number(args['submit-batch']||16)));
  const claimArg=String(args.claim??'auto').toLowerCase();
  const manualClaim=claimArg!=='auto'&&Number(claimArg)>0?Math.max(1,Math.min(500,Number(claimArg))):0;
  const deviceId=String(args['device-id']||`node-${os.hostname()}-${crypto.randomUUID().slice(0,8)}`);
  const deviceName=String(args.name||`Node ${os.hostname()}`);
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));

  const api=async(action,{method='GET',body=null}={})=>{
    const r=await fetch(`${base}/api.php?action=${encodeURIComponent(action)}`,{method,headers:{'Accept':'application/json','Content-Type':'application/json','X-AI-Training-Key':key},body:body?JSON.stringify(body):undefined});
    let j;try{j=await r.json();}catch(_){throw new Error(`HTTP ${r.status} (non-JSON)`);}
    if(!r.ok||j.ok===false)throw new Error(j.error||`HTTP ${r.status}`);return j;
  };
  const text=async p=>{const r=await fetch(`${base}/${p}`,{cache:'no-store'});if(!r.ok)throw new Error(`GET ${p}: ${r.status}`);return await r.text();};

  console.log(`[INIT] ${base} campaign=${campaignId} workers=${workers}/${avail} target=${targetLabel} claim=${manualClaim||'auto'} claimWindow=${claimMinutes}m submitBatch=${submitBatch} softStop=${maxMinutes}m`);
  const [engine,shared,suites]=await Promise.all([text('assets/tactical-lab-worker-bundle.js'),text('shared-sim.js'),text('assets/suites.json')]);

  const pool=[],idle=[],pending=new Map(),queue=[];let seq=1;
  function drain(){while(idle.length&&queue.length){const w=idle.shift(),x=queue.shift();x.workerIndex=w.idx;x.startedAt=Date.now();pending.set(x.id,x);w.postMessage({type:'run',id:x.id,seed:x.seed,campaign:x.campaign});}}
  function spawn(i){
    const w=new Worker(new URL(import.meta.url),{workerData:{engine,shared,suites}});w.idx=i;
    w.on('message',m=>{const p=pending.get(m.id);pending.delete(m.id);idle.push(w);if(p){const ms=Date.now()-p.startedAt;if(m.ok){const r=m.result;console.log(`[W${w.idx+1}] seed ${p.seed} done ${(ms/1000).toFixed(1)}s pts=${(100*Number(r.points||0)).toFixed(1)}% W-D-L=${r.wins||0}-${r.draws||0}-${r.losses||0} Δ=${Math.round(Number(r.delta||0))}`);p.resolve(r);}else p.reject(new Error(m.error));}drain();});
    w.on('error',e=>console.error(`[W${i+1} ERROR]`,e));pool.push(w);idle.push(w);
  }
  function run(seed,campaign){return new Promise((resolve,reject)=>{queue.push({id:seq++,seed,campaign,resolve,reject,startedAt:0,workerIndex:-1});drain();});}
  for(let i=0;i<workers;i++)spawn(i);

  let completed=0,start=Date.now(),localFinished=0;
  const softStopAt=start+maxMinutes*60_000;
  const rateSps=()=>{const sec=(Date.now()-start)/1000;return sec>10&&completed>0?completed/sec:0;};
  const remaining=()=>continuous?500:Math.max(0,limit-completed);
  const desiredClaim=()=>{
    const rem=remaining();
    if(rem<=0)return 0;
    if(manualClaim)return Math.min(manualClaim,rem);
    const sps=rateSps();
    const n=sps>0?Math.round(sps*claimMinutes*60):workers*16;
    return Math.max(1,Math.min(500,rem,Math.max(workers*4,n)));
  };
  const doneLabel=()=>`${completed}/${targetLabel}`;

  try{
    while(continuous||completed<limit){
      if(Date.now()>=softStopAt){console.log(`[SOFT STOP] reached ${maxMinutes} min; not claiming more work`);break;}
      const want=desiredClaim();
      if(want<=0)break;
      const claim=await api('claim',{method:'POST',body:{campaign_id:campaignId,count:want,device_id:deviceId,device_name:deviceName,user_agent:`Node ${process.version}`,platform:`${process.platform}/${process.arch}`,worker_count:workers,benchmark_sps:rateSps()||null,lease_seconds:900}});
      if(!claim.seeds.length){
        const done=Number(claim.stats?.done||0),total=Number(claim.stats?.total||0);
        if(total>0&&done>=total){console.log(`[DONE] campaign complete ${done}/${total}`);break;}
        if(!continuous){console.log('[DONE] no seeds available');break;}
        console.log(`[IDLE] no claimable seeds right now${total?` global=${done}/${total}`:''}; retrying in 15s`);
        await sleep(15000);
        continue;
      }
      const token=claim.lease_token;
      console.log(`[LEASE] ${claim.seeds.length} jobs ${claim.seeds[0]}…${claim.seeds.at(-1)} global=${claim.stats?.done??'?'} / ${claim.stats?.total??'?'}`);
      const hb=setInterval(()=>api('heartbeat',{method:'POST',body:{lease_token:token,device_id:deviceId,lease_seconds:900,worker_count:workers,benchmark_sps:rateSps()||null}}).then(x=>console.log(`[HEARTBEAT] lease ${x.extended} jobs | submitted=${doneLabel()} | rate=${(rateSps()*60).toFixed(2)} seeds/min`)).catch(e=>console.error('[HEARTBEAT ERROR]',e.message)),60000);
      const buffer=[];let flushChain=Promise.resolve();
      const flush=(force=false)=>{flushChain=flushChain.then(async()=>{
        if(!buffer.length||(!force&&buffer.length<submitBatch))return;
        const batch=buffer.splice(0,buffer.length);
        const sub=await api('submit',{method:'POST',body:{campaign_id:campaignId,lease_token:token,device_id:deviceId,results:batch,include_stats:false}});
        completed+=Number(sub.accepted||0)+Number(sub.duplicates||0);
        const sec=(Date.now()-start)/1000,rate=sec?completed/sec*60:0;
        const globalText=sub.stats?` global=${sub.stats.done}/${sub.stats.total}`:'';
        console.log(`[BATCH] +${sub.accepted||0}${sub.duplicates?` dup=${sub.duplicates}`:''} done=${doneLabel()} rate=${rate.toFixed(2)} seeds/min${globalText}`);
      });return flushChain;};
      try{
        await Promise.all(claim.seeds.map(seed=>run(seed,claim.campaign).then(async result=>{
          localFinished++;buffer.push(result);
          console.log(`[PROGRESS] calculated=${localFinished} submitted=${doneLabel()} buffered=${buffer.length}`);
          if(buffer.length>=submitBatch)await flush(false);
        })));
        await flush(true);
      }finally{clearInterval(hb);await flushChain;}
    }
  }catch(e){console.error('[FATAL]',e?.stack||e);process.exitCode=1;}finally{await Promise.all(pool.map(w=>w.terminate()));}
  console.log(`[END] submitted=${completed} calculated=${localFinished} in ${((Date.now()-start)/60000).toFixed(1)} min avg=${(rateSps()*60).toFixed(2)} seeds/min`);
}

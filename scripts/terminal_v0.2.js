(function(){
  // ==== CONFIG ====
  const monthlySalary=28750, days=22, workStart=9, workEnd=17;
  const daily=monthlySalary/days, hourly=daily/(workEnd-workStart), perMin=hourly/60, perSec=perMin/60;

  // ==== CLEANUP ====
  document.getElementById('salary-hud-overlay')?.remove();
  document.getElementById('salary-hud-style')?.remove();

  // ==== STYLES ====
  const css='' +
  ':root{--neo:#6fff6f;--neo-dim:#44aa44;--muted:#88c988;--soft:#1c1f1c;--b:rgba(100,255,120,.12)}' +
  '#salary-hud-overlay{position:fixed;inset:0;z-index:2147483647;background:radial-gradient(circle at 50% 40%,#000 0%,#010 60%,#000 100%);color:var(--neo-dim);font-family:"Courier New",monospace;display:flex;align-items:center;justify-content:center;overflow:hidden}' +
  '#matrix-canvas{position:absolute;inset:0;width:100%;height:100%}' +
  '.hud-wrap{position:relative;width:min(1200px,95vw);z-index:2;display:flex;flex-direction:column;gap:14px}' +
  '.title-line{font-size:clamp(26px,4vw,40px);color:var(--neo);text-shadow:0 0 6px var(--neo);text-align:center}' +
  '.panel{border:1px solid var(--b);background:rgba(0,0,0,.7);padding:14px 20px;border-radius:10px;box-shadow:0 0 25px rgba(0,255,102,.05) inset}' +
  '.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 28px;font-size:18px;color:var(--neo)}' +
  '.label{opacity:.75}.value{font-weight:700;color:var(--neo);font-size:20px}' +
  '.bar{width:100%;height:16px;border:1px solid var(--neo-dim);background:rgba(0,255,102,.05);border-radius:3px;overflow:hidden;margin-top:10px}' +
  '.bar-fill{height:100%;width:0%;background:var(--neo);transition:width .35s linear;filter:brightness(.9)}' +
  '.task-panel .section-title{color:var(--neo);font-size:16px;margin-bottom:8px}' +
  '.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}' +
  '.input{background:#0a0a0a;border:1px solid var(--b);color:var(--muted);padding:8px 10px;border-radius:6px;min-width:260px}' +
  '.btn{background:#111;border:1px solid var(--b);color:var(--neo-dim);padding:8px 12px;border-radius:6px;cursor:pointer}.btn:hover{border-color:var(--neo-dim);color:var(--neo)}' +
  '.lists{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}' +
  '.bucket{border:1px solid var(--b);background:var(--soft);border-radius:8px;padding:10px;min-height:120px}' +
  '.bucket-title{color:var(--neo);margin-bottom:6px;font-size:15px}' +
  '.task{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;border:1px solid var(--b);background:rgba(0,0,0,.4);border-radius:6px;padding:8px;margin-top:6px}' +
  '.task .name{color:var(--neo);font-weight:700}.task .meta{color:var(--neo-dim);font-size:12px}.task .earn{color:var(--neo);font-size:13px;text-align:right}' +
  '.mini{grid-column:1 / -1;height:6px;border:1px solid var(--b);border-radius:3px;overflow:hidden}.mini .fill{height:100%;width:0%;background:var(--neo);transition:width .35s linear}' +
  '.task-badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}.task-badge{border:1px solid rgba(100,255,120,.25);color:#6fff6f;padding:2px 8px;border-radius:999px;font-size:11px;background:rgba(0,0,0,.4)}' +
  '.footer{text-align:center;margin-top:2px;font-size:12px;opacity:.75;color:var(--neo-dim)}';
  const st=document.createElement('style'); st.id='salary-hud-style'; st.textContent=css; document.documentElement.appendChild(st);

  // ==== BASE UI ====
  const overlay=document.createElement('div'); overlay.id='salary-hud-overlay';
  const canvas=document.createElement('canvas'); canvas.id='matrix-canvas';
  const wrap=document.createElement('div'); wrap.className='hud-wrap';
  const title=document.createElement('div'); title.className='title-line'; title.textContent='# S42 REAL-TIME SALARY TERMINAL';
  const panel=document.createElement('div'); panel.className='panel';
  const grid=document.createElement('div'); grid.className='grid'; panel.appendChild(grid);
  const dayBar=document.createElement('div'); dayBar.className='bar'; const dayFill=document.createElement('div'); dayFill.className='bar-fill'; dayBar.appendChild(dayFill); panel.appendChild(dayBar);
  function row(lab){const L=document.createElement('div');L.className='label';L.textContent=lab;const V=document.createElement('div');V.className='value';V.textContent='--';grid.append(L,V);return V;}
  const vS=row('AED / second'), vM=row('AED / minute'), vH=row('AED / hour'), vD=row('AED / working day'), vE=row('Earned today'), vP=row('Workday done');

  // Task panel
  const taskPanel=document.createElement('div'); taskPanel.className='panel task-panel';
  const secTitle=document.createElement('div'); secTitle.className='section-title'; secTitle.textContent='Task Tracker — scientifically validating "productivity".';
  const controls=document.createElement('div'); controls.className='controls';
  const taskInput=document.createElement('input'); taskInput.className='input'; taskInput.placeholder='Task name';
  const btnStart=document.createElement('button'); btnStart.className='btn'; btnStart.textContent='Start';
  const btnBack=document.createElement('button'); btnBack.className='btn'; btnBack.textContent='Add to Backlog';
  const btnStop=document.createElement('button'); btnStop.className='btn'; btnStop.textContent='Stop Active';
  controls.append(taskInput,btnStart,btnBack,btnStop);

  const lists=document.createElement('div'); lists.className='lists';
  const colA=document.createElement('div'); colA.className='bucket';
  const colB=document.createElement('div'); colB.className='bucket';
  const colH=document.createElement('div'); colH.className='bucket';
  function t(lbl){const d=document.createElement('div');d.className='bucket-title';d.textContent=lbl;return d;}
  colA.appendChild(t('▶ Current')); colB.appendChild(t('📝 Backlog')); colH.appendChild(t('✅ History'));
  lists.append(colA,colB,colH); taskPanel.append(secTitle,controls,lists);

  const footer=document.createElement('div'); footer.className='footer'; footer.textContent='ESC to close • Only counts Mon–Fri 09:00–17:00 • Local only';
  overlay.append(canvas); wrap.append(title,panel,taskPanel,footer); overlay.append(wrap); document.body.appendChild(overlay);

  // ==== HELPERS ====
  const pad2=n=>String(n).padStart(2,'0'), todayKey=()=>{const d=new Date();return d.getFullYear()+'-'+pad2(d.getMonth()+1)+'-'+pad2(d.getDate());};
  const wd=d=>{const n=d.getDay();return n>=1&&n<=5;}, wh=d=>{const h=d.getHours()+d.getMinutes()/60;return h>=workStart&&h<workEnd;};
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)), hms=ms=>{const s=Math.max(0,ms/1000|0),h=s/3600|0,m=(s%3600)/60|0,x=s%60;return pad2(h)+':'+pad2(m)+':'+pad2(x);};
  const clear=(n)=>{while(n.firstChild)n.removeChild(n.firstChild);};
  const toast=msg=>{const t=document.createElement('div');Object.assign(t.style,{position:'fixed',right:'14px',bottom:'14px',padding:'10px 12px',background:'rgba(0,0,0,.7)',border:'1px solid rgba(100,255,120,.2)',borderRadius:'8px',color:'#6fff6f',fontFamily:'"Courier New",monospace',zIndex:'2147483651'});t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.style.transition='opacity .4s',10);setTimeout(()=>t.style.opacity='0',2000);setTimeout(()=>t.remove(),2600);};

  // ==== STATE ====
  const load=()=>{try{return JSON.parse(localStorage.getItem('officeHudTasks')||'{}')}catch(e){return{}}};
  const save=s=>localStorage.setItem('officeHudTasks',JSON.stringify(s));
  const init=s=>{const k=todayKey(); if(!s[k]) s[k]={active:[],backlog:[],history:[]}; return k;};
  const task=(name)=>({id:'t'+Math.random().toString(36).slice(2),name,status:'active',start:Date.now(),end:null,accruedSec:0,_lastTick:Date.now(),ach:[]});
  const backlog=(name)=>({id:'b'+Math.random().toString(36).slice(2),name,status:'backlog',ach:[]});

  const quips=['Deliverable: immaculate vibes.','Blocked by pantry queue.','Action item: remember why we opened Excel.','Cross-functional synergy achieved (with coffee).','Optimized KPIs: Kups Per Interval.','Stakeholder sign-off: the mirror.','Drafted a memo to future me.','99% planning, 1% executing (perfect ratio).','Added value by existing near a whiteboard.','Risk mitigated: empty mug.'];
  const rquip=()=>quips[(Math.random()*quips.length)|0];

  // per-task awards (per day)
  const aLoad=()=>{try{return JSON.parse(localStorage.getItem('officeHudAwards')||'{}')}catch(e){return{}}};
  const aSave=a=>localStorage.setItem('officeHudAwards',JSON.stringify(a));
  const aBucket=id=>{const a=aLoad(),d=todayKey(); if(!a[d])a[d]={}; if(!a[d].tasks)a[d].tasks={}; if(!a[d].tasks[id])a[d].tasks[id]={}; return a;};
  function grantOnce(t,key,txtFn){const a=aBucket(t.id),d=todayKey(); if(!a[d].tasks[t.id][key]){a[d].tasks[t.id][key]=true;aSave(a);const txt=txtFn(); if(!t.ach.includes(txt)) t.ach.push(txt); if(t._view&&t._view.badges){const b=document.createElement('div');b.className='task-badge';b.textContent=txt;t._view.badges.appendChild(b);} toast('🏆 '+txt);}}
  function checkAwards(t,now){const earned=t.accruedSec*perSec; if(earned>=1)grantOnce(t,'d1',()=> 'First Dirham 💸'); if(earned>=50)grantOnce(t,'d50',()=> '50 AED Club 🪙'); if(earned>=100)grantOnce(t,'d100',()=> 'Triple Digits 💯'); if((t.accruedSec||0)>=3600)grantOnce(t,'h1',()=> 'One Full Focus Hour ⏱️'); const h=now.getHours(); if(h>=12&&h<14)grantOnce(t,'lunch',()=> 'Lunch Survivor 🍽️'); if(h>=16&&h<17)grantOnce(t,'tea',()=> 'Tea Time Champion 🫖');}

  // ==== RENDER ====
  function taskCard(t,type){
    const card=document.createElement('div'); card.className='task';
    const left=document.createElement('div'), right=document.createElement('div');
    const name=document.createElement('div'); name.className='name'; name.textContent=t.name;
    const meta=document.createElement('div'); meta.className='meta'; meta.textContent= type==='history'?(t.quip||rquip()):(type==='backlog'?'Queued for legendary productivity':'In progress…');
    const badges=document.createElement('div'); badges.className='task-badges';
    left.append(name,meta,badges);
    const earn=document.createElement('div'); earn.className='earn'; earn.textContent='—'; right.appendChild(earn);
    const mini=document.createElement('div'); mini.className='mini'; const fill=document.createElement('div'); fill.className='fill'; mini.appendChild(fill);
    card.append(left,right,mini);
    if(type==='active'){const bt=document.createElement('button'); bt.className='btn'; bt.textContent='Stop'; bt.onclick=()=>stop(t.id); card.appendChild(bt);}
    if(type==='backlog'){const bt=document.createElement('button'); bt.className='btn'; bt.textContent='Start'; bt.onclick=()=>startFromBacklog(t.id); card.appendChild(bt);}
    return {card,earn,fill,badges};
  }
  function render(s,k){
    clear(colA); colA.appendChild(colA.firstChild||t('▶ Current'));
    clear(colB); colB.appendChild(colB.firstChild||t('📝 Backlog'));
    clear(colH); colH.appendChild(colH.firstChild||t('✅ History'));
    s[k].active.forEach(ti=>{const v=taskCard(ti,'active'); colA.appendChild(v.card); ti._view=v; (ti.ach||[]).forEach(x=>{const b=document.createElement('div'); b.className='task-badge'; b.textContent=x; v.badges.appendChild(b);});});
    s[k].backlog.forEach(ti=>{const v=taskCard(ti,'backlog'); colB.appendChild(v.card); ti._view=v; (ti.ach||[]).forEach(x=>{const b=document.createElement('div'); b.className='task-badge'; b.textContent=x; v.badges.appendChild(b);});});
    s[k].history.forEach(ti=>{const v=taskCard(ti,'history'); v.earn.textContent=hms(ti.end-ti.start)+' • '+(ti.accruedSec*perSec).toFixed(2)+' AED'; v.fill.style.width='100%'; colH.appendChild(v.card); ti._view=v; (ti.ach||[]).forEach(x=>{const b=document.createElement('div'); b.className='task-badge'; b.textContent=x; v.badges.appendChild(b);});});
  }

  // ==== OPS ====
  function accrue(list){const now=Date.now(),d=new Date(),ok=wd(d)&&wh(d); list.forEach(t=>{const ds=ok?Math.max(0,((now-(t._lastTick||now))/1000|0)):0; if(ds>0)t.accruedSec=(t.accruedSec||0)+ds; t._lastTick=now;});}
  function start(name){if(!name)return;const s=load(),k=init(s); s[k].active.push(task(name)); save(s); render(s,k);}
  function stop(id){const s=load(),k=init(s); const i=s[k].active.findIndex(t=>t.id===id); if(i>=0){const t=s[k].active[i]; accrue([t]); t.status='done'; t.end=Date.now(); t.quip=rquip(); checkAwards(t,new Date()); s[k].active.splice(i,1); s[k].history.unshift(t); save(s); render(s,k);}}
  function stopAll(){const s=load(),k=init(s); accrue(s[k].active); s[k].active.forEach(t=>{t.status='done';t.end=Date.now();t.quip=rquip();checkAwards(t,new Date());}); s[k].history=s[k].active.concat(s[k].history); s[k].active=[]; save(s); render(s,k);}
  function addBack(name){if(!name)return;const s=load(),k=init(s); s[k].backlog.unshift(backlog(name)); save(s); render(s,k);}
  function startFromBacklog(id){const s=load(),k=init(s); const i=s[k].backlog.findIndex(t=>t.id===id); if(i>=0){const b=s[k].backlog.splice(i,1)[0]; const nt=task(b.name); nt.ach=(b.ach||[]).slice(); s[k].active.unshift(nt); save(s); render(s,k);}}

  // ==== EVENTS ====
  btnStart.onclick=()=>{const n=taskInput.value.trim(); if(!n)return; start(n); taskInput.value=''; taskInput.focus(); if(/meeting/i.test(n)) toast('This could have been an email.');};
  btnBack.onclick =()=>{const n=taskInput.value.trim(); if(!n)return; addBack(n); taskInput.value=''; taskInput.focus();};
  btnStop.onclick =stopAll;

  // ==== INITIAL RENDER ====
  (function(){const s=load(),k=init(s); Object.keys(s).forEach(x=>{if(x!==k) delete s[x];}); save(s); render(s,k);})();

  // ==== MATRIX RAIN ====
  const ctx=canvas.getContext('2d',{alpha:false}); let W,H,dpr,cols,fs,drops; const glyphs='アイウエオカキクケコサシスセソ0123456789', speed=.3;
  function resize(){dpr=window.devicePixelRatio||1; W=canvas.clientWidth=overlay.clientWidth; H=canvas.clientHeight=overlay.clientHeight; canvas.width=W*dpr; canvas.height=H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0); fs=Math.max(20,(W/60)|0); ctx.font=String(fs)+'px Courier'; cols=Math.ceil(W/fs); drops=Array(cols).fill(0).map(()=>Math.random()*-50);}
  function draw(){ctx.fillStyle='rgba(0,0,0,.2)';ctx.fillRect(0,0,W,H);ctx.fillStyle='rgba(120,255,120,.5)'; for(let i=0;i<cols;i++){const ch=glyphs.charAt((Math.random()*glyphs.length)|0); const x=i*fs,y=drops[i]*fs; ctx.fillText(ch,x,y); if(y>H&&Math.random()>.98)drops[i]=0; else drops[i]+=speed;} requestAnimationFrame(draw);}
  resize(); window.addEventListener('resize',resize,{passive:true}); requestAnimationFrame(draw);

  // ==== LOOP & EXIT ====
  let lastSave=0;
  function tick(){
    const now=new Date(), srt=new Date(now), end=new Date(now);
    srt.setHours(workStart,0,0,0); end.setHours(workEnd,0,0,0);
    const total=Math.max(1,end-srt), elapsed=clamp(now-srt,0,total), prog=wd(now)?(elapsed/total)*100:0;
    let earned=0; if(wd(now)){ if(wh(now)) earned=(elapsed/1000)*perSec; else if(now>=end) earned=daily; }
    vS.textContent=perSec.toFixed(5); vM.textContent=perMin.toFixed(3); vH.textContent=hourly.toFixed(2); vD.textContent=daily.toFixed(2);
    vE.textContent=earned.toFixed(2)+' AED'; vP.textContent=prog.toFixed(1)+' %'; dayFill.style.width=prog.toFixed(1)+'%';
    const s=load(),k=init(s); accrue(s[k].active);
    s[k].active.forEach(t=>{if(!t._view)return; const ms=Date.now()-t.start; t._view.earn.textContent=hms(ms)+' • '+(t.accruedSec*perSec).toFixed(2)+' AED'; t._view.fill.style.width=Math.min(100,(t.accruedSec/36)|0)+'%'; checkAwards(t,now);});
    const ts=Date.now(); if(ts-lastSave>1000){save(s); lastSave=ts;}
  }
  const loop=setInterval(tick,100); tick();

  const water=setInterval(()=>toast('Hydration KPI: consider a refill.'),90*60*1000);
  window.addEventListener('keydown',e=>{if(e.key==='Escape'){clearInterval(loop);clearInterval(water);overlay.remove();st.remove();}});
})();

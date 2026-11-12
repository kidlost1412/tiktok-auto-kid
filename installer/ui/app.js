(function(){
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const S = {
  info:null, dir:'', data:'', desktop:true, auto:true,
  busy:false, kind:'install', stages:[], idx:-1, pct:0, shown:0,
  goDelete:false, dataSize:null, removed:[], warns:[], opts:null, goInfo:null, lastCheck:{app:0,data:0}, doneInfo:null
};
const STAGES_INSTALL = [
  ['tai-app','Tải ứng dụng'],['phan-mem','Cài phần mềm cần thiết'],['du-lieu','Chuẩn bị dữ liệu'],
  ['loi-tat','Tạo lối tắt'],['khoi-dong','Kiểm tra hoạt động']
];
const STAGES_GO_KEEP = [['sao-luu','Sao lưu dữ liệu'],['dung','Tắt ứng dụng'],['loi-tat','Gỡ lối tắt và đăng ký'],['xoa','Xoá tệp ứng dụng'],['don','Dọn dẹp']];
const STAGES_GO_ALL = STAGES_GO_KEEP.slice(1);

const ICO_WARN = '<svg viewBox="0 0 24 24"><path d="M12 8v5m0 3.5v.01M10.3 4.6L3.2 17a2 2 0 001.7 3h14.2a2 2 0 001.7-3L13.7 4.6a2 2 0 00-3.4 0z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ICO_OK = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 12.5l2.7 2.7L16 9.8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ICO_TICK = '<svg viewBox="0 0 12 12"><path d="M2.5 6.3l2.4 2.4 4.6-5" fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ICO_USER = '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 20c1.2-4 4.2-6 8-6s6.8 2 8 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

function fmtSize(b){
  const gb = b/1073741824;
  if (gb >= 1000) return (gb/1024).toFixed(1).replace('.',',')+' TB';
  if (gb >= 10) return Math.round(gb)+' GB';
  if (gb >= 1) return gb.toFixed(1).replace('.',',')+' GB';
  return Math.max(1,Math.round(b/1048576))+' MB';
}
function el(tag, cls, html){ const e=document.createElement(tag); if(cls) e.className=cls; if(html!=null) e.innerHTML=html; return e; }
function esc(s){ return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
const sameP = (a,b)=> a && b && a.toLowerCase()===b.toLowerCase();

/* ---------- chuyển màn hình ---------- */
function show(name){
  $$('.screen').forEach(s=>s.classList.toggle('active', s.id==='s-'+name));
  const mode = {go:'Gỡ cài đặt',godone:'Gỡ cài đặt'}[name] || (S.kind==='go' && name==='progress' ? 'Gỡ cài đặt' : 'Cài đặt');
  $('#tbMode').textContent = mode;
  if (name==='done') startConfetti();
}

/* ---------- thẻ ổ đĩa + chọn đường dẫn ---------- */
function buildCards(kind){
  const box = kind==='app' ? $('#dirCards') : $('#dataCards');
  box.innerHTML='';
  const inf = S.info, need = kind==='app' ? 2*1073741824 : 50*1073741824;
  const mk = (path, letterHtml, name, sub, free, total, badge) => {
    const c = el('button','card'); c.type='button'; c.dataset.path = path;
    const used = total ? Math.min(100, Math.max(2, (1-free/total)*100)) : 0;
    c.innerHTML = '<div class="top"><span class="letter">'+letterHtml+'</span><span class="nm">'+esc(name)+'<small>'+esc(sub)+'</small></span></div>'+
      (total ? '<div class="bar'+(free<need?' low':'')+'"><i style="width:0"></i></div><div class="sp"><b>'+fmtSize(free)+'</b> trống / '+fmtSize(total)+'</div>' : '<div class="sp">Chỉ cho tài khoản của bạn, không cần quyền quản trị</div>')+
      (badge?'<span class="badge">'+badge+'</span>':'')+'<span class="tick">'+ICO_TICK+'</span>';
    c.addEventListener('click',()=>setPath(kind,path));
    box.appendChild(c);
    requestAnimationFrame(()=>requestAnimationFrame(()=>{ const i=c.querySelector('.bar i'); if(i) i.style.width=used+'%'; }));
  };
  if (kind==='app'){
    mk(inf.defaultDir, ICO_USER, 'Mặc định', 'Khuyên dùng', 0, 0, 'KHUYÊN DÙNG');
  }
  inf.drives.forEach(d=>{
    const path = d.letter+':\\'+(kind==='app'?'TikTok Auto Kid':'TikTok Auto Kid Data');
    const badge = kind==='data' && d.letter===inf.bestDrive ? 'TRỐNG NHIỀU NHẤT' : '';
    mk(path, d.letter, d.label || 'Ổ đĩa cục bộ', d.letter+':\\', d.free, d.total, badge);
  });
}
function markSelected(kind){
  const box = kind==='app' ? $('#dirCards') : $('#dataCards');
  const p = kind==='app' ? S.dir : S.data;
  Array.from(box.children).forEach(c=>c.classList.toggle('sel', sameP(c.dataset.path,p)));
}
async function setPath(kind,p){
  if (kind==='app') S.dir=p; else S.data=p;
  $(kind==='app'?'#dirPath':'#dataPath').textContent = p;
  markSelected(kind);
  const seq = ++S.lastCheck[kind];
  const r = await window.ttaCheckPath(kind,p);
  if (seq!==S.lastCheck[kind]) return;
  if (r.path && r.path!==p){ if(kind==='app') S.dir=r.path; else S.data=r.path; }
  const box = $(kind==='app'?'#dirMsg':'#dataMsg'); box.innerHTML='';
  const addMsg = (cls, ico, text, btn) => {
    const m = el('div','msg '+cls, ico+'<span>'+text+'</span>');
    if (btn){ const b=el('button',null,esc(btn.label)); b.addEventListener('click',btn.fn); m.appendChild(b); }
    box.appendChild(m);
  };
  const sugBtn = r.suggest ? {label:'Dùng thư mục con', fn:()=>setPath(kind,r.suggest)} : null;
  if (r.error) addMsg('bad',ICO_WARN,esc(r.error)+(r.suggest?'<br><span style="opacity:.8">Gợi ý: '+esc(r.suggest)+'</span>':''), sugBtn);
  if (r.warn) addMsg('warn',ICO_WARN,esc(r.warn)+(r.nonAscii&&r.suggest?'<br><span style="opacity:.85">Gợi ý không dấu: '+esc(r.suggest)+'</span>':''), r.nonAscii&&r.suggest ? {label:'Dùng đường dẫn này',fn:()=>setPath(kind,r.suggest)} : null);
  if (r.valid && !r.warn) addMsg('ok',ICO_OK,'Còn trống '+fmtSize(r.free)+' trên ổ này.');
  (kind==='app'?$('#dirNext'):$('#dataNext')).disabled = !r.valid;
  if (kind==='app') $('#dirNext').dataset.valid = r.valid ? '1':''; else $('#dataNext').dataset.valid = r.valid ? '1':'';
}

async function pick(kind){
  const p = await window.ttaPickFolder(kind);
  if (p) setPath(kind,p);
}

/* ---------- tiến độ ---------- */
function buildChecklist(){
  const box = $('#checklist'); box.innerHTML='';
  S.stages.forEach(([id,label])=>{
    const c = el('div','ck','<span class="dot">'+ICO_TICK+'</span><span>'+esc(label)+'</span>');
    c.dataset.id = id; box.appendChild(c);
  });
}
function paintChecklist(){
  $$('#checklist .ck').forEach((c,i)=>{
    c.classList.toggle('done', i<S.idx);
    c.classList.toggle('active', i===S.idx);
  });
}
function resetProgress(){
  S.pct=0; S.shown=0; S.idx=-1; S.warns=[]; S.removed=[];
  $('#barFill').style.width='0%'; $('#pctNum').textContent='0';
  $('#progWarns').innerHTML=''; $('#logBox').textContent='';
  $('#errCard').classList.add('hidden');
  $$('#s-progress .prog-grid').forEach(g=>g.classList.remove('hidden'));
  $('#progStage').textContent = S.kind==='go' ? 'Đang chuẩn bị gỡ…' : 'Chuẩn bị…';
  $('#progMsg').textContent = 'Vui lòng chờ một chút';
  $('#progEyebrow').textContent = S.kind==='go' ? 'Đang gỡ cài đặt' : 'Đang cài đặt';
  buildChecklist(); paintChecklist();
}
let raf=0;
function tick(){
  const d = S.pct - S.shown;
  if (Math.abs(d) > 0.05){ S.shown += d*0.07 + Math.sign(d)*0.03; if ((d>0&&S.shown>S.pct)||(d<0&&S.shown<S.pct)) S.shown=S.pct; }
  const v = Math.max(0,Math.min(100,S.shown));
  $('#barFill').style.width = v+'%';
  $('#pctNum').textContent = Math.floor(v);
  raf = requestAnimationFrame(tick);
}
function onProgress(e){
  if (typeof e.pct==='number') S.pct = Math.max(S.pct, Math.min(100,e.pct));
  let i = S.stages.findIndex(s=>s[0]===e.stage);
  if (e.stage==='xong') i = S.stages.length;
  if (i>=0 && i>=S.idx){ S.idx=i; }
  if (i>=0 && i<S.stages.length) $('#progStage').textContent = S.stages[i][1];
  if (e.stage==='xong') $('#progStage').textContent = S.kind==='go' ? 'Sắp xong' : 'Hoàn tất';
  if (e.msg) $('#progMsg').textContent = e.msg;
  paintChecklist();
}
function addLog(line){
  const b=$('#logBox'); const near = b.scrollTop+b.clientHeight >= b.scrollHeight-20;
  b.textContent += line+'\n';
  if (b.textContent.length>60000) b.textContent = b.textContent.slice(-40000);
  if (near) b.scrollTop = b.scrollHeight;
}
function addWarn(m){
  S.warns.push(m);
  const box=$('#progWarns'); box.innerHTML='';
  S.warns.slice(-2).forEach(w=>box.appendChild(el('div','msg warn',ICO_WARN+'<span>'+esc(w)+'</span>')));
}

async function beginInstall(opts){
  S.kind='install'; S.opts=opts; S.stages=STAGES_INSTALL;
  resetProgress(); show('progress'); S.busy=true;
  try { await window.ttaStartInstall(opts); } catch(e){ onError({msg:String(e)}); }
}
async function beginGo(){
  S.kind='go'; S.stages = S.goDelete ? STAGES_GO_ALL : STAGES_GO_KEEP;
  resetProgress(); show('progress'); S.busy=true;
  try { await window.ttaStartUninstall({deleteAll:S.goDelete}); } catch(e){ onError({msg:String(e)}); }
}
function onError(e){
  S.busy=false;
  $('#errTitle').textContent = S.kind==='go' ? 'Chưa gỡ xong' : 'Ối, chưa cài xong 😢';
  $('#errMsg').textContent = e.msg || 'Đã có lỗi không rõ nguyên nhân.';
  $('#progWarns').innerHTML='';
  $$('#s-progress .prog-grid').forEach(g=>g.classList.add('hidden'));
  $('#errCard').classList.remove('hidden');
}
function onDone(e){
  S.busy=false; S.pct=100; S.doneInfo=e; S.idx=S.stages.length; paintChecklist();
  $('#progStage').textContent = 'Hoàn tất'; $('#progMsg').textContent='';
  setTimeout(()=>{
    if (S.kind==='go') finishGo(e); else finishInstall(e);
  }, 900);
}
function sumBox(label,val){ const d=el('div'); d.innerHTML='<small>'+esc(label)+'</small><span title="'+esc(val)+'">'+esc(val)+'</span>'; return d; }
function finishInstall(e){
  $('#doneTitle').textContent = e.dry ? 'Chạy thử xong' : 'Cài đặt xong rồi! 🎉';
  $('#doneSub').textContent = e.dry ? 'Đây chỉ là chạy thử, chưa có gì bị thay đổi trên máy.' : (e.demo ? 'Đây là bản mô phỏng, chưa cài gì thật.' : 'TikTok Auto Kid đã sẵn sàng trên máy bạn rồi nè!');
  const inf=$('#doneInfo'); inf.innerHTML='';
  inf.appendChild(sumBox('Ứng dụng', e.dir||'')); inf.appendChild(sumBox('Video & dữ liệu', e.data||''));
  const w=$('#doneWarns'); w.innerHTML='';
  (e.warns||[]).slice(0,2).forEach(m=>w.appendChild(el('div','msg warn',ICO_WARN+'<span>'+esc(m)+'</span>')));
  $('#btnOpenApp').classList.toggle('hidden', !!(e.dry||e.demo));
  show('done');
}
function li(t){ return el('li',null,esc(t)); }
function finishGo(e){
  const rm=$('#goRemoved'); rm.innerHTML='';
  (S.removed.length?S.removed:['TikTok Auto Kid đã được gỡ khỏi máy']).forEach(x=>rm.appendChild(li(x)));
  const nt=$('#goNotes'); nt.innerHTML='';
  if (e.deleteAll) nt.appendChild(li('Video, sản phẩm và cơ sở dữ liệu đã được xoá vĩnh viễn.'));
  else if (e.data) {
    nt.appendChild(li('Dữ liệu được giữ lại tại: '+e.data));
    if (e.kept) nt.appendChild(li('Bản sao lưu cơ sở dữ liệu nằm trong: '+e.kept+'. Cài lại sau này sẽ khôi phục từ đó.'));
  }
  nt.appendChild(li('Python, Node.js, ffmpeg và Claude Code được giữ lại vì phần mềm khác có thể đang dùng.'));
  nt.appendChild(li('Tiện ích Chrome cần gỡ thủ công: mở chrome://extensions rồi bấm Gỡ cài đặt ở TikTok Auto Kid.'));
  if (e.test) nt.appendChild(li('(Chế độ thử nghiệm: chỉ tác động lên thư mục giả.)'));
  show('godone');
}

window.__ev = function(e){
  switch(e.t){
    case 'progress': onProgress(e); break;
    case 'log': addLog(e.line); break;
    case 'warn': addWarn(e.msg); break;
    case 'error': onError(e); break;
    case 'done': onDone(e); break;
    case 'cancelled': S.busy=false; show('opts'); break;
    case 'removed': S.removed.push(e.item); break;
    case 'datasize': S.dataSize=e.bytes; paintGoSize(); break;
  }
};

/* ---------- gỡ cài đặt ---------- */
function paintGoSize(){
  const t = S.dataSize==null ? 'Đang tính dung lượng…' : 'Sẽ xoá khoảng '+fmtSize(S.dataSize);
  $('#goAllSize').textContent = t;
}
async function initGo(){
  const gi = await window.ttaGoInfo(); S.goInfo=gi;
  const msgs=$('#goMsg'); msgs.innerHTML='';
  S.goDelete=false; selectGo(false);
  if (!gi.found){
    $('#goLead').textContent = 'Không tìm thấy bản cài TikTok Auto Kid trên máy này.';
    $('#goRun').disabled = true;
    $('#goKeep').disabled = true; $('#goAll').disabled = true;
    if (gi.deleteWhy) msgs.appendChild(el('div','msg bad',ICO_WARN+'<span>'+esc(gi.deleteWhy)+'</span>'));
    return;
  }
  $('#goLead').textContent = 'Phiên bản '+(gi.version||'?')+' tại '+gi.dir;
  $('#goKeepPath').textContent = gi.data || 'Không có thư mục dữ liệu riêng';
  $('#goAllPath').textContent = gi.data || gi.dir;
  paintGoSize();
  if (gi.dataInside) msgs.appendChild(el('div','msg ok',ICO_OK+'<span>Dữ liệu đang nằm trong thư mục cài. Nếu giữ lại, nó sẽ được dời ra cạnh thư mục cài để không bị mất.</span>'));
  if (!gi.deleteOk){
    $('#goAll').disabled = true;
    msgs.appendChild(el('div','msg warn',ICO_WARN+'<span>Không thể xoá sạch tự động: '+esc(gi.deleteWhy||'')+'.</span>'));
  }
}
function selectGo(del){
  S.goDelete=del;
  $('#goKeep').classList.toggle('sel',!del);
  $('#goAll').classList.toggle('sel',del); $('#goAll').classList.toggle('danger',del);
  $('#goConfirmBox').classList.toggle('hidden',!del);
  if (!del) $('#goConfirm').checked=false;
  updateGoRun();
}
function updateGoRun(){
  const bad = !S.goInfo || !S.goInfo.found;
  $('#goRun').disabled = bad || (S.goDelete && !$('#goConfirm').checked);
  $('#goRun').textContent = S.goDelete ? 'Xoá sạch và gỡ' : 'Gỡ cài đặt';
}

/* ---------- confetti nhẹ ---------- */
let cRaf=0;
function startConfetti(){
  const cv=$('#confetti'), ctx=cv.getContext('2d'); const dpr=window.devicePixelRatio||1;
  const W=cv.clientWidth, H=cv.clientHeight; cv.width=W*dpr; cv.height=H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  const cols=['#F59ABD','#FED7E2','#7ED39C','#FFE9A8','#FEEBC8','#FF6B6B','#C6F6D5'];
  const ps=Array.from({length:90},()=>({x:Math.random()*W,y:-20-Math.random()*H*.7,r:2+Math.random()*4,vx:(Math.random()-.5)*.8,vy:1+Math.random()*2.2,rot:Math.random()*6,vr:(Math.random()-.5)*.2,c:cols[(Math.random()*cols.length)|0],s:Math.random()<.5}));
  const t0=performance.now(); cancelAnimationFrame(cRaf);
  (function loop(now){
    const t=(now-t0)/1000; ctx.clearRect(0,0,W,H);
    const fade = t>4.5 ? Math.max(0,1-(t-4.5)/1.5) : 1;
    ps.forEach(p=>{ p.x+=p.vx+Math.sin(t*2+p.r)*.4; p.y+=p.vy; p.rot+=p.vr;
      ctx.save(); ctx.globalAlpha=.85*fade; ctx.translate(p.x,p.y); ctx.rotate(p.rot); ctx.fillStyle=p.c; ctx.strokeStyle='#4A3428'; ctx.lineWidth=1.2;
      if(p.s){ ctx.fillRect(-p.r,-p.r/2,p.r*2,p.r); ctx.strokeRect(-p.r,-p.r/2,p.r*2,p.r); } else { ctx.beginPath(); ctx.arc(0,0,p.r*.7,0,7); ctx.fill(); ctx.stroke(); } ctx.restore(); });
    if (t<6) cRaf=requestAnimationFrame(loop); else ctx.clearRect(0,0,W,H);
  })(t0);
}

/* ---------- hộp thoại ---------- */
function ask(title,text,yes,no,onYes){
  $('#mTitle').textContent=title; $('#mText').textContent=text;
  $('#mYes').textContent=yes||'Đồng ý'; $('#mNo').textContent=no||'Huỷ';
  $('#mYes').classList.toggle('hidden', !onYes);
  $('#modal').classList.remove('hidden');
  $('#mNo').onclick=()=>$('#modal').classList.add('hidden');
  $('#mYes').onclick=()=>{ $('#modal').classList.add('hidden'); onYes&&onYes(); };
}
async function tryClose(){
  if (S.busy){
    if (S.kind==='go') return ask('Đang gỡ cài đặt','Vui lòng đợi thêm một chút để việc gỡ hoàn tất, thoát giữa chừng có thể để lại tệp thừa.','','Đã hiểu',null);
    return ask('Dừng cài đặt?','Cài đặt đang chạy dở. Nếu thoát bây giờ, bạn có thể chạy lại trình cài đặt bất cứ lúc nào để cài tiếp.','Dừng và thoát','Ở lại',async()=>{ try{await window.ttaCancel();}catch(_){} window.ttaClose(); });
  }
  window.ttaClose();
}

/* ---------- khởi động ---------- */
async function boot(){
  $('#btnMin').onclick=()=>window.ttaMinimize();
  $('#btnClose').onclick=tryClose;
  $('#titlebar').addEventListener('mousedown',e=>{ if(e.button===0 && !e.target.closest('.tb-btn')) window.ttaDrag(); });
  $$('[data-go]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.go)));

  const inf = await window.ttaInfo(); S.info=inf;
  $('#verText').textContent = 'Phiên bản '+inf.version + (inf.demo?'  ·  chế độ mô phỏng':'');
  S.dir = inf.defaultDir; S.data = inf.defaultData;
  buildCards('app'); buildCards('data');

  const old = inf.installed;
  if (old){
    $('#welcomeNew').classList.add('hidden'); $('#welcomeOld').classList.remove('hidden');
    $('#oldInfo').textContent = 'Phiên bản '+(old.version||'?')+'  ·  '+old.dir;
  }
  $('#btnStart').onclick=()=>{ setPath('app',S.dir); show('dir'); };
  $('#btnOther').onclick=()=>{ setPath('app',inf.defaultDir); show('dir'); };
  $('#btnRepair').onclick=()=>{
    S.dir=old.dir; S.data=old.data||inf.defaultData;
    beginInstall({dir:S.dir,data:S.data,desktop:true,autostart:!!old.autostart});
  };
  $('#btnUninstall').onclick=async()=>{
    if (await window.ttaGoEntry()) { window.ttaClose(); return; }
    S.kind='go'; await initGo(); show('go');
  };
  $('#btnPickDir').onclick=()=>pick('app');
  $('#btnPickData').onclick=()=>pick('data');
  $('#dirNext').onclick=()=>{ if(!$('#dirNext').dataset.valid) return; setPath('data',S.data); show('data'); };
  $('#dataNext').onclick=()=>{ if(!$('#dataNext').dataset.valid) return;
    $('#sumDir').textContent=S.dir; $('#sumData').textContent=S.data; show('opts'); };
  $('#btnInstall').onclick=()=>beginInstall({dir:S.dir,data:S.data,desktop:$('#optDesktop').checked,autostart:$('#optAuto').checked});

  $('#btnDetail').onclick=()=>{ const o=$('#logBox').classList.toggle('open'); $('#btnDetail').classList.toggle('open',o);
    $('#btnDetail').firstChild.textContent = o?'Ẩn chi tiết':'Xem chi tiết'; const b=$('#logBox'); b.scrollTop=b.scrollHeight; };
  $('#btnCancel').onclick=()=>ask(S.kind==='go'?'Dừng gỡ cài đặt?':'Huỷ cài đặt?','Bạn có chắc muốn dừng lại không?','Dừng lại','Tiếp tục',async()=>{
    if (S.kind==='go') return; try{await window.ttaCancel();}catch(_){} });
  $('#btnRetry').onclick=()=>{ if (S.kind==='go') beginGo(); else beginInstall(S.opts); };
  $('#btnLog').onclick=()=>window.ttaOpenLog();
  $('#btnErrBack').onclick=()=>{ S.busy=false; if (S.kind==='go') show('go'); else show(old?'welcome':'opts'); };
  $('#btnOpenApp').onclick=async()=>{ try{ await window.ttaLaunchApp(); }catch(_){} window.ttaClose(); };
  $('#btnDone').onclick=()=>window.ttaClose();
  $('#btnGoClose').onclick=()=>window.ttaClose();

  $('#goKeep').onclick=()=>selectGo(false);
  $('#goAll').onclick=()=>{ if(!$('#goAll').disabled) selectGo(true); };
  $('#goConfirm').onchange=updateGoRun;
  $('#goCancel').onclick=()=>window.ttaClose();
  $('#goRun').onclick=()=>beginGo();

  tick();
  await startScreen(inf);
}

async function startScreen(inf){
  if (inf.mode==='go'){ S.kind='go'; await initGo(); }
  const sc = inf.screen || (inf.mode==='go' ? 'go' : 'welcome');
  switch(sc){
    case 'dir': await setPath('app',S.dir); show('dir'); break;
    case 'dir-warn': await setPath('app','C:\\Người dùng\\Video'); show('dir'); break;
    case 'data': await setPath('app',S.dir); await setPath('data',S.data); show('data'); break;
    case 'opts': await setPath('app',S.dir); await setPath('data',S.data); $('#sumDir').textContent=S.dir; $('#sumData').textContent=S.data; show('opts'); break;
    case 'progress': case 'error': beginInstall({dir:S.dir,data:S.data,desktop:true,autostart:true}); break;
    case 'done': finishInstall({dir:S.dir,data:S.data,demo:true,warns:[]}); break;
    case 'go': S.kind='go'; await initGo(); show('go'); break;
    case 'go-delete': S.kind='go'; await initGo(); selectGo(true); $('#goConfirm').checked=true; updateGoRun(); show('go'); break;
    case 'go-progress': S.kind='go'; await initGo(); S.goDelete=false; beginGo(); break;
    case 'go-progress-all': S.kind='go'; await initGo(); S.goDelete=true; beginGo(); break;
    default: show(inf.mode==='go' ? 'go' : 'welcome');
  }
}

window.addEventListener('DOMContentLoaded',()=>{ boot().catch(e=>{ document.body.insertAdjacentHTML('beforeend','<pre style="position:fixed;left:20px;top:60px;color:#fb7185;z-index:99">'+esc(e&&e.stack||e)+'</pre>'); }); });
})();

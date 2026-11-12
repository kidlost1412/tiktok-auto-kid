// V6 graphics kit renderer.
// node scripts/render_graphics.mjs --script <kich-ban.json> --out <graphics dir> [--only g01,g02] [--no-zone-check] [--no-sheet]
//        [--validator <pipeline-v6/build/validate_script.py>]
// Steps: preflight/layout (kit_layout.py, rejects misfits) -> render each item to
// <id>.mov ProRes 4444 with alpha -> every-frame alpha check (check_frames.py)
// -> contact sheet -> graphics-manifest.json -> atomic swap of <out>.
// All work happens in "<out>.tmp-<stamp>"; on any failure it is kept for
// inspection and <out> is untouched. An existing <out> is renamed to
// "<out>.bak-<stamp>" (never deleted) before the new one is renamed in; if that rename fails the .bak is put back.
// frame items: the shared validator (with media checks) runs first; each clip range (+ crossfade handles) is transcoded to a
// CFR 30 fps proxy in the per-run public dir "<tmp>/public" (fonts copied there too); sources are hashed before and after.
import {bundle} from '@remotion/bundler';
import {renderMedia,selectComposition} from '@remotion/renderer';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {makeProxy,sourceStamp,PROXY_ENCODE} from './frame_proxy.mjs';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'..');
const kitMod=await import(pathToFileURL(path.join(root,'..','pipeline-v6','kitpaths.mjs')).href);
kitMod.useAsciiTemp();// Remotion bundling crashes (0xC0000409) with a non-ASCII TEMP
const kitPython=kitMod.pythonExe();// kit venv python (kitpaths contract), never a bare `python` from PATH
const args=process.argv.slice(2);
const opt=(k)=>{const i=args.indexOf(k);return i>=0?args[i+1]:undefined;};
const flag=(k)=>args.includes(k);
const scriptPath=opt('--script'),outDir=opt('--out');
if(!scriptPath||!outDir){console.error('usage: --script <kich-ban.json> --out <dir>');process.exit(2);}
const sha=(p)=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const fontPath=path.join(root,'public','v6','fonts','BeVietnamPro-Black.ttf');
if(!fs.existsSync(fontPath)){console.error(`missing font ${fontPath}`);process.exit(2);}
const validator=path.resolve(opt('--validator')??path.join(root,'..','pipeline-v6','build','validate_script.py'));
const py=(script,pargs)=>{
 const r=spawnSync(kitPython,[path.join(here,script),...pargs],{stdio:'inherit',env:{...process.env,PYTHONIOENCODING:'utf-8'}});
 if(r.status!==0)throw new Error(`${script} failed (exit ${r.status})`);
};
const stamp=new Date().toISOString().replace(/[-:]/g,'').replace(/\..*/,'');
const out=path.resolve(outDir);
const tmp=`${out}.tmp-${stamp}`;
fs.mkdirSync(tmp,{recursive:true});
const t0=Date.now();
try{
 const scriptSha=sha(scriptPath);// hash of the exact bytes read for this run
 const scriptCopy=path.join(tmp,'kich-ban.input.json');
 fs.copyFileSync(scriptPath,scriptCopy);
 if(sha(scriptCopy)!==scriptSha)throw new Error('script changed while copying');
 const input=JSON.parse(fs.readFileSync(scriptCopy,'utf8').replace(/^﻿/,''));
 const hasFrame=(input.graphics??[]).some(g=>g?.type==='frame');
 if(hasFrame){// shared validator (timing, sources incl. crossfade handles, palette) BEFORE any transcode
  const r=spawnSync(kitPython,['-X','utf8',validator,scriptCopy],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'},maxBuffer:64e6});
  let v=null;try{v=JSON.parse(r.stdout);}catch{/* reported below */}
  if(r.status!==0||!v?.ok)throw new Error(`script invalid (${validator}, exit ${r.status}):\n  `+(v?v.errors.join('\n  '):(r.stdout+r.stderr).slice(-1500)));
  console.log('validator: ok');
 }
 const layoutPath=path.join(tmp,'layout.json');
 py('kit_layout.py',['--script',scriptCopy,'--font',fontPath,'--out',layoutPath,...(flag('--no-zone-check')?['--no-zone-check']:[])]);
 const layout=JSON.parse(fs.readFileSync(layoutPath,'utf8'));
 const only=opt('--only')?.split(',');
 if(only){layout.items=layout.items.filter(i=>only.includes(i.id));fs.writeFileSync(layoutPath,JSON.stringify(layout,null,1));}
 // per-run public dir: every font of the repo public dir (compositions load theirs at import time) + frame proxies
 const pub=path.join(tmp,'public');
 const copyFonts=(rel)=>{for(const e of fs.readdirSync(path.join(root,'public',rel),{withFileTypes:true})){
  const r=path.join(rel,e.name);
  if(e.isDirectory())copyFonts(r);
  else if(/\.(ttf|otf)$/i.test(e.name)){fs.mkdirSync(path.join(pub,rel),{recursive:true});fs.copyFileSync(path.join(root,'public',r),path.join(pub,r));}}};
 copyFonts('');
 const frameSources={};// path -> stamp before transcode
 const frameRecords={};// item id -> [{panel, clip, source, src_start_f, frames, proxy, ...}]
 for(const it of layout.items.filter(i=>i.type==='frame')){
  fs.mkdirSync(path.join(pub,'frame'),{recursive:true});
  frameRecords[it.id]=[];
  it.layout.panels.forEach((pn,pi)=>pn.clips.forEach((c,ci)=>{
   const src=c.proxy.path;
   frameSources[src]??=sourceStamp(src);
   const out=path.join(pub,...c.proxy.src.split('/'));
   const r=makeProxy({src,startF:c.proxy.src_start_f,frames:c.proxy.frames,out});
   Object.assign(c.proxy,{w:r.w,h:r.h});
   frameRecords[it.id].push({panel:pi,clip:ci,source:src,src_start_f:c.proxy.src_start_f,frames:c.proxy.frames,
    timeline_f:[it.f0+c.seq_from,it.f0+c.seq_from+c.seq_len],proxy:c.proxy.src,proxy_sha256:sha(out),proxy_size:[r.w,r.h],ffmpeg_args:r.args.map(a=>a===out?'<proxy>':a)});
   console.log(`proxy ${c.proxy.src} <- ${path.basename(src)} frames ${c.proxy.src_start_f}+${c.proxy.frames} (${r.w}x${r.h})`);
  }));
 }
 fs.writeFileSync(layoutPath,JSON.stringify(layout,null,1));
 console.log('bundling...');
 const serveUrl=await bundle({entryPoint:path.join(root,'src','index.ts'),publicDir:pub});
 const timings={};
 for(const it of layout.items){
  const inputProps={id:it.id,type:it.type,f0:it.f0,f1:it.f1,frames:it.frames,layout:it.layout};
  const composition=await selectComposition({serveUrl,id:'KitElement',inputProps});
  if(composition.durationInFrames!==it.frames)throw new Error(`${it.id}: duration ${composition.durationInFrames} != ${it.frames}`);
  const s=Date.now();
  await renderMedia({serveUrl,composition,inputProps,codec:'prores',proResProfile:'4444',imageFormat:'png',pixelFormat:'yuva444p10le',
   outputLocation:path.join(tmp,`${it.id}.mov`),overwrite:false,logLevel:'warn'});
  timings[it.id]=(Date.now()-s)/1000;
  console.log(`rendered ${it.id} (${it.frames} frames) ${timings[it.id].toFixed(1)}s`);
 }
 const checksPath=path.join(tmp,'frame-checks.json');
 try{py('check_frames.py',['--layout',layoutPath,'--dir',tmp,'--out',checksPath]);}
 catch(e){
  // Only with --no-zone-check (preview of a script whose items are known off-zone): keep going, per-item check_pass=false stays in the manifest.
  if(!flag('--no-zone-check'))throw e;
  console.error(`WARNING (--no-zone-check): ${e.message}; failing items are marked check_pass=false in the manifest`);
 }
 const script=JSON.parse(fs.readFileSync(scriptCopy,'utf8').replace(/^﻿/,''));
 if(!flag('--no-sheet'))py('contact_sheet.py',['--layout',layoutPath,'--dir',tmp,'--main',script.main.path,'--font',fontPath,'--out',path.join(tmp,'contact-sheet.png')]);
 const checks=JSON.parse(fs.readFileSync(checksPath,'utf8'));
 const manifest={
  schema:'graphics-manifest/1',created:new Date().toISOString(),
  script_path:path.resolve(scriptPath),script_sha256:scriptSha,graphics_scale:layout.graphics_scale,
  tools:{remotion:JSON.parse(fs.readFileSync(path.join(root,'node_modules','remotion','package.json'),'utf8')).version,node:process.version,
   kit_files:Object.fromEntries(['src/kit/KitElement.tsx','scripts/kit_layout.py','scripts/check_frames.py','scripts/render_graphics.mjs','scripts/frame_proxy.mjs'].map(f=>[f,sha(path.join(root,f))]))},
  font:{file:'BeVietnamPro-Black.ttf',sha256:sha(fontPath)},
  format:{codec:'prores',profile:'4444',pixel_format_requested:'yuva444p10le',fps:30,width:1080,height:1920,local_frame0:'f0'},
  zones:layout.zones,
  items:layout.items.map(it=>{const c=checks.find(x=>x.id===it.id);return {
   id:it.id,type:it.type,file:`${it.id}.mov`,f0:it.f0,f1:it.f1,frames:it.frames,sha256:sha(path.join(tmp,`${it.id}.mov`)),
   render_seconds:timings[it.id],pix_fmt_decoded:c.pix_fmt,check_pass:c.pass,empty_frames:c.empty_frames,
   alpha_bbox_union:c.union_bbox,alpha_bbox_per_frame:c.bbox_per_frame,layout_blocks:it.layout.blocks,
   ...(it.type==='frame'?{behind_person:it.item.behind_person===true,frame_blocks:it.layout.frame_blocks,frame_clips:frameRecords[it.id]}:{})};}),
  frame_sources:Object.values(frameSources),frame_proxy_encode:PROXY_ENCODE,
  contact_sheet:flag('--no-sheet')?null:{file:'contact-sheet.png',sha256:sha(path.join(tmp,'contact-sheet.png'))},
 };
 fs.writeFileSync(path.join(tmp,'graphics-manifest.json'),JSON.stringify(manifest,null,1));
 if(sha(scriptPath)!==scriptSha)throw new Error('kich-ban.json changed during the render; output not published');
 for(const s0 of Object.values(frameSources)){const s1=sourceStamp(s0.path);
  if(s1.size!==s0.size||s1.mtime_ms!==s0.mtime_ms||s1.sha256!==s0.sha256)throw new Error(`frame source changed during the render: ${s0.path}; output not published`);}
 const bak=`${out}.bak-${stamp}`;
 if(fs.existsSync(out))fs.renameSync(out,bak);
 try{fs.renameSync(tmp,out);}
 catch(e){if(fs.existsSync(bak)&&!fs.existsSync(out))fs.renameSync(bak,out);throw new Error(`publish rename failed (${e.message}); previous output restored from ${bak}`);}
 console.log(`DONE ${layout.items.length} items in ${((Date.now()-t0)/1000).toFixed(1)}s -> ${out}`+(fs.existsSync(`${out}.bak-${stamp}`)?` (previous kept at ${out}.bak-${stamp})`:''));
}catch(e){
 console.error(`FAILED: ${e.message}\nwork dir kept for inspection: ${tmp}; ${out} untouched`);
 process.exit(1);
}

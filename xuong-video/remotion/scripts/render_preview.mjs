// V6 full composite preview (internal review only).
// node scripts/render_preview.mjs --script <kich-ban.json> --graphics <dir with graphics-manifest.json> --voice <wav> --out <mp4>
//        [--subs-lines <wrap_subs json>] [--rembg-python <python.exe>] [--u2net-home <dir>] [--only-frames a:b]
// Prepares "<out>.work/public" (main/B-roll transcodes, graphics, person mattes, audio mix), bundles V6Preview with that
// public dir, renders video only, muxes the offline audio mix. Existing work files are overwritten in place, never deleted.
import {bundle} from '@remotion/bundler';
import {renderMedia,selectComposition} from '@remotion/renderer';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'..');
const args=process.argv.slice(2);
const opt=(k,d)=>{const i=args.indexOf(k);return i>=0?args[i+1]:d;};
const need=(k)=>{const v=opt(k);if(!v){console.error(`missing ${k}`);process.exit(2);}return v;};
const scriptPath=need('--script'),gdir=need('--graphics'),voice=need('--voice'),outMp4=path.resolve(need('--out'));
const subsLinesPath=opt('--subs-lines');
// kit path contract (pipeline-v6/kitpaths.mjs): kit python (has rembg) and the kit-local u2net model dir (U2NET_HOME)
const kit=await import(pathToFileURL(path.join(root,'..','pipeline-v6','kitpaths.mjs')).href);
kit.useAsciiTemp();// Remotion bundling crashes (0xC0000409) with a non-ASCII TEMP
const rembgPy=opt('--rembg-python',kit.pythonExe());
const u2net=opt('--u2net-home',kit.u2netHome());
const only=opt('--only-frames');// "a:b": render just that frame range (debug)
// behind spans (title_behind + behind_person, merged) come from the SAME helper the CapCut builder uses
const {behindSpans,isBehind}=await import(pathToFileURL(path.resolve(opt('--builder',path.join(root,'..','pipeline-v6','build','build_draft.mjs')))).href);
const run=(cmd,a,env={})=>{
 const r=spawnSync(cmd,a,{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8',...env}});
 if(r.status!==0)throw new Error(`${path.basename(cmd)} failed (${r.status}): ${(r.stderr||'').slice(-800)}`);
 return r.stdout;
};
const script=JSON.parse(fs.readFileSync(scriptPath,'utf8').replace(/^﻿/,''));
const manifest=JSON.parse(fs.readFileSync(path.join(gdir,'graphics-manifest.json'),'utf8'));
const N=script.duration_f;
const work=`${outMp4}.work`,pub=path.join(work,'public');
for(const d of ['',  'matte','clips','gfx','v6/fonts'])fs.mkdirSync(path.join(pub,d),{recursive:true});
const copy=(s,d)=>fs.copyFileSync(s,path.join(pub,d));
// every font of the repo public dir (other compositions in the bundle load theirs at import time)
const copyFonts=(rel)=>{for(const e of fs.readdirSync(path.join(root,'public',rel),{withFileTypes:true})){
 const r=path.join(rel,e.name);
 if(e.isDirectory()){fs.mkdirSync(path.join(pub,r),{recursive:true});copyFonts(r);}
 else if(/\.(ttf|otf)$/i.test(e.name))copy(path.join(root,'public',r),r);}};
copyFonts('');
const probe=(f)=>{const j=JSON.parse(run('ffprobe',['-v','error','-select_streams','v:0','-show_entries','stream=width,height:stream_side_data=rotation','-of','json',f]));
 const s=j.streams[0];const rot=Math.abs((s.side_data_list?.[0]?.rotation)||0)%180===90;return rot?{w:s.height,h:s.width}:{w:s.width,h:s.height};};
const x264=['-c:v','libx264','-crf','12','-preset','fast','-pix_fmt','yuv420p','-an','-r','30'];

// main: 971 frames from src_in_f, cover to 1080x1920
console.log('main...');
const mainIn=script.main.src_in_f||0;
run('ffmpeg',['-v','error','-y','-ss',String(mainIn/30),'-i',script.main.path,'-frames:v',String(N),'-vf','scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920',...x264,path.join(pub,'main.mp4')]);
// B-roll: trim to the used range, downscale only when larger than a cover fit at zoom 1
const broll=script.broll.map(b=>{
 const n=b.f1-b.f0;const d=probe(b.path);const k=Math.max(1080/d.w,1920/d.h);
 const even=(v)=>Math.max(2,2*Math.round(v/2));
 const sw=k<1?even(d.w*k):d.w,sh=k<1?even(d.h*k):d.h;
 const dst=`clips/${b.id}.mp4`;
 run('ffmpeg',['-v','error','-y','-ss',String(b.src_in_f/30),'-i',b.path,'-frames:v',String(n),'-vf',`scale=${sw}:${sh}`,...x264,path.join(pub,dst)]);
 const z=b.zoom||{from:1,to:1};
 return {id:b.id,f0:b.f0,f1:b.f1,src:dst,w:sw,h:sh,zoom_from:z.from,zoom_to:z.to,center:b.center||[0.5,0.5]};
});
// graphics clips (from the manifest, ProRes 4444 alpha)
const sg=new Map((script.graphics||[]).map(g=>[g.id,g]));
const graphics=manifest.items.map(it=>{
 const dst=`gfx/${it.file}`;fs.copyFileSync(path.join(gdir,it.file),path.join(pub,dst));
 const g=sg.get(it.id)||{};
 return {id:it.id,type:it.type,f0:it.f0,f1:it.f1,src:dst,behind:isBehind(g),z:g.z??0};
});
// person mattes: computed once per merged span of all behind items (title_behind and behind_person)
const mattes=[];
for(const [i,sp] of behindSpans(script.graphics||[]).entries()){
 const prefix=`span${i}`;
 console.log(`matte ${prefix} (${sp.ids.join('+')}) frames ${sp.f0}-${sp.f1}...`);
 run(rembgPy,['-X','utf8',path.join(here,'preview_mattes.py'),'--video',script.main.path,'--src-in-f',String(mainIn),'--f0',String(sp.f0),'--f1',String(sp.f1),
  '--prefix',prefix,'--outdir',path.join(pub,'matte')],{U2NET_HOME:u2net});
 mattes.push({id:prefix,f0:sp.f0,f1:sp.f1,prefix});
}
// subtitles: lines from wrap_subs output when given, else one line
const lineMap=new Map();
if(subsLinesPath){const sl=JSON.parse(fs.readFileSync(subsLinesPath,'utf8').replace(/^﻿/,''));for(const c of sl.cues)lineMap.set(c.id,c.line_word_counts);}
const subs=script.subs.map(c=>{
 const counts=lineMap.get(c.id)||[c.words.length];
 if(counts.reduce((a,b)=>a+b,0)!==c.words.length)throw new Error(`${c.id}: line_word_counts ${counts} != ${c.words.length} words`);
 let i=0;const lines=counts.map(n=>c.words.slice(i,i+=n));
 return {id:c.id,f0:c.f0,f1:c.f1,lines};
});
const pal=script.style.palette;
const props={duration_f:N,main:{src:'main.mp4',w:1080,h:1920},main_moves:script.main_moves||[],transitions:script.transitions||[],broll,graphics,mattes,subs,
 sub:{font_px:script.sub_style?.font_px??42,center_y:1425,color:pal.sub_text,active:pal.sub_active,bg:pal.sub_bg,bg_alpha:pal.sub_bg_alpha,pad_x:18,pad_y:8,radius:14,line_h:54}};
fs.writeFileSync(path.join(work,'props.json'),JSON.stringify(props,null,1));
// audio
console.log('audio mix...');
const mixWav=path.join(work,'mix.wav');
console.log(run(kit.pythonExe(),['-X','utf8',path.join(here,'preview_audio.py'),'--script',scriptPath,'--voice',voice,'--out',mixWav]));
// render
console.log('bundling...');
const serveUrl=await bundle({entryPoint:path.join(root,'src','index.ts'),publicDir:pub});
const composition=await selectComposition({serveUrl,id:'V6Preview',inputProps:props});
const silent=path.join(work,'video-only.mp4');
const frameRange=only?only.split(':').map(Number):null;
await renderMedia({serveUrl,composition,inputProps:props,codec:'h264',crf:14,imageFormat:'jpeg',jpegQuality:95,muted:true,
 outputLocation:silent,overwrite:true,logLevel:'warn',...(frameRange?{frameRange:[frameRange[0],frameRange[1]-1]}:{}),
 onProgress:({progress})=>{if(Math.round(progress*100)%10===0)process.stdout.write(`\rrender ${Math.round(progress*100)}%`);}});
fs.mkdirSync(path.dirname(outMp4),{recursive:true});
run('ffmpeg',['-v','error','-y','-i',silent,'-i',mixWav,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','256k','-shortest',outMp4]);
console.log(`\nDONE ${outMp4}`);

// Frame style renderer: decoration-only PNG (still) or ProRes 4444 .mov (entrance animation) for a list of boxes.
// node scripts/render_frame_style.mjs --jobs <jobs.json>
//   jobs.json = [{"style": "clean", "params": {...}, "boxes": [{"box": [x0,y0,x1,y1], "radius": 40, "label": {...}}],
//                 "canvas": [1080, 1920], "out": "<file>.png | <file>.mov", "animated": false, "frames": 90, "enter_f": 12}, ...]
// Params are merged over the catalog defaults (frame-styles/catalog.json: style defaults, then label_defaults) and checked
// against params_schema; an unknown style/param or a bad value fails before anything renders. One bundle serves all jobs.
// Each output is written to "<out>.tmp-<pid>" first and renamed into place (an existing file is replaced only by a
// complete render). Prints one JSON line {"ok": true, "outputs": [...]} (or {"ok": false, "error": ...}, exit 1).
import {bundle} from '@remotion/bundler';
import {renderMedia,renderStill,selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
export const root=path.resolve(here,'..');
// Remotion bundling crashes (0xC0000409) with a non-ASCII TEMP: kitpaths.useAsciiTemp moves TEMP/TMP to <drive>:\vk-tmp\<kit-hash8>
(await import(pathToFileURL(path.join(root,'..','pipeline-v6','kitpaths.mjs')).href)).useAsciiTemp();
export const catalogPath=path.join(root,'frame-styles','catalog.json');
export const loadCatalog=()=>JSON.parse(fs.readFileSync(catalogPath,'utf8').replace(/^﻿/,''));

const HEX=/^#[0-9A-Fa-f]{6}$/,HEXA=/^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$/;
export function resolveJob(job,cat=loadCatalog()){
 const st=cat.styles.find(s=>s.id===job.style);
 if(!st)throw new Error(`unknown frame style ${JSON.stringify(job.style)}; known: ${cat.styles.map(s=>s.id).join(', ')}`);
 const params={...cat.label_defaults,...st.defaults,...(job.params??{})};
 for(const [k,v] of Object.entries(params)){
  const sc=cat.params_schema[k];
  if(!sc)throw new Error(`${job.style}: unknown param ${k}`);
  if(sc.type==='number'&&!(typeof v==='number'&&v>=sc.min&&v<=sc.max))throw new Error(`${job.style}: ${k} must be a number in ${sc.min}..${sc.max}, got ${JSON.stringify(v)}`);
  if(sc.type==='color'&&!HEX.test(v))throw new Error(`${job.style}: ${k} must be #RRGGBB, got ${JSON.stringify(v)}`);
  if(sc.type==='color_alpha'&&!HEXA.test(v))throw new Error(`${job.style}: ${k} must be #RRGGBB or #RRGGBBAA, got ${JSON.stringify(v)}`);
 }
 const canvas=job.canvas??[1080,1920];
 if(!(Array.isArray(job.boxes)&&job.boxes.length))throw new Error('boxes must be a non-empty list');
 for(const b of job.boxes){
  const [x0,y0,x1,y1]=b.box??[];
  if(![x0,y0,x1,y1].every(Number.isFinite)||!(x0<x1&&y0<y1))throw new Error(`bad box ${JSON.stringify(b.box)}`);
  if(!(Number.isFinite(b.radius)&&b.radius>=0))throw new Error(`box ${JSON.stringify(b.box)}: radius must be px >= 0`);
  if(b.label!=null&&!(typeof b.label.text==='string'&&b.label.text.trim()))throw new Error('label.text must be a non-empty string');
 }
 const animated=job.animated===true,enter_f=job.enter_f??12,frames=animated?(job.frames??enter_f):1;
 if(!(Number.isInteger(frames)&&frames>=1&&Number.isInteger(enter_f)&&enter_f>=1))throw new Error('frames/enter_f must be integers >= 1');
 const out=path.resolve(job.out);
 if(!/\.(png|mov)$/i.test(out))throw new Error(`out must end in .png or .mov: ${out}`);
 if(/\.mov$/i.test(out)!==animated)throw new Error(`animated ${animated} needs a ${animated?'.mov':'.png'} output: ${out}`);
 return {out,props:{style:st.id,params,boxes:job.boxes.map(b=>({box:b.box,radius:b.radius,label:b.label??null})),canvas,frames,enter_f,animated}};
}

// per-run public dir with only the repo fonts (the repo public dir also holds large videos the bundler would copy)
export const fontsPublic=()=>{
 const pub=fs.mkdtempSync(path.join(os.tmpdir(),'frame-style-pub-'));
 const copy=(rel)=>{for(const e of fs.readdirSync(path.join(root,'public',rel),{withFileTypes:true})){
  const r=path.join(rel,e.name);
  if(e.isDirectory())copy(r);
  else if(/\.(ttf|otf)$/i.test(e.name)){fs.mkdirSync(path.join(pub,rel),{recursive:true});fs.copyFileSync(path.join(root,'public',r),path.join(pub,r));}}};
 copy('');
 if(!fs.existsSync(path.join(pub,'v6','fonts','BeVietnamPro-Black.ttf')))throw new Error('missing public/v6/fonts/BeVietnamPro-Black.ttf');
 return pub;
};

export async function renderJobs(jobs,{log=()=>{}}={}){
 const cat=loadCatalog();
 const resolved=jobs.map(j=>resolveJob(j,cat));// validate everything before bundling
 const pub=fontsPublic();
 try{
  const serveUrl=await bundle({entryPoint:path.join(root,'src','index.ts'),publicDir:pub});
  const outputs=[];
  for(const {out,props} of resolved){
   const composition=await selectComposition({serveUrl,id:'FrameStyle',inputProps:props});
   fs.mkdirSync(path.dirname(out),{recursive:true});
   const tmp=`${out}.tmp-${process.pid}${path.extname(out)}`;
   try{
    if(props.animated)await renderMedia({serveUrl,composition,inputProps:props,codec:'prores',proResProfile:'4444',imageFormat:'png',pixelFormat:'yuva444p10le',outputLocation:tmp,overwrite:true,logLevel:'warn'});
    else await renderStill({serveUrl,composition,inputProps:props,frame:0,imageFormat:'png',output:tmp,overwrite:true,logLevel:'warn'});
    fs.renameSync(tmp,out);
   }finally{if(fs.existsSync(tmp))fs.rmSync(tmp);}
   log(`rendered ${props.style} -> ${out}`);
   outputs.push({out,style:props.style,animated:props.animated,frames:props.frames,params:props.params});
  }
  return outputs;
 }finally{fs.rmSync(pub,{recursive:true,force:true});}
}

if(import.meta.url===pathToFileURL(process.argv[1]).href){
 const args=process.argv.slice(2);const i=args.indexOf('--jobs');
 try{
  if(i<0)throw new Error('usage: --jobs <jobs.json>');
  const jobs=JSON.parse(fs.readFileSync(args[i+1],'utf8').replace(/^﻿/,''));
  const outputs=await renderJobs(Array.isArray(jobs)?jobs:[jobs],{log:m=>console.error(m)});
  console.log(JSON.stringify({ok:true,outputs}));
 }catch(e){console.log(JSON.stringify({ok:false,error:String(e.message??e)}));process.exit(1);}
}

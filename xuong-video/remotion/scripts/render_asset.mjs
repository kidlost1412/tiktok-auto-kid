// Asset renderer (CapCut-native graphics): transparent PNG stills of the Asset composition (src/assets/Asset.tsx).
// node scripts/render_asset.mjs --jobs <jobs.json>
//   jobs.json = [{"kind": "tick", "params": {"d": 44, "fill": "#1F9E46", "mark": "#FFFFFF"}, "out": "<file>.png"},
//                {"kind": "ellipse", "params": {"rx": 205, "ry": 78, "stroke": 11, "outline": 25, "color": "#E1262D",
//                 "outline_color": "#FFFFFF", "points": [[x, y], ...]}, "out": "<file>.png"}, ...]
// Canvas: tick d x d; ellipse = the drawn ellipse's extent (max |point| x radius + outline/2 + 2 px pad) each side, even sizes,
// ellipse centre = canvas centre. Everything is validated before bundling; each output goes to "<out>.tmp-<pid>.png" and is
// renamed into place. Prints one JSON line {"ok": true, "outputs": [{out, width, height}]} or {"ok": false, "error"} (exit 1).
import {bundle} from '@remotion/bundler';
import {renderStill,selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {fontsPublic} from './render_frame_style.mjs';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'..');
const HEX=/^#[0-9A-Fa-f]{6}$/;
const num=(v,lo)=>typeof v==='number'&&Number.isFinite(v)&&v>=lo;

export function resolveAsset(job){
 const p=job.params??{};
 const out=path.resolve(job.out??'');
 if(!/\.png$/i.test(out))throw new Error(`out must end in .png: ${out}`);
 if(job.kind==='tick'){
  if(!(Number.isInteger(p.d)&&p.d>=4))throw new Error('tick: d must be an integer >= 4 (px)');
  if(!HEX.test(p.fill)||!HEX.test(p.mark))throw new Error('tick: fill and mark must be #RRGGBB');
  return {out,props:{kind:'tick',width:p.d,height:p.d,params:{fill:p.fill,mark:p.mark}}};
 }
 if(job.kind==='ellipse'){
  for(const k of ['rx','ry','stroke','outline'])if(!num(p[k],1))throw new Error(`ellipse: ${k} must be a number >= 1`);
  if(!HEX.test(p.color)||!HEX.test(p.outline_color))throw new Error('ellipse: color and outline_color must be #RRGGBB');
  if(!(Array.isArray(p.points)&&p.points.length>=3&&p.points.every(q=>Array.isArray(q)&&q.length===2&&q.every(Number.isFinite))))throw new Error('ellipse: points must be [[x, y], ...] (unit circle)');
  const ext=Math.max(p.stroke,p.outline)/2+2;
  const hw=Math.max(...p.points.map(q=>Math.abs(q[0])))*p.rx+ext,hh=Math.max(...p.points.map(q=>Math.abs(q[1])))*p.ry+ext;
  const even=v=>2*Math.ceil(v);
  return {out,props:{kind:'ellipse',width:even(hw),height:even(hh),params:p}};
 }
 throw new Error(`unknown asset kind ${JSON.stringify(job.kind)} (tick | ellipse)`);
}

export async function renderAssets(jobs){
 const resolved=jobs.map(resolveAsset);
 const pub=fontsPublic();// fonts only (the bundle loads the kit fonts; the repo public dir holds large videos)
 try{
  const serveUrl=await bundle({entryPoint:path.join(root,'src','index.ts'),publicDir:pub});
  const outputs=[];
  for(const {out,props} of resolved){
   const composition=await selectComposition({serveUrl,id:'Asset',inputProps:props});
   fs.mkdirSync(path.dirname(out),{recursive:true});
   const tmp=`${out}.tmp-${process.pid}.png`;
   try{
    await renderStill({serveUrl,composition,inputProps:props,frame:0,imageFormat:'png',output:tmp,overwrite:true,logLevel:'warn'});
    fs.renameSync(tmp,out);
   }finally{if(fs.existsSync(tmp))fs.rmSync(tmp);}
   outputs.push({out,width:props.width,height:props.height});
  }
  return outputs;
 }finally{fs.rmSync(pub,{recursive:true,force:true});}
}

if(import.meta.url===pathToFileURL(process.argv[1]).href){
 const args=process.argv.slice(2);const i=args.indexOf('--jobs');
 try{
  if(i<0)throw new Error('usage: --jobs <jobs.json>');
  const jobs=JSON.parse(fs.readFileSync(args[i+1],'utf8').replace(/^﻿/,''));
  console.log(JSON.stringify({ok:true,outputs:await renderAssets(Array.isArray(jobs)?jobs:[jobs])}));
 }catch(e){console.log(JSON.stringify({ok:false,error:String(e.message??e)}));process.exit(1);}
}

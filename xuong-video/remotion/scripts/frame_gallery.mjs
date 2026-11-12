// Contact sheet of the frame style library so the requester can pick / reject styles.
// node scripts/frame_gallery.mjs [--out frame-styles/gallery/gallery.jpg] [--profile <profile.json>] [--python <python.exe>]
// Per catalog style two tiles on a sample scene: a 2x2 grid and one card with a label badge (Vietnamese text). With
// --profile, tiles of liked/rejected styles are captioned accordingly. PNG renders go to "<out dir>/tiles/".
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {loadCatalog,renderJobs,root} from './render_frame_style.mjs';

const here=path.dirname(fileURLToPath(import.meta.url));
const args=process.argv.slice(2);
const opt=(k,d)=>{const i=args.indexOf(k);return i>=0?args[i+1]:d;};
const out=path.resolve(opt('--out',path.join(root,'frame-styles','gallery','gallery.jpg')));
const python=opt('--python',process.env.FRAME_PYTHON??(await import(pathToFileURL(path.join(root,'..','pipeline-v6','kitpaths.mjs')).href)).pythonExe());
const tiles=path.join(path.dirname(out),'tiles');
// sample geometry: 2x2 grid with even 40 px margins (L14), radius = 0.12 * min(w,h)/2 (CapCut grid default round 0.12, see README)
const R=(b,round)=>Math.round(round*Math.min(b[2]-b[0],b[3]-b[1])/2*100)/100;
const GRID=[[40,260,520,900],[560,260,1040,900],[40,940,520,1580],[560,940,1040,1580]];
const CARD=[150,420,930,1130];
export const SAMPLES={grid:GRID.map(b=>({box:b,radius:R(b,0.12)})),
 card:[{box:CARD,radius:R(CARD,0.10),label:{text:'KHÁCH HÀNG THẬT',corner:'tl'}}]};
const cat=loadCatalog();
const jobs=[];
for(const s of cat.styles)for(const [k,boxes] of Object.entries(SAMPLES))jobs.push({style:s.id,boxes,out:path.join(tiles,`${s.id}-${k}.png`)});
try{
 await renderJobs(jobs,{log:m=>console.error(m)});
 fs.writeFileSync(path.join(tiles,'samples.json'),JSON.stringify(SAMPLES));
 const r=spawnSync(python,[path.join(here,'frame_gallery_sheet.py'),'--tiles',tiles,'--out',out,...(opt('--profile')?['--profile',opt('--profile')]:[])],{stdio:'inherit'});
 if(r.status!==0)throw new Error(`frame_gallery_sheet.py failed (exit ${r.status})`);
 console.log(JSON.stringify({ok:true,gallery:out,styles:cat.styles.map(s=>s.id)}));
}catch(e){console.log(JSON.stringify({ok:false,error:String(e.message??e)}));process.exit(1);}

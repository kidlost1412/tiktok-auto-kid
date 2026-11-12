// CFR 30 fps proxies of B-roll source ranges for the `frame` graphic (Remotion cannot read the original paths).
// Proxy frame k = the source frame displayed at (startF + k) / 30 s, for any source frame rate (24 / 29.58 / 29.97 / 30):
// seek 2 s early keeping the original timestamps, then fps=30 with round=up starting exactly at the in-point
// (round=up = latest source frame whose pts <= the output tick), timestamps reset to 0, exact frame count, no audio.
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';

export const PROXY_ENCODE=['-c:v','libx264','-crf','12','-preset','fast','-pix_fmt','yuv420p','-an'];

const run=(cmd,args)=>{
 const r=spawnSync(cmd,args,{encoding:'utf8',maxBuffer:64e6});
 if(r.status!==0)throw new Error(`${cmd} failed (${r.status}): ${(r.stderr||'').slice(-600)}`);
 return r.stdout;
};

// container start time (s): ffmpeg -ss is relative to it, -copyts timestamps are not
export const startTime=(src)=>{const v=run('ffprobe',['-v','error','-show_entries','format=start_time','-of','csv=p=0',src]).trim();return v&&v!=='N/A'?Number(v):0;};

export function proxyArgs({src,startF,frames,out,start=0}){
 const t=startF/30;
 return ['-v','error','-y','-ss',Math.max(0,t-2).toFixed(6),'-copyts','-i',src,'-map','0:v:0',
  '-vf',`fps=30:round=up:start_time=${(start+t).toFixed(6)},setpts=PTS-STARTPTS,scale=trunc(iw/2)*2:trunc(ih/2)*2`,
  '-frames:v',String(frames),...PROXY_ENCODE,out];
}

export const sha256File=(p)=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
export const sourceStamp=(p)=>{const st=fs.statSync(p);return {path:p,size:st.size,mtime_ms:st.mtimeMs,sha256:sha256File(p)};};

// Transcode, then verify frame count / rate / no audio. Returns {w, h, frames, args}.
export function makeProxy({src,startF,frames,out}){
 if(!Number.isInteger(startF)||startF<0||!Number.isInteger(frames)||frames<1)throw new Error(`bad proxy range ${startF}+${frames} for ${src}`);
 const args=proxyArgs({src,startF,frames,out,start:startTime(src)});
 run('ffmpeg',args);
 const j=JSON.parse(run('ffprobe',['-v','error','-count_frames','-show_entries','stream=codec_type,width,height,nb_read_frames,r_frame_rate','-of','json',out]));
 const v=j.streams.find(s=>s.codec_type==='video');
 if(j.streams.some(s=>s.codec_type==='audio'))throw new Error(`proxy ${out} has audio`);
 if(Number(v.nb_read_frames)!==frames)throw new Error(`proxy ${out}: ${v.nb_read_frames} frames != ${frames} (source ${src} too short from frame ${startF}?)`);
 if(v.r_frame_rate!=='30/1')throw new Error(`proxy ${out}: rate ${v.r_frame_rate} != 30/1`);
 return {w:v.width,h:v.height,frames,args};
}

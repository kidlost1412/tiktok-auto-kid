// V6 full composite PREVIEW (internal aesthetic review, not a deliverable).
// Everything is positioned from props prepared by scripts/render_preview.mjs from kich-ban.json (frame-accurate).
// Layer order bottom -> top: main, behind graphics (title_behind + behind_person; z asc, then f0), person matte of main (one per merged
// behind span), B-roll, other graphics (z asc, then f0), subtitles. Same stacking as the CapCut builder.
// CapCut matting is approximated by pre-computed rembg mattes of the main video.
import {loadFont} from '@remotion/fonts';
import React from 'react';
import {AbsoluteFill,Img,OffthreadVideo,Sequence,staticFile,useCurrentFrame} from 'remotion';

const SUB_FONT='V6 DT-PhuDu';
loadFont({family:SUB_FONT,url:staticFile('DTPhudu-Black.otf'),weight:'900'});

type Move={f0:number;f1:number;zoom_from:number;zoom_to:number;center:[number,number]};
type Clip={id:string;f0:number;f1:number;src:string;w:number;h:number;zoom_from:number;zoom_to:number;center:[number,number]};
type Gfx={id:string;type:string;f0:number;f1:number;src:string;behind?:boolean;z?:number};
type Word={text:string;f0:number;f1:number};
type Cue={id:string;f0:number;f1:number;lines:Word[][]};
type Trans={at_f:number;slug:string;dur_f:number};
export type PreviewProps={transitions?:Trans[];
 duration_f:number;main:{src:string;w:number;h:number};main_moves:Move[];broll:Clip[];graphics:Gfx[];
 mattes:{id:string;f0:number;f1:number;prefix:string}[];subs:Cue[];
 sub:{font_px:number;center_y:number;color:string;active:string;bg:string;bg_alpha:number;pad_x:number;pad_y:number;radius:number;line_h:number};
};

const hex=(c:string,a:number)=>{const n=parseInt(c.slice(1),16);return `rgba(${n>>16&255},${n>>8&255},${n&255},${a})`;};

// Cover fit + zoom z about normalised point c, c mapped to the canvas centre (540,960); linear z over the n frames.
const placed=(w:number,h:number,z:number,c:[number,number]):React.CSSProperties=>{
 const k=Math.max(1080/w,1920/h);const Wc=w*k,Hc=h*k;
 return {position:'absolute',left:540-z*c[0]*Wc,top:960-z*c[1]*Hc,width:z*Wc,height:z*Hc};
};
const lerp=(a:number,b:number,f:number,n:number)=>a+(b-a)*(n>1?f/(n-1):0);

const mainStyle=(frame:number,m:{w:number;h:number},moves:Move[])=>{
 const mv=moves.find(x=>frame>=x.f0&&frame<x.f1);
 return mv?placed(m.w,m.h,lerp(mv.zoom_from,mv.zoom_to,frame-mv.f0,mv.f1-mv.f0),mv.center):placed(m.w,m.h,1,[0.5,0.5]);
};

const Subs:React.FC<{cues:Cue[];S:PreviewProps['sub']}>=({cues,S})=>{
 const f=useCurrentFrame();
 const cue=cues.find(c=>f>=c.f0&&f<c.f1);
 if(!cue)return null;
 const all=cue.lines.flat();
 const hot=[...all].reverse().find(w=>f>=w.f0);// last started word stays highlighted through pauses
 return <div style={{position:'absolute',left:0,width:1080,top:S.center_y,transform:'translateY(-50%)',display:'flex',justifyContent:'center'}}>
  <div style={{background:hex('#000000',S.bg_alpha),borderRadius:S.radius,padding:`${S.pad_y}px ${S.pad_x}px`,textAlign:'center'}}>
   {cue.lines.map((ln,i)=><div key={i} style={{fontFamily:SUB_FONT,fontWeight:900,fontSize:S.font_px,lineHeight:`${S.line_h}px`,whiteSpace:'nowrap'}}>
    {ln.map((w,j)=><span key={j} style={{color:w===hot?S.active:S.color}}>{w.text.toUpperCase()}{j<ln.length-1?' ':''}</span>)}
   </div>)}
  </div>
 </div>;
};

// APPROXIMATION of the CapCut transitions (woosh / horizontal-blur / pull-in): a directional blur + slide (or push-in)
// centred on the cut, applied to the picture layers only (not graphics above B-roll, not subtitles). Not the real CapCut effect.
const Transition:React.FC<{ts:Trans[];children:React.ReactNode}>=({ts,children})=>{
 const f=useCurrentFrame();
 const t=ts.find(x=>f>=x.at_f-x.dur_f/2&&f<x.at_f+x.dur_f/2);
 let style:React.CSSProperties={position:'absolute',inset:0},blur=0;
 if(t){
  const q=(f-(t.at_f-t.dur_f/2)+0.5)/t.dur_f;const I=Math.sin(Math.PI*q);
  if(t.slug==='pull-in'){style={...style,transform:`scale(${1+0.18*I})`};blur=10*I;}
  else if(t.slug==='horizontal-blur'){style={...style,transform:`scale(${1+0.06*I})`};blur=34*I;}
  else{const dx=q<0.5?-(q/0.5)*90:(1-(q-0.5)/0.5)*90;style={...style,transform:`translateX(${dx}px) scale(${1+0.1*I})`};blur=26*I;}
  if(blur>0)style={...style,filter:'url(#hblur)'};
 }
 return <AbsoluteFill>
  <svg width={0} height={0} style={{position:'absolute'}}><filter id="hblur" x="-20%" y="-5%" width="140%" height="110%"><feGaussianBlur stdDeviation={`${blur} ${t&&t.slug==='pull-in'?blur:0}`}/></filter></svg>
  <div style={style}>{children}</div>
 </AbsoluteFill>;
};

export const V6Preview:React.FC<PreviewProps>=(p)=>{
 const f=useCurrentFrame();
 const ms=mainStyle(f,p.main,p.main_moves);
 const byZ=(a:Gfx,b:Gfx)=>(a.z??0)-(b.z??0)||a.f0-b.f0;
 const behind=p.graphics.filter(g=>g.behind??g.type==='title_behind').sort(byZ);
 const others=p.graphics.filter(g=>!(g.behind??g.type==='title_behind')).sort(byZ);
 const gfx=(g:Gfx)=><Sequence key={g.id} from={g.f0} durationInFrames={g.f1-g.f0} layout="none">
  <OffthreadVideo src={staticFile(g.src)} transparent muted style={{position:'absolute',left:0,top:0,width:1080,height:1920}}/>
 </Sequence>;
 return <AbsoluteFill style={{backgroundColor:'#000'}}>
  <Transition ts={p.transitions??[]}>
  <OffthreadVideo src={staticFile(p.main.src)} muted style={ms}/>
  {behind.map(gfx)}
  {p.mattes.map(m=><Sequence key={m.id} from={m.f0} durationInFrames={m.f1-m.f0} layout="none">
   <MatteImg prefix={m.prefix} style={ms}/>
  </Sequence>)}
  {p.broll.map(b=><Sequence key={b.id} from={b.f0} durationInFrames={b.f1-b.f0} layout="none">
   <BRoll b={b}/>
  </Sequence>)}
  </Transition>
  {others.map(gfx)}
  <Subs cues={p.subs} S={p.sub}/>
 </AbsoluteFill>;
};

const MatteImg:React.FC<{prefix:string;style:React.CSSProperties}>=({prefix,style})=>{
 const f=useCurrentFrame();// inside the Sequence: local frame
 return <Img src={staticFile(`matte/${prefix}-${f}.png`)} style={style}/>;
};

const BRoll:React.FC<{b:Clip}>=({b})=>{
 const f=useCurrentFrame();const n=b.f1-b.f0;
 return <OffthreadVideo src={staticFile(b.src)} muted style={placed(b.w,b.h,lerp(b.zoom_from,b.zoom_to,f,n),b.center)}/>;
};

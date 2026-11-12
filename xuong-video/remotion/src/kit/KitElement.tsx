// V6 graphics kit: one graphics item of kich-ban.json per render, on a full
// 1080x1920 transparent canvas, local frame 0 = item.f0 (R1).
// All geometry comes precomputed from scripts/kit_layout.py (props.layout);
// this file only draws and animates it.
import {loadFont} from '@remotion/fonts';
import React,{useEffect} from 'react';
import {AbsoluteFill,Easing,Img,OffthreadVideo,Sequence,cancelRender,continueRender,delayRender,interpolate,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';

const FONT='V6 BeVietnamPro Black';
loadFont({family:FONT,url:staticFile('v6/fonts/BeVietnamPro-Black.ttf'),weight:'900'});

const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
type Box=[number,number,number,number];
type Line={text:string;size:number;lh:number;top:number;color:string;w:number};
type Row={text:string;lf:number;x:number;y:number;w:number;h:number;tw:number};
type Key={f:number;cx:number;cy:number;rx:number;ry:number};
export type Palette={card_bg:string;card_border:string;card_shadow:string;card_text:string;card_accent:string;pill_bg:string;pill_text:string;tick:string;circle:string;circle_outline:string;cta_bg:string;cta_text:string;
 frame_border?:string;frame_label_bg?:string;frame_label_text?:string};
type FrameLabel={text:string;box:Box;tw:number;lh:number;font_size:number;pad_x:number;text_top:number;pop_in:boolean;pop_out:boolean};
type FrameClip={f0:number;f1:number;seq_from:number;seq_len:number;h_in:number;h_out:number;zoom_from:number;zoom_to:number;easing:string;center:[number,number];
 proxy:{src:string;w?:number;h?:number};label:FrameLabel|null};
type FramePanel={box:Box;f_in:number;enter:'pop'|'slide'|'none'|'fade';clips:FrameClip[];feather?:{top:number;bottom:number;left:number;right:number}};
type Label={text:string;box:Box;tw:number;lh:number;font_size:number;pad_x:number};
export type KitLayout={palette:Palette;box?:Box;lines?:Line[];rows?:Row[];lh?:number;font_size?:number;tw?:number;arrow?:[number,number,number];text?:string;unit_points?:[number,number][];keys?:Key[];pred_bbox:Box;
 dims?:Record<string,number>;baseline?:number;src?:string;canvas?:[number,number,number,number];center?:[number,number];label?:Label;peak?:number;fill?:string;tip?:[number,number];highlight_active?:boolean;highlight_f?:number;exit_none?:boolean;title_style?:'fill'|'outline';rotate_deg?:number;rotate_center?:[number,number];accent?:{text:string;size:number;baseline:number;outline:number};body?:[number,number][];head?:[number,number][];
 panels?:FramePanel[];xfade_f?:number;style?:'card'|'blend'};
export type KitProps={id:string;type:'keyword'|'checklist'|'circle'|'cta'|'title_behind'|'cutout'|'flash'|'big_text'|'arrow'|'frame';f0:number;f1:number;frames:number;layout:KitLayout};

const text=(size:number,lh:number):React.CSSProperties=>({fontFamily:FONT,fontWeight:900,fontSize:size,lineHeight:`${lh}px`,whiteSpace:'nowrap'});

// Fail loudly if any text is wider than the box the layout reserved for it.
const useFitCheck=(id:string)=>{
 const frame=useCurrentFrame();
 useEffect(()=>{
  const h=delayRender(`fit check ${id}`);
  document.fonts.ready.then(()=>{
   document.querySelectorAll<HTMLElement>('[data-fit]').forEach(el=>{
    if(el.scrollWidth>el.clientWidth+1)cancelRender(new Error(`${id}: text "${el.textContent}" overflows (${el.scrollWidth} > ${el.clientWidth}px)`));
   });
   continueRender(h);
  });
 },[frame,id]);
};

// Common out: last 5 frames shrink/fade, never fully empty (every frame keeps alpha).
// item.exit === 'none' (layout.exit_none): no out animation, full opacity/scale through the last frame.
const outAnim=(f:number,n:number,L:KitLayout)=>L.exit_none?{o:1,s:1}:({o:interpolate(f,[n-6,n-1],[1,0.2],clamp),s:interpolate(f,[n-6,n-1],[1,0.9],clamp)});

const Keyword:React.FC<KitProps>=({layout:L,frames})=>{
 const P=L.palette;const D=L.dims!;const f=useCurrentFrame();
 const [x0,y0,x1,y1]=L.box!;const w=x1-x0,h=y1-y0;
 const sIn=interpolate(f,[0,4,7],[0.6,1.06,1],clamp);const oIn=interpolate(f,[0,3],[0.3,1],clamp);
 const out=outAnim(f,frames,L);
 return <div style={{position:'absolute',left:x0,top:y0,width:w,height:h,transform:`rotate(${-2+(L.rotate_deg??0)}deg) scale(${sIn*out.s})`,opacity:oIn*out.o}}>
  <div style={{position:'absolute',left:D.shadow,top:D.shadow,width:w,height:h,borderRadius:D.radius,background:P.card_shadow}}/>
  <div style={{position:'absolute',inset:0,borderRadius:D.radius,background:P.card_bg,border:`${D.border}px solid ${P.card_border}`}}/>
  {L.lines!.map((l,i)=><div key={i} data-fit style={{...text(l.size,l.lh),position:'absolute',left:0,width:w,top:l.top,textAlign:'center',color:l.color}}>{l.text}</div>)}
 </div>;
};

const Tick:React.FC<{d:number;fill:string;mark:string}>=({d,fill,mark})=><svg width={d} height={d} viewBox="0 0 52 52" style={{flex:'none'}}>
 <circle cx="26" cy="26" r="26" fill={fill}/>
 <path d="M14 27 L23 36 L39 18" fill="none" stroke={mark} strokeWidth="7" strokeLinecap="round" strokeLinejoin="round"/>
</svg>;

const Checklist:React.FC<KitProps>=({layout:L,frames})=>{
 const P=L.palette;const D=L.dims!;const f=useCurrentFrame();const out=outAnim(f,frames,L);
 const shown=L.rows!.filter(r=>f>=r.lf);const newest=shown.length?Math.max(...shown.map(r=>r.lf)):-1;
 return <>{shown.map(r=>{
  const k=f-r.lf;
  const hot=!!L.highlight_active&&r.lf===newest&&k<(L.highlight_f??20);
  return <div key={r.text} style={{position:'absolute',left:r.x,top:r.y,width:r.w,height:r.h,borderRadius:999,background:hot?P.card_accent:P.pill_bg,
   transform:`translateX(${interpolate(k,[0,6],[-D.slide,0],clamp)}px)`,opacity:interpolate(k,[0,3],[0.35,1],clamp)*out.o,
   display:'flex',alignItems:'center',paddingLeft:D.pad_l,boxSizing:'border-box'}}>
   <Tick d={D.tick} fill={P.tick} mark={P.pill_bg}/>
   <div data-fit style={{...text(L.font_size!,L.lh!),marginLeft:D.tick_gap,width:r.tw,color:P.pill_text}}>{r.text}</div>
  </div>;})}</>;
};

// Ease-in-out (smoothstep) between consecutive keys; same formula as circle_geom() in kit_layout.py.
const lerpKeys=(keys:Key[],g:number)=>{
 const ks=[...keys].sort((a,b)=>a.f-b.f);
 if(g<=ks[0].f)return ks[0];
 for(let i=1;i<ks.length;i++){
  if(g<=ks[i].f){
   const a=ks[i-1],b=ks[i];let u=(g-a.f)/(b.f-a.f);u=u*u*(3-2*u);
   return {cx:a.cx+(b.cx-a.cx)*u,cy:a.cy+(b.cy-a.cy)*u,rx:a.rx+(b.rx-a.rx)*u,ry:a.ry+(b.ry-a.ry)*u};
  }
 }
 return ks[ks.length-1];
};

const Circle:React.FC<KitProps>=({layout:L,f0,frames})=>{
 const P=L.palette;const D=L.dims!;const f=useCurrentFrame();
 const {cx,cy,rx,ry}=lerpKeys(L.keys!,f0+f);
 const d=L.unit_points!.map((p,i)=>`${i?'L':'M'}${(cx+p[0]*rx).toFixed(2)} ${(cy+p[1]*ry).toFixed(2)}`).join(' ');
 const p=interpolate(f,[0,9],[0.1,1],clamp);// draw-on over 10 frames, frame 0 already visible
 const out=outAnim(f,frames,L);
 const dash={pathLength:1,strokeDasharray:`${p} 2`,fill:'none',strokeLinecap:'round' as const,strokeLinejoin:'round' as const};
 return <svg viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,width:1080,height:1920,opacity:out.o}}>
  <path d={d} {...dash} stroke={P.circle_outline} strokeWidth={D.outline}/>
  <path d={d} {...dash} stroke={P.circle} strokeWidth={D.stroke}/>
 </svg>;
};

// arrow: curved body draws on over 7 frames, the head strokes appear at frame 5 (8-frame draw-on in total).
const Arrow:React.FC<KitProps>=({layout:L,frames})=>{
 const P=L.palette;const D=L.dims!;const f=useCurrentFrame();const out=outAnim(f,frames,L);
 const body=L.body!.map((p,i)=>`${i?'L':'M'}${p[0]} ${p[1]}`).join(' ');
 const [tx,ty]=L.tip!;
 const head=f>=5?`M${L.head![0][0]} ${L.head![0][1]} L${tx} ${ty} L${L.head![1][0]} ${L.head![1][1]}`:'';
 const p=interpolate(f,[0,7],[0.1,1],clamp);
 const common={fill:'none',strokeLinecap:'round' as const,strokeLinejoin:'round' as const};
 return <svg viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,width:1080,height:1920,opacity:out.o}}>
  <path d={body} pathLength={1} strokeDasharray={`${p} 2`} {...common} stroke={P.circle_outline} strokeWidth={D.outline}/>
  {head&&<path d={head} {...common} stroke={P.circle_outline} strokeWidth={D.outline}/>}
  <path d={body} pathLength={1} strokeDasharray={`${p} 2`} {...common} stroke={P.circle} strokeWidth={D.stroke}/>
  {head&&<path d={head} {...common} stroke={P.circle} strokeWidth={D.stroke}/>}
 </svg>;
};

// big_text: the key number. Scale-in 0.3 -> peak (<=1.08) -> 1.0 over 9 frames with a stretched ghost on frames 1-3,
// hold, 5-frame out. Fill card_accent, card_bg outline outside the glyphs, soft dark glow.
const BigText:React.FC<KitProps>=({layout:L,frames})=>{
 const P=L.palette;const D=L.dims!;const f=useCurrentFrame();
 const [cx,cy]=L.center!;
 const sAt=(g:number)=>interpolate(g,[0,5,D.in_f],[0.3,D.peak,1],{...clamp,easing:Easing.out(Easing.cubic)});
 const out=L.exit_none?0:interpolate(f,[frames-D.out_f,frames-1],[0,1],clamp);
 const sc=sAt(f)*(1-0.1*out);const o=interpolate(f,[0,2],[0.4,1],clamp)*(1-0.8*out);
 const glyph=(key:string,tf:string)=><g key={key} transform={tf}>
  {L.accent&&<text x={540} y={L.accent.baseline} textAnchor="middle" fontFamily={FONT} fontWeight={900} fontSize={L.accent.size} fill={P.card_text}
   stroke={P.card_bg} strokeWidth={L.accent.outline*2} strokeLinejoin="round" paintOrder="stroke">{L.accent.text}</text>}
  <text x={540} y={L.baseline} textAnchor="middle" fontFamily={FONT} fontWeight={900} fontSize={L.font_size} fill={P.card_accent}
   stroke={P.card_bg} strokeWidth={D.outline*2} strokeLinejoin="round" paintOrder="stroke">{L.text}</text>
 </g>;
 const at=(m:number,sx:number,sy:number)=>`translate(${cx} ${cy}) scale(${m*sx} ${m*sy}) translate(${-cx} ${-cy})`;
 // motion-blur feel on frames 1-3: two vertically stretched trails at the scales of the previous frames (always inside the current bbox)
 const ghosts=f>=1&&f<=3?[[1,0.5],[2,0.28]]:[];
 const [rx,ry]=L.rotate_center??[cx,cy];
 return <svg viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,width:1080,height:1920,opacity:o,filter:`drop-shadow(0 0 ${D.glow*0.8}px rgba(0,0,0,0.7))`}}>
  <g transform={`rotate(${L.rotate_deg??0} ${rx} ${ry})`}>
   {ghosts.map(([back,a],i)=><g key={i} opacity={a}>{glyph(`g${i}`,at(sAt(f-back),1,1.12))}</g>)}
   {glyph('main',at(sc,1,1))}
  </g>
 </svg>;
};

const Cta:React.FC<KitProps>=({layout:L,frames})=>{
 const P=L.palette;const D=L.dims!;const f=useCurrentFrame();
 const [x0,y0,x1,y1]=L.box!;const [ax,ay,a]=L.arrow!;
 const sIn=interpolate(f,[0,4,7],[0.7,1.05,1],clamp);const oIn=interpolate(f,[0,3],[0.3,1],clamp);const out=outAnim(f,frames,L);
 const b=D.bounce*Math.abs(Math.sin(Math.PI*(f%20)/20));// 20-frame bounce loop toward down-left
 return <div style={{position:'absolute',left:x0,top:y0,width:x1-x0,height:y1-y0,transform:`scale(${sIn*out.s})`,opacity:oIn*out.o}}>
  <div style={{position:'absolute',inset:0,borderRadius:999,background:P.cta_bg}}/>
  <div data-fit style={{...text(L.font_size!,L.lh!),position:'absolute',left:D.pad_l,top:(y1-y0-L.lh!)/2,width:L.tw,color:P.cta_text}}>{L.text}</div>
  <svg width={a} height={a} viewBox="0 0 54 54" style={{position:'absolute',left:ax-x0-b,top:ay-y0+b}}>
   <path d="M44 10 L14 40 M14 18 L14 40 L36 40" fill="none" stroke={P.cta_text} strokeWidth="8" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
 </div>;
};

// title_behind: text only on transparent; the builder puts a matted copy of the speaker above it.
// Slam 1.6->1.0 over 4 frames, 2-frame shake, hold, last 3 frames fade. Opacity never reaches 0 (every frame keeps alpha).
const SHAKE:[number,number][]=[[6,-3],[-5,3]];
const Title:React.FC<KitProps>=({layout:L,frames})=>{
 const P=L.palette;const D=L.dims!;const f=useCurrentFrame();
 const y=L.baseline!;const cy=L.center?L.center[1]:(L.pred_bbox[1]+L.pred_bbox[3])/2;
 const s=interpolate(f,[0,3],[1.6,1],{...clamp,easing:Easing.out(Easing.cubic)});
 const o=interpolate(f,[0,3],[0.2,1],clamp)*(L.exit_none?1:interpolate(f,[frames-4,frames-1],[1,0.2],clamp));
 const [dx,dy]=f>=4&&f<6?SHAKE[f-4]:[0,0];
 return <svg viewBox="0 0 1080 1920" style={{position:'absolute',inset:0,width:1080,height:1920,opacity:o}}>
  <g transform={`translate(${dx} ${dy}) translate(540 ${cy}) scale(${s}) rotate(${L.rotate_deg??0}) translate(-540 ${-cy})`}>
   {L.title_style==='outline'?<>
    {/* outline: transparent letters, stroke centred on the glyph edge in the fill colour, dark halo (halo px each side) underneath */}
    <text x={540} y={y} textAnchor="middle" fontFamily={FONT} fontWeight={900} fontSize={L.font_size} fill="none"
     stroke={P.card_bg} strokeWidth={D.stroke_w+2*D.halo} strokeLinejoin="round">{L.text}</text>
    <text x={540} y={y} textAnchor="middle" fontFamily={FONT} fontWeight={900} fontSize={L.font_size} fill="none"
     stroke={L.fill??P.card_text} strokeWidth={D.stroke_w} strokeLinejoin="round">{L.text}</text>
   </>:
   <text x={540} y={y} textAnchor="middle" fontFamily={FONT} fontWeight={900} fontSize={L.font_size} fill={L.fill??P.card_text}
    stroke={P.card_bg} strokeWidth={D.outline*2} strokeLinejoin="round" paintOrder="stroke">{L.text}</text>}
  </g>
 </svg>;
};

// cutout: PNG (white outline + shadow already baked in by kit_layout.py) popping in with overshoot and slight rotation,
// floating while held, scaling down over the last frames. The label pill rides in the same group.
const Cutout:React.FC<KitProps>=({layout:L,frames})=>{
 const P=L.palette;const D=L.dims!;const f=useCurrentFrame();
 const [cx,cy]=L.center!;const [cl,ct,cw,ch]=L.canvas!;
 const sIn=interpolate(f,[0,7,D.pop_f],[0.1,D.overshoot,1],{...clamp,easing:Easing.out(Easing.quad)});
 const rot=interpolate(f,[0,8,D.pop_f],[D.deg,-1,0],clamp);
 const sOut=L.exit_none?1:interpolate(f,[frames-D.out_f,frames-1],[1,0.12],clamp);
 const fl=f>=D.pop_f?D.float_px*Math.sin(2*Math.PI*(f-D.pop_f)/40):0;
 const o=interpolate(f,[0,3],[0.4,1],clamp);
 const lb=L.label;
 return <div style={{position:'absolute',left:0,top:0,width:1080,height:1920,opacity:o,transformOrigin:`${cx}px ${cy}px`,
   transform:`translateY(${fl}px) rotate(${rot}deg) scale(${sIn*sOut})`}}>
  <Img src={L.src!} style={{position:'absolute',left:cl,top:ct,width:cw,height:ch}}/>
  {lb&&<div style={{position:'absolute',left:lb.box[0],top:lb.box[1],width:lb.box[2]-lb.box[0],height:lb.box[3]-lb.box[1],borderRadius:999,background:P.pill_bg,
   display:'flex',alignItems:'center',justifyContent:'center',boxSizing:'border-box'}}>
   <div data-fit style={{...text(lb.font_size,lb.lh),width:lb.tw,color:P.pill_text}}>{lb.text}</div>
  </div>}
 </div>;
};

// flash: full-frame white, 0.85 at local frame 0 decaying linearly to 0 on the last frame.
const Flash:React.FC<KitProps>=({layout:L,frames})=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{backgroundColor:'#FFFFFF',opacity:L.exit_none?L.peak!:interpolate(f,[0,frames-1],[L.peak!,0],clamp)}}/>;
};

// frame: framed B-roll panels (BRIEF-frame-feature.md section 5). All frames local (0 = item f0); geometry from kit_layout.py,
// proxy file names/sizes from render_graphics.mjs (CFR 30 fps H.264, proxy frame k = timeline frame seq_from + k).
// Entrance per panel (from f_in): pop = scale 0.86 -> 1.03 (k=5) -> 1.0 (k=7), opacity 0.3 -> 1 (k=0..2); slide = translateY -slide -> 0
// ease-out over 8 frames + same opacity. Exit = outAnim, transform origin = panel box centre.
// Crossfade (xfade_f = 2h): outgoing clip stays opaque underneath through b+h-1; incoming clip is on top with opacity (k+1)/(xfade_f+1)
// at window frame k = f-(b-h); zoom is held at the nearest endpoint during handle frames.
const EASE:Record<string,(t:number)=>number>={linear:t=>t,ease_in:t=>t*t,ease_out:t=>1-(1-t)**2,ease_in_out:t=>t<0.5?2*t*t:1-((-2*t+2)**2)/2};
const FrameClipVideo:React.FC<{c:FrameClip;bw:number;bh:number;xf:number}>=({c,bw,bh,xf})=>{
 const k=useCurrentFrame();const f=c.seq_from+k;// local item frame
 const n=c.f1-c.f0;const t=Math.min(Math.max(f,c.f0),c.f1-1);const p=n>1?(t-c.f0)/(n-1):0;
 const z=c.zoom_from+(c.zoom_to-c.zoom_from)*EASE[c.easing](p);
 const w=c.proxy.w!,h=c.proxy.h!;const s=Math.max(bw/w,bh/h);
 const o=c.h_in>0&&f<c.f0+c.h_in?(k+1)/(xf+1):1;
 return <OffthreadVideo src={staticFile(c.proxy.src)} muted style={{position:'absolute',left:bw/2-z*c.center[0]*w*s,top:bh/2-z*c.center[1]*h*s,width:z*w*s,height:z*h*s,opacity:o}}/>;
};
const labelAnim=(f:number,l:FrameLabel,c:FrameClip)=>{
 if(l.pop_out&&f>=c.f1-3)return {s:interpolate(f,[c.f1-3,c.f1-1],[1,0.6],clamp),o:interpolate(f,[c.f1-3,c.f1-1],[1,0.3],clamp)};
 if(l.pop_in&&f<c.f0+6)return {s:interpolate(f,[c.f0,c.f0+3,c.f0+5],[0.7,1.08,1],clamp),o:interpolate(f,[c.f0,c.f0+2],[0.4,1],clamp)};
 return {s:1,o:1};
};
// style blend: no border/shadow/radius/pills; each panel edge ramps alpha linearly 0 -> 1 over its feather px (CSS mask, edges intersected).
// enter fade: opacity (k+1)/enter_f clamped (k=0 stays visible: no empty first frame), no scale/slide. Blend exit (default): opacity 1 -> 0.2
// over the last enter_f frames (never fully empty, like outAnim), no scale; exit none = full opacity through the last frame.
const featherMask=(w:number,h:number,F:{top:number;bottom:number;left:number;right:number})=>{
 const g=(dir:string,n:number,rev:boolean)=>n>0?`linear-gradient(${dir},${rev?`#000 calc(100% - ${n}px),transparent 100%`:`transparent 0,#000 ${n}px`})`:'linear-gradient(#000,#000)';
 const m=[g('to bottom',F.top,false),g('to top',F.bottom,false),g('to right',F.left,false),g('to left',F.right,false)].join(',');
 return {WebkitMaskImage:m,maskImage:m,WebkitMaskComposite:'source-in',maskComposite:'intersect',WebkitMaskSize:`${w}px ${h}px`,maskSize:`${w}px ${h}px`} as React.CSSProperties;
};
const Frame:React.FC<KitProps>=({layout:L,frames})=>{
 const P=L.palette;const D=L.dims!;const f=useCurrentFrame();const blend=L.style==='blend';
 const out=blend?{o:L.exit_none?1:interpolate(f,[frames-D.enter_f,frames-1],[1,0.2],clamp),s:1}:outAnim(f,frames,L);const xf=L.xfade_f??0;
 return <>{L.panels!.map((pn,pi)=>{
  const k=f-pn.f_in;
  if(k<0)return null;
  const [x0,y0,x1,y1]=pn.box;const b=D.border;const bw=x1-x0,bh=y1-y0;
  if(blend){
   const oB=pn.enter==='none'?1:pn.enter==='fade'?Math.min(1,(k+1)/D.enter_f):interpolate(k,[0,2],[0.3,1],clamp);
   const sB=pn.enter==='pop'?interpolate(k,[0,5,7],[0.86,D.pop,1],clamp):1;
   const tB=pn.enter==='slide'?interpolate(k,[0,7],[-D.slide,0],{...clamp,easing:Easing.out(Easing.quad)}):0;
   return <div key={pi} style={{position:'absolute',left:x0,top:y0,width:bw,height:bh,transformOrigin:'50% 50%',overflow:'hidden',background:'#000',
    transform:`translateY(${tB}px) scale(${sB})`,opacity:oB*out.o,...featherMask(bw,bh,pn.feather!)}}>
    {pn.clips.map((c,ci)=><Sequence key={ci} from={c.seq_from} durationInFrames={c.seq_len} layout="none"><FrameClipVideo c={c} bw={bw} bh={bh} xf={xf}/></Sequence>)}
   </div>;
  }
  const oIn=pn.enter==='none'?1:pn.enter==='fade'?Math.min(1,(k+1)/D.enter_f):interpolate(k,[0,2],[0.3,1],clamp);
  const sIn=pn.enter==='pop'?interpolate(k,[0,5,7],[0.86,D.pop,1],clamp):1;
  const ty=pn.enter==='slide'?interpolate(k,[0,7],[-D.slide,0],{...clamp,easing:Easing.out(Easing.quad)}):0;
  return <div key={pi} style={{position:'absolute',left:x0-b,top:y0-b,width:bw+2*b,height:bh+2*b,transformOrigin:'50% 50%',
    transform:`translateY(${ty}px) scale(${sIn*out.s})`,opacity:oIn*out.o}}>
   <div style={{position:'absolute',inset:0,borderRadius:D.radius,background:P.frame_border,boxShadow:`0 ${D.shadow_dy}px ${D.shadow_blur}px rgba(0,0,0,${D.shadow_alpha})`}}/>
   <div style={{position:'absolute',left:b,top:b,width:bw,height:bh,borderRadius:Math.max(0,D.radius-b),overflow:'hidden',background:'#000'}}>
    {pn.clips.map((c,ci)=><Sequence key={ci} from={c.seq_from} durationInFrames={c.seq_len} layout="none"><FrameClipVideo c={c} bw={bw} bh={bh} xf={xf}/></Sequence>)}
   </div>
   {pn.clips.map((c,ci)=>{
    const l=c.label;if(!l||f<c.f0||f>=c.f1)return null;
    const a=labelAnim(f,l,c);
    return <div key={`l${ci}`} style={{position:'absolute',left:l.box[0]-(x0-b),top:l.box[1]-(y0-b),width:l.box[2]-l.box[0],height:l.box[3]-l.box[1],borderRadius:999,
      background:P.frame_label_bg,boxSizing:'border-box',transform:`scale(${a.s})`,opacity:a.o}}>
     <div data-fit style={{...text(l.font_size,l.lh),position:'absolute',left:l.pad_x,top:l.text_top,width:l.tw,color:P.frame_label_text}}>{l.text}</div>
    </div>;})}
  </div>;})}</>;
};

export const KitElement:React.FC<KitProps>=(props)=>{
 useFitCheck(props.id);
 const {fps}=useVideoConfig();
 if(fps!==30)throw new Error('kit expects 30 fps');
 const bodies={keyword:Keyword,checklist:Checklist,circle:Circle,cta:Cta,title_behind:Title,cutout:Cutout,flash:Flash,big_text:BigText,arrow:Arrow,frame:Frame};
 const Body=bodies[props.type];
 const body=<Body {...props}/>;
 return <AbsoluteFill style={{backgroundColor:'transparent'}}>{body}</AbsoluteFill>;
};

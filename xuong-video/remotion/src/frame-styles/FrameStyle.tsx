// Frame style library: ONLY the decoration around a list of boxes (transparent everywhere else), so the box itself can
// stay a native CapCut clip with a rounded rectangle mask. Catalog + params: frame-styles/catalog.json (defaults are
// merged by scripts/render_frame_style.mjs before the props reach this component).
//
// Geometry rules (every style):
// - box = [x0, y0, x1, y1] canvas px, radius = the cell mask's corner radius in px (see frame-styles/README.md for the
//   CapCut roundCorner <-> px mapping).
// - Everything is drawn inside one SVG mask whose hole is the box inset by `cover` px with radius max(0, radius - cover),
//   concentric with the box corners. So nothing covers the video more than `cover` px (cover = 2 px for edge styles,
//   border_px for tape), and the inner contour of the ring follows the mask's corner arc exactly.
// - Rings are concentric rounded rectangles: offset d outside the box has corner radius radius + d.
// Entrance (animated): strokes draw in (pathLength dash) over enter_f frames; filled parts (card, tape, label) pop
// (scale 0.9 -> 1.03 -> 1, opacity 0.3 -> 1); glows fade in. Still render = last frame = fully drawn.
import {loadFont} from '@remotion/fonts';
import React,{useEffect,useState} from 'react';
import {AbsoluteFill,Easing,cancelRender,continueRender,delayRender,interpolate,staticFile,useCurrentFrame} from 'remotion';

const FONT='FS BeVietnamPro Black';
// the face joins document.fonts only after this async fetch finishes: measuring must wait for it (else fallback-font metrics)
const fontReady=loadFont({family:FONT,url:staticFile('v6/fonts/BeVietnamPro-Black.ttf'),weight:'900'});

export type Box=[number,number,number,number];
export type FrameLabel={text:string;corner?:'tl'|'tr'|'bl'|'br';shape?:'pill'|'ribbon'};
export type FrameBox={box:Box;radius:number;label?:FrameLabel|null};
export type FrameParams={border_px:number;color:string;color2?:string;glow_color?:string;glow_px?:number;shadow_alpha?:number;shadow_blur?:number;
 shadow_dy?:number;gap_px?:number;margin_px?:number;bottom_px?:number;corner_len?:number;tape_color?:string;tape_len?:number;
 label_bg?:string;label_text?:string;label_size?:number};
export type FrameStyleProps={style:string;params:FrameParams;boxes:FrameBox[];canvas:[number,number];frames:number;enter_f:number;animated:boolean};

const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;

// rounded rectangle path, clockwise, radius clamped to half the shorter side
export const rr=(x0:number,y0:number,x1:number,y1:number,r:number)=>{
 const R=Math.max(0,Math.min(r,(x1-x0)/2,(y1-y0)/2));
 if(R===0)return `M${x0} ${y0}H${x1}V${y1}H${x0}Z`;
 return `M${x0+R} ${y0}H${x1-R}A${R} ${R} 0 0 1 ${x1} ${y0+R}V${y1-R}A${R} ${R} 0 0 1 ${x1-R} ${y1}H${x0+R}A${R} ${R} 0 0 1 ${x0} ${y1-R}V${y0+R}A${R} ${R} 0 0 1 ${x0+R} ${y0}Z`;
};
// the concentric rounded rect offset d px outside the box (d < 0 = inside)
const off=(b:FrameBox,d:number)=>{const [x0,y0,x1,y1]=b.box;return rr(x0-d,y0-d,x1+d,y1+d,Math.max(0,b.radius+d));};

// edge styles cover at most OV px of the video (anti-aliasing overlap so no hairline gap shows between mask and ring)
const OV=2;
const coverOf=(style:string,P:FrameParams)=>style==='tape'?Math.max(OV,P.border_px):OV;

type Ctx={p:number;pop:{s:number;o:number};P:FrameParams;id:string};
const draw=(p:number)=>p>=1?{}:{pathLength:1,strokeDasharray:`${Math.max(0.001,p)} 1`};
// a ring of width w whose inner edge sits `inner` px from the box edge (negative = inside)
const Ring:React.FC<{b:FrameBox;inner:number;w:number;stroke:string;p:number;filter?:string;opacity?:number}>=({b,inner,w,stroke,p,filter,opacity})=>
 <path d={off(b,inner+w/2)} fill="none" stroke={stroke} strokeWidth={w} strokeLinejoin="round" filter={filter} opacity={opacity} {...draw(p)}/>;

const popT=(b:FrameBox,s:number)=>{const [x0,y0,x1,y1]=b.box;const cx=(x0+x1)/2,cy=(y0+y1)/2;return `translate(${cx} ${cy}) scale(${s}) translate(${-cx} ${-cy})`;};

// L-shaped accents following each corner arc, legs of length len past the arc
const cornersPath=(b:FrameBox,d:number,len:number)=>{
 const [x0,y0,x1,y1]=b.box;const r=Math.max(0,Math.min(b.radius,(x1-x0)/2,(y1-y0)/2))+d;
 const X0=x0-d,Y0=y0-d,X1=x1+d,Y1=y1+d;
 return [`M${X0} ${Y0+r+len}V${Y0+r}A${r} ${r} 0 0 1 ${X0+r} ${Y0}H${X0+r+len}`,
  `M${X1-r-len} ${Y0}H${X1-r}A${r} ${r} 0 0 1 ${X1} ${Y0+r}V${Y0+r+len}`,
  `M${X1} ${Y1-r-len}V${Y1-r}A${r} ${r} 0 0 1 ${X1-r} ${Y1}H${X1-r-len}`,
  `M${X0+r+len} ${Y1}H${X0+r}A${r} ${r} 0 0 1 ${X0} ${Y1-r}V${Y1-r-len}`].join('');
};

const STYLES:Record<string,(b:FrameBox,i:number,c:Ctx)=>React.ReactNode>={
 // white ring + soft drop shadow (shadow only outside the box)
 clean:(b,i,{p,P})=><g key={i}>
  <path d={off(b,P.border_px/2)} fill="none" stroke="#000" strokeWidth={P.border_px} filter="url(#fs-shadow)" opacity={p}/>
  <Ring b={b} inner={-OV} w={P.border_px+OV} stroke={P.color} p={p}/></g>,
 // crisp ring + brand-colour outer glow
 glow:(b,i,{p,P})=><g key={i}>
  <path d={off(b,P.border_px)} fill="none" stroke={P.glow_color} strokeWidth={P.border_px*2} filter="url(#fs-glow)" opacity={p}/>
  <Ring b={b} inner={-OV} w={P.border_px+OV} stroke={P.color} p={p}/></g>,
 // two thin concentric lines with a gap
 double:(b,i,{p,P})=>{const w=Math.max(3,P.border_px*0.3);return <g key={i}>
  <Ring b={b} inner={-OV} w={w+OV} stroke={P.color} p={p}/>
  <Ring b={b} inner={w+(P.gap_px??6)} w={w} stroke={P.color} p={p}/></g>;},
 // two-colour diagonal gradient stroke + faint shadow
 gradient:(b,i,{p,P})=><g key={i}>
  <path d={off(b,P.border_px/2)} fill="none" stroke="#000" strokeWidth={P.border_px} filter="url(#fs-shadow)" opacity={p}/>
  <Ring b={b} inner={-OV} w={P.border_px+OV} stroke={`url(#fs-grad-${i})`} p={p}/></g>,
 // instant-photo card: even margins, thick bottom, soft shadow; the photo hole is the box with the mask radius
 polaroid:(b,i,{pop,P})=>{const [x0,y0,x1,y1]=b.box;const m=P.margin_px??22,mb=P.bottom_px??90;
  const outer=rr(x0-m,y0-m,x1+m,y1+mb,Math.min(10,m));
  return <g key={i} transform={popT(b,pop.s)} opacity={pop.o}>
   <path d={outer+off(b,-OV)} fillRule="evenodd" fill={P.color} filter="url(#fs-shadow)"/></g>;},
 // thin ring + two strips of masking tape across opposite corners
 tape:(b,i,{p,pop,P})=>{const [x0,y0,x1,y1]=b.box;const L=P.tape_len??150,T=Math.round(L*0.3);
  const tape=(cx:number,cy:number,deg:number,k:string)=><g key={k} transform={`translate(${cx} ${cy}) rotate(${deg})`}>
   <path d={`M${-L/2} ${-T/2} l6 ${T/4} l-6 ${T/4} l6 ${T/4} l-6 ${T/4} H${L/2} l-6 ${-T/4} l6 ${-T/4} l-6 ${-T/4} l6 ${-T/4} Z`} fill={P.tape_color} filter="url(#fs-soft)"/></g>;
  // centre so the strip's inner long edge crosses the corner arc midpoint (radius*(1-1/sqrt2) inside the corner) at depth `cover`
  const cv=Math.max(OV,P.border_px);
  const o=Math.max(0,Math.min(b.radius,(x1-x0)/2,(y1-y0)/2))*(1-Math.SQRT1_2)+(cv-T/2)*Math.SQRT1_2;
  return <g key={i}>
   <Ring b={b} inner={-OV} w={P.border_px+OV} stroke={P.color} p={p}/>
   <g transform={popT(b,pop.s)} opacity={pop.o}>{tape(x0+o,y0+o,-45,'a')}{tape(x1-o,y1-o,-45,'b')}</g></g>;},
 // only L-shaped corner accents on the edge
 corner:(b,i,{p,P})=>{const [x0,y0,x1,y1]=b.box;const len=(P.corner_len??0.16)*Math.min(x1-x0,y1-y0);
  return <path key={i} d={cornersPath(b,P.border_px/2-OV,len)} fill="none" stroke={P.color} strokeWidth={P.border_px+OV} strokeLinecap="round" {...draw(p)}/>;},
 // neon tube: coloured outline, white-hot core, two glows
 neon:(b,i,{p,P})=><g key={i} opacity={interpolate(p,[0,0.4,0.55,0.7,1],[0.2,1,0.45,1,1])}>
  <path d={off(b,P.border_px/2)} fill="none" stroke={P.color} strokeWidth={P.border_px*2.2} filter="url(#fs-glow)"/>
  <Ring b={b} inner={-OV} w={P.border_px+OV} stroke={P.color} p={1}/>
  <Ring b={b} inner={P.border_px*0.3} w={Math.max(2,P.border_px*0.3)} stroke="#FFFFFF" p={1} opacity={0.9}/></g>,
 // no line at all: the box floats on a soft shadow
 lift:(b,i,{p})=><path key={i} d={off(b,0)} fill="#000" filter="url(#fs-lift)" opacity={p}/>,
};
export const STYLE_IDS=Object.keys(STYLES);

// label badge: ink measured in the browser with the real font (diacritics included) so nothing clips
type Ink={w:number;asc:number;desc:number;left:number};
const useInk=(texts:string[],size:number)=>{
 const [ink,setInk]=useState<Record<string,Ink>|null>(null);
 const key=JSON.stringify(texts)+size;
 useEffect(()=>{
  if(!texts.length){setInk({});return;}
  const h=delayRender(`label ink ${key}`);
  fontReady.then(()=>Promise.all(texts.map(t=>document.fonts.load(`900 ${size}px "${FONT}"`,t)))).then(()=>{
   const ctx=document.createElement('canvas').getContext('2d')!;ctx.font=`900 ${size}px "${FONT}"`;
   const out:Record<string,Ink>={};
   for(const t of texts){const m=ctx.measureText(t);out[t]={w:m.actualBoundingBoxLeft+m.actualBoundingBoxRight,asc:m.actualBoundingBoxAscent,desc:m.actualBoundingBoxDescent,left:m.actualBoundingBoxLeft};}
   setInk(out);continueRender(h);
  }).catch(e=>cancelRender(e));
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[key]);
 return ink;
};
const Label:React.FC<{b:FrameBox;ink:Ink;P:FrameParams;cover:number;pop:{s:number;o:number}}>=({b,ink,P,cover,pop})=>{
 const l=b.label!;const [x0,y0,x1,y1]=b.box;const size=P.label_size??40;
 const px=Math.round(size*0.55),py=Math.round(size*0.3);
 const w=Math.ceil(ink.w+2*px),h=Math.ceil(ink.asc+ink.desc+2*py);
 if(w>x1-x0)cancelRender(new Error(`label "${l.text}" (${w}px) is wider than its box (${x1-x0}px)`));
 const c=l.corner??'tl';const inset=Math.max(16,b.radius*0.8);
 const left=c.endsWith('l')?x0+inset:x1-inset-w;
 const top=c.startsWith('t')?y0+cover-h:y1-cover;// sits outside the box, overlapping only `cover` px
 const shape=l.shape==='ribbon'
  ?(c.startsWith('t')?`M${left} ${top+h}V${top+6}q0-6 6-6H${left+w-6}q6 0 6 6V${top+h}Z`:`M${left} ${top}H${left+w}V${top+h-6}q0 6-6 6H${left+6}q-6 0-6-6Z`)
  :rr(left,top,left+w,top+h,h/2);
 const cx=left+w/2,cy=top+h/2;
 return <g transform={`translate(${cx} ${cy}) scale(${pop.s}) translate(${-cx} ${-cy})`} opacity={pop.o}>
  <path d={shape} fill={P.label_bg} filter="url(#fs-soft)"/>
  <text x={left+px+ink.left} y={top+py+ink.asc} fontFamily={FONT} fontWeight={900} fontSize={size} fill={P.label_text}>{l.text}</text></g>;
};

export const FrameStyle:React.FC<FrameStyleProps>=({style,params:P,boxes,canvas,frames,enter_f,animated})=>{
 const f=useCurrentFrame();
 const body=STYLES[style];
 if(!body)throw new Error(`unknown frame style ${style}; known: ${STYLE_IDS.join(', ')}`);
 const labels=boxes.filter(b=>b.label?.text).map(b=>b.label!.text);
 const ink=useInk(labels,P.label_size??40);
 const k=animated?f:frames-1;
 const p=animated?interpolate(k,[0,Math.max(1,enter_f-1)],[0,1],{...clamp,easing:Easing.out(Easing.cubic)}):1;
 const pop=animated?{s:interpolate(k,[0,enter_f*0.6,enter_f],[0.9,1.03,1],clamp),o:interpolate(k,[0,enter_f*0.3],[0.3,1],clamp)}:{s:1,o:1};
 const cover=coverOf(style,P);
 const [W,H]=canvas;
 const ctx:Ctx={p,pop,P,id:style};
 return <AbsoluteFill style={{backgroundColor:'transparent'}}>
  <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{position:'absolute',inset:0}}>
   <defs>
    <mask id="fs-out" maskUnits="userSpaceOnUse" x={0} y={0} width={W} height={H}>
     <rect x={0} y={0} width={W} height={H} fill="#fff"/>
     {boxes.map((b,i)=><path key={i} d={off(b,-cover)} fill="#000"/>)}
    </mask>
    <filter id="fs-shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx={0} dy={P.shadow_dy??10} stdDeviation={P.shadow_blur??14} floodColor="#000" floodOpacity={P.shadow_alpha??0.45}/></filter>
    <filter id="fs-lift" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation={P.shadow_blur??22}/><feOffset dy={P.shadow_dy??16}/>
     <feComponentTransfer><feFuncA type="linear" slope={P.shadow_alpha??0.6}/></feComponentTransfer></filter>
    <filter id="fs-glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation={P.glow_px??14}/></filter>
    <filter id="fs-soft" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx={0} dy={3} stdDeviation={3} floodColor="#000" floodOpacity={0.3}/></filter>
    {boxes.map((b,i)=><linearGradient key={i} id={`fs-grad-${i}`} gradientUnits="userSpaceOnUse" x1={b.box[0]} y1={b.box[1]} x2={b.box[2]} y2={b.box[3]}>
     <stop offset="0" stopColor={P.color}/><stop offset="1" stopColor={P.color2??P.color}/></linearGradient>)}
   </defs>
   <g mask="url(#fs-out)">
    {boxes.map((b,i)=>body(b,i,ctx))}
    {ink&&boxes.map((b,i)=>b.label?.text?<Label key={`l${i}`} b={b} ink={ink[b.label.text]} P={P} cover={cover} pop={pop}/>:null)}
   </g>
  </svg>
 </AbsoluteFill>;
};

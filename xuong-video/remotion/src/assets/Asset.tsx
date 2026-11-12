// Asset factory for CapCut-native graphics (pipeline-v6 native/layouts.py): small transparent stills CapCut cannot draw,
// rendered once and kept in the shared asset library (workflow-data/asset-library). Same drawing code as the kit
// (KitElement.tsx Tick / Circle) so a native video looks like the Remotion one.
//   tick:    {d, fill, mark}                       -> d x d tick-in-circle (KitElement Tick)
//   ellipse: {rx, ry, stroke, outline, color, outline_color, points}
//            -> fully drawn hand ellipse (kit Circle at draw-on progress 1) centred in a width x height canvas
import React from 'react';

export type AssetProps={kind:'tick'|'ellipse';width:number;height:number;params:Record<string,unknown>};

export const Asset:React.FC<AssetProps>=({kind,width,height,params:p})=>{
 if(kind==='tick'){
  return <svg width={width} height={height} viewBox="0 0 52 52" style={{position:'absolute',left:0,top:0}}>
   <circle cx="26" cy="26" r="26" fill={p.fill as string}/>
   <path d="M14 27 L23 36 L39 18" fill="none" stroke={p.mark as string} strokeWidth="7" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>;
 }
 const pts=p.points as [number,number][];const rx=p.rx as number,ry=p.ry as number;const cx=width/2,cy=height/2;
 const d=pts.map((q,i)=>`${i?'L':'M'}${(cx+q[0]*rx).toFixed(2)} ${(cy+q[1]*ry).toFixed(2)}`).join(' ');
 const common={fill:'none',strokeLinecap:'round' as const,strokeLinejoin:'round' as const};
 return <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{position:'absolute',left:0,top:0}}>
  <path d={d} {...common} stroke={p.outline_color as string} strokeWidth={p.outline as number}/>
  <path d={d} {...common} stroke={p.color as string} strokeWidth={p.stroke as number}/>
 </svg>;
};

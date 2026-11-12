// HUB VIDEO — composition dữ liệu hoá cho hub sản xuất hàng loạt (không phải preview CapCut).
// FFmpeg đã cắt/chỉnh màu clip và trộn sẵn âm thanh; ở đây chỉ dàn cảnh, chuyển cảnh, chữ, thẻ, mũi tên.
// Bố cục theo VÙNG để các lớp không đè nhau: TOP (thẻ mở/thẻ chốt) · SUB (phụ đề) · ARROW (góc trái dưới).
import {loadFont} from '@remotion/fonts';
import React from 'react';
import {Video} from '@remotion/media';
import {AbsoluteFill, Audio, Easing, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Caption as Caption3, CapCfg, CapLine} from './Caption';
import {Atmos, Block, Blocks} from './Blocks';

const FONT = 'DT Phudu';
loadFont({family: FONT, url: staticFile('DTPhudu-Black.otf'), weight: '900'});

export type HubClip = {src: string; f0: number; f1: number; motion: 'zoom_in' | 'zoom_out' | 'pan_left' | 'pan_right' | 'still' | 'punch'};
export type HubWord = {w: string; f0: number; f1: number; s: number; emph?: boolean};
export type HubProps = {
  duration_f: number;
  audio: string;
  clips: HubClip[];
  transition: {kind: 'cut' | 'crossfade' | 'slide_left' | 'slide_up' | 'zoom_punch' | 'whip' | 'mix'; dur_f: number};
  words: HubWord[];
  lines?: CapLine[];
  cap?: CapCfg;
  blocks?: Block[];
  atmos?: {vignette: boolean; grain: boolean; leaks: number[]; hue: number};
  caption: {style: string; center_y: number; upper: boolean; group: number};
  colors: {accent: string; brand_red: string; brand_green: string; text: string};
  open_card: {kind: string; text: string; f1: number};
  cta: {kind: string; line1: string; line2: string; f0: number};
  arrow: {f0: number; label: string};
  progress_bar: boolean;
};

// ---------------------------------------------------------------- CLIPS + CHUYỂN CẢNH
const motionStyle = (m: HubClip['motion'], p: number): React.CSSProperties => {
  const e = Easing.inOut(Easing.quad)(p);
  switch (m) {
    case 'zoom_in': return {transform: `scale(${1.04 + 0.08 * e})`};
    case 'zoom_out': return {transform: `scale(${1.12 - 0.08 * e})`};
    case 'pan_left': return {transform: `scale(1.12) translateX(${30 - 60 * e}px)`};
    case 'pan_right': return {transform: `scale(1.12) translateX(${-30 + 60 * e}px)`};
    case 'punch': return {transform: `scale(${1.0 + 0.10 * Math.min(1, p * 6) - 0.04 * Math.max(0, p * 6 - 1) / 5})`};
    default: return {transform: 'scale(1.04)'};
  }
};

const TRANS = ['crossfade', 'slide_left', 'slide_up', 'zoom_punch', 'whip'] as const;

const transStyle = (kind: string, side: 'in' | 'out', t: number): React.CSSProperties => {
  // t: 0→1 trong khoảng chuyển; side 'in' = clip mới, 'out' = clip cũ
  const e = Easing.inOut(Easing.cubic)(t);
  switch (kind) {
    case 'crossfade': return side === 'in' ? {opacity: e} : {};
    case 'slide_left': return {transform: `translateX(${side === 'in' ? (1 - e) * 1080 : -e * 1080}px)`};
    case 'slide_up': return {transform: `translateY(${side === 'in' ? (1 - e) * 1920 : -e * 1920}px)`};
    case 'zoom_punch': return side === 'in' ? {opacity: e, transform: `scale(${1.25 - 0.25 * e})`} : {transform: `scale(${1 + 0.15 * e})`};
    case 'whip': {
      const blur = Math.sin(e * Math.PI) * 28;
      return {transform: `translateX(${side === 'in' ? (1 - e) * 1080 : -e * 1080}px)`, filter: `blur(${blur}px)`};
    }
    default: return {};
  }
};

const Clips: React.FC<{clips: HubClip[]; tr: HubProps['transition']}> = ({clips, tr}) => {
  const f = useCurrentFrame();
  const d = tr.kind === 'cut' ? 0 : tr.dur_f;
  return <AbsoluteFill style={{backgroundColor: '#000'}}>
    {clips.map((c, i) => {
      const start = c.f0 - (i > 0 ? d / 2 : 0);
      const end = c.f1 + (i < clips.length - 1 ? d / 2 : 0);
      if (f < start - 1 || f > end + 1) return null;
      const kind = tr.kind === 'mix' ? TRANS[(i * 7 + 3) % TRANS.length] : tr.kind;
      const nextKind = tr.kind === 'mix' ? TRANS[((i + 1) * 7 + 3) % TRANS.length] : tr.kind;
      let st: React.CSSProperties = {};
      if (d > 0 && i > 0 && f < c.f0 + d / 2) st = transStyle(kind, 'in', (f - (c.f0 - d / 2)) / d);
      if (d > 0 && i < clips.length - 1 && f > c.f1 - d / 2) st = transStyle(nextKind, 'out', (f - (c.f1 - d / 2)) / d);
      const p = Math.min(1, Math.max(0, (f - start) / Math.max(1, end - start)));
      return <AbsoluteFill key={i} style={{...st, zIndex: i, overflow: 'hidden'}}>
        <Sequence from={Math.round(start)} durationInFrames={Math.max(1, Math.round(end - start))} layout="none">
          <AbsoluteFill style={motionStyle(c.motion, p)}>
            <Video src={staticFile(c.src)} muted style={{width: 1080, height: 1920, objectFit: 'cover'}}/>
          </AbsoluteFill>
        </Sequence>
      </AbsoluteFill>;
    })}
  </AbsoluteFill>;
};

// ---------------------------------------------------------------- PHỤ ĐỀ KARAOKE
type Chunk = HubWord[];
const chunkWords = (ws: HubWord[], size: number): Chunk[] => {
  const out: Chunk[] = []; let cur: HubWord[] = [];
  ws.forEach((w, i) => {
    cur.push(w);
    const next = ws[i + 1];
    const sentenceEnd = !next || next.s !== w.s;           // không vắt cụm qua 2 câu
    const punct = /[,…:;]$/.test(w.w) && cur.length >= 2;
    if (sentenceEnd || cur.length >= size || punct) {out.push(cur); cur = [];}
  });
  return out;
};

const STROKE = (px: number, c = '#000') =>
  `${px}px ${px}px 0 ${c}, -${px}px ${px}px 0 ${c}, ${px}px -${px}px 0 ${c}, -${px}px -${px}px 0 ${c}, 0 ${px + 2}px ${px * 2}px rgba(0,0,0,0.55)`;

const Caption: React.FC<{p: HubProps}> = ({p}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const chunks = chunkWords(p.words, p.caption.group);
  const idx = chunks.findIndex((c, i) => f >= c[0].f0 - 2 && f < (chunks[i + 1]?.[0].f0 ?? c[c.length - 1].f1 + 8) - 1);
  if (idx < 0 || f >= p.cta.f0 - 1 && p.caption.center_y < 700) return null;
  const ch = chunks[idx];
  const t0 = ch[0].f0 - 2;
  const enter = spring({frame: f - t0, fps, config: {damping: 14, stiffness: 220}});
  const st = p.caption.style;
  const big = st === 'pop_tung_tu' || st === 'chu_lon_2_dong';
  const size = big ? 104 : 84;
  const hot = [...ch].reverse().find(w => f >= w.f0);
  const A = p.colors.accent;
  const box: React.CSSProperties =
    st === 'hop_den' ? {background: 'rgba(0,0,0,0.62)', borderRadius: 22, padding: '10px 26px'} :
    st === 'hop_xanh' ? {background: p.colors.brand_green, borderRadius: 22, padding: '10px 26px', boxShadow: '0 10px 30px rgba(0,0,0,0.35)'} :
    st === 'hop_do' ? {background: p.colors.brand_red, borderRadius: 22, padding: '10px 26px', boxShadow: '0 10px 30px rgba(0,0,0,0.35)'} : {};
  const plainText = st === 'hop_den' || st === 'hop_xanh' || st === 'hop_do' ? {} : {textShadow: STROKE(5)};
  return <div style={{position: 'absolute', left: 70, width: 870, top: p.caption.center_y, transform: `translateY(-50%) scale(${0.86 + 0.14 * enter})`,
    opacity: Math.min(1, enter * 1.6), display: 'flex', justifyContent: 'center'}}>
    <div style={{...box, textAlign: 'center', maxWidth: 870}}>
      <div style={{fontFamily: FONT, fontWeight: 900, fontSize: size, lineHeight: 1.12, color: p.colors.text, ...plainText}}>
        {ch.map((w, j) => {
          const on = hot === w;
          const done = f >= w.f0;
          const pop = on ? spring({frame: f - w.f0, fps, config: {damping: 10, stiffness: 260}}) : 0;
          const word = p.caption.upper ? w.w.toUpperCase() : w.w;
          let s: React.CSSProperties = {display: 'inline-block', margin: '0 8px', transform: `scale(${1 + (w.emph ? 0.18 : 0.08) * pop})`};
          if (st === 'pill' && on) s = {...s, background: A, color: '#111', borderRadius: 14, padding: '0 14px', textShadow: 'none'};
          else if (st === 'gach_chan' && on) s = {...s, color: A, borderBottom: `10px solid ${A}`};
          else if (st === 'phat_sang' && on) s = {...s, color: A, textShadow: `0 0 26px ${A}, ${STROKE(5)}`};
          else if (on || (st === 'tich_luy' && done)) s = {...s, color: A};
          if (w.emph && st !== 'pill') s = {...s, color: on ? A : s.color};
          return <span key={j} style={s}>{word}</span>;
        })}
      </div>
    </div>
  </div>;
};

// ---------------------------------------------------------------- THẺ MỞ ĐẦU
const OpenCard: React.FC<{p: HubProps}> = ({p}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const c = p.open_card;
  if (c.kind === 'khong' || f > c.f1) return null;
  const inn = spring({frame: f, fps, config: {damping: 13, stiffness: 180}});
  const out = interpolate(f, [c.f1 - 8, c.f1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const base: React.CSSProperties = {fontFamily: FONT, fontWeight: 900, color: '#fff', position: 'absolute', opacity: out};
  if (c.kind === 'ribbon_do' || c.kind === 'ribbon_xanh')
    return <div style={{...base, top: 250, left: 0, transform: `translateX(${(inn - 1) * 1080}px)`, background: c.kind === 'ribbon_do' ? p.colors.brand_red : p.colors.brand_green,
      padding: '16px 46px 16px 70px', fontSize: 62, borderRadius: '0 60px 60px 0', boxShadow: '0 12px 30px rgba(0,0,0,0.35)'}}>{c.text}</div>;
  if (c.kind === 'tem_xoay')
    return <div style={{...base, top: 230, left: 0, width: 1080, display: 'flex', justifyContent: 'center'}}>
      <div style={{transform: `rotate(${(1 - inn) * -25 - 3}deg) scale(${inn})`, border: `8px solid ${p.colors.brand_red}`, color: p.colors.brand_red,
        background: 'rgba(255,255,255,0.94)', padding: '14px 40px', fontSize: 66, borderRadius: 18}}>{c.text}</div></div>;
  if (c.kind === 'chu_lon')
    return <div style={{...base, top: 0, left: 60, width: 960, height: 1920, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
      fontSize: 120, lineHeight: 1.05, textShadow: STROKE(7), transform: `scale(${0.7 + 0.3 * inn})`}}>{c.text}</div>;
  // thanh_tren
  return <div style={{...base, top: 0, left: 0, width: 1080, transform: `translateY(${(inn - 1) * 260}px)`}}>
    <div style={{marginTop: 210, marginLeft: 90, marginRight: 150, background: '#fff', color: p.colors.brand_red, fontSize: 60, padding: '14px 30px',
      borderLeft: `18px solid ${p.colors.brand_green}`, borderRadius: 14, boxShadow: '0 12px 30px rgba(0,0,0,0.3)'}}>{c.text}</div></div>;
};

// ---------------------------------------------------------------- THẺ CHỐT + MŨI TÊN
const Cta: React.FC<{p: HubProps}> = ({p}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const c = p.cta;
  if (f < c.f0) return null;
  const inn = spring({frame: f - c.f0, fps, config: {damping: 12, stiffness: 170}});
  const pulse = 1 + 0.035 * Math.sin((f - c.f0) / 5);
  const colors: Record<string, [string, string]> = {
    the_qua: ['#fff', p.colors.brand_red], hop_xanh: [p.colors.brand_green, '#fff'], hop_do: [p.colors.brand_red, '#fff'], nhan_vang: [p.colors.accent, '#111']};
  const [bg, fg] = colors[c.kind] ?? colors.hop_do;
  return <div style={{position: 'absolute', top: 240, left: 0, width: 1080, display: 'flex', justifyContent: 'center', transform: `translateY(${(1 - inn) * -120}px)`, opacity: Math.min(1, inn * 1.5)}}>
    <div style={{background: bg, color: fg, fontFamily: FONT, fontWeight: 900, textAlign: 'center', padding: '22px 44px', borderRadius: 28, maxWidth: 860,
      boxShadow: '0 16px 40px rgba(0,0,0,0.4)', transform: `scale(${pulse})`, border: c.kind === 'the_qua' ? `8px solid ${p.colors.brand_red}` : 'none'}}>
      {c.kind === 'the_qua' && <div style={{fontSize: 44, color: p.colors.brand_green, marginBottom: 6}}>🎁 QUÀ TẶNG</div>}
      <div style={{fontSize: 70, lineHeight: 1.08}}>{c.line1}</div>
      <div style={{fontSize: 52, marginTop: 8, opacity: 0.95}}>{c.line2}</div>
    </div>
  </div>;
};

const Arrow: React.FC<{p: HubProps}> = ({p}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (f < p.arrow.f0) return null;
  const inn = spring({frame: f - p.arrow.f0, fps, config: {damping: 12}});
  const bob = Math.sin((f - p.arrow.f0) / 4) * 14;
  return <div style={{position: 'absolute', left: 60, top: ((p as any).arrow?.top ?? 1250) + bob, opacity: inn, transform: `scale(${inn})`, display: 'flex', alignItems: 'center', gap: 18}}>
    <svg width="120" height="150" viewBox="0 0 120 150">
      <path d="M38 0 H82 V80 H118 L60 148 L2 80 H38 Z" fill={p.colors.accent} stroke="#111" strokeWidth="7" strokeLinejoin="round"/>
    </svg>
    <div style={{fontFamily: FONT, fontWeight: 900, fontSize: 54, color: '#fff', textShadow: STROKE(5)}}>{p.arrow.label}</div>
  </div>;
};

const Progress: React.FC<{p: HubProps}> = ({p}) => {
  const f = useCurrentFrame();
  if (!p.progress_bar) return null;
  return <div style={{position: 'absolute', top: 0, left: 0, height: 12, width: `${(f / p.duration_f) * 100}%`, background: p.colors.accent}}/>;
};

// Lớp chữ trong suốt: FFmpeg dựng nền video, rồi ghép lớp này lên trên.
export const HubOverlay: React.FC<HubProps> = (p) => p.blocks ? <AbsoluteFill style={{backgroundColor: 'transparent'}}>
  {p.atmos && <Atmos {...p.atmos}/>}
  <Progress p={p}/>
  <Blocks blocks={p.blocks} th={{font: FONT, accent: p.colors.accent, red: p.colors.brand_red, green: p.colors.brand_green, text: p.colors.text}}/>
  {p.lines && p.cap && <Caption3 lines={p.lines} cfg={p.cap} font={FONT} accent={p.colors.accent} text={p.colors.text}/>}
  <Arrow p={p}/>
</AbsoluteFill> : <AbsoluteFill style={{backgroundColor: 'transparent'}}>
  <Progress p={p}/>
  <OpenCard p={p}/>
  {p.lines && p.cap
    ? <Caption3 lines={p.lines} cfg={p.cap} font={FONT} accent={p.colors.accent} text={p.colors.text}/>
    : <Caption p={p}/>}
  <Cta p={p}/>
  <Arrow p={p}/>
</AbsoluteFill>;

export const HubVideo: React.FC<HubProps> = (p) => <AbsoluteFill style={{backgroundColor: '#000'}}>
  <Clips clips={p.clips} tr={p.transition}/>
  <Progress p={p}/>
  <OpenCard p={p}/>
  <Caption p={p}/>
  <Cta p={p}/>
  <Arrow p={p}/>
  <Audio src={staticFile(p.audio)}/>
</AbsoluteFill>;

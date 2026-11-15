// CHỮ PHÁ CÁCH: họ khối chữ LỚN (100–150 px), 1–2 dòng, tối đa ~14 ký tự/dòng, một chữ nhấn.
// Quy tắc chung: không vượt vùng an toàn (không trên y=220, không dưới y=1600, không bên phải x=920 trong y 760–1560),
// tự bẻ dòng thay vì tràn, dòng cao ≥ 1.2 + đệm để không cụt dấu tiếng Việt.
import {fitText} from '@remotion/layout-utils';
import React from 'react';
import {Easing, interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Block, Theme} from './Blocks';

const STROKE = (px: number, c = '#000') => ({WebkitTextStroke: `${px}px ${c}`, paintOrder: 'stroke fill' as const});
const SHADOW = 'drop-shadow(0 12px 22px rgba(0,0,0,0.5))';
const MAX_KY_TU = 14;
const LH = 1.24;                                    // dòng cao: dấu mũ/dấu thanh của chữ IN HOA không bị cắt

type W = {w: string; i: number};

export const chiaDong = (text: string, maxC = MAX_KY_TU): W[][] => {   // bẻ dòng cân đối, mỗi dòng ≤ maxC ký tự nếu được
  const ws: W[] = String(text || '').toUpperCase().replace(/\s+/g, ' ').trim().split(' ').filter(Boolean).map((w, i) => ({w, i}));
  if (!ws.length) return [];
  const len = (a: W[]) => a.reduce((s, x) => s + x.w.length, 0) + Math.max(0, a.length - 1);
  if (len(ws) <= maxC) return [ws];
  let best: W[][] | null = null; let bs = 1e9;
  for (let k = 1; k < ws.length; k++) {
    const a = ws.slice(0, k), b = ws.slice(k), s = Math.max(len(a), len(b));
    if (s < bs) {bs = s; best = [a, b];}
  }
  if (best && bs <= maxC) return best;
  const out: W[][] = []; let cur: W[] = [];                  // quá dài: xuống nhiều dòng (chữ sẽ tự co)
  for (const x of ws) {
    if (cur.length && len([...cur, x]) > maxC) {out.push(cur); cur = [];}
    cur.push(x);
  }
  if (cur.length) out.push(cur);
  return out;
};

const nhanIdx = (b: Block, lines: W[][]) => {
  const n = lines.reduce((s, l) => s + l.length, 0);
  const v = b.data.nhan;
  return v === undefined || v === null ? n - 1 : Number(v);     // -1 = không tô chữ nào
};

const clamp = (v: number, a: number, c: number) => Math.max(a, Math.min(c, v));

// Hộp đặt chữ: tính cỡ chữ vừa chiều rộng + toạ độ trong vùng an toàn.
const useBox = (b: Block, lines: W[][], target: number, font: string, defTop = 250, chieuRong = 0) => {
  const top0 = Number((b as any).top ?? defTop);
  const est = lines.length * target * LH + 70;
  const t0 = clamp(top0, 230, 1590 - est);
  const hep = t0 + est > 760 && t0 < 1560;                      // chạm dải nút TikTok bên phải → hẹp lại, tâm lệch trái
  const width = hep ? 860 : 960;
  const maxW = chieuRong || width - 70;
  let px = target;
  for (const l of lines) {
    const fit = fitText({text: l.map(x => x.w).join(' '), withinWidth: maxW, fontFamily: font, fontWeight: '900'}).fontSize;
    px = Math.min(px, fit * 0.95);
  }
  return {top: clamp(top0, 230, 1590 - (lines.length * px * LH + 70)), width, px: Math.floor(px), left: 60};
};

const Stand: React.FC<{bx: {top: number; width: number; left: number}; children: React.ReactNode; style?: React.CSSProperties}> = ({bx, children, style}) =>
  <div style={{position: 'absolute', top: bx.top, left: bx.left, width: bx.width, display: 'flex', justifyContent: 'center', ...style}}>{children}</div>;

const useLife2 = (b: Block, outLen = 8) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = f - b.f0;
  const out = interpolate(f, [b.f1 - outLen, b.f1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return {f, t, fps, out};
};

const Dong: React.FC<{lines: W[][]; hi: number; px: number; ws: (w: W, hot: boolean) => React.CSSProperties; ls?: (k: number) => React.CSSProperties; extra?: (w: W, hot: boolean) => React.ReactNode}> = ({lines, hi, px, ws, ls, extra}) =>
  <>{lines.map((l, k) => <div key={k} style={{whiteSpace: 'nowrap', lineHeight: LH, padding: `${px * 0.04}px 0`, ...(ls ? ls(k) : {})}}>
    {l.map((x, j) => <React.Fragment key={j}><span style={{display: 'inline-block', ...ws(x, x.i === hi)}}>{x.w}{extra ? extra(x, x.i === hi) : null}</span>{j < l.length - 1 ? ' ' : ''}</React.Fragment>)}
  </div>)}</>;

const hiBox = (th: Theme, px: number): React.CSSProperties =>
  ({background: th.accent, color: '#111', WebkitTextStroke: '0px', padding: `0 ${px * 0.14}px`, borderRadius: px * 0.14});

// 1. ĐẬP: chữ phóng to đập vào màn hình, rung nhẹ; chữ nhấn nằm trong ô vàng. Dùng được ở bất kỳ đâu (không chỉ câu mở).
export const ChuDap: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, fps, out} = useLife2(b);
  const lines = chiaDong(String(b.data.text || '')); const hi = nhanIdx(b, lines);
  const bx = useBox(b, lines, 136, th.font);
  const s = spring({frame: t, fps, config: {damping: 9, stiffness: 260}});
  const shake = t < 8 ? (random(`cd${t}`) - 0.5) * 18 : 0;
  return <Stand bx={bx} style={{opacity: out}}>
    <div style={{textAlign: 'center', transform: `translate(${shake}px, 0) scale(${2.2 - 1.2 * s})`, fontFamily: th.font, fontSize: bx.px, color: th.text,
      ...STROKE(Math.round(bx.px * 0.12)), filter: SHADOW}}>
      <Dong lines={lines} hi={hi} px={bx.px} ws={(x, hot) => hot ? hiBox(th, bx.px) : {}}/>
    </div>
  </Stand>;
};

// 2. MẶT NẠ: thanh màu quét ngang, chữ lộ dần theo thanh.
export const ChuMatNa: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, out} = useLife2(b);
  const lines = chiaDong(String(b.data.text || '')); const hi = nhanIdx(b, lines);
  const bx = useBox(b, lines, 128, th.font);
  const p = interpolate(t, [0, 16], [0, 1], {extrapolateRight: 'clamp', extrapolateLeft: 'clamp', easing: Easing.inOut(Easing.cubic)});
  const bar = interpolate(t, [0, 12, 22], [0, 1, 0], {extrapolateRight: 'clamp', extrapolateLeft: 'clamp'});
  const pad = bx.px * 0.3;
  return <Stand bx={bx} style={{opacity: out}}>
    <div style={{position: 'relative', fontFamily: th.font, fontSize: bx.px, color: th.text, textAlign: 'center', filter: SHADOW}}>
      <div style={{padding: `${pad}px ${pad}px`, clipPath: `inset(0 ${100 - p * 100}% 0 0)`, ...STROKE(Math.round(bx.px * 0.11))}}>
        <Dong lines={lines} hi={hi} px={bx.px} ws={(x, hot) => hot ? {color: th.accent} : {}}/>
      </div>
      <div style={{position: 'absolute', top: pad * 0.4, bottom: pad * 0.4, left: `${p * 100 - 3}%`, width: bx.px * 0.16, background: th.accent, opacity: bar, borderRadius: 8}}/>
    </div>
  </Stand>;
};

// 3. NGHIÊNG: cả cụm nghiêng, chữ nhấn nằm trong ô màu nghiêng ngược.
export const ChuNghieng: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, fps, out} = useLife2(b);
  const lines = chiaDong(String(b.data.text || '')); const hi = nhanIdx(b, lines);
  const bx = useBox(b, lines, 124, th.font);
  const s = spring({frame: t, fps, config: {damping: 12, stiffness: 190}});
  return <Stand bx={bx} style={{opacity: out * Math.min(1, s * 1.6)}}>
    <div style={{textAlign: 'center', fontFamily: th.font, fontSize: bx.px, color: th.text, ...STROKE(Math.round(bx.px * 0.1)), filter: SHADOW,
      transform: `translateY(${(1 - s) * 70}px) rotate(${-4 + (1 - s) * -10}deg) scale(${0.75 + 0.25 * s})`}}>
      <Dong lines={lines} hi={hi} px={bx.px} ws={(x, hot) => hot ? {...hiBox(th, bx.px), transform: 'rotate(3deg)', boxShadow: '0 10px 0 rgba(0,0,0,0.85)'} : {}}/>
    </div>
  </Stand>;
};

// 4. XẾP TẦNG: dòng trên nhỏ, dòng dưới rất lớn màu nhấn; hai dòng vào từ hai phía.
export const ChuTang: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, fps, out} = useLife2(b);
  let lines = chiaDong(String(b.data.text || ''));
  if (lines.length === 1 && lines[0].length >= 2) lines = [lines[0].slice(0, -1), lines[0].slice(-1)];
  const bx = useBox(b, lines, 150, th.font);
  const sizes = lines.map((l, k) => {
    const want = k === lines.length - 1 ? bx.px : bx.px * 0.68;
    const fit = fitText({text: l.map(x => x.w).join(' '), withinWidth: bx.width - 70, fontFamily: th.font, fontWeight: '900'}).fontSize * 0.95;
    return Math.floor(Math.min(want, fit));
  });
  return <Stand bx={bx} style={{opacity: out, flexDirection: 'column', alignItems: 'center', fontFamily: th.font}}>
    {lines.map((l, k) => {
      const s = spring({frame: t - k * 5, fps, config: {damping: 10, stiffness: 240}});
      const last = k === lines.length - 1;
      return <div key={k} style={{whiteSpace: 'nowrap', fontSize: sizes[k], lineHeight: LH, padding: `${sizes[k] * 0.03}px 0`, color: last ? th.accent : th.text, ...STROKE(Math.round(sizes[k] * 0.12)),
        filter: SHADOW, opacity: Math.min(1, s * 1.5), transform: `translateX(${(1 - s) * (k % 2 ? 420 : -420)}px) scale(${1 + (1 - s) * 0.4})`}}>
        {l.map(x => x.w).join(' ')}</div>;
    })}
  </Stand>;
};

// 5. SỐ + ĐƠN VỊ: số rất lớn, đơn vị bên dưới; nhãn nhỏ phía trên (tuỳ chọn).
export const ChuSo: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, fps, out} = useLife2(b);
  const so = String(b.data.so ?? b.data.text ?? '').toUpperCase().trim();
  const don = String(b.data.don_vi || '').toUpperCase().trim();
  const tren = String(b.data.nhan_tren || '').toUpperCase().trim();
  const dem = /^\d{1,6}$/.test(so);
  const v = dem ? String(Math.round(Number(so) * interpolate(t, [2, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)}))) : so;
  const lines: W[][] = [[{w: so, i: 0}]];
  const bx = useBox(b, lines, 240, th.font, 250);
  const total = bx.px * LH + (don ? bx.px * 0.5 * LH : 0) + (tren ? 90 : 0);
  const top = clamp(Number((b as any).top ?? 250), 230, 1590 - total);
  const s = spring({frame: t, fps, config: {damping: 8, stiffness: 250}});
  const u = spring({frame: t - 6, fps, config: {damping: 12, stiffness: 200}});
  const donPx = Math.floor(Math.min(120, bx.px * 0.5));
  return <Stand bx={{...bx, top}} style={{opacity: out, flexDirection: 'column', alignItems: 'center', fontFamily: th.font}}>
    {tren && <div style={{fontSize: 62, lineHeight: LH, color: th.text, ...STROKE(8), opacity: u, transform: `translateY(${(1 - u) * -30}px)`, filter: SHADOW}}>{tren}</div>}
    <div style={{fontSize: bx.px, lineHeight: LH, color: th.accent, ...STROKE(Math.round(bx.px * 0.1)), filter: SHADOW, transform: `scale(${0.5 + 0.5 * s})`, whiteSpace: 'nowrap'}}>{v}</div>
    {don && <div style={{fontSize: donPx, lineHeight: LH, color: th.text, ...STROKE(Math.round(donPx * 0.12)), marginTop: -bx.px * 0.12, filter: SHADOW,
      opacity: u, transform: `translateY(${(1 - u) * 40}px)`, whiteSpace: 'nowrap'}}>{don}</div>}
  </Stand>;
};

// 6. GẠCH CHÂN: chữ hiện lên, nét gạch tô vẽ dần dưới chữ nhấn.
export const ChuGach: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, fps, out} = useLife2(b);
  const lines = chiaDong(String(b.data.text || '')); const hi = nhanIdx(b, lines);
  const bx = useBox(b, lines, 130, th.font);
  const s = spring({frame: t, fps, config: {damping: 14, stiffness: 200}});
  const p = interpolate(t, [8, 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  return <Stand bx={bx} style={{opacity: out * Math.min(1, s * 1.5)}}>
    <div style={{textAlign: 'center', fontFamily: th.font, fontSize: bx.px, color: th.text, ...STROKE(Math.round(bx.px * 0.11)), filter: SHADOW,
      transform: `translateY(${(1 - s) * 50}px)`}}>
      <Dong lines={lines} hi={hi} px={bx.px} ws={(x, hot) => hot ? {position: 'relative', color: th.accent, paddingBottom: bx.px * 0.2, margin: '0 0.05em'} : {}}
        extra={(x, hot) => hot ? <svg viewBox="0 0 200 24" preserveAspectRatio="none" style={{position: 'absolute', left: 0, bottom: bx.px * 0.02, width: '100%', height: bx.px * 0.2, overflow: 'visible'}}>
          <path d="M3 14 C 40 4, 80 22, 120 10 S 180 12, 197 6" pathLength={1} fill="none" stroke="#000" strokeWidth={bx.px * 0.17} strokeLinecap="round" vectorEffect="non-scaling-stroke"
            strokeDasharray={1} strokeDashoffset={1 - p}/>
          <path d="M3 14 C 40 4, 80 22, 120 10 S 180 12, 197 6" pathLength={1} fill="none" stroke={th.accent} strokeWidth={bx.px * 0.1} strokeLinecap="round" vectorEffect="non-scaling-stroke"
            strokeDasharray={1} strokeDashoffset={1 - p}/></svg> : null}/>
    </div>
  </Stand>;
};

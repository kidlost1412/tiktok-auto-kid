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

// 23/11 (kiểu kol-vip2 Kid duyệt): chữ VÀNG KIM — lớp sau viền đen dày, lớp trước tô dải vàng (viền không ăn vào màu vàng).
export const KIM_NEN = 'linear-gradient(180deg,#FFFBD8 0%,#FFE57A 30%,#F7BA00 50%,#C88600 57%,#FFD23F 76%,#FFF4B8 100%)';
export const Kim: React.FC<{children: React.ReactNode; vien: number; style?: React.CSSProperties}> = ({children, vien, style}) =>
  <span style={{position: 'relative', display: 'inline-block', ...style}}>
    <span style={{WebkitTextStroke: `${vien}px #1C1200`, color: '#1C1200', paintOrder: 'stroke fill'}}>{children}</span>
    <span style={{position: 'absolute', left: 0, top: 0, width: '100%', height: '100%', backgroundImage: KIM_NEN, WebkitBackgroundClip: 'text',
      backgroundClip: 'text', WebkitTextFillColor: 'transparent', WebkitTextStroke: '0px', whiteSpace: 'nowrap'}}>{children}</span>
  </span>;

// Đáy vùng chữ lớn: có phụ đề thì dừng trên dòng phụ đề (bản mẫu bọ trĩ: phụ đề che chữ "ML" dưới số 240).
const dayVung = (th: Theme) => Math.min(1590, Number(th.day ?? 1590));

// Hộp đặt chữ: tính cỡ chữ vừa chiều rộng + toạ độ trong vùng an toàn.
const useBox = (b: Block, lines: W[][], target: number, font: string, defTop = 250, chieuRong = 0, day = 1590) => {
  const top0 = Number((b as any).top ?? defTop);
  const est = lines.length * target * LH + 70;
  const t0 = clamp(top0, 230, day - est);
  const hep = t0 + est > 760 && t0 < 1560;                      // chạm dải nút TikTok → hẹp đều hai bên, tâm vẫn giữa khung (Kid 23/11: mắt người thấy lệch)
  const width = hep ? 860 : 960;
  const maxW = chieuRong || width - 70;
  let px = target;
  for (const l of lines) {
    const fit = fitText({text: l.map(x => x.w).join(' '), withinWidth: maxW, fontFamily: font, fontWeight: '900'}).fontSize;
    px = Math.min(px, fit * 0.95);
  }
  return {top: clamp(top0, 230, day - (lines.length * px * LH + 70)), width, px: Math.floor(px), left: (1080 - width) / 2};
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

const Dong: React.FC<{lines: W[][]; hi: number; px: number; ws: (w: W, hot: boolean) => React.CSSProperties; ls?: (k: number) => React.CSSProperties; extra?: (w: W, hot: boolean) => React.ReactNode;
  kim?: number}> = ({lines, hi, px, ws, ls, extra, kim}) =>
  <>{lines.map((l, k) => <div key={k} style={{whiteSpace: 'nowrap', lineHeight: LH, padding: `${px * 0.04}px 0`, ...(ls ? ls(k) : {})}}>
    {l.map((x, j) => <React.Fragment key={j}>{kim && x.i === hi
      ? <Kim vien={kim}>{x.w}</Kim>
      : <span style={{display: 'inline-block', ...ws(x, x.i === hi)}}>{x.w}{extra ? extra(x, x.i === hi) : null}</span>}{j < l.length - 1 ? ' ' : ''}</React.Fragment>)}
  </div>)}</>;

const hiBox = (th: Theme, px: number): React.CSSProperties =>
  ({background: th.accent, color: '#111', WebkitTextStroke: '0px', padding: `0 ${px * 0.14}px`, borderRadius: px * 0.14});

// 1. ĐẬP: chữ phóng to đập vào màn hình, rung nhẹ; chữ nhấn nằm trong ô vàng. Dùng được ở bất kỳ đâu (không chỉ câu mở).
export const ChuDap: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const lines = chiaDong(String(b.data.text || '')); const hi = nhanIdx(b, lines);
  return th.kieu === 'cum' && hi >= 0 && lines.flat().length >= 2 ? <ChuCum b={b} th={th} lines={lines} hi={hi}/> : <ChuDapThuong b={b} th={th}/>;
};

const ChuDapThuong: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, fps, out} = useLife2(b);
  const lines = chiaDong(String(b.data.text || '')); const hi = nhanIdx(b, lines);
  const bx = useBox(b, lines, 136, th.font, 250, 0, dayVung(th));
  const s = spring({frame: t, fps, config: {damping: 9, stiffness: 260}});
  const shake = t < 8 ? (random(`cd${t}`) - 0.5) * 18 : 0;
  const ws = (x: W, hot: boolean): React.CSSProperties => !hot ? {} : th.kieu === 'mau' ? {color: th.accent} : hiBox(th, bx.px);
  return <Stand bx={bx} style={{opacity: out}}>
    <div style={{textAlign: 'center', transform: `translate(${shake}px, 0) scale(${2.2 - 1.2 * s})`, fontFamily: th.font, fontSize: bx.px, color: th.text,
      ...STROKE(Math.round(bx.px * 0.12)), filter: SHADOW}}>
      <Dong lines={lines} hi={hi} px={bx.px} ws={ws} kim={th.kieu === 'kim' ? Math.round(bx.px * 0.14) : 0}/>
    </div>
  </Stand>;
};

// 1b. CỤM NHIỀU CỠ (text lockup, học từ video mẫu 23/11): từ phụ nhỏ, mảnh (Be Vietnam Pro) ở trên, từ chính rất to bên dưới.
// Vào: từ phụ trượt xuống + hiện, từ chính đập vào sau 4 khung; ra: biến gọn trong 4 khung.
export const LEAD_FONT = 'BVP Medium';
const ChuCum: React.FC<{b: Block; th: Theme; lines: W[][]; hi: number}> = ({b, th, lines, hi}) => {
  const {t, fps, out} = useLife2(b, 4);
  const ws = lines.flat();
  const truoc = ws.filter(x => x.i < hi).map(x => x.w).join(' ');
  const chinh = ws.find(x => x.i === hi)?.w ?? '';
  const sau = ws.filter(x => x.i > hi).map(x => x.w).join(' ');
  const W0 = 860;
  const px = Math.floor(Math.min(230, fitText({text: chinh, withinWidth: W0, fontFamily: th.font, fontWeight: '900'}).fontSize * 0.95));
  const nho = (s: string) => Math.floor(Math.min(74, fitText({text: s || 'x', withinWidth: W0, fontFamily: LEAD_FONT, fontWeight: '500'}).fontSize * 0.95));
  const cao = px * LH + (truoc ? 100 : 0) + (sau ? 100 : 0) + 40;
  const top = clamp(Number((b as any).top ?? 300), 230, dayVung(th) - cao);
  const a = spring({frame: t, fps, config: {damping: 14, stiffness: 200}});
  const k = spring({frame: t - 4, fps, config: {damping: 9, stiffness: 270}});
  const c = spring({frame: t - 8, fps, config: {damping: 14, stiffness: 200}});
  const phu = (s: string, p: number, dy: number): React.ReactNode => s ? <div style={{fontFamily: LEAD_FONT, fontWeight: 500, fontSize: nho(s), lineHeight: 1.3,
    color: th.text, ...STROKE(6), filter: SHADOW, opacity: p, transform: `translateY(${(1 - p) * dy}px)`, whiteSpace: 'nowrap'}}>{s.toLowerCase()}</div> : null;
  return <div style={{position: 'absolute', top, left: 60, width: 960, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: out}}>
    {phu(truoc, a, -30)}
    <div style={{fontFamily: th.font, fontSize: px, lineHeight: LH, color: th.accent, ...STROKE(Math.round(px * 0.11)), filter: SHADOW, whiteSpace: 'nowrap',
      opacity: Math.min(1, k * 2), transform: `scale(${1.6 - 0.6 * k})`}}>{chinh}</div>
    {phu(sau, c, 30)}
  </div>;
};

// 2. MẶT NẠ: thanh màu quét ngang, chữ lộ dần theo thanh.
export const ChuMatNa: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, out} = useLife2(b);
  const lines = chiaDong(String(b.data.text || '')); const hi = nhanIdx(b, lines);
  const bx = useBox(b, lines, 128, th.font, 250, 0, dayVung(th));
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
  const bx = useBox(b, lines, 124, th.font, 250, 0, dayVung(th));
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
  const bx = useBox(b, lines, 150, th.font, 250, 0, dayVung(th));
  const sizes = lines.map((l, k) => {
    const want = k === lines.length - 1 ? bx.px : bx.px * 0.68;
    const fit = fitText({text: l.map(x => x.w).join(' '), withinWidth: bx.width - 70, fontFamily: th.font, fontWeight: '900'}).fontSize * 0.95;
    return Math.floor(Math.min(want, fit));
  });
  return <Stand bx={bx} style={{opacity: out, flexDirection: 'column', alignItems: 'center', fontFamily: th.font}}>
    {lines.map((l, k) => {
      const s = spring({frame: t - k * 5, fps, config: {damping: 10, stiffness: 240}});
      const last = k === lines.length - 1;
      const chu = l.map(x => x.w).join(' ');
      return <div key={k} style={{whiteSpace: 'nowrap', fontSize: sizes[k], lineHeight: LH, padding: `${sizes[k] * 0.03}px 0`, color: last ? th.accent : th.text, ...STROKE(Math.round(sizes[k] * 0.12)),
        filter: SHADOW, opacity: Math.min(1, s * 1.5), transform: `translateX(${(1 - s) * (k % 2 ? 420 : -420)}px) scale(${1 + (1 - s) * 0.4})`}}>
        {last && th.kieu === 'kim' ? <Kim vien={Math.round(sizes[k] * 0.14)}>{chu}</Kim> : chu}</div>;
    })}
  </Stand>;
};

// 5b. SỐ RÈ (glitch, học từ video mẫu 23/11): 10 khung đầu số bị xé ngang + lệch kênh đỏ/xanh, giật nhẹ, rồi đứng yên sạch.
const SoRe: React.FC<{v: string; px: number; t: number; th: Theme}> = ({v, px, t, th}) => {
  const re = t < 10 ? 1 - t / 10 : (t >= 26 && t < 29 ? 0.5 : 0);         // rè lúc vào + 1 nhịp rè ngắn giữa chừng
  const lech = re * px * 0.06;
  const cat = (k: number) => {                                                // 3 lát ngang lệch nhau
    const a = random(`re${t}-${k}`), y0 = Math.floor(a * 80), h = 8 + Math.floor(random(`reh${t}-${k}`) * 18);
    return {clipPath: `inset(${y0}% 0 ${Math.max(0, 100 - y0 - h)}% 0)`, transform: `translateX(${(random(`rex${t}-${k}`) - 0.5) * px * 0.4 * re}px)`};
  };
  const lop = (mau: string, dx: number, st: React.CSSProperties = {}) => <div style={{position: 'absolute', inset: 0, color: mau, transform: `translateX(${dx}px)`,
    mixBlendMode: 'screen', whiteSpace: 'nowrap', ...st}}>{v}</div>;
  return <div style={{position: 'relative', fontSize: px, lineHeight: LH, whiteSpace: 'nowrap', filter: SHADOW}}>
    <div style={{color: '#FFF6D8', ...STROKE(Math.round(px * 0.09), '#111'), transform: `translateX(${(random(`rj${t}`) - 0.5) * 14 * re}px)`}}>{v}</div>
    {re > 0 && lop('#FF2D55', -lech)}
    {re > 0 && lop('#21E6FF', lech)}
    {re > 0 && [0, 1, 2].map(k => <div key={k} style={{position: 'absolute', inset: 0, color: th.accent, whiteSpace: 'nowrap', ...cat(k)}}>{v}</div>)}
  </div>;
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
  const bx = useBox(b, lines, 240, th.font, 250, 0, dayVung(th));
  const total = bx.px * LH + (don ? bx.px * 0.5 * LH : 0) + (tren ? 90 : 0);
  const top = clamp(Number((b as any).top ?? 250), 230, dayVung(th) - total);
  const s = spring({frame: t, fps, config: {damping: 8, stiffness: 250}});
  const u = spring({frame: t - 6, fps, config: {damping: 12, stiffness: 200}});
  const donPx = Math.floor(Math.min(120, bx.px * 0.5));
  return <Stand bx={{...bx, top}} style={{opacity: out, flexDirection: 'column', alignItems: 'center', fontFamily: th.font}}>
    {tren && <div style={{fontSize: 62, lineHeight: LH, color: th.text, ...STROKE(8), opacity: u, transform: `translateY(${(1 - u) * -30}px)`, filter: SHADOW}}>{tren}</div>}
    {th.kieu === 're' ? <SoRe v={so} px={bx.px} t={t} th={th}/> :
    <div style={{fontSize: bx.px, lineHeight: LH, color: th.accent, ...STROKE(Math.round(bx.px * 0.1)), filter: SHADOW, transform: `scale(${0.5 + 0.5 * s})`, whiteSpace: 'nowrap'}}>
      {th.kieu === 'kim' ? <Kim vien={Math.round(bx.px * 0.12)}>{v}</Kim> : v}</div>}
    {don && <div style={{fontSize: donPx, lineHeight: LH, color: th.text, ...STROKE(Math.round(donPx * 0.12)), marginTop: -bx.px * 0.12, filter: SHADOW,
      opacity: u, transform: `translateY(${(1 - u) * 40}px)`, whiteSpace: 'nowrap'}}>{don}</div>}
  </Stand>;
};

// 6. GẠCH CHÂN: chữ hiện lên, nét gạch tô vẽ dần dưới chữ nhấn.
export const ChuGach: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, fps, out} = useLife2(b);
  const lines = chiaDong(String(b.data.text || '')); const hi = nhanIdx(b, lines);
  const bx = useBox(b, lines, 130, th.font, 250, 0, dayVung(th));
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

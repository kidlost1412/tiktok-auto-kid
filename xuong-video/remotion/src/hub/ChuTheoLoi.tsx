// KHUNG "CHỮ THEO LỜI" (v10 bọ trĩ kol-vip2 Kid duyệt, gộp vào app 23/11): không thẻ, không phụ đề chạy.
// Mỗi khối = chữ DẪN nhỏ thường hiện từng từ theo lời + TỪ CHÍNH viết hoa to hiện đúng lúc đọc (slam / type / fade), cắt cứng khi khối sau vào.
// Màu theo đoạn câu chuyện (máy gán ở engine/chu_theo_loi.py). Vàng kim chỉ ở chữ khổng lồ hook.
import {loadFont} from '@remotion/fonts';
import {fitText} from '@remotion/layout-utils';
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Kim} from './ChuLon';

loadFont({family: 'BVP Bold', url: staticFile('BeVietnamPro-Bold.ttf'), weight: '700'});
loadFont({family: 'Anton', url: staticFile('Anton-Regular.ttf'), weight: '400'});

type Dan = {w: string; f: number};
export type LoiKhoi = {f0: number; f1: number; dan: Dan[]; key: string; kf: number; duoi?: string; vai: string; mau: string; co: number;
  mode: 'slam' | 'type' | 'fade'; deco?: 'shake' | 'under' | null; font: string; look: 'flat' | 'gloss'; icon?: 'gio' | null; vt: 'tren' | 'duoi'; y: number};
export type Loi = {khoi: LoiKhoi[]; hook?: {text: string; f0: number; f1: number; kieu: 'flicker' | 'flash' | 'drop'; top?: number;
  nguoi?: {dir: string; n: number; f0: number}} | null;     // nguoi: chuỗi PNG người đã tách (public/<dir>/frame_000001.png…) vẽ ĐÈ lên chữ khổng lồ → chữ nằm sau người
  qua?: {text: string; f0: number; f1: number; y: number; mau: string} | null; dan_mau: string};

const RONG = 790;                     // rộng tối đa khối chữ (v10), căn giữa khung
const LH = 1.14;                      // dòng đủ cao cho dấu tiếng Việt chữ hoa
const BONG = '0 0 3px rgba(0,0,0,0.85), 0 3px 2px rgba(0,0,0,0.55), 0 8px 22px rgba(0,0,0,0.55)';   // viền tối mềm + bóng đổ
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

const toi = (hex: string, k: number) => {           // làm tối màu hex (mặt dưới chữ bóng)
  const n = parseInt(hex.replace('#', ''), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(v => Math.round(v * k));
  return `rgb(${c.join(',')})`;
};

const vua = (text: string, font: string, weight: string, toiDa: number, rong = RONG) =>
  Math.min(toiDa, fitText({text, withinWidth: rong, fontFamily: font, fontWeight: weight}).fontSize * 0.96);

const matChu = (b: LoiKhoi): React.CSSProperties => b.look === 'gloss'
  ? {backgroundImage: `linear-gradient(180deg,#FFFFFF 0%,${b.mau} 52%,${toi(b.mau === '#FFFFFF' ? '#C9D3DD' : b.mau, 0.72)} 100%)`,
    WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent',
    filter: 'drop-shadow(0 0 2px rgba(0,0,0,0.9)) drop-shadow(0 7px 12px rgba(0,0,0,0.6))'}
  : {color: b.mau, textShadow: BONG};

// TỪ CHÍNH — 3 kiểu hiện của v10
const TuChinh: React.FC<{b: LoiKhoi; px: number; t: number}> = ({b, px, t}) => {
  const {fps} = useVideoConfig();
  const base: React.CSSProperties = {fontFamily: b.font, fontWeight: 900, fontSize: px, lineHeight: LH, whiteSpace: 'nowrap', ...matChu(b)};
  if (t < 0) return <div style={{...base, opacity: 0}}>{b.key}</div>;
  if (b.mode === 'type') {             // từng chữ cái bật ra trái → phải (~1 chữ/khung), chữ mới nhỏ nhô lên rồi hạ
    return <div style={base}>{Array.from(b.key).map((c, i) => {
      const u = clamp((t - i) / 3, 0, 1);
      return <span key={i} style={{display: 'inline-block', opacity: t >= i ? 1 : 0, transform: `translateY(${(1 - u) * -px * 0.12}px) scale(${0.7 + 0.3 * u})`,
        whiteSpace: 'pre'}}>{c}</span>;
    })}</div>;
  }
  if (b.mode === 'fade') {             // cả dòng trồi từ dưới, nhạt → đậm, nảy nhẹ, nhoè tan
    const s = spring({frame: t, fps, config: {damping: 14, stiffness: 190}});
    return <div style={{...base, opacity: clamp(t / 5, 0, 1), transform: `translateY(${(1 - s) * px * 0.45}px)`, filter: `${base.filter ?? ''} blur(${Math.max(0, 5 - t)}px)`}}>{b.key}</div>;
  }
  const sc = interpolate(t, [0, 5], [1.22, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});    // slam: lao vào từ to, nhoè rồi nét
  return <div style={{...base, opacity: clamp(t / 2, 0, 1), transform: `scale(${sc})`, filter: `${base.filter ?? ''} blur(${Math.max(0, 6 - t * 1.4)}px)`}}>{b.key}</div>;
};

const GachChan: React.FC<{mau: string; t: number}> = ({mau, t}) => {        // gạch chân vẽ tay trái → phải 0,2 s
  const p = clamp(t / 6, 0, 1);
  return <svg viewBox="0 0 400 30" preserveAspectRatio="none" style={{position: 'absolute', left: '4%', bottom: -6, width: '92%', height: 26, overflow: 'visible'}}>
    <path d="M4 18 C 90 8, 200 26, 396 10" fill="none" stroke={mau} strokeWidth={11} strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p}
      style={{filter: 'drop-shadow(0 2px 3px rgba(0,0,0,0.6))'}}/>
  </svg>;
};

const GioNeon: React.FC<{mau: string; f: number; px: number}> = ({mau, f, px}) => {   // icon giỏ hàng nét neon đứng rời cạnh từ chính, vệt sáng chạy
  const s = px * 0.78;
  return <svg width={s} height={s} viewBox="0 0 64 64" style={{filter: `drop-shadow(0 0 8px ${mau}) drop-shadow(0 0 2px rgba(0,0,0,0.8))`, flex: 'none'}}>
    <g fill="none" stroke={mau} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 10 H14 L22 42 H52 L58 20 H18" pathLength={1} strokeDasharray="0.18 0.06" strokeDashoffset={-(f % 40) / 40}/>
      <circle cx={26} cy={53} r={4}/><circle cx={48} cy={53} r={4}/>
    </g>
  </svg>;
};

const Khoi: React.FC<{b: LoiKhoi; danMau: string}> = ({b, danMau}) => {
  const f = useCurrentFrame();
  const px = vua(b.key, b.font, '900', b.co);
  const pd = Math.max(56, Math.round(px * 0.62));     // từ chính dài bị co → chữ dẫn không được nhỏ quá mức đọc được trên điện thoại
  const danTxt = b.dan.map(d => d.w).join(' ');
  const pdan = danTxt ? vua(danTxt, 'BVP Bold', '700', pd) : 0;
  const hDan = pdan ? pdan * 1.25 : 0;
  const top = b.y - hDan - px * LH / 2;
  const t = f - b.kf;
  const lac = b.deco === 'shake' && t >= 0 ? Math.sin(t * 1.7) * 16 * Math.exp(-t / 9) : 0;
  return <div style={{position: 'absolute', left: (1080 - RONG) / 2 - 40, width: RONG + 80, top, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
    <div style={{position: 'absolute', left: -60, right: -60, top: -50, bottom: -60, zIndex: -1,          // lót tối rất mềm: chữ sáng luôn có nền tối hơn (thử ảnh xám)
      background: 'radial-gradient(ellipse at center, rgba(0,0,0,0.34) 0%, rgba(0,0,0,0.18) 45%, rgba(0,0,0,0) 72%)'}}/>
    {pdan > 0 && <div style={{fontFamily: 'BVP Bold', fontWeight: 700, fontSize: pdan, lineHeight: 1.25, color: danMau, textShadow: BONG, whiteSpace: 'nowrap',
      marginBottom: px * 0.03}}>
      {b.dan.map((d, i) => {
        const u = clamp((f - d.f) / 3, 0, 1);     // "nhấc lên": nhỏ, lệch phải-dưới rồi vào dòng 0,1 s
        return <span key={i} style={{display: 'inline-block', opacity: f >= d.f ? 1 : 0, transform: `translate(${(1 - u) * 10}px, ${(1 - u) * 12}px) scale(${0.82 + 0.18 * u})`,
          marginRight: i < b.dan.length - 1 ? '0.26em' : 0}}>{d.w}</span>;
      })}
    </div>}
    <div style={{position: 'relative', display: 'flex', alignItems: 'center', gap: px * 0.18, transform: `translateX(${lac}px)`}}>
      {b.icon === 'gio' && t >= 0 && <GioNeon mau={b.mau} f={f} px={px}/>}
      <div style={{position: 'relative'}}>
        <TuChinh b={b} px={px} t={t}/>
        {b.deco === 'under' && t >= 6 && <GachChan mau="#FF3B4A" t={t - 6}/>}
      </div>
    </div>
    {b.duoi && t >= 4 && <div style={{fontFamily: 'BVP Bold', fontWeight: 700, fontSize: Math.round(px * 0.58), lineHeight: 1.25, color: danMau, textShadow: BONG,
      whiteSpace: 'nowrap', opacity: clamp((t - 4) / 4, 0, 1)}}>{b.duoi}</div>}
  </div>;
};

// Chữ khổng lồ vàng kim ở hook (lần vàng kim duy nhất của video): chớp / lóe / rơi
const ChuKhongLo: React.FC<{h: NonNullable<Loi['hook']>}> = ({h}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (f < h.f0 || f >= h.f1) return null;
  const t = f - h.f0;
  const px = vua(h.text, 'Anton', '400', 280, 1000);
  let op = 1, ty = 0, sc = 1, lech = 0, loe = 0;
  if (h.kieu === 'flicker') {
    op = t < 9 ? [1, 0, 1, 1, 0, 0, 1, 0, 1][t] : 1;
    lech = t < 12 ? 10 * (1 - t / 12) : 0;
  } else if (h.kieu === 'flash') {
    loe = interpolate(t, [0, 2, 8], [0, 0.85, 0], {extrapolateRight: 'clamp'});
    sc = interpolate(t, [0, 6], [1.15, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
    op = t < 1 ? 0 : 1;
  } else {
    const s = spring({frame: t, fps, config: {damping: 9, stiffness: 160}});
    ty = (1 - s) * -520;
  }
  const out = interpolate(f, [h.f1 - 4, h.f1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill>
    {loe > 0 && <AbsoluteFill style={{background: '#fff', opacity: loe}}/>}
    <div style={{position: 'absolute', top: h.top ?? 170, left: 0, width: 1080, display: 'flex', justifyContent: 'center', opacity: op * out,
      transform: `translateY(${ty}px) scale(${sc})`, fontFamily: 'Anton', fontSize: px, lineHeight: 1.12,
      textShadow: lech ? `${lech}px 0 rgba(255,40,60,0.75), ${-lech}px 0 rgba(40,220,255,0.75)` : undefined,
      filter: 'drop-shadow(0 14px 24px rgba(0,0,0,0.55))'}}>
      <Kim vien={Math.round(px * 0.06)}>{h.text}</Kim>
    </div>
  </AbsoluteFill>;
};

const NguoiHook: React.FC<{h: NonNullable<Loi['hook']>}> = ({h}) => {      // người tách sẵn, đúng khung theo số khung hiện tại
  const f = useCurrentFrame();
  const n = h.nguoi;
  if (!n || f < h.f0 || f >= h.f1 || f - n.f0 >= n.n) return null;
  return <AbsoluteFill><Img src={staticFile(`${n.dir}/frame_${String(f - n.f0 + 1).padStart(6, '0')}.png`)}/></AbsoluteFill>;
};

const DongQua: React.FC<{q: NonNullable<Loi['qua']>}> = ({q}) => {
  const f = useCurrentFrame();
  if (f < q.f0 || f >= q.f1) return null;
  const t = f - q.f0;
  const px = vua(q.text, 'DT Phudu', '900', 84, 860);
  return <div style={{position: 'absolute', top: q.y - px * 0.6, left: 0, width: 1080, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 18,
    opacity: clamp(t / 5, 0, 1), transform: `translateY(${(1 - clamp(t / 7, 0, 1)) * 30}px)`}}>
    <svg width={px * 0.9} height={px * 0.9} viewBox="0 0 64 64" style={{filter: `drop-shadow(0 0 6px ${q.mau}) drop-shadow(0 0 2px rgba(0,0,0,0.8))`}}>
      <g fill="none" stroke={q.mau} strokeWidth={5} strokeLinejoin="round"><rect x={8} y={26} width={48} height={32} rx={3}/><rect x={4} y={16} width={56} height={11} rx={3}/>
        <path d="M32 16 V58 M32 16 C 22 4, 12 12, 22 16 M32 16 C 42 4, 52 12, 42 16"/></g>
    </svg>
    <div style={{fontFamily: 'DT Phudu', fontWeight: 900, fontSize: px, lineHeight: LH, color: q.mau, textShadow: BONG, whiteSpace: 'nowrap'}}>{q.text}</div>
  </div>;
};

export const ChuTheoLoi: React.FC<{loi: Loi}> = ({loi}) => {
  const f = useCurrentFrame();
  const b = loi.khoi.find(k => f >= k.f0 && f < k.f1);       // cắt cứng: một khối mỗi lúc
  return <AbsoluteFill>
    {loi.hook && <ChuKhongLo h={loi.hook}/>}
    {loi.hook?.nguoi && <NguoiHook h={loi.hook}/>}
    {b && <Khoi key={b.f0} b={b} danMau={loi.dan_mau}/>}
    {loi.qua && <DongQua q={loi.qua}/>}
  </AbsoluteFill>;
};

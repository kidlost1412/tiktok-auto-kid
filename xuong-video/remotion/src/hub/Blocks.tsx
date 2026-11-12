// THƯ VIỆN KHỐI chữ/đồ họa cho hub (chặng 2). Mỗi khối: {loai, f0, f1, data}. Vùng (zone) do Python xếp để không đè:
//   TOP y≈200–640 · CENTER (chỉ câu mở ngắn) · LOWER y≈1150–1320 (lower-third) · phụ đề ở đáy · mũi tên trái.
import {LightLeak} from '@remotion/light-leaks';
import {Star} from '@remotion/shapes';
import React from 'react';
import {AbsoluteFill, Easing, interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export type Block = {loai: string; f0: number; f1: number; data: Record<string, any>};
export type Theme = {font: string; accent: string; red: string; green: string; text: string};

const STROKE = (px: number, c = '#000') => ({WebkitTextStroke: `${px}px ${c}`, paintOrder: 'stroke fill' as const});
const SHADOW = '0 14px 36px rgba(0,0,0,0.38)';

const useLife = (b: Block, outLen = 8) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = f - b.f0;
  const inn = spring({frame: t, fps, config: {damping: 14, stiffness: 190}});
  const out = interpolate(f, [b.f1 - outLen, b.f1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return {f, t, fps, inn, out, dur: b.f1 - b.f0};
};

const Zone: React.FC<{top: number; children: React.ReactNode; style?: React.CSSProperties}> = ({top, children, style}) =>
  <div style={{position: 'absolute', top, left: 60, width: 880, display: 'flex', justifyContent: 'center', ...style}}>{children}</div>;

// ---------------------------------------------------------------- CÂU MỞ (HOOK)
const HookDap: React.FC<{b: Block; th: Theme}> = ({b, th}) => {      // chữ to đập vào màn hình
  const {t, fps, out} = useLife(b);
  const words: string[] = String(b.data.text || '').toUpperCase().split(' ');
  const hi = Number(b.data.nhan ?? words.length - 1);
  const s = spring({frame: t, fps, config: {damping: 9, stiffness: 260}});
  const shake = t < 8 ? (random(`s${t}`) - 0.5) * 18 : 0;
  return <AbsoluteFill style={{opacity: out, justifyContent: 'center', alignItems: 'center'}}>
    <div style={{width: 900, textAlign: 'center', transform: `translate(${shake}px, -180px) scale(${2.2 - 1.2 * s})`, fontFamily: th.font, fontSize: 118,
      lineHeight: 1.02, color: th.text, ...STROKE(16), filter: `drop-shadow(${SHADOW})`}}>
      {words.map((w, i) => <span key={i} style={i === hi ? {color: '#111', background: th.accent, padding: '0 14px', borderRadius: 12, WebkitTextStroke: '0px'} : {}}>{w} </span>)}
    </div>
  </AbsoluteFill>;
};

const HookTungTu: React.FC<{b: Block; th: Theme}> = ({b, th}) => {   // từng chữ xếp tầng
  const {t, fps, out, dur} = useLife(b);
  const words: string[] = String(b.data.text || '').toUpperCase().split(' ');
  const step = Math.max(3, Math.min(7, Math.floor((dur * 0.6) / Math.max(1, words.length))));
  return <Zone top={(b as any).top ?? 260} style={{opacity: out, flexDirection: 'column', alignItems: 'center'}}>
    {words.map((w, i) => {
      const s = spring({frame: t - i * step, fps, config: {damping: 12, stiffness: 230}});
      return <div key={i} style={{fontFamily: th.font, fontSize: i % 2 ? 84 : 100, lineHeight: 1.0, color: i % 3 === 1 ? th.accent : th.text,
        ...STROKE(12), transform: `translateX(${(1 - s) * (i % 2 ? 300 : -300)}px)`, opacity: s}}>{w}</div>;
    })}
  </Zone>;
};

const HookGoMay: React.FC<{b: Block; th: Theme}> = ({b, th}) => {    // gõ máy
  const {t, out, inn} = useLife(b);
  const text = String(b.data.text || '');
  const n = Math.min(text.length, Math.floor(t * 1.6));
  const cursor = Math.floor(t / 8) % 2 === 0;
  return <Zone top={(b as any).top ?? 250} style={{opacity: out}}>
    <div style={{background: 'rgba(255,255,255,0.96)', borderRadius: 20, padding: '20px 30px', boxShadow: SHADOW, transform: `scale(${0.9 + 0.1 * inn})`,
      fontFamily: th.font, fontSize: 64, color: '#111', maxWidth: 860, borderLeft: `14px solid ${th.red}`}}>
      {text.slice(0, n)}<span style={{color: th.red, opacity: cursor ? 1 : 0}}>|</span>
    </div>
  </Zone>;
};

const HookMatNa: React.FC<{b: Block; th: Theme}> = ({b, th}) => {    // lộ chữ sau thanh màu quét
  const {t, out} = useLife(b);
  const p = interpolate(t, [0, 14], [0, 1], {extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
  const bar = interpolate(t, [0, 10, 20], [0, 1, 0], {extrapolateRight: 'clamp'});
  return <Zone top={(b as any).top ?? 280} style={{opacity: out}}>
    <div style={{position: 'relative', fontFamily: th.font, fontSize: 92, lineHeight: 1.05, color: th.text, textAlign: 'center', ...STROKE(12),
      clipPath: `inset(0 ${100 - p * 100}% 0 0)`}}>{String(b.data.text || '').toUpperCase()}
      <div style={{position: 'absolute', top: 0, bottom: 0, left: `${p * 100 - 6}%`, width: '6%', background: th.accent, opacity: bar}}/>
    </div>
  </Zone>;
};

const HookTem: React.FC<{b: Block; th: Theme}> = ({b, th}) => {      // tem đóng dấu
  const {t, fps, out} = useLife(b);
  const s = spring({frame: t, fps, config: {damping: 10, stiffness: 300}});
  return <Zone top={(b as any).top ?? 250} style={{opacity: out}}>
    <div style={{transform: `rotate(${-8 + (1 - s) * -20}deg) scale(${2.4 - 1.4 * s})`, border: `10px solid ${th.red}`, color: th.red, fontFamily: th.font,
      fontSize: 76, padding: '10px 36px', borderRadius: 16, background: 'rgba(255,255,255,0.92)', boxShadow: SHADOW, letterSpacing: 2}}>
      {String(b.data.text || '').toUpperCase()}</div>
  </Zone>;
};

const HookBang: React.FC<{b: Block; th: Theme}> = ({b, th}) => {     // dải băng chạy vào
  const {inn, out} = useLife(b);
  const bg = b.data.mau === 'xanh' ? th.green : th.red;
  return <div style={{position: 'absolute', top: 260, left: 0, opacity: out, transform: `translateX(${(inn - 1) * 1080}px) skewX(-6deg)`,
    background: bg, padding: '18px 54px 18px 80px', borderRadius: '0 26px 26px 0', boxShadow: SHADOW}}>
    <div style={{transform: 'skewX(6deg)', fontFamily: th.font, fontSize: 70, color: '#fff'}}>{String(b.data.text || '').toUpperCase()}</div>
  </div>;
};

const HookHoi: React.FC<{b: Block; th: Theme}> = ({b, th}) => {      // bong bóng câu hỏi
  const {fps, t, out} = useLife(b);
  const s = spring({frame: t, fps, config: {damping: 11, stiffness: 220}});
  return <Zone top={(b as any).top ?? 240} style={{opacity: out}}>
    <div style={{position: 'relative', transform: `scale(${s})`, transformOrigin: '20% 100%', background: '#fff', color: '#111', borderRadius: 40,
      padding: '24px 40px', fontFamily: th.font, fontSize: 66, maxWidth: 820, textAlign: 'center', boxShadow: SHADOW, border: `6px solid ${th.accent}`}}>
      {b.data.text}
      <div style={{position: 'absolute', bottom: -34, left: 90, width: 0, height: 0, borderLeft: '22px solid transparent', borderRight: '22px solid transparent',
        borderTop: `36px solid ${th.accent}`}}/>
    </div>
  </Zone>;
};

// ---------------------------------------------------------------- NHẤN GIỮA BÀI
const Tick: React.FC<{p: number; color: string}> = ({p, color}) =>
  <svg width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" fill={color}/>
    <path d="M17 33 L28 44 L48 22" fill="none" stroke="#fff" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round"
      strokeDasharray="50" strokeDashoffset={50 - 50 * p}/></svg>;

const Checklist: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {t, fps, inn, out, dur} = useLife(b);
  const items: string[] = (b.data.items || []).slice(0, 4);
  const gap = Math.max(6, Math.floor((dur * 0.7) / Math.max(1, items.length)));
  return <Zone top={(b as any).top ?? 230} style={{opacity: out}}>
    <div style={{background: 'rgba(255,255,255,0.95)', borderRadius: 26, padding: '22px 30px', boxShadow: SHADOW, transform: `translateY(${(1 - inn) * -60}px)`,
      opacity: inn, minWidth: 600}}>
      {b.data.tieu_de && <div style={{fontFamily: th.font, fontSize: 46, color: th.red, marginBottom: 8}}>{String(b.data.tieu_de).toUpperCase()}</div>}
      {items.map((it, i) => {
        const s = spring({frame: t - 4 - i * gap, fps, config: {damping: 13}});
        return <div key={i} style={{display: 'flex', alignItems: 'center', gap: 18, margin: '8px 0', opacity: s, transform: `translateX(${(1 - s) * 80}px)`}}>
          <Tick p={Math.min(1, s * 1.2)} color={th.green}/>
          <span style={{fontFamily: th.font, fontSize: 52, color: '#111'}}>{it}</span>
        </div>;
      })}
    </div>
  </Zone>;
};

const SoDem: React.FC<{b: Block; th: Theme}> = ({b, th}) => {        // số đếm chạy
  const {t, inn, out} = useLife(b);
  const target = Number(b.data.so || 0);
  const v = Math.round(target * interpolate(t, [4, 26], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)}));
  return <Zone top={(b as any).top ?? 230} style={{opacity: out}}>
    <div style={{display: 'flex', alignItems: 'center', gap: 26, transform: `scale(${0.8 + 0.2 * inn})`}}>
      {b.data.nhan_trai && <div style={{background: th.red, color: '#fff', fontFamily: th.font, fontSize: 60, padding: '12px 26px', borderRadius: 18, boxShadow: SHADOW}}>
        {String(b.data.nhan_trai).toUpperCase()}</div>}
      <div style={{fontFamily: th.font, fontSize: 64, color: th.text, ...STROKE(10)}}>→</div>
      <div style={{fontFamily: th.font, fontSize: 132, lineHeight: 1, color: th.accent, ...STROKE(14)}}>{v}
        <span style={{fontSize: 64, color: th.text}}> {String(b.data.don_vi || '').toUpperCase()}</span></div>
    </div>
  </Zone>;
};

const SoSanh: React.FC<{b: Block; th: Theme}> = ({b, th}) => {       // bảng so sánh ✗ / ✓
  const {t, fps, inn, out} = useLife(b);
  const col = (title: string, rows: string[], good: boolean, delay: number) => {
    const s = spring({frame: t - delay, fps, config: {damping: 14}});
    return <div style={{flex: 1, background: good ? th.green : '#3A3A3A', borderRadius: 22, padding: '16px 18px', opacity: s, transform: `translateY(${(1 - s) * 50}px)`,
      boxShadow: SHADOW}}>
      <div style={{fontFamily: th.font, fontSize: 44, color: '#fff', marginBottom: 6, textAlign: 'center'}}>{title.toUpperCase()}</div>
      {rows.slice(0, 3).map((r, i) => <div key={i} style={{fontFamily: th.font, fontSize: 40, color: '#fff', margin: '6px 0'}}>
        <span style={{color: good ? '#FFE14D' : '#FF6B6B'}}>{good ? '✓' : '✗'}</span> {r}</div>)}
    </div>;
  };
  return <Zone top={(b as any).top ?? 230} style={{opacity: out * inn}}>
    <div style={{display: 'flex', gap: 18, width: 860}}>
      {col(String(b.data.trai_tieu_de || 'ĐỒNG THƯỜNG'), b.data.trai || [], false, 2)}
      {col(String(b.data.phai_tieu_de || 'TOÀN CẦU'), b.data.phai || [], true, 10)}
    </div>
  </Zone>;
};

const VongTron: React.FC<{b: Block; th: Theme}> = ({b, th}) => {     // vẽ vòng tròn quanh sản phẩm
  const {t, out, inn} = useLife(b);
  const p = interpolate(t, [0, 16], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const C = 2 * Math.PI * 330;
  return <AbsoluteFill style={{opacity: out}}>
    <svg width="1080" height="1920" style={{position: 'absolute'}}>
      <ellipse cx="540" cy="880" rx="300" ry="420" fill="none" stroke={th.accent} strokeWidth="14" strokeLinecap="round"
        strokeDasharray={C} strokeDashoffset={C * (1 - p)} transform="rotate(-80 540 880)"/>
    </svg>
    {b.data.nhan && <div style={{position: 'absolute', top: 360, left: 0, width: 1080, textAlign: 'center', opacity: inn}}>
      <span style={{background: th.accent, color: '#111', fontFamily: th.font, fontSize: 52, padding: '8px 24px', borderRadius: 14}}>{String(b.data.nhan).toUpperCase()}</span>
    </div>}
  </AbsoluteFill>;
};

const LowerThird: React.FC<{b: Block; th: Theme}> = ({b, th}) => {
  const {inn, out, t} = useLife(b);
  const line = interpolate(t, [0, 12], [0, 1], {extrapolateRight: 'clamp'});
  return <div style={{position: 'absolute', top: 1160, left: 50, opacity: out, transform: `translateX(${(inn - 1) * 600}px)`}}>
    <div style={{height: 10, width: 420 * line, background: th.accent, borderRadius: 6, marginBottom: 8}}/>
    <div style={{background: th.red, color: '#fff', fontFamily: th.font, fontSize: 58, padding: '8px 26px', borderRadius: '12px 12px 12px 0'}}>{String(b.data.dong1 || '').toUpperCase()}</div>
    {b.data.dong2 && <div style={{display: 'inline-block', background: '#fff', color: '#111', fontFamily: th.font, fontSize: 40, padding: '6px 22px', borderRadius: '0 0 12px 12px'}}>{b.data.dong2}</div>}
  </div>;
};

const NhanDan: React.FC<{b: Block; th: Theme}> = ({b, th}) => {      // nhãn dán xoay
  const {t, fps, out} = useLife(b);
  const s = spring({frame: t, fps, config: {damping: 9, stiffness: 240}});
  return <div style={{position: 'absolute', top: 240, right: 170, opacity: out, transform: `rotate(${12 - (1 - s) * 40}deg) scale(${s})`}}>
    <div style={{position: 'relative', width: 300, height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{position: 'absolute'}}><Star points={14} innerRadius={125} outerRadius={150} fill={th.red} cornerRadius={6}/></div>
      <div style={{position: 'relative', fontFamily: th.font, fontSize: 44, color: '#fff', textAlign: 'center', width: 220, lineHeight: 1.05}}>{String(b.data.text || '').toUpperCase()}</div>
    </div>
  </div>;
};

const DaQuang: React.FC<{b: Block; th: Theme}> = ({b, th}) => {      // bút dạ quang
  const {t, out} = useLife(b);
  const p = interpolate(t, [2, 16], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <Zone top={(b as any).top ?? 270} style={{opacity: out}}>
    <div style={{fontFamily: th.font, fontSize: 80, color: '#111', textAlign: 'center', lineHeight: 1.15,
      backgroundImage: `linear-gradient(transparent 18%, ${th.accent} 18%, ${th.accent} 92%, transparent 92%)`, backgroundRepeat: 'no-repeat',
      backgroundSize: `${p}% 100%`, padding: '0 16px', textShadow: '0 0 0 #000', filter: 'drop-shadow(0 6px 12px rgba(0,0,0,0.3))'}}>
      <span style={{color: p > 30 ? '#111' : th.text, ...(p > 30 ? {} : STROKE(10))}}>{String(b.data.text || '').toUpperCase()}</span></div>
  </Zone>;
};

const CanhBao: React.FC<{b: Block; th: Theme}> = ({b, th}) => {      // băng cảnh báo
  const {inn, out, f} = useLife(b);
  const stripes = `repeating-linear-gradient(-45deg, #FFD400 0 26px, #111 26px 52px)`;
  return <Zone top={(b as any).top ?? 240} style={{opacity: out}}>
    <div style={{transform: `scaleX(${inn})`, boxShadow: SHADOW, borderRadius: 16, overflow: 'hidden', width: 860}}>
      <div style={{height: 22, background: stripes, backgroundPosition: `${f * 3}px 0`}}/>
      <div style={{background: '#111', padding: '14px 26px', textAlign: 'center'}}>
        <div style={{fontFamily: th.font, fontSize: 44, color: '#FFD400'}}>⚠ {String(b.data.tieu_de || 'LƯU Ý').toUpperCase()}</div>
        <div style={{fontFamily: th.font, fontSize: 58, color: '#fff'}}>{String(b.data.text || '').toUpperCase()}</div>
      </div>
      <div style={{height: 22, background: stripes, backgroundPosition: `${-f * 3}px 0`}}/>
    </div>
  </Zone>;
};

const DaiChay: React.FC<{b: Block; th: Theme}> = ({b, th}) => {      // dải chữ chạy
  const {f, out, inn} = useLife(b);
  const unit = `${String(b.data.text || '').toUpperCase()}  ★  `;
  return <div style={{position: 'absolute', top: 230, left: 0, width: 1080, overflow: 'hidden', opacity: out * inn, transform: 'rotate(-3deg)',
    background: th.accent, padding: '12px 0', boxShadow: SHADOW}}>
    <div style={{whiteSpace: 'nowrap', fontFamily: th.font, fontSize: 56, color: '#111', transform: `translateX(${-(f * 9) % 1400}px)`}}>{unit.repeat(8)}</div>
  </div>;
};

const BongChu: React.FC<{b: Block; th: Theme}> = ({b, th}) => {      // chữ nổ + sao
  const {t, fps, out} = useLife(b);
  const s = spring({frame: t, fps, config: {damping: 8, stiffness: 280}});
  return <Zone top={(b as any).top ?? 250} style={{opacity: out}}>
    <div style={{position: 'relative', width: 760, height: 330, display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${s})`}}>
      <div style={{position: 'absolute', transform: `rotate(${t * 1.5}deg)`}}><Star points={16} innerRadius={120} outerRadius={175} fill={th.accent}/></div>
      <div style={{position: 'relative', fontFamily: th.font, fontSize: 84, color: '#fff', ...STROKE(12), textAlign: 'center', lineHeight: 1}}>{String(b.data.text || '').toUpperCase()}</div>
    </div>
  </Zone>;
};

const MuiTenChi: React.FC<{b: Block; th: Theme}> = ({b, th}) => {    // mũi tên chỉ vào sản phẩm
  const {f, inn, out} = useLife(b);
  const bob = Math.sin(f / 4) * 16;
  return <div style={{position: 'absolute', top: 250 + bob, left: 0, width: 1080, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: out * inn}}>
    <div style={{background: '#fff', color: th.red, fontFamily: th.font, fontSize: 54, padding: '8px 26px', borderRadius: 16, boxShadow: SHADOW}}>{String(b.data.text || '').toUpperCase()}</div>
    <svg width="120" height="170" viewBox="0 0 120 170"><path d="M40 0 H80 V100 H118 L60 168 L2 100 H40 Z" fill={th.accent} stroke="#111" strokeWidth="7"/></svg>
  </div>;
};

// ---------------------------------------------------------------- CHỐT
const HopQua: React.FC<{b: Block; th: Theme}> = ({b, th}) => {       // hộp quà bật nắp + pháo giấy
  const {t, fps, out, inn} = useLife(b, 4);
  const lid = spring({frame: t - 6, fps, config: {damping: 10, stiffness: 200}});
  const conf = Array.from({length: 26}, (_, i) => {
    const a = random(`a${i}`) * Math.PI - Math.PI, v = 9 + random(`v${i}`) * 9, tt = Math.max(0, t - 8);
    return {x: Math.cos(a) * v * tt, y: Math.sin(a) * v * tt + 0.45 * tt * tt, c: [th.accent, th.red, th.green, '#fff'][i % 4], r: random(`r${i}`) * 360 + tt * 12};
  });
  return <Zone top={(b as any).top ?? 220} style={{opacity: out}}>
    <div style={{position: 'relative', display: 'flex', alignItems: 'center', gap: 24, transform: `scale(${0.7 + 0.3 * inn})`}}>
      <svg width="170" height="170" viewBox="0 0 170 170" style={{overflow: 'visible'}}>
        <rect x="20" y="70" width="130" height="95" rx="10" fill={th.red}/><rect x="76" y="70" width="18" height="95" fill={th.accent}/>
        <g transform={`translate(0 ${-lid * 46}) rotate(${-lid * 18} 20 70)`}><rect x="10" y="44" width="150" height="30" rx="8" fill={th.red}/>
          <rect x="76" y="44" width="18" height="30" fill={th.accent}/></g>
        {conf.map((c, i) => t > 8 && <rect key={i} x={85 + c.x} y={60 + c.y} width="12" height="18" fill={c.c} transform={`rotate(${c.r} ${85 + c.x} ${60 + c.y})`}/>)}
      </svg>
      <div style={{background: '#fff', borderRadius: 24, padding: '16px 28px', boxShadow: SHADOW, border: `6px solid ${th.red}`}}>
        <div style={{fontFamily: th.font, fontSize: 60, color: th.red, lineHeight: 1.05}}>{String(b.data.dong1 || '').toUpperCase()}</div>
        <div style={{fontFamily: th.font, fontSize: 42, color: th.green}}>{String(b.data.dong2 || '').toUpperCase()}</div>
      </div>
    </div>
  </Zone>;
};

const BangQua: React.FC<{b: Block; th: Theme}> = ({b, th}) => {      // bảng các mức quà
  const {t, fps, out, inn} = useLife(b, 4);
  const rows: string[] = (b.data.cac_muc || []).slice(0, 4);
  return <Zone top={(b as any).top ?? 210} style={{opacity: out}}>
    <div style={{background: 'rgba(255,255,255,0.96)', borderRadius: 26, padding: '16px 26px', boxShadow: SHADOW, transform: `translateY(${(1 - inn) * -80}px)`, minWidth: 700}}>
      <div style={{fontFamily: th.font, fontSize: 48, color: th.red, textAlign: 'center', marginBottom: 6}}>🎁 {String(b.data.tieu_de || 'QUÀ TẶNG THEO ĐƠN').toUpperCase()}</div>
      {rows.map((r, i) => {
        const s = spring({frame: t - 4 - i * 5, fps, config: {damping: 14}});
        return <div key={i} style={{fontFamily: th.font, fontSize: 40, color: '#111', padding: '6px 12px', margin: '4px 0', borderRadius: 10,
          background: i % 2 ? '#F2F2F2' : '#FFF6D6', opacity: s, transform: `translateX(${(1 - s) * 60}px)`}}>{r}</div>;
      })}
    </div>
  </Zone>;
};

const NutGioHang: React.FC<{b: Block; th: Theme}> = ({b, th}) => {   // nút giỏ hàng nhấp nháy
  const {f, inn, out} = useLife(b, 4);
  const pulse = 1 + 0.06 * Math.sin(f / 3.5);
  return <Zone top={(b as any).top ?? 250} style={{opacity: out * inn, flexDirection: 'column', alignItems: 'center'}}>
    {b.data.dong1 && <div style={{fontFamily: th.font, fontSize: 56, color: th.text, ...STROKE(10), marginBottom: 14}}>{String(b.data.dong1).toUpperCase()}</div>}
    <div style={{transform: `scale(${pulse})`, background: `linear-gradient(180deg, ${th.red}, #A3141B)`, color: '#fff', fontFamily: th.font, fontSize: 70,
      padding: '18px 56px', borderRadius: 999, boxShadow: `0 0 0 ${8 + 6 * Math.sin(f / 3.5)}px rgba(255,255,255,0.35), ${SHADOW}`}}>
      🛒 {String(b.data.text || 'BẤM GIỎ HÀNG').toUpperCase()}</div>
  </Zone>;
};

const TheQua: React.FC<{b: Block; th: Theme}> = ({b, th}) => {       // thẻ quà (kiểu cũ đã duyệt)
  const {t, fps, out} = useLife(b, 4);
  const inn = spring({frame: t, fps, config: {damping: 12, stiffness: 170}});
  const pulse = 1 + 0.035 * Math.sin(t / 5);
  const kind = b.data.kieu || 'hop_do';
  const [bg, fg] = kind === 'hop_xanh' ? [th.green, '#fff'] : kind === 'nhan_vang' ? [th.accent, '#111'] : kind === 'the_trang' ? ['#fff', th.red] : [th.red, '#fff'];
  return <Zone top={(b as any).top ?? 240} style={{opacity: out * Math.min(1, inn * 1.5), transform: `translateY(${(1 - inn) * -120}px)`}}>
    <div style={{background: bg, color: fg, fontFamily: th.font, textAlign: 'center', padding: '22px 44px', borderRadius: 28, boxShadow: SHADOW, transform: `scale(${pulse})`,
      border: kind === 'the_trang' ? `8px solid ${th.red}` : 'none'}}>
      <div style={{fontSize: 70, lineHeight: 1.08}}>{String(b.data.dong1 || '').toUpperCase()}</div>
      <div style={{fontSize: 52, marginTop: 8}}>{String(b.data.dong2 || '').toUpperCase()}</div>
    </div>
  </Zone>;
};

// ---------------------------------------------------------------- KHÔNG KHÍ
export const Atmos: React.FC<{vignette: boolean; grain: boolean; leaks: number[]; hue: number}> = ({vignette, grain, leaks, hue}) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{pointerEvents: 'none'}}>
    {vignette && <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.42) 100%)'}}/>}
    {grain && <AbsoluteFill style={{opacity: 0.07, mixBlendMode: 'overlay'}}>
      <svg width="1080" height="1920"><filter id="g"><feTurbulence type="fractalNoise" baseFrequency="0.9" seed={f % 30} numOctaves="2"/></filter>
        <rect width="1080" height="1920" filter="url(#g)"/></svg></AbsoluteFill>}
    {leaks.map((l, i) => f >= l && f < l + 30 &&
      <AbsoluteFill key={i} style={{opacity: interpolate(f, [l, l + 8, l + 22, l + 30], [0, 0.75, 0.75, 0]), mixBlendMode: 'screen'}}>
        <LightLeak seed={i + 3} hueShift={hue} durationInFrames={30} from={l}/>
      </AbsoluteFill>)}
  </AbsoluteFill>;
};

export const REGISTRY: Record<string, React.FC<{b: Block; th: Theme}>> = {
  hook_dap: HookDap, hook_tung_tu: HookTungTu, hook_go_may: HookGoMay, hook_mat_na: HookMatNa, hook_tem: HookTem, hook_bang: HookBang, hook_hoi: HookHoi,
  checklist: Checklist, so_dem: SoDem, so_sanh: SoSanh, vong_tron: VongTron, lower_third: LowerThird, nhan_dan: NhanDan, da_quang: DaQuang,
  canh_bao: CanhBao, dai_chay: DaiChay, bong_chu: BongChu, mui_ten_chi: MuiTenChi,
  hop_qua: HopQua, bang_qua: BangQua, nut_gio_hang: NutGioHang, the_qua: TheQua,
};

export const Blocks: React.FC<{blocks: Block[]; th: Theme}> = ({blocks, th}) => {
  const f = useCurrentFrame();
  return <>{blocks.filter(b => f >= b.f0 && f < b.f1 && REGISTRY[b.loai]).map((b, i) => {
    const C = REGISTRY[b.loai];
    return <C key={`${b.loai}-${b.f0}-${i}`} b={b} th={th}/>;
  })}</>;
};

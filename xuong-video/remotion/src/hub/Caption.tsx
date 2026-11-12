// Phụ đề karaoke v3: MỘT dòng theo cụm ý (Claude ngắt), chữ nhỏ là lớp phụ, đặt thấp, karaoke đúng từng chữ.
import {fitText} from '@remotion/layout-utils';
import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';

export type CapWord = {w: string; f0: number; f1: number; emph?: boolean};
export type CapLine = {text: string; f0: number; f1: number; words: CapWord[]};
export type CapStyle = 'to_dan' | 'mo_sang' | 'o_nhay' | 'gach_chay' | 'nhich_len' | 'hop_mo' | 'quet_mau' | 'vien_day';
export type CapCfg = {style: CapStyle; center_y: number; upper: boolean; max_px: number};

const MAX_W = 940;   // vùng an toàn: tránh cột nút TikTok bên phải
const MIN_PX = 42;

export const Caption: React.FC<{lines: CapLine[]; cfg: CapCfg; font: string; accent: string; text: string}> = ({lines, cfg, font, accent, text}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const idx = lines.findIndex((l, i) => f >= l.f0 - 3 && f < (lines[i + 1] ? lines[i + 1].f0 - 3 : l.f1 + 14));
  if (idx < 0) return null;
  const ln = lines[idx];
  const shown = cfg.upper ? ln.text.toUpperCase() : ln.text;
  // chừa chỗ cho viền chữ + ô màu của chữ đang đọc
  const fit = fitText({text: shown, withinWidth: MAX_W - 90, fontFamily: font, fontWeight: '900'}).fontSize * 0.94;
  const px = Math.max(MIN_PX, Math.min(cfg.max_px, fit));
  const oneLine = fit >= MIN_PX;
  const enter = spring({frame: f - (ln.f0 - 3), fps, config: {damping: 18, stiffness: 200}});
  const st = cfg.style;
  const stroke = st === 'vien_day' ? 14 : 10;
  const baseText: React.CSSProperties = st === 'hop_mo' ? {} : {WebkitTextStroke: `${stroke}px #000`, paintOrder: 'stroke fill'};
  const active = [...ln.words].reverse().find(w => f >= w.f0);
  return <div style={{position: 'absolute', left: 50, width: MAX_W, top: cfg.center_y, display: 'flex', justifyContent: 'center',
    transform: `translateY(calc(-50% + ${(1 - enter) * 16}px))`, opacity: Math.min(1, enter * 1.4)}}>
    <div style={{textAlign: 'center', fontFamily: font, fontWeight: 900, fontSize: px, lineHeight: 1.18, color: text,
      whiteSpace: oneLine ? 'nowrap' : 'normal',
      ...(st === 'hop_mo' ? {background: 'rgba(0,0,0,0.58)', borderRadius: 18, padding: '8px 22px'} : {}),
      textShadow: st === 'hop_mo' ? 'none' : '0 4px 14px rgba(0,0,0,0.45)'}}>
      {ln.words.map((w, j) => {
        const word = cfg.upper ? w.w.toUpperCase() : w.w;
        const on = active === w;
        const done = f >= w.f1 || (active ? ln.words.indexOf(active) > j : false);
        const p = Math.min(1, Math.max(0, (f - w.f0) / Math.max(1, w.f1 - w.f0)));
        const pop = on ? spring({frame: f - w.f0, fps, config: {damping: 12, stiffness: 240}}) : 0;
        let s: React.CSSProperties = {display: 'inline-block', ...baseText};
        const hot = w.emph ? 1.12 : 1.05;
        switch (st) {
          case 'to_dan': s = {...s, color: on || done ? accent : text}; break;
          case 'mo_sang': s = {...s, opacity: on || done ? 1 : 0.45, color: on ? accent : text}; break;
          case 'o_nhay': if (on) s = {...s, background: accent, color: '#111', WebkitTextStroke: '0px', borderRadius: px * 0.22,
            padding: `0 ${px * 0.18}px`, transform: `scale(${0.9 + 0.1 * pop})`}; break;
          case 'gach_chay': s = {...s, color: on ? accent : text, backgroundImage: on ? `linear-gradient(${accent},${accent})` : 'none',
            backgroundRepeat: 'no-repeat', backgroundPosition: '0 100%', backgroundSize: `${p * 100}% ${px * 0.12}px`, paddingBottom: px * 0.12}; break;
          case 'nhich_len': s = {...s, color: on ? accent : text, transform: `translateY(${-px * 0.12 * pop}px) scale(${1 + (hot - 1) * pop})`}; break;
          case 'hop_mo': s = {...s, color: on ? accent : text, transform: `scale(${1 + (hot - 1) * pop})`}; break;
          case 'quet_mau': s = on ? {...s, backgroundImage: `linear-gradient(90deg, ${accent} ${p * 100}%, ${text} ${p * 100}%)`,
            WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent'} : {...s, color: done ? accent : text}; break;
          case 'vien_day': s = {...s, color: on ? accent : text, transform: `scale(${1 + (hot - 1) * pop})`}; break;
        }
        return <React.Fragment key={j}><span style={s}>{word}</span>{j < ln.words.length - 1 ? ' ' : ''}</React.Fragment>;
      })}
    </div>
  </div>;
};

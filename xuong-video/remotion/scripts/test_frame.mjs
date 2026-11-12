// node --test scripts/test_frame.mjs   (from tc01-remotion)
// frame graphic: proxy frame mapping (S9), layout preflight fixtures (M4), crossfade schedule through a real render (M2).
import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync, spawnSync} from 'node:child_process';
import fs from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {makeProxy} from './frame_proxy.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const PY = (await import(pathToFileURL(path.join(root, '..', 'pipeline-v6', 'kitpaths.mjs')).href)).pythonExe(); // kit venv python
const font = path.join(root, 'public', 'v6', 'fonts', 'BeVietnamPro-Black.ttf');
const tmp = () => {const d = path.join(fs.mkdtempSync(path.join(tmpdir(), 'v9 frame ')), "Vườn cải's #1, thử"); fs.mkdirSync(d); return d;};
const ff = (...a) => execFileSync('ffmpeg', ['-v', 'error', '-y', ...a]);
// gray source whose frame n has luma `expr(N)`; lossless so the level identifies the frame
const graySrc = (p, size, rate, secs, expr) => ff('-f', 'lavfi', '-i', `color=black:s=${size}:r=${rate}:d=${secs},format=gray,geq=lum='${expr}'`, '-c:v', 'libx264', '-crf', '0', '-pix_fmt', 'yuv444p', p);
// Render fixtures name TC01 footage on the owner's machine (C:/Users/.../tc/*.mp4). The kit must not depend on it: every
// footage path of a fixture is replaced by a synthetic gray clip long enough for its use (src_in_f + span + 60 frames);
// f88e350a... keeps its real length of 985 frames (M3 overrun case). Main = 1080x1920, library clips = 576x1024.
const synthDir = fs.mkdtempSync(path.join(tmpdir(), 'nguồn giả #1, '));
const synthCache = new Map();
const synthClip = (orig, frames, main) => {
  const key = `${orig}|${frames}`;
  if (!synthCache.has(key)) {
    const p = path.join(synthDir, `clip ${synthCache.size} ${path.basename(orig)}`);
    ff('-f', 'lavfi', '-i', `color=c=gray:s=${main ? '1080x1920' : '576x1024'}:r=30`, '-frames:v', String(frames), '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', p);
    synthCache.set(key, p);
  }
  return synthCache.get(key);
};
const localFixture = (name, edit = s => s) => {
  const s = edit(JSON.parse(fs.readFileSync(path.join(here, 'fixtures', name), 'utf8')));
  const need = new Map();
  const walk = o => { if (Array.isArray(o)) return o.forEach(walk); if (!o || typeof o !== 'object') return;
    if (typeof o.path === 'string' && o !== s.main) need.set(o.path, Math.max(need.get(o.path) ?? 0, (o.src_in_f ?? 0) + (o.f1 - o.f0)));
    Object.values(o).forEach(walk); };
  walk(s);
  const map = new Map([...need].map(([p, n]) => [p, synthClip(p, /f88e350a52553237a464079a2016bc5b/.test(p) ? 985 : n + 60, false)]));
  s.main.path = synthClip(s.main.path, (s.main.src_in_f ?? 0) + s.duration_f + 60, true);
  const swap = o => { if (Array.isArray(o)) return o.forEach(swap); if (!o || typeof o !== 'object') return;
    if (typeof o.path === 'string' && map.has(o.path)) o.path = map.get(o.path); Object.values(o).forEach(swap); };
  swap(s);
  const sp = path.join(tmp(), name); fs.writeFileSync(sp, JSON.stringify(s));
  return sp;
};
const lumaAt = (file, w, h, x, y) => { // luma of pixel (x,y) of every frame
  const b = execFileSync('ffmpeg', ['-v', 'error', '-i', file, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], {maxBuffer: 1 << 30});
  const n = b.length / (w * h); return [...Array(n).keys()].map(i => b[i * w * h + y * w + x]);
};

test('S9 proxy: 24 fps source, non-zero in-point -> proxy frame k shows source frame floor((startF+k)*24/30)', () => {
  const d = tmp(), src = path.join(d, 'nguồn 24fps #2, a.mp4'), out = path.join(d, 'p.mp4');
  graySrc(src, '64x64', 24, 10, 'mod(N\\,40)*6');
  const r = makeProxy({src, startF: 91, frames: 12, out});
  assert.deepEqual([r.w, r.h, r.frames], [64, 64, 12]);
  // floor((91+k)*24/30) = 72,73,74,75,76,76,77,78,79,80,80,81 -> mod 40
  assert.deepEqual(lumaAt(out, 64, 64, 32, 32).map(v => Math.round(v / 6) % 40), [32, 33, 34, 35, 36, 36, 37, 38, 39, 0, 0, 1]);
  // 30 fps source: proxy frame k = source frame startF + k exactly
  const s30 = path.join(d, 's30.mp4'), o30 = path.join(d, 'p30.mp4');
  graySrc(s30, '64x64', 30, 4, 'mod(N\\,40)*6');
  makeProxy({src: s30, startF: 37, frames: 6, out: o30});
  assert.deepEqual(lumaAt(o30, 64, 64, 32, 32).map(v => Math.round(v / 6) % 40), [37, 38, 39, 0, 1, 2]);
  // asking past the end of the source is an error, not a short proxy
  assert.throws(() => makeProxy({src: s30, startF: 110, frames: 20, out: path.join(d, 'x.mp4')}), /frames != 20/);
});

test('M4 layout preflight: good-frame passes, negative fixtures are rejected for the right reason', () => {
  const lay = (f) => spawnSync(PY, ['-X', 'utf8', path.join(here, 'kit_layout.py'), '--script', path.join(here, 'fixtures', f), '--font', font, '--out', path.join(tmp(), 'l.json')], {encoding: 'utf8'});
  const good = lay('good-frame.json');
  assert.equal(good.status, 0, good.stdout + good.stderr);
  for (const [f, needle] of [['bad-frame-edge.json', 'outside safe zone'], ['bad-frame-subband.json', 'overlaps subtitle band'], ['bad-frame-tiktok.json', 'TikTok button zone'],
    ['bad-frame-label-too-long.json', 'pill width'], ['bad-frame-panels-intersect.json', 'frame panels intersect'], ['bad-frame-no-palette-key.json', 'frame_label_bg']]) {
    const r = lay(f);
    assert.equal(r.status, 1, `${f} should be rejected: ${r.stdout}`);
    assert.ok(r.stdout.includes(needle), `${f}: ${needle} not in ${r.stdout}`);
  }
});

test('M2 crossfade through render_graphics: every boundary frame = (k+1)/(xfade+1) blend of the right source frames', {timeout: 600000}, () => {
  const d = tmp();
  const A = path.join(d, 'nguồn A #1.mp4'), B = path.join(d, 'nguồn B, 2.mp4'), main = path.join(d, 'chính.mp4');
  graySrc(A, '576x1024', 30, 4, '20+40*mod(N\\,6)');   // levels 20..220
  graySrc(B, '576x1024', 30, 4, '230-40*mod(N\\,6)');  // levels 230..30
  graySrc(main, '1080x1920', 30, 4, '128');
  const pal = {card_bg: '#0B5D2E', card_border: '#FFE14D', card_shadow: '#E0262B', card_text: '#FFFFFF', card_accent: '#FFE14D', pill_bg: '#FFFFFF', pill_text: '#0B5D2E',
    tick: '#1FA64A', circle: '#FFE14D', circle_outline: '#0B5D2E', cta_bg: '#E0262B', cta_text: '#FFFFFF', frame_border: '#FFFFFF', frame_label_bg: '#0B5D2E', frame_label_text: '#FFFFFF'};
  const clips = [[A, 10, 0, 30], [B, 20, 30, 60], [A, 50, 60, 90]].map(([p, s, f0, f1]) => ({path: p, src_in_f: s, f0, f1}));
  const script = {schema: 'kich-ban/1', project_id: 't', draft_name: 't', fps: 30, width: 1080, height: 1920, duration_f: 90, main: {path: main, src_in_f: 0},
    mix: {target_lufs: -14, true_peak_max_dbtp: -1}, music: {path: null, gain_rel_voice_db: -18},
    graphics: [{id: 'g', type: 'frame', f0: 0, f1: 90, exit: 'none', xfade_f: 4, panels: [{box: [130, 240, 950, 800], f_in: 0, enter: 'none', clips}]}],
    style: {graphics_scale: 1.0, palette: pal}};
  const sp = path.join(d, 'kịch bản.json'); fs.writeFileSync(sp, JSON.stringify(script));
  const out = path.join(d, 'gfx');
  const r = spawnSync(process.execPath, [path.join(here, 'render_graphics.mjs'), '--script', sp, '--out', out, '--no-sheet'], {encoding: 'utf8', maxBuffer: 64e6});
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const got = lumaAt(path.join(out, 'g.mov'), 1080, 1920, 540, 520);
  assert.equal(got.length, 90);
  const lvA = n => 20 + 40 * (n % 6), lvB = n => 230 - 40 * (n % 6);
  const lv = [lvA, lvB, lvA];
  const h = 2, xf = 4;
  const val = (i, f) => lv[i](clips[i].src_in_f + f - clips[i].f0);  // source frame shown by clip i at timeline f (handles included)
  for (let f = 0; f < 90; f++) {
    let want;
    const b = [30, 60].find(x => f >= x - h && f < x + h);
    if (b !== undefined) {
      const i = b === 30 ? 0 : 1, a = (f - (b - h) + 1) / (xf + 1);
      want = a * val(i + 1, f) + (1 - a) * val(i, f);
    } else want = val(f < 30 ? 0 : f < 60 ? 1 : 2, f);
    assert.ok(Math.abs(got[f] - want) <= 4, `frame ${f}: luma ${got[f]}, expected ${want.toFixed(1)}`);
  }
  const m = JSON.parse(fs.readFileSync(path.join(out, 'graphics-manifest.json'), 'utf8'));
  assert.deepEqual(m.items[0].frame_clips.map(c => [c.src_start_f, c.frames, c.timeline_f]), [[10, 32, [0, 32]], [18, 34, [28, 62]], [48, 32, [58, 90]]]);
  assert.equal(m.frame_sources.length, 2);
  assert.ok(m.frame_sources.every(s => /^[0-9a-f]{64}$/.test(s.sha256) && s.size > 0));
});

test('Vietnamese stacked-mark labels: one pill height for all labels, worst-case ink inside with >= 3 px, render passes every-frame checks', {timeout: 600000}, () => {
  const out = path.join(tmp(), 'gfx');
  const r = spawnSync(process.execPath, [path.join(here, 'render_graphics.mjs'), '--script', localFixture('good-frame-vn-labels.json'), '--out', out, '--no-sheet'], {encoding: 'utf8', maxBuffer: 64e6});
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const lay = JSON.parse(fs.readFileSync(path.join(out, 'layout.json'), 'utf8')).items[0].layout;
  const labels = lay.panels[0].clips.map(c => c.label);
  assert.deepEqual(labels.map(l => l.text), ['KÍCH RỄ TC01', 'ĐẶC BIỆT · ỰC ẶC', 'KÍCH RỄ TC01']);
  assert.equal(new Set(labels.map(l => l.box[3] - l.box[1])).size, 1, 'same pill height for every label');
  assert.equal(new Set(labels.map(l => l.box[1] + l.text_top)).size, 1, 'same text baseline for every label');
  // ink of the probe set at 40 px / 48 px line (PIL, measured): top -12.5 (Ễ), bottom 48.5 (Ặ) -> band 61 + 2x4 pad = 69
  assert.equal(labels[0].box[3] - labels[0].box[1], 69);
  assert.ok(Math.abs(labels[0].text_top - 16.5) < 1e-9, `text_top ${labels[0].text_top}`);  // (69-61)/2 + 12.5
  const m = JSON.parse(fs.readFileSync(path.join(out, 'graphics-manifest.json'), 'utf8'));
  assert.equal(m.items[0].check_pass, true);
});

test('full_bleed 2x2 grid: preflight passes with the flag, fails without it, still fails for a label pill in the TikTok rail', () => {
  const lay = (f) => spawnSync(PY, ['-X', 'utf8', path.join(here, 'kit_layout.py'), '--script', path.join(here, 'fixtures', f), '--font', font, '--out', path.join(tmp(), 'l.json')], {encoding: 'utf8'});
  const good = lay('good-frame-fullbleed.json');
  assert.equal(good.status, 0, good.stdout + good.stderr);
  const off = lay('bad-frame-fullbleed-off.json');
  assert.equal(off.status, 1, off.stdout);
  assert.ok(off.stdout.includes('outside safe zone'), off.stdout);
  const rail = lay('bad-frame-fullbleed-label-rail.json');
  assert.equal(rail.status, 1, rail.stdout);
  assert.ok(rail.stdout.includes('TikTok button zone'), rail.stdout);
});

test('full_bleed 2x2 grid renders (borders/pop overshoot past the canvas just crop)', {timeout: 600000}, () => {
  const out = path.join(tmp(), 'gfx');
  const r = spawnSync(process.execPath, [path.join(here, 'render_graphics.mjs'), '--script', localFixture('good-frame-fullbleed.json'), '--out', out, '--no-sheet'], {encoding: 'utf8', maxBuffer: 64e6});
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const m = JSON.parse(fs.readFileSync(path.join(out, 'graphics-manifest.json'), 'utf8'));
  assert.equal(m.items[0].check_pass, true);
});

test('blend style: both example layouts pass preflight; the same overlapping boxes as card are rejected for overlap', () => {
  const lay = (f) => spawnSync(PY, ['-X', 'utf8', path.join(here, 'kit_layout.py'), '--script', path.join(here, 'fixtures', f), '--font', font, '--out', path.join(tmp(), 'l.json')], {encoding: 'utf8'});
  for (const f of ['good-frame-blend-sky.json', 'good-frame-blend-pair.json']) {
    const r = lay(f);
    assert.equal(r.status, 0, f + r.stdout + r.stderr);
  }
  const card = lay('bad-frame-blend-pair-card.json');
  assert.equal(card.status, 1, card.stdout);
  assert.ok(card.stdout.includes('frame panels intersect'), card.stdout);
});

test('blend style renders: per-frame checks pass; alpha ~0 at the feathered bottom, ~1 in the centre, ramp mid-way, intermediate in the overlap', {timeout: 600000}, () => {
  const out = path.join(tmp(), 'gfx');
  const r = spawnSync(process.execPath, [path.join(here, 'render_graphics.mjs'), '--script', localFixture('good-frame-blend-pair.json'), '--out', out, '--no-sheet'], {encoding: 'utf8', maxBuffer: 64e6});
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const m = JSON.parse(fs.readFileSync(path.join(out, 'graphics-manifest.json'), 'utf8'));
  assert.equal(m.items[0].check_pass, true);
  const raw = execFileSync('ffmpeg', ['-v', 'error', '-i', path.join(out, m.items[0].file), '-vf', "select='eq(n,30)'", '-frames:v', '1', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'], {maxBuffer: 1 << 30});
  assert.equal(raw.length, 1080 * 1920 * 4);
  const a = (x, y) => raw[(y * 1080 + x) * 4 + 3] / 255;
  const meas = {centre: a(270, 300), bottomEdge: a(270, 819), midRamp: a(270, 690), belowBox: a(270, 830), overlapMid: a(540, 300), overlapLeft: a(532, 300), overlapRight: a(547, 300), rightOfOverlap: a(800, 300)};
  console.log('ALPHA ' + JSON.stringify(meas));
  assert.ok(meas.centre > 0.99, 'centre');
  assert.ok(meas.bottomEdge < 0.03, 'bottom edge');
  assert.ok(meas.belowBox < 0.01, 'below the box');
  assert.ok(Math.abs(meas.midRamp - 0.5) < 0.06, 'linear mid ramp');
  assert.ok(meas.overlapMid > 0.6 && meas.overlapMid < 0.9, 'overlap middle is an intermediate alpha (two half-transparent edges composited)');
  assert.ok(meas.rightOfOverlap > 0.99, 'second panel centre');
});

test('M3: render_graphics runs the shared validator before any transcode and aborts (no output published)', () => {
  const d = tmp();
  // f88e... has 985 frames: 975 + 90 overruns
  const sp = localFixture('good-frame.json', s => { s.graphics[1].panels[0].clips[0].src_in_f = 975; return s; });
  const out = path.join(d, 'gfx');
  const r = spawnSync(process.execPath, [path.join(here, 'render_graphics.mjs'), '--script', sp, '--out', out, '--no-sheet'], {encoding: 'utf8', maxBuffer: 64e6});
  assert.equal(r.status, 1);
  assert.match(r.stderr, /script invalid[\s\S]*source overrun/);
  assert.ok(!fs.existsSync(out), 'nothing published');
  const kept = fs.readdirSync(d).find(n => n.startsWith('gfx.tmp-'));
  assert.ok(kept && !fs.existsSync(path.join(d, kept, 'public', 'frame')), 'no proxy was transcoded');
});

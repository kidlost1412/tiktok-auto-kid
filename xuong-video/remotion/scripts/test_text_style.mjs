// node --test scripts/test_text_style.mjs   (from tc01-remotion)
// rotate_deg (big_text / keyword / title_behind) and title_behind style=outline: layout preflight on the ROTATED box, real renders.
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const PY = (await import(pathToFileURL(path.join(root, '..', 'pipeline-v6', 'kitpaths.mjs')).href)).pythonExe(); // kit venv python
const font = path.join(root, 'public', 'v6', 'fonts', 'BeVietnamPro-Black.ttf');
const tmp = () => {const d = path.join(fs.mkdtempSync(path.join(tmpdir(), 'text style ')), "Vườn cải's #1, thử"); fs.mkdirSync(d); return d;};
const base = JSON.parse(fs.readFileSync(path.join(here, 'fixtures', 'bad-bigtext-subband.json'), 'utf8'));  // palette incl. title_fill, scale 1.0
const scriptWith = (graphics) => {const p = path.join(tmp(), 'kich-ban.json'); fs.writeFileSync(p, JSON.stringify({...base, graphics}), 'utf8'); return p;};
const layout = (graphics) => {
  const out = path.join(tmp(), 'l.json');
  const r = spawnSync(PY, ['-X', 'utf8', path.join(here, 'kit_layout.py'), '--script', scriptWith(graphics), '--font', font, '--out', out], {encoding: 'utf8'});
  return {...r, lay: r.status === 0 ? JSON.parse(fs.readFileSync(out, 'utf8')) : null};
};
const bt = (cy, deg) => ({id: 'b', type: 'big_text', f0: 0, f1: 40, text: '100ML', cy, ...(deg === undefined ? {} : {rotate_deg: deg})});
const bbox = (L) => L.lay.items[0].layout.pred_bbox;

test('big_text near the right edge: 0 deg passes, 8 deg is rejected because the ROTATED box enters the TikTok rail', () => {
  const flat = layout([bt(800, 0)]);
  assert.equal(flat.status, 0, flat.stdout);
  const rot = layout([bt(800, 8)]);
  assert.equal(rot.status, 1, rot.stdout);
  assert.ok(rot.stdout.includes('TikTok button zone'), rot.stdout);
  // rotating the other way mirrors the box vertically, so it fails too
  assert.equal(layout([bt(800, -8)]).status, 1);
});

test('big_text rotated 8 deg well inside the zones passes; its predicted hold bbox is taller than the flat one (rotated corners)', () => {
  const flat = layout([bt(500, 0)]);
  const rot = layout([bt(500, 8)]);
  assert.equal(rot.status, 0, rot.stdout);
  assert.equal(flat.status, 0, flat.stdout);
  const hf = flat.lay.items[0].layout.hold_bbox, hr = rot.lay.items[0].layout.hold_bbox;
  // half-width 432+: rotating 8 deg adds 2*432*sin(8deg) = ~120 px of height
  assert.ok((hr[3] - hr[1]) - (hf[3] - hf[1]) > 100, `${hf} vs ${hr}`);
});

test('keyword rotated 6 deg fully inside the safe zone passes; rotate_deg adds to the built-in -2 deg tilt', () => {
  const kw = (deg) => ({id: 'k', type: 'keyword', f0: 0, f1: 40, text: 'KÍCH RỄ', accent: 'MẠNH', y: 600, ...(deg === undefined ? {} : {rotate_deg: deg})});
  const r0 = layout([kw()]);
  const r6 = layout([kw(6)]);
  assert.equal(r6.status, 0, r6.stdout + r6.stderr);
  assert.equal(r0.lay.items[0].layout.rotate_deg ?? 0, 0);
  assert.equal(r6.lay.items[0].layout.rotate_deg, 6);
  const h = (L) => bbox(L)[3] - bbox(L)[1];
  assert.ok(h(r6) > h(r0), `${bbox(r0)} vs ${bbox(r6)}`);
});

test('keyword near the subtitle band: flat passes, rotated 15 deg is rejected on the rotated box', () => {
  const kw = (deg) => ({id: 'k', type: 'keyword', f0: 0, f1: 40, text: 'KÍCH RỄ', accent: 'MẠNH', y: 1160, rotate_deg: deg});
  const flat = layout([kw(0)]);
  assert.equal(flat.status, 0, flat.stdout);
  const r = layout([kw(15)]);
  assert.equal(r.status, 1, r.stdout);
});

test('title_behind: outline keeps the 90% width target incl. stroke, stroke = 3.5% of font; rotation is zone-checked', () => {
  const tb = (extra) => ({id: 't', type: 'title_behind', f0: 0, f1: 24, text: 'KÍCH RỄ', y: 560, matte_from: 'main', ...extra});
  const fill = layout([tb({})]), outl = layout([tb({style: 'outline'})]), rot = layout([tb({rotate_deg: 4})]);
  for (const r of [fill, outl, rot]) assert.equal(r.status, 0, r.stdout + r.stderr);
  const span = (r) => r.lay.items[0].layout.span_ratio;
  assert.ok(Math.abs(span(fill) - 0.9) < 0.01 && Math.abs(span(outl) - 0.9) < 0.01, `${span(fill)} ${span(outl)}`);
  const sw = outl.lay.items[0].layout.dims.stroke_w, fs = outl.lay.items[0].layout.font_size;
  assert.ok(Math.abs(sw / fs - 0.035) < 0.002, `stroke ${sw} / font ${fs}`);
  // 90% wide text rotated 15 deg cannot stay inside the 20 px frame margin
  assert.equal(layout([tb({rotate_deg: 15})]).status, 1);
});

const render = (graphics) => {
  const out = path.join(tmp(), 'gfx');
  const r = spawnSync(process.execPath, [path.join(here, 'render_graphics.mjs'), '--script', scriptWith(graphics), '--out', out, '--no-sheet'], {encoding: 'utf8', maxBuffer: 64e6});
  assert.equal(r.status, 0, r.stdout + r.stderr);
  return {out, m: JSON.parse(fs.readFileSync(path.join(out, 'graphics-manifest.json'), 'utf8')), lay: JSON.parse(fs.readFileSync(path.join(out, 'layout.json'), 'utf8'))};
};

test('render: rotated big_text passes the per-frame checks; rendered hold bbox is inside the predicted rotated bbox', {timeout: 600000}, () => {
  const {m, lay} = render([bt(600, 8)]);
  const it = m.items[0];
  assert.equal(it.check_pass, true);
  const L = lay.items[0].layout;
  const hold = it.alpha_bbox_per_frame[20];  // frames 9..34 are the hold
  console.log('ROTATED_BIGTEXT ' + JSON.stringify({predicted_hold_bbox: L.hold_bbox.map(Math.round), rendered_hold_bbox: hold, predicted_union_bbox: L.pred_bbox.map(Math.round), rendered_union_bbox: it.alpha_bbox_union}));
  const tol = 2;
  assert.ok(hold[0] >= L.hold_bbox[0] - tol && hold[1] >= L.hold_bbox[1] - tol && hold[2] <= L.hold_bbox[2] + tol && hold[3] <= L.hold_bbox[3] + tol, 'rendered hold bbox inside the prediction');
  const u = it.alpha_bbox_union, p = L.pred_bbox;
  assert.ok(u[0] >= p[0] - tol && u[1] >= p[1] - tol && u[2] <= p[2] + tol && u[3] <= p[3] + tol, 'rendered union inside the predicted union');
  // not absurdly loose (glyph ink does not fill the rotated corners, so the prediction is conservative)
  assert.ok((hold[2] - hold[0]) > 0.88 * (L.hold_bbox[2] - L.hold_bbox[0]) && (hold[3] - hold[1]) > 0.75 * (L.hold_bbox[3] - L.hold_bbox[1]), 'prediction not absurdly loose');
});

test('render: outline title_behind passes the per-frame checks; alpha ~1 on the stroke, ~0 inside the letter body and the counter', {timeout: 600000}, () => {
  const {out, m} = render([{id: 't', type: 'title_behind', f0: 0, f1: 24, text: 'OOO', y: 640, matte_from: 'main', style: 'outline'}]);
  assert.equal(m.items[0].check_pass, true);
  const r = spawnSync(PY, ['-X', 'utf8', path.join(here, 'measure_outline_alpha.py'), '--layout', path.join(out, 'layout.json'), '--id', 't', '--mov', path.join(out, 't.mov'), '--frame', '10', '--font', font], {encoding: 'utf8'});
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const a = JSON.parse(r.stdout);
  console.log('OUTLINE_ALPHA ' + r.stdout.trim());
  assert.ok(a.alpha_stroke_center > 0.98, `stroke centre ${a.alpha_stroke_center}`);
  assert.ok(a.alpha_body_center < 0.02, `letter body centre ${a.alpha_body_center}`);
  assert.ok(a.alpha_counter_center < 0.02, `counter centre ${a.alpha_counter_center}`);
  assert.ok(a.body_width > 3 * a.stroke_w, 'letter wall must be thicker than 3 strokes for the probe to be meaningful');
});

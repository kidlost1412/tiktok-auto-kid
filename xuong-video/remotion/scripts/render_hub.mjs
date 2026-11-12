// Dựng LỚP CHỮ trong suốt (PNG từng khung) cho hub: đóng gói 1 lần, dựng nhiều video.
// node scripts/render_hub.mjs <jobs.json> <publicDir>
// jobs.json = [{"props": "<props.json>", "frames": "<thư mục PNG>"}]
import {bundle} from '@remotion/bundler';
import {renderFrames, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [, , jobsFile, publicDir] = process.argv;
const jobs = JSON.parse(fs.readFileSync(jobsFile, 'utf8'));
const t0 = Date.now();
const serveUrl = await bundle({entryPoint: path.join(root, 'src', 'hub', 'entry.ts'), publicDir, onProgress: () => {}});
console.log(JSON.stringify({bundled: (Date.now() - t0) / 1000}));
const conc = Number(process.env.HUB_CONC || 3);   // 3: máy 16 GB RAM (6 từng làm hết RAM)
async function one(j, inputProps, c) {
  const composition = await selectComposition({serveUrl, id: 'HubOverlay', inputProps, chromiumOptions: {gl: 'angle'}, timeoutInMilliseconds: 180000});
  fs.mkdirSync(j.frames, {recursive: true});
  await renderFrames({composition, serveUrl, inputProps, chromiumOptions: {gl: 'angle'}, timeoutInMilliseconds: 180000, outputDir: j.frames,
    imageFormat: 'png', concurrency: c, imageSequencePattern: 'f[frame].[ext]', onStart: () => {}, onFrameUpdate: () => {}, logLevel: 'error'});
}
for (const j of jobs) {
  const t = Date.now();
  let inputProps;
  try { inputProps = JSON.parse(fs.readFileSync(j.props, 'utf8')); }
  catch (e) { console.log(JSON.stringify({err: j.frames, msg: 'không đọc được props: ' + String(e).slice(0, 200)})); continue; }
  try {
    await one(j, inputProps, conc);
    console.log(JSON.stringify({ok: j.frames, s: (Date.now() - t) / 1000}));
  } catch (e) {
    // Máy thiếu RAM/GPU → WebGL (vệt sáng) hỏng: dựng lại KHÔNG vệt sáng, ít luồng hơn, thay vì bỏ video
    try {
      if (inputProps.atmos) inputProps.atmos.leaks = [];
      fs.rmSync(j.frames, {recursive: true, force: true});
      await one(j, inputProps, Math.max(2, Math.floor(conc / 2)));
      console.log(JSON.stringify({ok: j.frames, s: (Date.now() - t) / 1000, ghi: 'dựng lại không vệt sáng'}));
    } catch (e2) {
      console.log(JSON.stringify({err: j.frames, msg: String(e2).slice(0, 300)}));
    }
  }
}
process.exit(0);   // không để tiến trình treo sau lỗi trình duyệt

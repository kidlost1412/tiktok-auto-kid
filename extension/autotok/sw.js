// Service worker: coordinator only. All long work (upload, editor, waiting) runs in the Studio tab's
// content script, so a stopped/restarted SW loses nothing: durable state lives in chrome.storage.local
// ('activeJob'), every handler re-reads it, and the worker is re-woken by alarms / content messages.
//
// Idempotency rules (X1 in miniature):
//  - activeJob is written BEFORE the window is opened; a job id that already has an activeJob (or was the
//    last finished one) is never started again -> no second window after a restart.
//  - 'authorized' is persisted BEFORE the content script is allowed to click Post, and only one 'authorize'
//    per job is ever granted (here and on the dev server). A reloaded tab or restarted SW after that point
//    finishes the job as 'uncertain', never re-clicks.
'use strict';

const STUDIO_URL = 'https://www.tiktok.com/tiktokstudio/upload';
const PROTOCOL = 1;
const EXT_VERSION = (typeof chrome.runtime.getManifest === 'function' && chrome.runtime.getManifest().version) || '0.0.0';
const DEFAULTS = { server: 'http://localhost:8010', token: '', clientId: null, windowStrategy: 'minimized', keepOpen: false, polling: true };
const HELLO_EVERY_MS = 55 * 1000;
const HEARTBEAT_EVERY_MS = 40 * 1000;
const NEED_RELOAD_TEXT = 'Cần tải lại tiện ích (chrome://extensions → ⟳)';
const JOB_DEADLINE_MS = 40 * 60 * 1000;   // whole job
const STALL_MS = 5 * 60 * 1000;           // no progress message from the tab (minimized tabs are throttled)
const CHUNK = 1024 * 1024;
const MAX_LOG = 40;
const CLOSE_GRACE_MS = 10000;
// K4 (cart): product sync + passive anchor template capture
const SHOP_HOST = 'shop.tiktok.com';
const SHOP_PATH = '/api/v1/streamer_desktop/selection/search';
const SYNC_DEADLINE_MS = 4.5 * 60 * 1000;   // whole sync (content.js waits 4 min for the page)
const SYNC_RETRY_MS = 60 * 1000;            // the same request_id is not retried sooner than this ... (a NEW request_id is never throttled)
const SYNC_MAX_TRIES = 3;
// v1.4: stats + comments collection (read only)
const COLLECT_EVERY_MS = 60 * 60 * 1000;        // regular cadence
const COLLECT_ON_OPEN_MS = 20 * 60 * 1000;      // a Studio page was opened: collect if the last run is older than this
const COLLECT_DEADLINE_MS = 8 * 60 * 1000;      // whole run (the MAIN world gives up after 6 min)
const COLLECT_CHUNK = 100;                   // ... nor more than this many times

// ---------- storage helpers (serialized so concurrent handlers cannot interleave read-modify-write) ----------
let chain = Promise.resolve();
const locked = (fn) => { const r = chain.then(fn); chain = r.catch(() => {}); return r; };

const getSettings = async () => Object.assign({}, DEFAULTS, (await chrome.storage.local.get('settings')).settings || {});
const getActive = async () => (await chrome.storage.local.get('activeJob')).activeJob || null;

function patchActive(patch, onlyId) {
  return locked(async () => {
    const a = await getActive();
    if (!a || (onlyId && a.id !== onlyId)) return null;
    const n = Object.assign({}, a, patch);
    await chrome.storage.local.set({ activeJob: n });
    return n;
  });
}

function log(msg, level) {
  const line = new Date().toISOString().slice(11, 23) + ' ' + (level ? level + ' ' : '') + msg;
  console.log('[autotok]', line);
  return locked(async () => {
    const { log: l = [] } = await chrome.storage.local.get('log');
    l.push(line);
    await chrome.storage.local.set({ log: l.slice(-MAX_LOG) });
  });
}

// ---------- backend API (PROTOCOL.md v1) ----------
const getConn = async () => (await chrome.storage.local.get('conn')).conn || { state: 'unpaired' };
const setConn = (patch) => locked(async () => { const c = Object.assign({}, await getConn(), patch, { at: Date.now() }); await chrome.storage.local.set({ conn: c }); return c; });

// Errors carry .status (HTTP), .code (protocol `error`) and .body. 401 / 409 states are recorded for the popup + poll loop.
async function api(path, { method = 'GET', body, timeoutMs = 15000, raw = false, headers = {}, auth = true } = {}) {
  const s = await getSettings();
  if (auth && !s.token) throw new Error('chưa ghép nối');
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const h = Object.assign({ 'X-Autotok-Protocol': String(PROTOCOL) }, auth ? { Authorization: 'Bearer ' + s.token } : {},
      method === 'POST' ? { 'X-Requested-With': 'autotok' } : {}, body ? { 'Content-Type': 'application/json; charset=utf-8' } : {}, headers);
    const r = await fetch(s.server + path, { method, signal: ctl.signal, headers: h, body: body ? JSON.stringify(body) : undefined });
    if (raw) return r;
    if (r.status === 204) return null;
    if (!r.ok) {
      let b = null; try { b = await r.json(); } catch (_) { /* non-JSON error body */ }
      const err = new Error((b && b.message) || `${method} ${path} -> HTTP ${r.status}`);
      err.status = r.status; err.code = b && b.error; err.body = b;
      await noteApiError(err);
      throw err;
    }
    return await r.json();
  } finally { clearTimeout(timer); }
}

async function noteApiError(e) {
  if (e.status === 401) await setConn({ state: 'unauthorized', message: 'Cần ghép nối lại' });
  else if (e.status === 409 && e.code === 'need_reload') await setConn({ state: 'need_reload', needReload: true, message: NEED_RELOAD_TEXT });
  else if (e.status === 409 && (e.code === 'identity_conflict' || e.code === 'no_identity')) await setConn({ state: e.code === 'identity_conflict' ? 'conflict' : 'no_identity', message: e.message });
}

// What the backend wants for a result: snake_case, not_sent, submitted schedule, sanitized response.
function toWire(a, r) {
  const w = { id: a.id, nonce: a.nonce, claim_token: a.claim_token, outcome: r.outcome, definite: r.definite === true, not_sent: r.notSent === true,
    reason: r.reason, detail: r.detail, http: r.http, status_code: r.status_code, status_msg: r.status_msg, item_id: r.item_id,
    creation_id: r.creation_id, video_id: r.video_id, schedule_time: r.schedule_time == null ? null : r.schedule_time, response: r.response, elapsed_ms: r.elapsed_ms,
    cover_status: r.cover_status, cover_warning: typeof r.cover_warning === 'string' ? r.cover_warning.slice(0, 300) : undefined };
  for (const k of Object.keys(w)) if (w[k] === undefined) delete w[k];
  return w;
}

// First https avatar URL the passport response offers (field names vary by TikTok rollout).
function avatarOf(d) {
  for (const k of ['avatar_url', 'avatar_larger', 'avatar_medium', 'avatar_thumb', 'avatar_uri']) {
    const v = d && d[k];
    const u = typeof v === 'string' ? v : v && Array.isArray(v.url_list) ? v.url_list[0] : '';
    if (typeof u === 'string' && /^https:\/\//i.test(u) && u.length <= 1900) return u;
  }
  return '';
}

// v1.4.1: the passport info often has no avatar. Ask tiktok.com for the public profile: the detail API first,
// then the profile page's embedded JSON. Cached per username for AVATAR_TTL_MS so hello stays cheap.
const AVATAR_TTL_MS = 6 * 3600 * 1000;
function avatarFromUser(u) {
  return avatarOf({ avatar_url: u && u.avatarLarger, avatar_larger: u && u.avatarMedium, avatar_medium: u && u.avatarThumb });
}
async function tiktokAvatar(username) {
  try {
    const st = (await chrome.storage.local.get('avatarCache')).avatarCache;
    if (st && st.username === username && Date.now() - st.at < AVATAR_TTL_MS) return st.url || '';
  } catch (_) { /* no cache */ }
  let url = '';
  try {
    const r = await fetch('https://www.tiktok.com/api/user/detail/?uniqueId=' + encodeURIComponent(username) + '&aid=1988', { credentials: 'include' });
    const j = await r.json();
    url = avatarFromUser(j && j.userInfo && j.userInfo.user);
  } catch (e) { console.warn('[autotok] avatar api', e); }
  if (!url) {
    try {
      const r = await fetch('https://www.tiktok.com/@' + encodeURIComponent(username), { credentials: 'include' });
      const m = /<script id="__UNIVERSAL_DATA_FOR_REWIND__"[^>]*>([\s\S]*?)<\/script>/.exec(await r.text());
      const scope = m && JSON.parse(m[1]).__DEFAULT_SCOPE__;
      url = avatarFromUser(scope && scope['webapp.user-detail'] && scope['webapp.user-detail'].userInfo && scope['webapp.user-detail'].userInfo.user);
    } catch (e) { console.warn('[autotok] avatar page', e); }
  }
  try { await chrome.storage.local.set({ avatarCache: { username, url, at: Date.now() - (url ? 0 : AVATAR_TTL_MS - 10 * 60 * 1000) } }); } catch (_) { /* ignore */ }
  return url;
}

// Logged-in TikTok account of this Chrome profile: the passport self endpoint only (data.username + data.user_id_str).
async function passportIdentity() {
  try {
    const r = await fetch('https://www.tiktok.com/passport/web/account/info/?aid=1988', { credentials: 'include' });
    const d = ((await r.json()) || {}).data || {};
    const username = typeof d.username === 'string' ? d.username.replace(/^@/, '').trim().toLowerCase() : '';
    const userId = typeof d.user_id_str === 'string' ? d.user_id_str.trim() : '';
    if (!username || !userId) return null;
    const id = { username, user_id: userId };
    const av = avatarOf(d);
    if (av) id.avatar_url = av;   // v1.3: the app downloads it (TikTok CDN links expire / block hotlinking)
    else {
      const pub = await tiktokAvatar(username);
      if (pub) id.avatar_url = pub;
    }
    return id;
  } catch (e) { console.warn('[autotok] passport', e); return null; }
}

// hello: protocol + version + identity. Answers need_reload / conflict / bound account.
async function sendHello() {
  const identity = await passportIdentity();
  const r = await api('/api/ext/hello', { method: 'POST', body: { protocol: PROTOCOL, ext_version: EXT_VERSION, identity } });
  const state = r.need_reload ? 'need_reload' : r.conflict ? 'conflict' : !identity ? 'no_identity' : 'ok';
  await setConn({ state, needReload: !!r.need_reload, message: r.need_reload ? (r.message || NEED_RELOAD_TEXT) : (r.message || ''),
    identity, bound: r.account || null, helloAt: Date.now(), error: '' });
  if (identity) await chrome.storage.local.set({ account: identity.username });
  return r;
}
async function helloIfDue(force) {
  const c = await getConn();
  if (!force && c.helloAt && Date.now() - c.helloAt < HELLO_EVERY_MS) return;
  try { await sendHello(); } catch (e) { console.warn('[autotok] hello', e); await setConn({ helloAt: Date.now() - HELLO_EVERY_MS + 10000, error: e.message }); }
}

function b64(buf) {
  const u = new Uint8Array(buf);
  let s = '';
  for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
  return btoa(s);
}

// ---------- window / tab ----------
async function openJobWindow(job) {
  const existing = await findJobTab({ id: job.id, windowId: null, strategy: 'tab' });
  if (existing) { await log(`đã có tab ${existing.id} cho job ${job.id}, không mở thêm`, 'WARN'); await patchActive({ tabId: existing.id, windowId: existing.windowId }, job.id); return; }
  const s = await getSettings();
  const { tab, windowId, strategy } = await createStudioWindow(STUDIO_URL + '#autotok=' + encodeURIComponent(job.id), s);
  await patchActive({ tabId: tab.id, windowId, phase: 'opened', strategy, lastBeat: Date.now() });
  await log(`mở tab ${tab.id} (cửa sổ ${windowId}, kiểu ${strategy}) cho job ${job.id}`);
}

// Is there a normal (user) window? Unknown (API missing / error) counts as "yes": behave exactly as before.
async function hasNormalWindow() {
  try { const ws = await chrome.windows.getAll({ windowTypes: ['normal'] }); return Array.isArray(ws) ? ws.length > 0 : true; } catch (_) { return true; }
}

// A Studio tab/window the user does not have to look at (job, product sync or collection), by the configured strategy.
// Never steals focus: a background-started Chrome (no window at all) must not pop up a visible "TikTok Studio" window, so
// the 'tab' strategy falls back to a minimized unfocused window when there is no normal window to hold the tab, and a
// minimized window that came up in the normal state is minimized again right away.
async function createStudioWindow(url, s) {
  let tab, windowId, strategy = s.windowStrategy;
  if (s.windowStrategy === 'tab' && await hasNormalWindow()) {
    tab = await chrome.tabs.create({ url, active: false });
    windowId = tab.windowId;
  } else if (s.windowStrategy === 'unfocused') {
    const w = await chrome.windows.create({ url, focused: false, state: 'normal', width: 1100, height: 800, left: 40, top: 40 });
    tab = w.tabs[0]; windowId = w.id;
  } else {
    if (strategy === 'tab') strategy = 'minimized';   // no normal window to hold a tab: use a minimized one
    const w = await chrome.windows.create({ url, state: 'minimized', focused: false });
    tab = w.tabs[0]; windowId = w.id;
    if (w.state && w.state !== 'minimized') { try { await chrome.windows.update(w.id, { state: 'minimized', focused: false }); } catch (e) { await log('thu nhỏ cửa sổ: ' + e.message, 'WARN'); } }
  }
  try { await chrome.tabs.update(tab.id, { autoDiscardable: false }); } catch (e) { await log('autoDiscardable: ' + e.message, 'WARN'); }
  return { tab, windowId, strategy };
}

async function closeJobWindow(a) {
  const s = await getSettings();
  if (s.keepOpen || !a) return;
  try {
    if (a.strategy === 'tab' && a.tabId != null) await chrome.tabs.remove(a.tabId);
    else if (a.windowId != null) await chrome.windows.remove(a.windowId);
  } catch (e) { await log('đóng cửa sổ: ' + e.message, 'WARN'); }
}

// ---------- job lifecycle ----------
async function startJob(job, local) {
  if (!['selftest', 'intercept', 'post', 'selfcheck'].includes(job.mode)) {
    await log(`từ chối job ${job.id}: chế độ "${job.mode}" không hỗ trợ`, 'WARN');
    if (!local) await api('/api/ext/result', { method: 'POST', body: { id: job.id, nonce: job.nonce, claim_token: job.claim_token, outcome: 'failed', definite: true, not_sent: true, reason: 'mode-unsupported' } }).catch((e) => log('gửi từ chối lỗi: ' + e.message, 'WARN'));
    return;
  }
  const claimed = await locked(async () => {
    const { activeJob, lastDoneId } = await chrome.storage.local.get(['activeJob', 'lastDoneId']);
    if (activeJob) return { ok: false, resume: activeJob.id === job.id };
    if (lastDoneId === job.id) return { ok: false, resume: false };
    await chrome.storage.local.set({
      activeJob: {
        id: job.id, nonce: job.nonce, claim_token: job.claim_token, mode: job.mode, job, local: !!local, phase: 'opening', openingAt: Date.now(),
        startedAt: Date.now(), lastBeat: Date.now(), tabId: null, windowId: null, authorized: false, finished: false,
      },
    });
    return { ok: true };
  });
  if (!claimed.ok) {
    if (!claimed.resume) await log(`bỏ qua job ${job.id}: đang có job khác hoặc đã xong`);
    return;
  }
  await log(`nhận job ${job.id} (${job.mode})`);
  try { await openJobWindow(job); } catch (e) {
    await finishJob(job.id, { outcome: 'failed', definite: true, reason: 'open-window-failed', detail: e.message });
  }
}

async function finishJob(id, result) {
  // Re-read `authorized` under the lock: once a post was authorized, a plain "failed" can no longer be trusted as
  // definite (the click may have happened) unless the page code explicitly said nothing was sent.
  let a = null;
  let final = result;
  await locked(async () => {
    const cur = await getActive();
    if (!cur || cur.id !== id) return;
    if (cur.authorized && result && result.outcome === 'failed' && result.notSent !== true) {
      final = Object.assign({}, result, { outcome: 'uncertain', definite: false, downgraded_from: 'failed' });
    }
    a = Object.assign({}, cur, { finished: true, result: final, finishedAt: Date.now() });
    await chrome.storage.local.set({ activeJob: a });
  });
  if (!a) return { ok: false, reason: 'no-active-job' };
  const full = Object.assign({ id, nonce: a.nonce, elapsed_ms: Date.now() - a.startedAt, authorized: a.authorized }, final);
  await log(`kết quả job ${id}: ${full.outcome}${full.reason ? ' (' + full.reason + ')' : ''}`);
  await chrome.storage.local.set({ lastResult: full });
  if (full.identity && (full.identity.value || full.identity.username)) await chrome.storage.local.set({ account: full.identity.value || full.identity.username });
  await closeJobWindow(a);
  if (!a.local && !(await deliverResult(a, full))) return { ok: true, pending: true };
  await locked(async () => { await chrome.storage.local.set({ lastDoneId: id }); await chrome.storage.local.remove('activeJob'); });
  return { ok: true };
}

const isGone = (e) => e && (e.status === 404 || e.status === 403);

// Drop a job the server no longer knows (404/403): keep the result for diagnosis, never retry it.
async function dropOrphan(a, result, why) {
  await log(`máy chủ không còn việc này, bỏ kết quả (${why})`, 'WARN');
  if (result) await chrome.storage.local.set({ lastOrphanResult: { id: a.id, result, at: Date.now() } });
  await closeJobWindow(a);
  await locked(async () => { await chrome.storage.local.set({ lastDoneId: a.id }); await chrome.storage.local.remove('activeJob'); });
}

// true = delivered or dropped (job cleared); false = transient failure, retry later with capped backoff.
async function deliverResult(a, full) {
  try {
    await api('/api/ext/result', { method: 'POST', body: toWire(a, full), timeoutMs: 20000 });
    return true;
  } catch (e) {
    if (isGone(e)) { await dropOrphan(a, full, e.message); return false; }
    const tries = (a.resultTries || 0) + 1;
    const delay = Math.min(2000 * 2 ** tries, 30000);
    await patchActive({ resultTries: tries, nextResultTry: Date.now() + delay }, a.id);
    await log(`gửi kết quả lỗi (${e.message}), thử lại sau ${delay / 1000}s`, 'WARN');
    return false;
  }
}

async function findJobTab(a) {
  const tabs = await chrome.tabs.query({ url: 'https://www.tiktok.com/*' });
  return tabs.find((x) => (x.url || '').includes('#autotok=' + encodeURIComponent(a.id))) || tabs.find((x) => x.windowId === a.windowId && a.strategy !== 'tab') || null;
}

// Revoked by the backend (deadline missed / cancelled in the app): never authorize, close the tab, forget the job.
async function revokeLocal(a, why) {
  await log(`backend đã thu hồi việc ${a.id} (${why})`, 'WARN');
  await closeJobWindow(a);
  await locked(async () => { await chrome.storage.local.set({ lastDoneId: a.id }); await chrome.storage.local.remove('activeJob'); });
}

// POST /api/ext/progress. -> {ok, revoked?}. Network errors are logged and reported as ok:true (a later heartbeat retries).
async function sendProgress(a, p) {
  try {
    const r = await api('/api/ext/progress', { method: 'POST', timeoutMs: 10000, body: Object.assign({ id: a.id, nonce: a.nonce, claim_token: a.claim_token }, p) });
    if (r && r.ok === false && (r.cancelled || r.state === 'revoked')) { await revokeLocal(a, 'progress'); return { ok: false, revoked: true }; }
    return { ok: true };
  } catch (e) {
    if (isGone(e)) { await dropOrphan(a, null, 'progress ' + e.message); return { ok: false, revoked: true }; }
    await log('gửi tiến độ lỗi: ' + e.message, 'WARN');
    return { ok: true, unsent: true };
  }
}

// Called on every tick and every wake-up: reconcile durable state with reality.
async function recover() {
  const a = await getActive();
  if (!a) return false;
  if (a.finished) { // result not delivered yet
    if (!a.local && Date.now() >= (a.nextResultTry || 0)) {
      const full = Object.assign({ id: a.id, nonce: a.nonce, authorized: a.authorized }, a.result);
      if (await deliverResult(a, full)) await locked(async () => { await chrome.storage.local.set({ lastDoneId: a.id }); await chrome.storage.local.remove('activeJob'); });
    } else if (a.local) {
      await locked(async () => { await chrome.storage.local.set({ lastDoneId: a.id }); await chrome.storage.local.remove('activeJob'); });
    }
    return true;
  }
  const now = Date.now();
  if (a.tabId == null) {
    const tabs = await chrome.tabs.query({ url: 'https://www.tiktok.com/tiktokstudio/*' });
    const t = tabs.find((x) => (x.url || '').includes('#autotok=' + encodeURIComponent(a.id)));
    if (t) { await patchActive({ tabId: t.id, windowId: t.windowId, phase: 'opened' }, a.id); await log('khôi phục tab ' + t.id); }
    else if (now - a.openingAt > 20000) { // window creation never finished and no tab exists: nothing was sent
      await openJobWindow(a.job);
    }
    return true;
  }
  let gone = false;
  try { await chrome.tabs.get(a.tabId); if (a.missingSince) await patchActive({ missingSince: null }, a.id); } catch (_) { gone = true; }
  if (gone) { // the tab id may have changed (prerender/discard): look it up by URL hash / window first
    const t = await findJobTab(a);
    if (t) { await log(`tìm lại tab theo URL/cửa sổ: ${a.tabId} -> ${t.id}`, 'WARN'); await patchActive({ tabId: t.id, windowId: t.windowId, missingSince: null }, a.id); return true; }
    if (!a.missingSince) { await patchActive({ missingSince: now }, a.id); return true; }
    if (now - a.missingSince < CLOSE_GRACE_MS) return true;
    await finishJob(a.id, a.authorized
      ? { outcome: 'uncertain', reason: 'tab-closed-after-authorization' }
      : { outcome: 'failed', definite: true, reason: 'tab-closed-before-authorization', detail: 'missing for ' + (now - a.missingSince) + ' ms, no tab with the job hash in window ' + a.windowId });
    return true;
  }
  if (!a.local && !a.authorized && now - (a.hbAt || 0) > HEARTBEAT_EVERY_MS) { // backend deadline: a heartbeat at least every 60 s
    await patchActive({ hbAt: now }, a.id);
    const r = await sendProgress(a, { phase: a.phase, msg: 'heartbeat' });
    if (r && r.revoked) return true;
  }
  if (now - a.startedAt > JOB_DEADLINE_MS || now - a.lastBeat > STALL_MS) {
    const why = now - a.startedAt > JOB_DEADLINE_MS ? 'job-deadline' : 'tab-stalled';
    await finishJob(a.id, a.authorized ? { outcome: 'uncertain', reason: why + '-after-authorization' }
      : { outcome: 'failed', definite: true, reason: why });
  }
  return true;
}

// ---------- K4: product sync ("Lấy sản phẩm từ shop") ----------
// Durable like a job: 'activeSync' in storage (written BEFORE the tab opens), one at a time, never while a job is active.
// The tab only GETs shop.tiktok.com (api-main.js) and is armed in 'block' mode: it can never reach /project/post/.
const getSync = async () => (await chrome.storage.local.get('activeSync')).activeSync || null;
const patchSync = (patch) => locked(async () => {
  const cur = await getSync();
  if (!cur) return null;
  const n = Object.assign({}, cur, patch);
  await chrome.storage.local.set({ activeSync: n });
  return n;
});

async function closeSyncWindow(sy) {
  const s = await getSettings();
  if (s.keepOpen || !sy) return;
  try {
    if (sy.strategy === 'tab' && sy.tabId != null) await chrome.tabs.remove(sy.tabId);
    else if (sy.windowId != null) await chrome.windows.remove(sy.windowId);
  } catch (e) { await log('đóng cửa sổ đồng bộ: ' + e.message, 'WARN'); }
}

// POST /api/ext/products once per COMPLETE source. Incomplete sources (error / page cap) are never sent: the app would
// mark every product it did not receive as missing. -> {ok: at least one source delivered, sources}
async function uploadProducts(sy, r) {
  if (!r || r.outcome !== 'sync_ok' || !r.identity) {
    await log(`đồng bộ sản phẩm lỗi: ${(r && (r.reason || r.outcome)) || '?'} ${(r && r.detail) || ''}`, 'WARN');
    return { ok: false, reason: r && r.reason };
  }
  const out = { ok: false, sources: {} };
  for (const source of ['my_shop', 'showcase']) {
    const src = r.sources && r.sources[source];
    if (!src) continue;
    if (!src.complete) { await log(`đồng bộ ${source}: chưa lấy đủ (${src.error || 'quá 40 trang'}), không gửi`, 'WARN'); out.sources[source] = { sent: false, error: src.error || 'incomplete' }; continue; }
    try {
      await api('/api/ext/products', { method: 'POST', timeoutMs: 60000, body: { request_id: sy.request_id, user_id: r.identity.user_id, username: r.identity.username, source, products: src.products, complete: true } });
      out.sources[source] = { sent: true, n: src.products.length }; out.ok = true;
      await log(`đã gửi ${src.products.length} sản phẩm (${source})`);
    } catch (e) { out.sources[source] = { sent: false, error: e.message }; await log(`gửi sản phẩm ${source} lỗi: ${e.message}${e.status === 409 ? ' (app từ chối: tài khoản không khớp)' : ''}`, 'WARN'); }
  }
  return out;
}

// POST /api/ext/sync_status {request_id, ok:false, reason}: tells the app why a sync failed so the page can show it.
// Old app without the endpoint: ignored.
async function reportSyncFailure(rid, reason) {
  try { await api('/api/ext/sync_status', { method: 'POST', timeoutMs: 8000, body: { request_id: rid, ok: false, reason: String(reason || 'unknown').slice(0, 200) } }); }
  catch (e) { await log('sync_status: ' + e.message, 'WARN'); }
}

function failureReason(result, summary) {
  if (result && result.outcome !== 'sync_ok') return (result.reason || result.outcome || 'unknown') + (result.detail ? ': ' + result.detail : '');
  if (summary && summary.reason) return summary.reason;
  const errs = Object.values((summary && summary.sources) || {}).map((x) => x && x.error).filter(Boolean);
  return errs.length ? errs.join('; ') : (summary && summary.error) || 'unknown';
}

async function finishSync(result) {
  let sy = null;
  await locked(async () => {
    const cur = await getSync();
    if (!cur || cur.finished) return;
    sy = Object.assign({}, cur, { finished: true });
    await chrome.storage.local.set({ activeSync: sy });
  });
  if (!sy) return { ok: false };
  let summary;
  try { summary = await uploadProducts(sy, result); } catch (e) { summary = { ok: false, error: e.message }; await log('đồng bộ sản phẩm: ' + e.message, 'WARN'); }
  await locked(async () => {
    const { syncState } = await chrome.storage.local.get('syncState');
    await chrome.storage.local.set({ lastSync: Object.assign({ request_id: sy.request_id, at: Date.now() }, summary) });
    if (summary.ok && syncState && syncState.request_id === sy.request_id) await chrome.storage.local.set({ syncState: Object.assign({}, syncState, { done: true }) });
  });
  await closeSyncWindow(sy);
  await locked(async () => { await chrome.storage.local.remove('activeSync'); });
  if (!summary.ok) await reportSyncFailure(sy.request_id, failureReason(result, summary));
  return { ok: true };
}

// true = a sync is running (no new claims meanwhile). Also reaps a stale / orphaned one after a restart.
async function recoverSync() {
  const sy = await getSync();
  if (!sy) return false;
  if (sy.finished) { await closeSyncWindow(sy); await locked(async () => { await chrome.storage.local.remove('activeSync'); }); return false; }
  if (Date.now() - sy.startedAt > SYNC_DEADLINE_MS) { await finishSync({ outcome: 'failed', reason: 'sync-timeout' }); return false; }
  if (sy.tabId != null) {
    let gone = false;
    try { await chrome.tabs.get(sy.tabId); } catch (_) { gone = true; }
    if (gone) { await finishSync({ outcome: 'failed', reason: 'tab-closed' }); return false; }
  }
  return true;
}

// Every NEW request_id is started promptly: it replaces a sync still running for an older request_id (the owner pressed
// the button again), and its retry budget starts at zero. The same request_id is retried at most SYNC_MAX_TRIES times.
async function startSync(rid) {
  const now = Date.now();
  let superseded = null, exhausted = false;
  const started = await locked(async () => {
    const { activeSync, syncState } = await chrome.storage.local.get(['activeSync', 'syncState']);
    if (activeSync && (activeSync.request_id === rid || activeSync.finished)) return false;   // same request running, or one still uploading
    const st = syncState && syncState.request_id === rid ? syncState : { request_id: rid, tries: 0 };
    if (st.done || now - (st.lastAt || 0) < SYNC_RETRY_MS) return false;
    if (st.tries >= SYNC_MAX_TRIES) { if (!st.gaveUp) { exhausted = true; await chrome.storage.local.set({ syncState: Object.assign({}, st, { gaveUp: true }) }); } return false; }
    if (activeSync) superseded = activeSync;                    // an older request is still running: abandon it (its nonce dies with it)
    await chrome.storage.local.set({
      activeSync: { request_id: rid, nonce: Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2), startedAt: now, tabId: null, windowId: null, strategy: null, finished: false },
      syncState: { request_id: rid, tries: st.tries + 1, lastAt: now, done: false },
    });
    return true;
  });
  if (exhausted) await reportSyncFailure(rid, 'gave-up');
  if (!started) return false;
  if (superseded) { await log(`yêu cầu mới ${rid} thay yêu cầu ${superseded.request_id} đang chạy`, 'WARN'); await closeSyncWindow(superseded); }
  await log(`đồng bộ sản phẩm (yêu cầu ${rid})`);
  try {
    const s = await getSettings();
    const { tab, windowId, strategy } = await createStudioWindow(STUDIO_URL + '#autotok=sync-' + encodeURIComponent(rid), s);
    await patchSync({ tabId: tab.id, windowId, strategy });
  } catch (e) { await finishSync({ outcome: 'failed', reason: 'open-window-failed', detail: e.message }); }
  return true;
}

// GET /api/ext/tasks -> {sync_products: <request_id>|null}. Old app without the endpoint: logged once, ignored.
let lastTasksErr = '';
async function pollTasks() {
  let t = null;
  try { t = await api('/api/ext/tasks', { timeoutMs: 10000 }); } catch (e) {
    if (e.message !== lastTasksErr) { lastTasksErr = e.message; await log('tasks: ' + e.message, 'WARN'); }
    return false;
  }
  lastTasksErr = '';
  const rid = t && t.sync_products != null && t.sync_products !== '' && t.sync_products !== false ? String(t.sync_products) : null;
  return rid ? startSync(rid) : false;
}

// ---------- v1.4: stats + comments collection ("Số liệu") ----------
// Read only. Runs in an ordinary Studio tab the owner already has open, else in a background window opened by the configured
// windowStrategy (minimized by default, never focused), exactly like a posting job. Never while a job / product sync is active.
// Durable like a job: 'activeCollect' is written BEFORE the tab opens; 'collectState' keeps cadence, backoff and the last comment id.
const getCollect = async () => (await chrome.storage.local.get('activeCollect')).activeCollect || null;
const getCS = async () => (await chrome.storage.local.get('collectState')).collectState || {};
const patchCS = (patch) => locked(async () => { const cur = (await chrome.storage.local.get('collectState')).collectState || {}; await chrome.storage.local.set({ collectState: Object.assign({}, cur, patch) }); });
const patchCollect = (patch) => locked(async () => {
  const cur = await getCollect();
  if (!cur) return null;
  const n = Object.assign({}, cur, patch);
  await chrome.storage.local.set({ activeCollect: n });
  return n;
});
const isStudioUrl = (u) => /^https:\/\/www\.tiktok\.com\/tiktokstudio\//.test(u || '');

async function closeCollectWindow(co) {
  if (!co || co.mode !== 'window') return;   // an ordinary tab of the owner is never closed
  const s = await getSettings();
  if (s.keepOpen) return;
  try {
    if (co.strategy === 'tab' && co.tabId != null) await chrome.tabs.remove(co.tabId);
    else if (co.windowId != null) await chrome.windows.remove(co.windowId);
  } catch (e) { await log('đóng cửa sổ thu số liệu: ' + e.message, 'WARN'); }
}

// Start a collection if one is due (reason 'open' = a Studio page was just opened: shorter minimum gap). -> true when a run was started.
async function collectIfDue(reason, hintTab) {
  const s = await getSettings();
  if (!s.token) return false;
  const c = await getConn();
  if (c.state !== 'ok' || c.needReload || !c.bound) return false;     // not paired / wrong protocol / account not enabled in the app
  const gap = reason === 'open' ? COLLECT_ON_OPEN_MS : COLLECT_EVERY_MS - 5 * 60 * 1000;
  const now = Date.now();
  const cs = await getCS();
  if (now < (cs.nextAt || 0) || now - (cs.lastAt || 0) < gap) return false;
  if (await getActive() || await getSync() || await getCollect()) return false;
  const identity = await passportIdentity();
  if (!identity) { await patchCS({ nextAt: now + 10 * 60 * 1000 }); return false; }   // not logged in to TikTok: try again later
  const since = cs.lastCommentTime ? Math.max(0, cs.lastCommentTime - 6 * 3600) : 0;
  const id = 'collect-' + now;
  const started = await locked(async () => {
    const { activeJob, activeSync, activeCollect, collectState } = await chrome.storage.local.get(['activeJob', 'activeSync', 'activeCollect', 'collectState']);
    if (activeJob || activeSync || activeCollect) return false;
    await chrome.storage.local.set({
      activeCollect: { id, nonce: Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2), startedAt: now, tabId: null, windowId: null, strategy: null, mode: 'window', finished: false,
        identity, plan: { windowDays: 30, insightDays: 7, lastCommentId: cs.lastCommentId || '', since }, sent: { videos: 0, comments: 0 }, sendError: '' },
      collectState: Object.assign({}, collectState, { lastAt: now }),
    });
    return true;
  });
  if (!started) return false;
  await log(`thu số liệu (${reason})`);
  try {
    const co = await getCollect();
    const tabs = await chrome.tabs.query({ url: 'https://www.tiktok.com/tiktokstudio/*' });
    const usable = (hintTab ? [hintTab] : tabs).filter((t) => t && isStudioUrl(t.url) && !(t.url || '').includes('#autotok=') && !t.discarded && t.status !== 'loading');
    for (const t of usable) {
      try {
        const r = await chrome.tabs.sendMessage(t.id, { type: 'collectRun', nonce: co.nonce, plan: co.plan });
        if (r && r.ok) { await patchCollect({ tabId: t.id, windowId: t.windowId, mode: 'existing' }); await log(`thu số liệu trong tab đang mở ${t.id}`); return true; }
      } catch (_) { /* content script of an older version / not injected: next tab, else a background window */ }
    }
    const { tab, windowId, strategy } = await createStudioWindow(STUDIO_URL + '#autotok=' + encodeURIComponent(id), s);
    await patchCollect({ tabId: tab.id, windowId, mode: 'window', strategy });
  } catch (e) { await finishCollect({ outcome: 'failed', reason: 'open-window-failed', detail: e.message }); }
  return true;
}

async function sendCollectBatch(co, path, body) {
  await api(path, { method: 'POST', timeoutMs: 60000, body: Object.assign({ user_id: co.identity.user_id, username: co.identity.username }, body) });
}

async function finishCollect(result) {
  let co = null;
  await locked(async () => {
    const cur = await getCollect();
    if (!cur || cur.finished) return;
    co = Object.assign({}, cur, { finished: true });
    await chrome.storage.local.set({ activeCollect: co });
  });
  if (!co) return { ok: false };
  const ok = !!(result && result.outcome === 'collect_ok') && !co.sendError;
  const cs = await getCS();
  const fails = ok ? 0 : (cs.fails || 0) + 1;
  const now = Date.now();
  await patchCS({
    fails, nextAt: ok ? 0 : now + Math.min(COLLECT_EVERY_MS, 5 * 60 * 1000 * 2 ** (fails - 1)),
    lastOkAt: ok ? now : cs.lastOkAt || null,
    last: { at: now, ok, outcome: result && result.outcome, reason: (result && result.reason) || co.sendError || '', videos: co.sent.videos, comments: co.sent.comments,
      insights: result && result.insights, errors: ((result && result.errors) || []).slice(0, 5), elapsed_ms: result && result.elapsed_ms },
  });
  await log(`thu số liệu xong: ${ok ? 'ok' : 'lỗi'} ${co.sent.videos} bài, ${co.sent.comments} bình luận${co.sendError ? ' (gửi lỗi: ' + co.sendError + ')' : ''}${result && result.reason ? ' (' + result.reason + ')' : ''}`, ok ? '' : 'WARN');
  await closeCollectWindow(co);
  await locked(async () => { await chrome.storage.local.remove('activeCollect'); });
  return { ok: true };
}

// true = a collection is running (no new claims meanwhile). Reaps a stale / orphaned one after a restart.
async function recoverCollect() {
  const co = await getCollect();
  if (!co) return false;
  if (co.finished) { await closeCollectWindow(co); await locked(async () => { await chrome.storage.local.remove('activeCollect'); }); return false; }
  if (Date.now() - co.startedAt > COLLECT_DEADLINE_MS) { await finishCollect({ outcome: 'failed', reason: 'collect-timeout' }); return false; }
  if (co.tabId != null) {
    let gone = false;
    try { await chrome.tabs.get(co.tabId); } catch (_) { gone = true; }
    if (gone) { await finishCollect({ outcome: 'failed', reason: 'tab-closed' }); return false; }
  }
  return true;
}

// The collect tab is recognised by its id or by its #autotok=collect-<time> hash (a tab id can change on prerender).
async function collectFor(t) {
  if (!t) return null;
  const co = await getCollect();
  if (!co || co.finished || co.mode !== 'window') return null;
  const byHash = (t.url || '').includes('#autotok=' + encodeURIComponent(co.id));
  if (co.tabId !== t.id && !byHash) return null;
  if (co.tabId !== t.id) await patchCollect({ tabId: t.id, windowId: t.windowId });
  return co;
}
async function collectOwner(sender, msg) {
  const co = await getCollect();
  if (!co || co.finished || !sender.tab || co.tabId !== sender.tab.id || !msg.nonce || msg.nonce !== co.nonce) return null;
  return co;
}

// ---------- K4: passive cart template (anchors of the owner's own manual post) ----------
const idLike = (x) => typeof x === 'string' && /^[0-9]{16,20}$/.test(x);

// Does the shop know this id as a product (exact product_id in a keyword=<id> search)? Fetched here (host permission, no CORS).
async function shopKnowsProduct(id) {
  for (const type of [3, 2]) {
    try {
      const r = await fetch(`https://${SHOP_HOST}${SHOP_PATH}?search_type=${type}&keyword=${id}&origin=2&cursor=0&count=10&aid=1180`, { credentials: 'include' });
      const text = await r.text();
      if (/"code"\s*:\s*0\s*[,}]/.test(text) && new RegExp('"product_id"\\s*:\\s*"?' + id + '"?\\s*[,}]').test(text)) return true;
    } catch (_) { /* unknown: not confirmed */ }
  }
  return false;
}

// The template must say exactly which id is the product (it is what gets replaced later). Never guess: a wrong id would keep
// the real product in the cart. -> id | null
async function pickTemplateProduct(candidates, keyed) {
  const cands = Array.from(new Set((Array.isArray(candidates) ? candidates : []).filter(idLike))).slice(0, 12);
  const keyedSet = new Set((Array.isArray(keyed) ? keyed : []).filter(idLike));
  const confirmed = [];
  for (const id of cands) if (await shopKnowsProduct(id)) confirmed.push(id);
  if (confirmed.length === 1) return keyedSet.size && !keyedSet.has(confirmed[0]) ? null : confirmed[0];
  if (confirmed.length > 1) return null;
  return keyedSet.size === 1 ? Array.from(keyedSet)[0] : null;
}

let lastCapture = { json: '', at: 0 };

// ---------- polling ----------
let polling = false;
let lastPollState = '';
const setPoll = async (state) => { if (state !== lastPollState) { lastPollState = state; await chrome.storage.local.set({ poll: { at: Date.now(), state } }); } };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function pollLoop() {
  if (polling) return;
  polling = true;
  try {
    for (;;) {
      try {
        const s = await getSettings();
        if (!s.polling || !s.token) { await setPoll(s.token ? 'tắt' : 'chưa ghép nối'); return; }
        await helloIfDue();
        if (await recover()) { await wait(4000); continue; }   // an active / undelivered job: no new claims
        if (await recoverSync()) {
          await setPoll('đang lấy sản phẩm từ shop');
          if (await pollTasks()) continue;                        // a NEWER request_id replaces the running sync at once
          await wait(4000); continue;
        }
        if (await recoverCollect()) { await setPoll('đang thu số liệu'); await wait(4000); continue; }
        const c = await getConn();
        if (c.state === 'unauthorized') { await setPoll('cần ghép nối lại'); return; }
        if (c.needReload) { await setPoll('cần tải lại tiện ích'); await wait(10000); continue; }   // never claim while out of protocol range
        if (c.state === 'conflict' || c.state === 'no_identity') { await setPoll(c.state === 'conflict' ? 'trùng tài khoản' : 'chưa đăng nhập TikTok'); await wait(10000); continue; }
        if (await pollTasks()) continue;                          // a product sync was started: let it run first
        if (await collectIfDue('timer')) continue;                // v1.4: hourly stats + comments (read only)
        await setPoll('đang chờ job');
        const job = await api('/api/ext/next?wait=20', { timeoutMs: 30000 });
        if (job) await startJob(job, false);
      } catch (e) {
        // includes "No SW" when Chrome tears the worker down mid-await: log, back off, alarm restarts us
        console.warn('[autotok] pollLoop', e);
        try { await setPoll('lỗi: ' + e.message); } catch (_) { return; }
        await wait(5000);
      }
    }
  } finally { polling = false; }
}

// ---------- content-script messages ----------
async function jobFor(sender, msg) {
  const a = await getActive();
  if (!a || a.finished || !sender.tab || a.tabId !== sender.tab.id) return null;
  if (msg.nonce && msg.nonce !== a.nonce) return null;
  return a;
}

// The sync tab is recognised by its id or its #autotok=sync-<request_id> hash (a tab id can change on prerender).
async function syncFor(t) {
  if (!t) return null;
  const sy = await getSync();
  if (!sy || sy.finished) return null;
  const byHash = (t.url || '').includes('#autotok=sync-' + encodeURIComponent(sy.request_id));
  if (sy.tabId !== t.id && !byHash) return null;
  if (sy.tabId !== t.id) await patchSync({ tabId: t.id, windowId: t.windowId });
  return sy;
}

const handlers = {
  async hello(msg, sender) {
    let a = await getActive();
    const t = sender.tab;
    if (a && !a.finished && t && !a.authorized && a.tabId !== t.id) {
      const byHash = (t.url || '').includes('#autotok=' + encodeURIComponent(a.id));
      const byWindow = a.windowId != null && t.windowId === a.windowId && a.strategy !== 'tab';
      if (a.tabId == null ? byHash : (byHash || byWindow)) {
        await log(`hello từ tab ${t.id} (${byHash ? 'hash' : 'cùng cửa sổ'}), nhận làm tab của job (trước: ${a.tabId})`, 'WARN');
        a = await patchActive({ tabId: t.id, windowId: t.windowId, phase: 'opened', missingSince: null }, a.id);
      }
    }
    a = a && !a.finished && t && a.tabId === t.id ? a : null;
    if (!a) {
      const co = await collectFor(t);
      if (co) return { role: 'collect', nonce: co.nonce, plan: co.plan };
      const sy = await syncFor(t);
      return sy ? { role: 'sync', request_id: sy.request_id, nonce: sy.nonce } : { role: 'none' };
    }
    if (a.authorized) { // tab reloaded after the Post click was authorized: never redo
      await finishJob(a.id, { outcome: 'uncertain', reason: 'tab-reloaded-after-authorization' });
      return { role: 'none' };
    }
    if (!a.local) { // resume only while the server still considers the job active
      let st = null;
      try { st = await api('/api/ext/job_state?id=' + encodeURIComponent(a.id), { timeoutMs: 5000 }); } catch (e) { await log('job_state: ' + e.message, 'WARN'); }
      if (!st || !['claimed', 'uploading', 'ready'].includes(st.state) || st.authorized) {
        await log(`không tiếp tục job ${a.id}: server=${st && st.state}${st && st.authorized ? ' đã cấp quyền' : ''}`, 'WARN');
        await chrome.storage.local.set({ lastDoneId: a.id }); await chrome.storage.local.remove('activeJob');
        return { role: 'none' };
      }
    }
    await patchActive({ phase: 'hello', lastBeat: Date.now() }, a.id);
    return { role: a.mode === 'selfcheck' ? 'selfcheck' : 'job', job: a.job, nonce: a.nonce };
  },

  async ready(msg, sender) { // content script injected: log + tell the dev server immediately
    const a = await getActive();
    const mine = !!(a && !a.finished && sender.tab && (a.tabId === sender.tab.id || (sender.tab.url || '').includes('#autotok=' + encodeURIComponent(a.id))));
    await log(`content script ${msg.stage} tab=${sender.tab && sender.tab.id} ${msg.where} job=${mine ? a.id : '-'}`);
    if (mine && !a.local) await sendProgress(a, { phase: 'content-ready', msg: msg.stage + ' ' + msg.where, extra: { tabId: sender.tab.id, state: msg.state } });
    if (!mine && msg.stage === 'load' && sender.tab && isStudioUrl(sender.tab.url) && !(sender.tab.url || '').includes('#autotok=')) collectIfDue('open', sender.tab).catch((e) => log('collect: ' + e.message, 'WARN'));
    return { ok: true };
  },

  async progress(msg, sender) {
    const a = await jobFor(sender, msg);
    if (!a) return { ok: false };
    await patchActive({ phase: msg.phase, pct: msg.pct == null ? null : msg.pct, lastBeat: Date.now() }, a.id);
    await log(`[${msg.phase}] ${msg.msg || ''}${msg.pct != null ? ' ' + msg.pct + '%' : ''}`);
    if (!a.local) {
      await patchActive({ hbAt: Date.now() }, a.id);
      const r = await sendProgress(a, { phase: msg.phase, msg: msg.msg, pct: msg.pct, extra: msg.extra });
      if (r.revoked) return { ok: false, revoked: true };
    }
    return { ok: true };
  },

  async videoMeta(msg, sender) {
    const a = await jobFor(sender, msg);
    if (!a || a.local) return { ok: false, error: 'no job' };
    const m = await api('/api/ext/video/meta?id=' + encodeURIComponent(a.id));
    return { ok: true, meta: Object.assign({}, m, { chunk: CHUNK }) };
  },

  // Per-product cover (<= 5 MB, one response). Any failure is reported to the content script, which posts without the cover.
  async coverGet(msg, sender) {
    const a = await jobFor(sender, msg);
    if (!a || a.local) return { ok: false, error: 'no job' };
    const r = await api('/api/ext/cover?id=' + encodeURIComponent(a.id), { raw: true, timeoutMs: 60000 });
    if (r.status !== 200) return { ok: false, error: 'HTTP ' + r.status };
    const buf = await r.arrayBuffer();
    if (buf.byteLength <= 0 || buf.byteLength > 5 * 1024 * 1024) return { ok: false, error: 'độ dài ảnh sai ' + buf.byteLength };
    await patchActive({ lastBeat: Date.now() }, a.id);
    return { ok: true, b64: b64(buf), len: buf.byteLength };
  },

  async videoChunk(msg, sender) {
    const a = await jobFor(sender, msg);
    if (!a || a.local) return { ok: false, error: 'no job' };
    const start = msg.index * CHUNK;
    const end = Math.min(start + CHUNK, msg.size) - 1;
    const r = await api('/api/ext/video?id=' + encodeURIComponent(a.id), { raw: true, timeoutMs: 120000, headers: { Range: `bytes=${start}-${end}` } });
    if (r.status !== 206) return { ok: false, error: 'HTTP ' + r.status + ' (cần 206 Partial Content)' };
    const buf = await r.arrayBuffer();
    if (buf.byteLength !== end - start + 1) return { ok: false, error: `độ dài sai ${buf.byteLength}` };
    await patchActive({ lastBeat: Date.now() }, a.id);
    return { ok: true, b64: b64(buf), len: buf.byteLength };
  },

  // One-time permission to click Post. Persist FIRST (conservative: a crash after this point = uncertain).
  // One-time publish grant. The local flag is persisted FIRST (a crash after it = uncertain), then the server's durable
  // conditional transition decides. A denial clears the local flag (nothing was sent).
  async authorize(msg, sender) {
    const a = await jobFor(sender, msg);
    if (!a || a.mode !== 'post') return { ok: false, reason: 'not-a-post-job' };
    const won = await locked(async () => {
      const cur = await getActive();
      if (!cur || cur.id !== a.id || cur.authorized || cur.finished) return false;
      await chrome.storage.local.set({ activeJob: Object.assign({}, cur, { authorized: true, authorizedAt: Date.now() }) });
      return true;
    });
    if (!won) return { ok: false, reason: 'already-authorized' };
    // The backend needs state=ready before it grants: tell it first (awaited, so the order is guaranteed). Nothing is
    // authorized yet, so any failure here is a plain denial.
    const ready = await sendProgress(a, { phase: 'ready', msg: 'sẵn sàng đăng' });
    if (!ready.ok || ready.unsent) {
      await patchActive({ authorized: false }, a.id);
      return { ok: false, reason: 'ready-not-confirmed' };
    }
    let r = null;
    try {
      r = await api('/api/ext/authorize', { method: 'POST', body: { id: a.id, nonce: a.nonce, claim_token: a.claim_token, body_sha256: msg.sha, creation_id: msg.creation_id,
        visibility_type: msg.visibility_type, schedule_time: msg.schedule_time == null ? null : msg.schedule_time, identity: msg.identity } });
    } catch (e) {
      // An HTTP answer (4xx, or 500 persist_failed) means NOT granted. No answer / other 5xx: it may have been granted.
      const denied = !!e.status && (e.status < 500 || e.code === 'persist_failed');
      r = { ok: false, reason: denied ? (e.code || 'http-' + e.status) : 'server-unreachable:' + e.message, unknown: !denied };
    }
    if (!r || !r.ok) {
      // unreachable = the server may have committed the grant: stay authorized (=> uncertain) and refuse the click
      if (!(r && r.unknown)) await patchActive({ authorized: false }, a.id);
      return { ok: false, reason: (r && r.reason) || 'denied' };
    }
    await log('ĐÃ CẤP QUYỀN đăng (một lần, gắn với hash nội dung)');
    return { ok: true };
  },

  // K4: content.js (sync / job tab) asks the SW to GET the shop search API because the page itself is blocked by CORS.
  // Only that one endpoint, GET, only for the active job tab or the active sync tab.
  async shopFetch(msg, sender) {
    let u; try { u = new URL(String(msg.url || '')); } catch (_) { return { ok: false, error: 'bad-url' }; }
    if (u.protocol !== 'https:' || u.host !== SHOP_HOST || u.pathname !== SHOP_PATH) return { ok: false, error: 'url-not-allowed' };
    const tabId = sender.tab && sender.tab.id;
    const a = await getActive(), sy = await getSync();
    const mine = (a && !a.finished && a.tabId === tabId) || (sy && !sy.finished && sy.tabId === tabId);
    if (!mine) return { ok: false, error: 'not-a-job-tab' };
    try { const r = await fetch(u.href, { credentials: 'include' }); return { ok: true, status: r.status, text: await r.text() }; } catch (e) { return { ok: false, error: String(e && e.message) }; }
  },

  // v1.4: batches from the collecting tab -> the app. Failures are remembered (the run then counts as failed and is retried
  // with backoff); the last comment id only advances after the app has acknowledged those comments.
  async collectBatch(msg, sender) {
    const co = await collectOwner(sender, msg);
    const b = msg.batch;
    if (!co || !b) return { ok: false };
    try {
      if (b.part === 'stats') {
        const videos = Array.isArray(b.videos) ? b.videos : [];
        const base = { collected_at: new Date().toISOString(), list_complete: b.list_complete === true };
        for (let i = 0; i === 0 || i < videos.length; i += COLLECT_CHUNK) {
          const chunk = videos.slice(i, i + COLLECT_CHUNK);
          await sendCollectBatch(co, '/api/ext/stats', Object.assign({}, base, i === 0 && b.account ? { account: b.account } : {}, { videos: chunk }));
          co.sent.videos += chunk.length;
        }
      } else if (b.part === 'comments') {
        const list = Array.isArray(b.comments) ? b.comments : [];
        for (let i = 0; i < list.length; i += COLLECT_CHUNK) {
          await sendCollectBatch(co, '/api/ext/comments', { comments: list.slice(i, i + COLLECT_CHUNK) });
          co.sent.comments += Math.min(COLLECT_CHUNK, list.length - i);
        }
        if (b.newest && b.newest.comment_id) await patchCS({ lastCommentId: String(b.newest.comment_id), lastCommentTime: Number(b.newest.created_at) || 0 });
      }
      await patchCollect({ sent: co.sent });
      return { ok: true };
    } catch (e) {
      await log(`gửi số liệu (${b.part}) lỗi: ${e.message}`, 'WARN');
      await patchCollect({ sendError: String(e.message).slice(0, 120), sent: co.sent });
      return { ok: false, error: e.message };
    }
  },

  async collectDone(msg, sender) {
    const co = await collectOwner(sender, msg);
    if (!co) return { ok: false };
    return finishCollect(msg.result);
  },

  async syncResult(msg, sender) {
    const sy = await getSync();
    if (!sy || sy.finished || !sender.tab || sy.tabId !== sender.tab.id || !msg.nonce || msg.nonce !== sy.nonce) return { ok: false };
    return finishSync(msg.result);
  },

  // K4: the owner posted a video with a cart by hand in Studio. Learn the template (anchors + which id is the product) and
  // hand it to the app. Fire and forget: nothing here touches the owner's request, and every failure is only logged.
  async anchorCapture(msg, sender) {
    const s = await getSettings();
    if (!s.token) return { ok: false, reason: 'unpaired' };
    const url = (sender.tab && sender.tab.url) || '';
    if (!/^https:\/\/www\.tiktok\.com\/tiktokstudio\//.test(url)) return { ok: false, reason: 'not-studio' };
    const a = await getActive();
    if (a && !a.finished && sender.tab && a.tabId === sender.tab.id) return { ok: false, reason: 'job-tab' };   // never learn from our own tab
    if (!Array.isArray(msg.anchors) || !msg.anchors.length) return { ok: false, reason: 'no-anchors' };
    const json = JSON.stringify(msg.anchors);
    if (json.length > 200000) return { ok: false, reason: 'too-big' };
    if (json === lastCapture.json && Date.now() - lastCapture.at < 30000) return { ok: true, duplicate: true };
    lastCapture = { json, at: Date.now() };
    const identity = await passportIdentity();
    if (!identity) { await log('mẫu giỏ hàng: chưa biết tài khoản TikTok, không gửi', 'WARN'); return { ok: false, reason: 'no-identity' }; }
    const productId = await pickTemplateProduct(msg.candidates, msg.keyed);
    if (!productId) { await log('mẫu giỏ hàng: không xác định chắc chắn đâu là product_id (nhiều ứng viên hoặc shop không nhận ra), không gửi', 'WARN'); return { ok: false, reason: 'product-id-unclear' }; }
    try {
      await api('/api/ext/anchor_template', { method: 'POST', timeoutMs: 20000, body: { user_id: identity.user_id, username: identity.username, product_id: productId,
        anchors: msg.anchors, captured_at: typeof msg.captured_at === 'string' ? msg.captured_at : new Date().toISOString() } });
      await chrome.storage.local.set({ lastCapture: { product_id: productId, username: identity.username, at: Date.now() } });
      await log(`đã học mẫu giỏ hàng (sản phẩm ${productId}, ${identity.username})`);
      return { ok: true };
    } catch (e) { await log('gửi mẫu giỏ hàng lỗi: ' + e.message, 'WARN'); return { ok: false, reason: 'send-failed' }; }
  },

  async result(msg, sender) {
    const a = await jobFor(sender, msg);
    if (!a) return { ok: false };
    return finishJob(a.id, msg.result);
  },
};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const h = msg && handlers[msg.type];
  if (!h) return false; // popup messages are handled below
  h(msg, sender).then(sendResponse, (e) => { log(`handler ${msg.type}: ${e.message}`, 'ERR'); sendResponse({ ok: false, error: e.message }); });
  return true;
});

// ---------- popup messages ----------
const popup = {
  async pair(msg) {
    const code = String(msg.code || '').trim();
    if (!/^[0-9]{6}$/.test(code)) { await chrome.storage.local.set({ pairError: 'Mã gồm đúng 6 chữ số' }); return { ok: false }; }
    await chrome.storage.local.set({ pairError: '', pairing: true });
    try {
      const r = await api('/api/ext/pair', { method: 'POST', auth: false, body: { code, label: 'Chrome', ext_version: EXT_VERSION, protocol: PROTOCOL } });
      await chrome.storage.local.set({ settings: Object.assign(await getSettings(), { token: r.token, clientId: r.client_id }), pairError: '', pairing: false });
      await setConn({ state: 'ok', needReload: false, message: '' });
      await helloIfDue(true);
      pollLoop().catch((e) => console.warn('[autotok] pollLoop', e));
      return { ok: true };
    } catch (e) {
      await chrome.storage.local.set({ pairError: e.message || 'Ghép nối lỗi', pairing: false });
      return { ok: false };
    }
  },
  async unpair() {
    await chrome.storage.local.set({ settings: Object.assign(await getSettings(), { token: '', clientId: null }), conn: { state: 'unpaired', at: Date.now() } });
    return { ok: true };
  },
  async saveSettings(msg) {
    await chrome.storage.local.set({ settings: Object.assign(await getSettings(), msg.settings) });
    pollLoop().catch((e) => console.warn('[autotok] pollLoop', e));
    return { ok: true };
  },
  async selfcheck() {
    const id = 'selfcheck-' + Date.now();
    await startJob({ id, nonce: Math.random().toString(36).slice(2), mode: 'selfcheck', caption: '', visibility: 'public', schedule_time: null }, true);
    return { ok: true, id };
  },
  async clear() { // abandon the active job (e.g. after a test); does not post anything
    const a = await getActive();
    if (a) {
      if (!a.local && !a.finished) await api('/api/ext/cancel', { method: 'POST', body: { id: a.id, nonce: a.nonce, claim_token: a.claim_token, reason: 'owner-cleared' }, timeoutMs: 5000 }).catch((e) => log('cancel lỗi (xoá local tiếp): ' + e.message, 'WARN'));
      try { if (a.strategy === 'tab' && a.tabId != null) await chrome.tabs.remove(a.tabId); else if (a.windowId != null) await chrome.windows.remove(a.windowId); } catch (e) { await log('đóng cửa sổ: ' + e.message, 'WARN'); }
      await chrome.storage.local.set({ lastDoneId: a.id });
    }
    await chrome.storage.local.remove(['activeJob', 'log']);
    await log('đã xoá job đang chạy và log');
    return { ok: true };
  },
  async poll() { pollLoop().catch((e) => console.warn('[autotok] pollLoop', e)); return { ok: true }; },
};
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || !msg.popup || !popup[msg.popup]) return false;
  popup[msg.popup](msg).then(sendResponse, (e) => sendResponse({ ok: false, error: e.message }));
  return true;
});

// ---------- wake-up sources ----------
chrome.alarms.create('autotok-tick', { periodInMinutes: 0.5 });
chrome.alarms.create('autotok-collect', { periodInMinutes: 60 });
const kick = () => pollLoop().catch((e) => console.warn('[autotok] pollLoop', e));
chrome.alarms.onAlarm.addListener((al) => {
  recover().catch((e) => log('recover: ' + e.message, 'ERR'));
  kick();
  if (al && al.name === 'autotok-collect') collectIfDue('alarm').catch((e) => log('collect: ' + e.message, 'WARN'));
});
chrome.runtime.onStartup.addListener(kick);
chrome.runtime.onInstalled.addListener(kick);

// Who closed / replaced the job tab? Log it; recover() decides after a grace period.
chrome.tabs.onRemoved.addListener(async (tabId, info) => {
  const a = await getActive();
  if (a && !a.finished && a.tabId === tabId) {
    await log(`tab ${tabId} bị đóng: isWindowClosing=${info.isWindowClosing} windowId=${info.windowId}`, 'WARN');
    await patchActive({ missingSince: Date.now() }, a.id);
  }
});
chrome.tabs.onReplaced.addListener(async (added, removed) => {
  const a = await getActive();
  if (a && !a.finished && a.tabId === removed) {
    await log(`tab ${removed} được thay bằng ${added} (prerender/discard)`, 'WARN');
    await patchActive({ tabId: added, missingSince: null, lastBeat: Date.now() }, a.id);
  }
});
log('SW khởi động');
kick();

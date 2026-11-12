// MAIN-world job runner (needs lib.js loaded first). Production job = mode 'post' (protocol v1); selftest/intercept exist for
// the dev-server test double only (upload-only / body built, never sent).
// Publishing (post mode only) goes through ONE gated path: publishOnce(). Everything else never sends /project/post/.
// Talks to content.js (isolated world) via window.postMessage {__autotok:1, nonce, ...}.
(function () {
  'use strict';
  if (window.__autotokApi) return;
  window.__autotokApi = true;
  const L = window.AutotokLib;
  const AID = 1988, REGION = 'ap-singapore-1';
  const MODES = ['selftest', 'intercept', 'post'];
  const gate = L.createPublishGate();
  let sentFlag = false;          // true from the moment xhr.send is invoked: any later problem is uncertain
  let running = false;           // single-flight: a duplicate 'run' message is ignored
  let NONCE = null;

  const mem = () => { const m = performance.memory; return m ? { usedMB: Math.round(m.usedJSHeapSize / 1048576), totalMB: Math.round(m.totalJSHeapSize / 1048576) } : null; };
  const post = (kind, data) => window.postMessage(Object.assign({ __autotok: 1, from: 'api', kind, nonce: NONCE }, data), location.origin);
  const progress = (phase, msg, pct, extra) => post('p', { phase, msg, pct, extra });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  class StepFail extends Error { constructor(step, msg, extra) { super(step + ': ' + msg); this.step = step; this.extra = extra; } }

  // Host + path only (query strings can carry signed values).
  const safeUrl = (u) => { try { const x = new URL(u, location.href); return x.host + x.pathname; } catch (_) { return '(bad url)'; } };
  const mask = (s) => (typeof s === 'string' && s.length > 8 ? s.slice(0, 3) + '…(' + s.length + ')' : '***');

  // One network step with the log fields the owner asked for. Never logs headers/bodies.
  async function step(name, url, init, { json = false } = {}) {
    const t0 = performance.now();
    const rec = { step: name, url: safeUrl(url), credentials: init.credentials, status: null, readable: false, ms: 0, mem: null };
    let r;
    try { r = await fetch(url, init); } catch (e) {
      rec.ms = Math.round(performance.now() - t0); rec.mem = mem();
      rec.error = e && e.name + ': ' + e.message;   // CORS failures surface as TypeError "Failed to fetch" (no detail available to scripts)
      progress('step', name + ' lỗi mạng/CORS', null, rec);
      throw new StepFail(name, 'network/CORS error (' + rec.error + ')', rec);
    }
    rec.status = r.status; rec.type = r.type;     // 'cors' = readable; 'opaque' would mean no-cors
    let text = null, data = null;
    try { text = await r.text(); rec.readable = true; } catch (e) { rec.error = 'body unreadable: ' + e.message; }
    if (json && text != null) { try { data = JSON.parse(text); } catch (_) { rec.error = 'non-JSON body'; } }
    rec.ms = Math.round(performance.now() - t0); rec.mem = mem();
    progress('step', `${name} HTTP ${r.status} ${rec.ms}ms`, null, rec);
    if (!r.ok) throw new StepFail(name, 'HTTP ' + r.status, rec);
    return { data, text, rec };
  }

  function creationId() {
    const a = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_';
    const b = crypto.getRandomValues(new Uint8Array(21));
    return Array.from(b, (x) => a[x % a.length]).join('');
  }
  const uuid = () => crypto.randomUUID();

  async function probeVideo(blob) {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(blob), v = document.createElement('video');
      const done = (r) => { URL.revokeObjectURL(url); v.removeAttribute('src'); v.load(); resolve(r); };
      const timer = setTimeout(() => done(null), 10000);
      v.preload = 'metadata'; v.muted = true;
      v.onloadedmetadata = () => { clearTimeout(timer); done(v.videoWidth && v.duration ? { width: v.videoWidth, height: v.videoHeight, duration_ms: Math.round(v.duration * 1000) } : null); };
      v.onerror = () => { clearTimeout(timer); done(null); };
      v.src = url;
    });
  }

  async function upload(job, blob) {
    const ids = { creation_id: creationId() };
    const cc = job.chunk_credentials === 'include' ? 'include' : 'omit';  // storage host is not tiktok.com: Python sends no cookies there
    // 1. create project
    const cp = await step('create-project', `/api/v1/web/project/create/?creation_id=${ids.creation_id}&type=1&aid=${AID}`, { method: 'POST', credentials: 'include' }, { json: true });
    if (!cp.data || !('project' in cp.data)) throw new StepFail('create-project', 'no "project" in response', cp.rec);
    ids.project_keys = Object.keys(cp.data.project || {}).slice(0, 10);
    // 2. upload auth (STS) - secrets never leave this function
    const au = await step('upload-auth', `/api/v1/video/upload/auth/?aid=${AID}`, { credentials: 'include' }, { json: true });
    const tok = au.data && au.data.video_token_v5;
    if (!tok || !tok.access_key_id || !tok.secret_acess_key || !tok.session_token) throw new StepFail('upload-auth', 'no video_token_v5 (session expired?)', au.rec);
    const creds = { accessKeyId: tok.access_key_id, secretAccessKey: tok.secret_acess_key /* sic */, sessionToken: tok.session_token, region: REGION, service: 'vod' };
    progress('step', 'sts', null, { accessKeyId: mask(tok.access_key_id), secret: mask(tok.secret_acess_key), token: mask(tok.session_token) });
    // 3. apply (SigV4, same origin)
    const applyUrl = `/top/v1?Action=ApplyUploadInner&Version=2020-11-19&SpaceName=tiktok&FileType=video&IsInner=1&FileSize=${blob.size}&s=g158iqx8434`;
    const sA = await L.sigv4({ method: 'GET', url: location.origin + applyUrl, ...creds, now: new Date() });
    const ap = await step('apply-upload', applyUrl, { credentials: 'include', headers: sA.headers }, { json: true });
    let node, store;
    try { node = ap.data.Result.InnerUploadAddress.UploadNodes[0]; store = node.StoreInfos[0]; if (!node.Vid || !store.StoreUri || !store.Auth || !node.UploadHost || !node.SessionKey) throw 0; } catch (_) { throw new StepFail('apply-upload', 'unexpected response shape', ap.rec); }
    ids.video_id = node.Vid;
    const host = node.UploadHost, storeUri = store.StoreUri, storeAuth = store.Auth, sessionKey = node.SessionKey;
    progress('step', 'upload-node', null, { host, storeUriLen: storeUri.length, auth: mask(storeAuth) });
    // 4. chunks: one 5 MiB part in flight, sliced lazily from the Blob, released right after use
    const uploadId = uuid(), crcs = [], parts = L.splitParts(blob.size);
    if (!parts.length) throw new StepFail('upload-part', 'video is empty');
    for (let i = 0; i < parts.length; i++) {
      let buf = await blob.slice(parts[i][0], parts[i][1]).arrayBuffer();
      const crc = L.crc32Hex(buf); crcs.push(crc);
      await step(`upload-part-${i + 1}/${parts.length}`, `https://${host}/${storeUri}?partNumber=${i + 1}&uploadID=${uploadId}&phase=transfer`, {
        method: 'POST', credentials: cc, body: buf,
        headers: { Authorization: storeAuth, 'Content-Type': 'application/octet-stream', 'Content-Disposition': 'attachment; filename="undefined"', 'Content-Crc32': crc },
      });
      buf = null;                                  // release before the next slice
      progress('transfer', `part ${i + 1}/${parts.length}`, Math.round(((i + 1) / parts.length) * 100), { mem: mem() });
      await sleep(0);
    }
    // 5. finish: cookie-free, straight to the storage host
    await step('finish-upload', `https://${host}/${storeUri}?uploadID=${uploadId}&phase=finish&uploadmode=part`, {
      method: 'POST', credentials: 'omit', headers: { Authorization: storeAuth, 'Content-Type': 'text/plain;charset=UTF-8' },
      body: crcs.map((c, i) => `${i + 1}:${c}`).join(','),
    });
    // 6. commit (SigV4). Python's body is a str without Content-Type, which requests_auth_aws_sigv4 turns into form-urlencoded.
    const commitUrl = '/top/v1?Action=CommitUploadInner&Version=2020-11-19&SpaceName=tiktok';
    const commitBody = JSON.stringify({ SessionKey: sessionKey, Functions: [{ name: 'GetMeta' }] });
    const sC = await L.sigv4({ method: 'POST', url: location.origin + commitUrl, body: commitBody, ...creds, now: new Date() });
    await step('commit-upload', commitUrl, { method: 'POST', credentials: 'include', body: commitBody, headers: Object.assign({ 'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8' }, sC.headers) });
    return { ids, parts: parts.length, chunkCredentials: cc };
  }

  // Everything except `text`/`markup_text` content is kept; ids are not secrets. Nothing here is sent anywhere.
  async function buildBody(job, ids, blob, v, anchors) {
    let sched = null;
    if (v.scheduleUnix != null) {
      const now = Math.floor(Date.now() / 1000);
      try { sched = L.finalizeSchedule(v.scheduleUnix, now); } catch (e) { throw new StepFail('schedule-expired', e.message, { notSent: true }); }
    }
    const userIds = {};
    for (const name of new Set(L.mentionsIn(job.caption))) {
      try { const r = await fetch('/@' + encodeURIComponent(name), { credentials: 'include' }); const m = /"userInfo":\{"user":\{"id":"(\d+)"/.exec(await r.text()); if (m) userIds[name] = m[1]; } catch (_) { /* stays plain text, like Python */ }
    }
    const { markup, textExtra } = L.buildCaption(job.caption, userIds);
    const probe = await probeVideo(blob);
    const payload = L.buildPayload({ creationId: ids.creation_id, videoId: ids.video_id, caption: job.caption, markup, textExtra, visibility: v.vis, probe, scheduleTime: sched, anchors, ...v.options });
    return { payload, probe, resolvedMentions: Object.keys(userIds), tz: Intl.DateTimeFormat().resolvedOptions().timeZone };
  }


  // ---- K4 cart: shop API (shop.tiktok.com), GET only, never /project/post/ ----
  // Page fetch first (this tab's cookies). If the browser refuses it (CORS surfaces as a TypeError) the same GET is relayed
  // through content.js -> service worker, which holds the shop.tiktok.com host permission (no CORS there).
  const shopWait = new Map();
  function shopViaSw(url) {
    return new Promise((resolve) => {
      const rid = uuid();
      shopWait.set(rid, resolve);
      post('shop-req', { rid, url });
      setTimeout(() => { if (shopWait.delete(rid)) resolve({ ok: false, error: 'sw-timeout' }); }, 30000);
    });
  }
  async function shopGet(url) {
    const t0 = performance.now();
    let via = 'page', status = null, text = null, error = null;
    try { const r = await fetch(url, { credentials: 'include' }); status = r.status; text = await r.text(); } catch (e) {
      via = 'sw';
      const r = await shopViaSw(url);
      if (r.ok) { status = r.status; text = r.text; } else error = r.error || 'sw-failed';
    }
    progress('step', `shop ${status == null ? 'lỗi' : 'HTTP ' + status} (${via}) ${Math.round(performance.now() - t0)}ms`, null, { step: 'shop-search', url: safeUrl(url), status, via, error });
    if (text == null) throw new Error('shop API unreachable (' + (error || 'no body') + ')');
    if (status !== 200) throw new Error('shop API HTTP ' + status);
    return text;
  }

  // Exact product_id + stock > 0, looked up by keyword=<id> in my shop (3), then showcase (2).
  // -> {ok} | {ok:false, reason:'product-unavailable'|'product-check-failed', detail}
  async function checkProduct(productId) {
    let found = null, errored = null;
    for (const type of [3, 2]) {
      let text;
      try { text = await shopGet(L.shopSearchUrl({ type, keyword: productId, cursor: 0, count: 10 })); } catch (e) { errored = e.message; continue; }
      const r = L.checkProductAvailable(text, productId);
      if (r.ok) return { ok: true, source: type === 3 ? 'my_shop' : 'showcase', product: r.product };
      if (r.reason === 'search-error') errored = 'search-error: ' + r.detail;
      else if (r.reason !== 'not-found') found = r.reason;           // found but out-of-stock / stock-unknown
    }
    if (found) return { ok: false, reason: 'product-unavailable', detail: found };
    if (errored) return { ok: false, reason: 'product-check-failed', detail: errored };
    return { ok: false, reason: 'product-unavailable', detail: 'not-found' };
  }

  // job.product -> {anchors} or {fail:{reason, detail}}. Everything here happens BEFORE any upload/publish (not_sent).
  async function prepareProduct(job) {
    const pr = job.product;
    const fail = (reason, detail) => ({ fail: { reason, detail: String(detail).slice(0, 300) } });
    if (!pr || typeof pr !== 'object') return fail('anchor-build-failed', 'job.product is not an object');
    // 1. pure build first (bad id / name > 30 / bad template): default real shape, or the app's captured template when given
    let b;
    try { b = L.buildProductAnchorsDetailed({ product_id: pr.product_id, product_name: pr.product_name }, pr.anchor_template, pr.template_product_id); } catch (e) { return fail('anchor-build-failed', e.message); }
    // 2. the product must exist with stock (exact id) -- still BEFORE any upload
    progress('product', 'kiểm tra sản phẩm ' + pr.product_id, null, { product_id: pr.product_id });
    const chk = await checkProduct(pr.product_id);
    if (!chk.ok) return fail(chk.reason, chk.detail);
    progress('product', 'đã dựng giỏ hàng', null, { product_id: pr.product_id, source: chk.source, fromTemplate: b.fromTemplate, anchors: b.anchors.length, replacedIds: b.replacedIds, replacedNames: b.replacedNames, stock: chk.product.stock_num });
    return { anchors: b.anchors };
  }

  // ---- K4 product sync (post-free): my shop (3) then showcase (2), 50 per page by offset, at most 40 pages ----
  const SYNC_PAGE = 50, SYNC_MAX_PAGES = 40;
  async function syncProducts() {
    const t0 = Date.now();
    const failed = (reason, detail) => post('done', { result: { outcome: 'failed', definite: true, notSent: true, reason, detail: String(detail).slice(0, 400), elapsed_ms: Date.now() - t0 } });
    let pj;
    try { pj = await (await fetch('/passport/web/account/info/?aid=' + AID, { credentials: 'include' })).json(); } catch (e) { return failed('identity-unknown', e.message); }
    const id = L.checkIdentity(pj, {});
    if (!id.ok) return failed('identity-unknown', id.reason);
    progress('identity', 'sync: ' + id.username, null, { username: id.username, userId: mask(id.userId) });
    const sources = {};
    for (const [type, source] of [[3, 'my_shop'], [2, 'showcase']]) {
      const list = [], seen = new Set();
      let complete = false, total = null, error = null, pages = 0;
      for (let page = 0; page < SYNC_MAX_PAGES; page++) {
        pages++;
        let r;
        try { r = L.parseShopProducts(await shopGet(L.shopSearchUrl({ type, keyword: '', cursor: page * SYNC_PAGE, count: SYNC_PAGE }))); } catch (e) { error = e.message; break; }
        if (!r.ok) { error = r.reason; break; }
        if (r.total != null) total = r.total;
        for (const p of r.products) if (!seen.has(p.product_id)) { seen.add(p.product_id); list.push(p); }
        progress('sync', `${source} trang ${page + 1}: ${list.length}${total != null ? '/' + total : ''}`, null, { source, page: page + 1, got: r.rawCount });
        if (r.rawCount < SYNC_PAGE || (total != null && (page + 1) * SYNC_PAGE >= total)) { complete = true; break; }
        await sleep(300);
      }
      sources[source] = { products: list, complete: complete && !error, total, pages, error };
    }
    const anyOk = Object.keys(sources).some((k) => sources[k].complete);
    post('done', { result: { outcome: anyOk ? 'sync_ok' : 'failed', definite: true, notSent: true, reason: anyOk ? undefined : 'sync-incomplete', identity: { username: id.username, user_id: id.userId },
      sources, elapsed_ms: Date.now() - t0 } });
  }

  // Strict identity: only the passport self endpoint decides (data.username + data.user_id_str).
  async function strictIdentity(job, when) {
    if (job.mode === 'post' && (!job.expect_account || !job.expect_user_id)) throw new StepFail('identity', 'post needs expect_account and expect_user_id', { notSent: true });
    let j = null;
    try { j = await (await fetch('/passport/web/account/info/?aid=' + AID, { credentials: 'include' })).json(); } catch (e) { throw new StepFail('identity', 'passport lookup failed: ' + e.message); }
    const r = L.checkIdentity(j, { username: job.expect_account, userId: job.expect_user_id });
    progress('identity', `${when}: ${r.ok ? 'ok' : r.reason} ${r.username || ''}`, null, { when, ok: r.ok, username: r.username || null, userId: r.userId ? mask(r.userId) : null });
    if (!r.ok) throw new StepFail('identity', `${r.reason}${r.username ? ` (page account ${r.username})` : ''} [${when}]`);
    return { value: r.username, user_id: r.userId };
  }

  // SDK readiness: page code replaced XHR.send on top of our wrapper (our hook is installed at document_start, so the
  // SDK wraps AFTER us). `[native code]` cannot be used because our own wrapper is not native either.
  async function waitSdk() {
    const hk = window.__autotokHook;
    if (!hk) throw new StepFail('sdk', 'hook-main.js not installed');
    const t0 = Date.now();
    while (XMLHttpRequest.prototype.send === hk.wrapperSend) {
      if (Date.now() - t0 > 30000) throw new StepFail('sdk-not-ready', 'page SDK never wrapped XMLHttpRequest.send', { byted_acrawler: typeof window.byted_acrawler });
      await sleep(500);
    }
    progress('sdk', 'SDK đã bọc XHR.send', null, { waitedMs: Date.now() - t0, byted_acrawler: typeof window.byted_acrawler });
  }

  let authResolve = null;
  function requestAuthorization(sha, creationId, binding) {
    return new Promise((resolve) => {
      authResolve = resolve;
      post('auth-req', Object.assign({ sha, creation_id: creationId }, binding));
      setTimeout(() => resolve({ ok: false, reason: 'authorize-timeout' }), 30000);
    });
  }

  // The ONLY place that can send a post. Grant is bound to sha256(body)+creation_id+nonce and consumed before send.
  async function publishOnce(bodyStr) {
    const url = '/tiktok/web/project/post/v1/?app_name=tiktok_web&channel=tiktok_web&device_platform=web&tz_name='
      + encodeURIComponent(Intl.DateTimeFormat().resolvedOptions().timeZone) + '&aid=' + AID;
    try { await gate.check(bodyStr, NONCE); } catch (e) { throw new StepFail('gate', e.message, { notSent: true }); }  // refused before send: definite
    // From here the grant is consumed. No await between the check and send.
    const xhr = new XMLHttpRequest();
    const settled = new Promise((resolve) => {
      xhr.onload = () => resolve({ status: xhr.status, text: String(xhr.responseText || '') });
      xhr.onerror = () => resolve({ error: 'network', blocked: !!xhr.__autotokBlocked });
      xhr.ontimeout = () => resolve({ error: 'timeout' });
      xhr.onabort = () => resolve({ error: 'abort' });
    });
    try {
      xhr.open('POST', url, true);
      xhr.withCredentials = true;
      xhr.timeout = 180000;
      xhr.setRequestHeader('content-type', 'application/json');
    } catch (e) { return { setupError: String(e && e.message) }; }       // nothing was sent
    window.__autotokHook.allow(xhr);
    sentFlag = true;
    try { xhr.send(bodyStr); } catch (e) { return { error: 'send-threw', message: String(e && e.message) }; }   // may have reached the network
    return settled;                                   // correlated to this exact XHR object; never retried
  }

  async function doPost(job, up, body, id) {   // id is replaced by the fresh pre-publish identity
    // Never post without the cart when the job asks for a product (checked again right before authorization).
    if (job.product && !((body.payload.feature_common_info_list[0].anchors || []).length)) return { outcome: 'failed', definite: true, notSent: true, reason: 'anchor-build-failed', detail: 'job.product is set but the body has no anchors' };
    const bodyStr = JSON.stringify(body.payload);
    const sha = await L.sha256Hex(bodyStr);
    await waitSdk();
    id = await strictIdentity(job, 'before-publish');
    const f0 = body.payload.feature_common_info_list[0];
    const schedule = f0.schedule_time == null ? null : f0.schedule_time;
    const auth = await requestAuthorization(sha, up.ids.creation_id, { visibility_type: f0.privacy_setting_info.visibility_type, schedule_time: schedule,
      identity: { username: id.value, user_id: id.user_id } });
    if (!auth.ok) throw new StepFail('authorize', 'denied: ' + auth.reason);   // nothing sent
    gate.arm({ sha, creationId: up.ids.creation_id, nonce: NONCE });
    progress('post', 'ĐÃ cấp quyền, gửi 1 lần', null, { sha: sha.slice(0, 12) });
    const res = await publishOnce(bodyStr);           // throws StepFail('gate', notSent) only when refused before send
    if (res.setupError) return { outcome: 'failed', definite: true, notSent: true, reason: 'publish-setup-failed', detail: res.setupError };
    if (res.blocked) return { outcome: 'failed', definite: true, notSent: true, reason: 'blocked-by-hook', note: 'không gì được gửi' };
    if (res.error) return { outcome: 'uncertain', reason: 'xhr-' + res.error, detail: res.message, note: 'đã gửi, không có phản hồi' };
    const m = L.mapPublishResult(res.status, res.text);
    if (m.outcome === 'uncertain') m.text = res.text.slice(0, 300);
    m.response = L.sanitizeResponse(res.text);
    return Object.assign(m, { schedule_time: schedule, creation_id: up.ids.creation_id, video_id: up.ids.video_id, body_sha256: sha, identity: id });
  }

  async function run(msg) {
    const job = msg.job;
    if (!MODES.includes(job.mode)) return post('done', { result: { outcome: 'failed', definite: true, reason: 'mode-disabled', detail: job.mode } });
    const t0 = Date.now();
    try {
      let v;
      try { v = L.validateJob(job, Math.floor(Date.now() / 1000)); } catch (e) { throw new StepFail('validate', e.message, { notSent: true }); }   // before any upload
      const resp = await fetch(msg.blobUrl);
      const blob = await resp.blob();
      post('blob-ready', {});                      // content.js may revoke the Blob URL now
      if (blob.size !== msg.size) throw new StepFail('blob', `size ${blob.size} != ${msg.size}`);
      const id0 = await strictIdentity(job, 'before-upload');     // nothing is uploaded for the wrong/unknown account
      let anchors = [];
      if (job.product && job.mode !== 'selftest') {          // K4: check + build the cart BEFORE uploading or publishing anything
        const pp = await prepareProduct(job);
        if (pp.fail) return post('done', { result: { outcome: 'failed', definite: true, notSent: true, reason: pp.fail.reason, detail: pp.fail.detail, elapsed_ms: Date.now() - t0 } });
        anchors = pp.anchors;
      }
      progress('start', `${job.mode}, ${(blob.size / 1048576).toFixed(1)} MB`, 0, { mem: mem() });
      const up = await upload(job, blob);
      let result = { outcome: job.mode === 'selftest' ? 'selftest_ok' : 'intercepted', note: 'đã tải video lên TikTok, CHƯA đăng', ids: up.ids, parts: up.parts, chunkCredentials: up.chunkCredentials, identity: id0, elapsed_ms: Date.now() - t0, mem: mem() };
      if (job.mode !== 'selftest') {
        const b = await buildBody(job, up.ids, blob, v, anchors);
        if (job.mode === 'intercept') Object.assign(result, { sent: false, body: b.payload, probe: b.probe, resolvedMentions: b.resolvedMentions, tz: b.tz });
        else result = Object.assign({ ids: up.ids, parts: up.parts, elapsed_ms: Date.now() - t0 }, await doPost(job, up, b, id0));
      }
      post('done', { result });
    } catch (e) {
      const notSent = e instanceof StepFail && e.extra && e.extra.notSent === true;
      if (sentFlag) post('done', { result: { outcome: 'uncertain', reason: 'error-after-send', detail: String(e.message).slice(0, 400), elapsed_ms: Date.now() - t0 } });
      else post('done', { result: { outcome: 'failed', definite: true, notSent, reason: e instanceof StepFail ? 'step:' + e.step : 'exception', detail: String(e.message).slice(0, 400), step: e.extra || null, elapsed_ms: Date.now() - t0 } });
    }
  }

  // ---- v1.4 stats + comments collection: READ ONLY (GET insight, POST item_list / commentsV2 which are list queries) ----
  // Runs in this MAIN world because item_list / commentsV2 are signed by the page's own hooks (msToken / X-Bogus).
  // Sequential, 1.2-2.2 s apart, backs off on errors, gives up on a stage after 3 failures in a row. Results leave as batches
  // to content.js -> service worker -> app; nothing here touches the Studio UI or sends a /project/post/ request.
  let collecting = false;
  async function collectStudio(msg) {
    const S = window.AutotokStudio;
    const nonce = String(msg.nonce);
    const plan = msg.plan || {};
    const emit = (kind, data) => window.postMessage(Object.assign({ __autotok: 1, from: 'api', kind, nonce }, data), location.origin);
    const note = (m) => emit('collect-log', { msg: String(m).slice(0, 200) });
    const t0 = Date.now();
    const DEADLINE = 6 * 60 * 1000;
    const errors = [];
    const gap = () => sleep(1200 + Math.floor(Math.random() * 1000));
    const expired = () => Date.now() - t0 > DEADLINE;
    const nowS = Math.floor(Date.now() / 1000);
    try {
      if (!S) throw new Error('studio-lib.js not loaded');
      // Wait for the page's signing SDK (it wraps XHR.send on top of our hook), but never longer than 20 s.
      const hk = window.__autotokHook;
      const w0 = Date.now();
      while (document.readyState !== 'complete' && Date.now() - w0 < 20000) await sleep(300);
      while (hk && XMLHttpRequest.prototype.send === hk.wrapperSend && Date.now() - w0 < 20000) await sleep(400);
      await sleep(1500);

      // One request with retries: 429 / 5xx / network wait longer; a 200 that is not JSON counts as a failure.
      const call = async (name, url, init) => {
        let why = '';
        for (let i = 0; i < 3; i++) {
          if (expired()) throw new Error('deadline');
          try {
            const r = await fetch(url, Object.assign({ credentials: 'include' }, init));
            if (r.status === 200) { const j = JSON.parse(await r.text()); return j; }
            why = 'HTTP ' + r.status;
            if (r.status === 401) break;
            await sleep(r.status === 429 ? 30000 : 3000 * (i + 1) * (i + 1));
          } catch (e) { why = String(e && e.message).slice(0, 60); await sleep(3000 * (i + 1)); }
        }
        errors.push(name + ': ' + why);
        return null;
      };
      const postJson = (body) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

      // 1. account: followers (+ a week of history, stored raw by the app)
      let account = null;
      const aj = await call('account', S.insightUrl(S.accountRequests()), {});
      if (aj) { const a = S.parseAccountInsight(aj); if (a.ok) account = { followers: a.followers, follower_history: a.history }; else errors.push('account: no follower_num'); }
      await gap();

      // 2. post list with counters, newest first, until items older than the window (or 10 pages)
      const windowS = (plan.windowDays || 30) * 86400;
      const videos = [];
      let cursor = 0, listOk = false, pages = 0, fails = 0;
      for (; pages < 10 && !expired(); pages++) {
        const j = await call('item_list', S.itemListUrl(), postJson(S.itemListBody(cursor, 50)));
        const p = j ? S.parseItemList(j) : null;
        if (!p || !p.ok) { if (p) errors.push('item_list: ' + p.reason); if (++fails >= 3 || !p) break; await gap(); continue; }
        listOk = true;
        let reachedOld = false;
        for (const it of p.items) {
          if (it.post_time > nowS) continue;                 // still scheduled, not published yet
          if (it.post_time < nowS - windowS) { reachedOld = true; continue; }
          videos.push(it);
        }
        note(`item_list trang ${pages + 1}: ${p.items.length} bài`);
        if (!p.hasMore || reachedOld || p.cursor === cursor) break;
        cursor = p.cursor;
        await gap();
      }
      await gap();

      // 3. insight for videos <= 7 days old (avg watch time, finish rate, traffic sources, new followers)
      const targets = S.pickInsightTargets(videos, nowS, plan.insightDays || 7, 3 * 3600, 40);
      const byId = new Map(videos.map((v) => [v.item_id, v]));
      let insFail = 0;
      for (const t of targets) {
        if (expired() || insFail >= 3) break;
        const j = await call('insight', S.videoInsightUrl(t.item_id), {});
        const ins = j ? S.parseVideoInsight(j) : null;
        if (ins && ins.ok) { insFail = 0; byId.get(t.item_id).insight = { avg_watch_s: ins.avg_watch_s, finish_rate: ins.finish_rate, total_watch_s: ins.total_watch_s, new_followers: ins.new_followers, traffic: ins.traffic }; }
        else if (!ins || !ins.empty) insFail++;
        await gap();
      }
      emit('collect-batch', { part: 'stats', account, videos, list_complete: listOk && fails === 0, pages, insights: targets.length });

      // 4. comments (whole channel, newest first) until the last comment id the app already has
      const comments = [];
      let newest = null, ccur = '', reached = false, cpages = 0, cfails = 0;
      const maxPages = plan.lastCommentId ? 6 : 15;
      const start = plan.since && plan.since > 0 ? plan.since : nowS - windowS;
      for (; cpages < maxPages && !expired(); cpages++) {
        const j = await call('comments', S.commentsUrl(), postJson(S.commentsBody(20, start, nowS + 3600, ccur)));
        const p = j ? S.parseComments(j) : null;
        if (!p || !p.ok) { if (++cfails >= 2) break; await gap(); continue; }
        if (!newest && p.comments.length) newest = { comment_id: p.comments[0].comment_id, created_at: p.comments[0].created_at };
        const t = S.takeNewComments(p.comments, plan.lastCommentId || '');
        comments.push(...t.fresh);
        if (t.reachedSeen || !p.hasMore || !p.cursor) { reached = true; break; }
        ccur = p.cursor;
        await gap();
      }
      if (comments.length || newest) emit('collect-batch', { part: 'comments', comments, newest, complete: reached });
      emit('collect-done', { result: { outcome: 'collect_ok', videos: videos.length, insights: targets.length, comments: comments.length, errors: errors.slice(0, 8), elapsed_ms: Date.now() - t0 } });
    } catch (e) {
      emit('collect-done', { result: { outcome: 'failed', reason: 'exception', detail: String(e && e.message).slice(0, 300), errors: errors.slice(0, 8), elapsed_ms: Date.now() - t0 } });
    }
  }

  window.addEventListener('message', (e) => {
    const d = e.data;
    if (e.source !== window || !d || d.__autotok !== 1 || d.from !== 'content' || d.kind !== 'collect') return;
    if (collecting) return;
    collecting = true;
    collectStudio(d).finally(() => { collecting = false; });
  });

  window.addEventListener('message', (e) => {
    const d = e.data;
    if (e.source === window && d && d.__autotok === 1 && d.from === 'content' && d.kind === 'auth-res' && d.nonce === NONCE && authResolve) { const r = authResolve; authResolve = null; r({ ok: !!d.ok, reason: d.reason }); return; }
    if (e.source === window && d && d.__autotok === 1 && d.from === 'content' && d.kind === 'shop-res' && d.nonce === NONCE) { const f = shopWait.get(d.rid); if (f) { shopWait.delete(d.rid); f({ ok: !!d.ok, status: d.status, text: d.text, error: d.error }); } return; }
    if (e.source !== window || !d || d.__autotok !== 1 || d.from === 'api' || (d.kind !== 'run' && d.kind !== 'sync_products')) return;
    if (d.kind === 'sync_products' && d.from !== 'content') return;
    if (running) { post('p', { phase: 'warn', msg: 'duplicate run ignored' }); return; }
    running = true; NONCE = String(d.nonce);
    if (d.kind === 'sync_products') { syncProducts().catch((err) => post('done', { result: { outcome: 'failed', definite: true, notSent: true, reason: 'exception', detail: String(err && err.message) } })); return; }
    run(d).catch((err) => post('done', { result: { outcome: 'failed', definite: true, reason: 'exception', detail: String(err && err.message) } }));
  });
})();

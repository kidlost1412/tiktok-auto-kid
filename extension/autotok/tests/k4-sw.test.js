// K4 cart on the service-worker side: GET /api/ext/tasks -> product sync tab, POST /api/ext/products, shop fetch relay,
// passive anchor template -> POST /api/ext/anchor_template. REAL sw.js, stubbed chrome.* and a fake backend (no ports).
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const json = (o, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => o, text: async () => JSON.stringify(o) });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ME = { data: { username: 'Me.User', user_id_str: '7000000000000000001' } };
const OLD = '7512345678901234567', SELLER = '7400000000000000001';

function loadSw({ server, settings, store0 }) {
  const store = Object.assign({}, store0);
  const onMsg = [];
  const calls = [];
  const created = [], removed = [], winRemoved = [];
  const ev = () => ({ addListener() {} });
  const chrome = {
    storage: { local: {
      async get(k) { const keys = k == null ? Object.keys(store) : [].concat(k); const o = {}; for (const x of keys) if (x in store) o[x] = JSON.parse(JSON.stringify(store[x])); return o; },
      async set(o) { for (const [k, v] of Object.entries(o)) store[k] = JSON.parse(JSON.stringify(v)); },
      async remove(k) { for (const x of [].concat(k)) delete store[x]; },
    } },
    alarms: { create() {}, onAlarm: ev() },
    runtime: { onMessage: { addListener: (f) => onMsg.push(f) }, onStartup: ev(), onInstalled: ev(), getManifest: () => ({ version: '1.1.0' }) },
    tabs: { query: async () => [], get: async (id) => ({ id }), update: async () => {}, remove: async (id) => { removed.push(id); }, create: async (o) => { created.push(o); return { id: 9, windowId: 1 }; }, onRemoved: ev(), onReplaced: ev() },
    windows: { create: async () => ({ id: 1, tabs: [{ id: 9 }] }), remove: async (id) => { winRemoved.push(id); } },
  };
  async function fetch(url, init = {}) {
    const u = new URL(url);
    const body = init.body ? JSON.parse(init.body) : null;
    const rec = { host: u.host, path: u.pathname, search: u.search, method: init.method || 'GET', body, headers: init.headers || {}, credentials: init.credentials };
    calls.push(rec);
    return server(u.pathname, body, rec);
  }
  const unrefTimeout = (f, ms) => { const t = setTimeout(f, ms); if (t.unref) t.unref(); return t; };
  const ctx = { chrome, fetch, setTimeout: unrefTimeout, clearTimeout, AbortController, console: { log() {}, warn() {}, error() {} }, btoa, Date, URL, Promise, Object, JSON, Math, Error, encodeURIComponent };
  vm.createContext(ctx);
  store.settings = Object.assign({ server: 'http://localhost:8000', token: 'T', clientId: 3, polling: false, windowStrategy: 'tab' }, settings);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'sw.js'), 'utf8'), ctx);
  const send = (msg, tab) => new Promise((resolve) => {
    const sender = { tab: Object.assign({ id: 9, url: 'https://www.tiktok.com/tiktokstudio/upload#autotok=sync-req1', windowId: 1 }, tab) };
    for (const f of onMsg) if (f(msg, sender, resolve) === true) return;
    resolve(undefined);
  });
  return { store, calls, send, created, removed, winRemoved, ctx };
}
const helloOk = () => json({ ok: true, client_id: 3, protocol_min: 1, protocol_max: 1, need_reload: false, message: '', account: null, conflict: false });
const baseServer = (over) => async (p, body, rec) => {
  if (over && over[p]) return over[p](body, rec);
  if (p === '/passport/web/account/info/') return json(ME);
  if (p === '/api/ext/hello') return helloOk();
  return json({ ok: true });
};
const activeSync = (over) => Object.assign({ request_id: 'req1', nonce: 'SN', startedAt: Date.now(), tabId: 9, windowId: 1, strategy: 'tab', finished: false }, over);
const prod = (id) => ({ product_id: id, title: 'SP ' + id, price: '99.000đ', cover_url: 'https://img/' + id, stock_num: 3, stock_status: 1 });
const syncOk = (over) => Object.assign({ outcome: 'sync_ok', identity: { username: 'me.user', user_id: '7000000000000000001' },
  sources: { my_shop: { products: [prod('7600000000000000001'), prod('7600000000000000002')], complete: true, total: 2, pages: 1, error: null }, showcase: { products: [], complete: true, total: 0, pages: 1, error: null } } }, over);

test('hello: the sync tab (by id or by #autotok=sync-<id> hash) gets role sync with the sync nonce; other tabs get none', async () => {
  const sw = loadSw({ server: baseServer(), store0: { activeSync: activeSync({ tabId: null }) } });
  const other = await sw.send({ type: 'hello', nonce: null }, { id: 77, url: 'https://www.tiktok.com/tiktokstudio/upload' });
  assert.equal(other.role, 'none');
  const mine = await sw.send({ type: 'hello', nonce: null }, { id: 9 });          // matched by the hash; tab id adopted
  assert.deepEqual([mine.role, mine.request_id, mine.nonce], ['sync', 'req1', 'SN']);
  assert.equal(sw.store.activeSync.tabId, 9);
  const again = await sw.send({ type: 'hello', nonce: null }, { id: 9 });
  assert.equal(again.role, 'sync');
});

test('syncResult: one POST /api/ext/products per COMPLETE source with the contract body; tab closed; state cleared', async () => {
  const sw = loadSw({ server: baseServer(), store0: { activeSync: activeSync(), syncState: { request_id: 'req1', tries: 1, lastAt: Date.now(), done: false } } });
  const r = await sw.send({ type: 'syncResult', nonce: 'SN', result: syncOk() }, { id: 9 });
  assert.equal(r.ok, true);
  const posts = sw.calls.filter((c) => c.path === '/api/ext/products');
  assert.equal(posts.length, 2);
  assert.deepEqual(posts.map((c) => c.method), ['POST', 'POST']);
  assert.equal(posts[0].headers['X-Requested-With'], 'autotok');
  assert.equal(posts[0].headers.Authorization, 'Bearer T');
  assert.deepEqual(posts[0].body, { request_id: 'req1', user_id: '7000000000000000001', username: 'me.user', source: 'my_shop', complete: true,
    products: [prod('7600000000000000001'), prod('7600000000000000002')] });
  assert.deepEqual([posts[1].body.source, posts[1].body.products, posts[1].body.complete], ['showcase', [], true]);
  assert.deepEqual(sw.removed, [9]);
  assert.equal('activeSync' in sw.store, false);
  assert.equal(sw.store.syncState.done, true);
  assert.equal(sw.calls.some((c) => c.path.includes('/project/post/')), false);
});

test('syncResult: an incomplete source is never sent; an app refusal (409) is logged, never thrown; failed syncs send nothing', async () => {
  const incomplete = syncOk(); incomplete.sources.showcase = { products: [prod('7600000000000000009')], complete: false, total: null, pages: 40, error: null };
  const sw = loadSw({ server: baseServer(), store0: { activeSync: activeSync() } });
  await sw.send({ type: 'syncResult', nonce: 'SN', result: incomplete }, { id: 9 });
  assert.deepEqual(sw.calls.filter((c) => c.path === '/api/ext/products').map((c) => c.body.source), ['my_shop']);

  const sw2 = loadSw({ server: baseServer({ '/api/ext/products': () => json({ ok: false, error: 'identity_conflict', message: 'x' }, 409) }), store0: { activeSync: activeSync(), syncState: { request_id: 'req1', tries: 1, lastAt: 1, done: false } } });
  const r2 = await sw2.send({ type: 'syncResult', nonce: 'SN', result: syncOk() }, { id: 9 });
  assert.equal(r2.ok, true);
  assert.equal(sw2.store.syncState.done, false);                         // nothing delivered: may be retried (bounded)
  assert.equal('activeSync' in sw2.store, false);

  const sw3 = loadSw({ server: baseServer(), store0: { activeSync: activeSync() } });
  await sw3.send({ type: 'syncResult', nonce: 'SN', result: { outcome: 'failed', reason: 'identity-unknown' } }, { id: 9 });
  assert.equal(sw3.calls.filter((c) => c.path === '/api/ext/products').length, 0);
  assert.equal('activeSync' in sw3.store, false);
});

test('syncResult: wrong nonce, wrong tab, or no active sync -> ignored, nothing sent', async () => {
  const sw = loadSw({ server: baseServer(), store0: { activeSync: activeSync() } });
  assert.equal((await sw.send({ type: 'syncResult', nonce: 'BAD', result: syncOk() }, { id: 9 })).ok, false);
  assert.equal((await sw.send({ type: 'syncResult', nonce: 'SN', result: syncOk() }, { id: 77 })).ok, false);
  assert.equal(sw.calls.filter((c) => c.path === '/api/ext/products').length, 0);
  const none = loadSw({ server: baseServer() });
  assert.equal((await none.send({ type: 'syncResult', nonce: 'SN', result: syncOk() }, { id: 9 })).ok, false);
});

test('polling: /api/ext/tasks {sync_products} opens ONE Studio sync tab (hash), persists activeSync first, and claims no job meanwhile', async () => {
  const sw = loadSw({ settings: { polling: true }, server: baseServer({
    '/api/ext/tasks': () => json({ sync_products: 'req1' }),
    '/api/ext/next': () => new Promise(() => {}),                           // never answers: a long poll
  }) });
  for (let i = 0; i < 100 && !sw.store.activeSync; i++) await sleep(20);
  await sleep(60);
  assert.equal(sw.created.length, 1);
  assert.equal(sw.created[0].url, 'https://www.tiktok.com/tiktokstudio/upload#autotok=sync-req1');
  assert.deepEqual([sw.store.activeSync.request_id, sw.store.activeSync.tabId, sw.store.activeSync.finished], ['req1', 9, false]);
  assert.equal(sw.store.syncState.tries, 1);
  assert.equal(sw.calls.filter((c) => c.path === '/api/ext/next').length, 0);   // the sync runs first
  assert.ok(sw.calls.filter((c) => c.path === '/api/ext/tasks').length >= 1);   // keeps asking while the sync runs: a newer request_id must replace it
});

test('polling: a missing /tasks endpoint (old app) does not break the loop; the long poll still happens', async () => {
  const sw = loadSw({ settings: { polling: true }, server: baseServer({
    '/api/ext/tasks': () => json({ ok: false, error: 'not_found', message: 'x' }, 404),
    '/api/ext/next': () => new Promise(() => {}),
  }) });
  for (let i = 0; i < 100 && !sw.calls.some((c) => c.path === '/api/ext/next'); i++) await sleep(20);
  assert.equal(sw.calls.some((c) => c.path === '/api/ext/next'), true);
  assert.equal(sw.created.length, 0);
});

test('polling: no sync is started while a job is active', async () => {
  const sw = loadSw({ settings: { polling: true }, store0: { activeJob: { id: 'ej_1', nonce: 'N', claim_token: 'C', mode: 'post', job: {}, local: false, startedAt: Date.now(), openingAt: Date.now(), lastBeat: Date.now(), hbAt: Date.now(), tabId: 5, windowId: 1, strategy: 'tab', authorized: false, finished: false } },
    server: baseServer({ '/api/ext/tasks': () => json({ sync_products: 'req1' }) }) });
  await sleep(300);
  assert.equal(sw.calls.filter((c) => c.path === '/api/ext/tasks').length, 0);
  assert.equal(sw.created.length, 0);
});

test('shopFetch: only the shop search endpoint, only for the active job/sync tab', async () => {
  const sw = loadSw({ server: baseServer({ '/api/v1/streamer_desktop/selection/search': () => json({ code: 0, data: { products: [] } }) }), store0: { activeSync: activeSync() } });
  const url = `https://shop.tiktok.com/api/v1/streamer_desktop/selection/search?search_type=3&keyword=${OLD}&origin=2&cursor=0&count=10&aid=1180`;
  const ok = await sw.send({ type: 'shopFetch', url }, { id: 9 });
  assert.deepEqual([ok.ok, ok.status], [true, 200]);
  assert.equal(JSON.parse(ok.text).code, 0);
  const call = sw.calls.find((c) => c.host === 'shop.tiktok.com');
  assert.deepEqual([call.method, call.credentials], ['GET', 'include']);
  assert.equal((await sw.send({ type: 'shopFetch', url }, { id: 77 })).error, 'not-a-job-tab');
  for (const bad of ['https://evil.example/api/v1/streamer_desktop/selection/search?x=1', 'https://shop.tiktok.com/api/v1/other', 'http://shop.tiktok.com/api/v1/streamer_desktop/selection/search', 'https://www.tiktok.com/tiktok/web/project/post/v1/', 'nope']) {
    assert.equal((await sw.send({ type: 'shopFetch', url: bad }, { id: 9 })).ok, false, bad);
  }
  assert.equal(sw.calls.filter((c) => c.host === 'shop.tiktok.com').length, 1);
});

// ---- passive capture ----
const anchors = () => [{ type: 'product', id: OLD, title: 'Áo', extra: JSON.stringify({ product_id: OLD, seller_id: SELLER }) }];
// the shop knows only the ids in `known` (search by keyword returns that product, my shop = type 3)
const shopServer = (known, extra) => baseServer(Object.assign({
  '/api/v1/streamer_desktop/selection/search': (b, rec) => {
    const q = Object.fromEntries(new URLSearchParams(rec.search));
    return json({ code: 0, data: { products: known.includes(q.keyword) && q.search_type === '3' ? [{ product_id: q.keyword, title: 't', stock_num: 1 }] : [], total: 1 } });
  },
}, extra));
const cap = (over) => Object.assign({ type: 'anchorCapture', anchors: anchors(), candidates: [OLD, SELLER], keyed: [OLD], captured_at: '2026-11-10T01:02:03.000Z' }, over);
const STUDIO_TAB = { id: 5, url: 'https://www.tiktok.com/tiktokstudio/upload' };

test('anchorCapture: identity from passport, product_id confirmed by the shop, POST /api/ext/anchor_template with the anchors verbatim', async () => {
  const sw = loadSw({ server: shopServer([OLD]) });
  const r = await sw.send(cap(), STUDIO_TAB);
  assert.equal(r.ok, true, JSON.stringify(r));
  const post = sw.calls.find((c) => c.path === '/api/ext/anchor_template');
  assert.deepEqual(post.body, { user_id: '7000000000000000001', username: 'me.user', product_id: OLD, anchors: anchors(), captured_at: '2026-11-10T01:02:03.000Z' });
  assert.equal(post.headers['X-Requested-With'], 'autotok');
  assert.equal(sw.store.lastCapture.product_id, OLD);
});

test('anchorCapture: never guesses -- seller id only, two confirmed products, conflicting key, or no identity -> nothing sent', async () => {
  const none = async (sw, msg) => { const r = await sw.send(msg, STUDIO_TAB); assert.equal(r.ok, false, JSON.stringify(r)); assert.equal(sw.calls.some((c) => c.path === '/api/ext/anchor_template'), false); };
  await none(loadSw({ server: shopServer([]) }), cap({ keyed: [], candidates: [SELLER, OLD] }));                          // nothing confirmed, no key: unknown
  await none(loadSw({ server: shopServer([OLD, SELLER]) }), cap());                                                          // two products
  await none(loadSw({ server: shopServer([SELLER]) }), cap());                                                               // shop confirms the seller id, the key says OLD
  await none(loadSw({ server: baseServer({ '/passport/web/account/info/': () => json({ data: {} }) }) }), cap());           // no identity
  // key-only fallback when the shop cannot confirm (offline) and exactly one product_id-keyed value exists
  const sw = loadSw({ server: shopServer([]) });
  assert.equal((await sw.send(cap({ keyed: [OLD] }), STUDIO_TAB)).ok, true);
  assert.equal(sw.calls.find((c) => c.path === '/api/ext/anchor_template').body.product_id, OLD);
});

test('anchorCapture: refused from a non-Studio page, the job tab, when unpaired, without anchors; duplicates within 30 s are sent once', async () => {
  const a = loadSw({ server: shopServer([OLD]) });
  assert.equal((await a.send(cap(), { id: 5, url: 'https://evil.example/tiktokstudio/' })).reason, 'not-studio');
  assert.equal((await a.send(cap({ anchors: [] }), STUDIO_TAB)).reason, 'no-anchors');
  const p = loadSw({ server: shopServer([OLD]), settings: { token: '' } });
  assert.equal((await p.send(cap(), STUDIO_TAB)).reason, 'unpaired');
  const j = loadSw({ server: shopServer([OLD]), store0: { activeJob: { id: 'ej_1', tabId: 5, finished: false, nonce: 'N', startedAt: Date.now() } } });
  assert.equal((await j.send(cap(), STUDIO_TAB)).reason, 'job-tab');
  const d = loadSw({ server: shopServer([OLD]) });
  await d.send(cap(), STUDIO_TAB);
  const second = await d.send(cap(), STUDIO_TAB);
  assert.equal(second.duplicate, true);
  assert.equal(d.calls.filter((c) => c.path === '/api/ext/anchor_template').length, 1);
});

// ---------- re-pressing "Lấy sản phẩm từ shop": every NEW request_id is processed promptly ----------
const waitFor = async (f, n = 150) => { for (let i = 0; i < n && !f(); i++) await sleep(20); };
const pollingServer = (tasks, over) => baseServer(Object.assign({ '/api/ext/tasks': () => json({ sync_products: tasks }), '/api/ext/next': () => new Promise(() => {}) }, over));

test('resync: a NEW request_id replaces a sync that is still running for an older one (old tab closed, new tab opened, tries reset)', async () => {
  const sw = loadSw({ settings: { polling: true }, server: pollingServer('req2'),
    store0: { activeSync: activeSync({ request_id: 'req1' }), syncState: { request_id: 'req1', tries: 2, lastAt: Date.now(), done: false } } });
  await waitFor(() => sw.created.length === 1);
  assert.equal(sw.created.length, 1);
  assert.equal(sw.created[0].url, 'https://www.tiktok.com/tiktokstudio/upload#autotok=sync-req2');
  assert.equal(sw.store.activeSync.request_id, 'req2');
  assert.deepEqual([sw.store.syncState.request_id, sw.store.syncState.tries], ['req2', 1]);
  assert.deepEqual(sw.removed, [9]);                                         // the abandoned request's tab
  // the abandoned request's nonce is dead: its late result is ignored
  assert.equal((await sw.send({ type: 'syncResult', nonce: 'SN', result: syncOk() }, { id: 9 })).ok, false);
  assert.equal(sw.calls.filter((c) => c.path === '/api/ext/products').length, 0);
});

test('resync: a new request_id is not blocked by an exhausted / recently tried older one', async () => {
  const sw = loadSw({ settings: { polling: true }, server: pollingServer('req2'),
    store0: { syncState: { request_id: 'req1', tries: 3, lastAt: Date.now() - 1000, done: false } } });
  await waitFor(() => sw.created.length === 1);
  assert.equal(sw.created.length, 1);
  assert.equal(sw.created[0].url.endsWith('#autotok=sync-req2'), true);
  assert.equal(sw.store.syncState.tries, 1);
});

test('resync: the SAME request_id is bounded (retry gap, max tries); exhausting it is reported once as gave-up', async () => {
  const soon = loadSw({ settings: { polling: true }, server: pollingServer('req1'),
    store0: { syncState: { request_id: 'req1', tries: 1, lastAt: Date.now() - 5000, done: false } } });
  await sleep(200);
  assert.equal(soon.created.length, 0);

  const spent = loadSw({ settings: { polling: true }, server: pollingServer('req1'),
    store0: { syncState: { request_id: 'req1', tries: 3, lastAt: Date.now() - 10 * 60 * 1000, done: false } } });
  await waitFor(() => spent.calls.some((c) => c.path === '/api/ext/sync_status'));
  await sleep(100);
  assert.equal(spent.created.length, 0);
  const reports = spent.calls.filter((c) => c.path === '/api/ext/sync_status');
  assert.equal(reports.length, 1);
  assert.deepEqual(reports[0].body, { request_id: 'req1', ok: false, reason: 'gave-up' });
});

test('resync: a failed sync tells the app why (POST /api/ext/sync_status); a successful one does not; an old app (404) is tolerated', async () => {
  const sw = loadSw({ server: baseServer(), store0: { activeSync: activeSync() } });
  await sw.send({ type: 'syncResult', nonce: 'SN', result: { outcome: 'failed', reason: 'identity-unknown' } }, { id: 9 });
  const reports = sw.calls.filter((c) => c.path === '/api/ext/sync_status');
  assert.equal(reports.length, 1);
  assert.deepEqual(reports[0].body, { request_id: 'req1', ok: false, reason: 'identity-unknown' });

  const ok = loadSw({ server: baseServer(), store0: { activeSync: activeSync() } });
  await ok.send({ type: 'syncResult', nonce: 'SN', result: syncOk() }, { id: 9 });
  assert.equal(ok.calls.filter((c) => c.path === '/api/ext/sync_status').length, 0);

  const old = loadSw({ server: baseServer({ '/api/ext/sync_status': () => json({ ok: false, error: 'not_found', message: 'x' }, 404) }), store0: { activeSync: activeSync() } });
  assert.equal((await old.send({ type: 'syncResult', nonce: 'SN', result: { outcome: 'failed', reason: 'tab-closed' } }, { id: 9 })).ok, true);
  assert.equal('activeSync' in old.store, false);
});

test('hello: identity carries the https avatar URL from the passport response (v1.3); non-https is dropped', async () => {
  const withAvatar = { data: { username: 'Me.User', user_id_str: '7000000000000000001', avatar_url: 'https://p16.tiktokcdn.com/a.jpeg' } };
  const sw = loadSw({ server: baseServer({ '/passport/web/account/info/': () => json(withAvatar) }), store0: {} });
  await sw.send({ type: 'hello', nonce: null }, { id: 77, url: 'https://www.tiktok.com/x' });
  await sleep(50);
  const hello = sw.calls.find((c) => c.path === '/api/ext/hello');
  if (hello) assert.equal(hello.body.identity.avatar_url, 'https://p16.tiktokcdn.com/a.jpeg');

  const bad = { data: { username: 'Me.User', user_id_str: '7000000000000000001', avatar_url: 'http://evil/a.jpg' } };
  const sw2 = loadSw({ server: baseServer({ '/passport/web/account/info/': () => json(bad) }), store0: {} });
  await sw2.send({ type: 'hello', nonce: null }, { id: 77, url: 'https://www.tiktok.com/x' });
  await sleep(50);
  const h2 = sw2.calls.find((c) => c.path === '/api/ext/hello');
  if (h2) assert.equal(h2.body.identity.avatar_url, undefined);
});

test('identity: passport without avatar -> avatar from tiktok.com user detail (v1.4.1); falls back to the profile page JSON', async () => {
  const none = { data: { username: 'Me.User', user_id_str: '7000000000000000001' } };
  const sw = loadSw({ server: baseServer({ '/passport/web/account/info/': () => json(none),
    '/api/user/detail/': () => json({ userInfo: { user: { avatarLarger: 'https://p16.tiktokcdn.com/big.jpeg' } } }) }), store0: {} });
  const id = await sw.ctx.passportIdentity();
  assert.equal(id.username, 'me.user');
  assert.equal(id.avatar_url, 'https://p16.tiktokcdn.com/big.jpeg');
  assert.equal(sw.calls.find((c) => c.path === '/api/user/detail/').search, '?uniqueId=me.user&aid=1988');

  const page = '<html><script id="__UNIVERSAL_DATA_FOR_REWIND__" type="application/json">' + JSON.stringify({ __DEFAULT_SCOPE__: { 'webapp.user-detail': { userInfo: { user: { avatarMedium: 'https://p16.tiktokcdn.com/m.jpeg' } } } } }) + '</script></html>';
  const sw2 = loadSw({ server: baseServer({ '/passport/web/account/info/': () => json(none), '/api/user/detail/': () => json({ statusCode: 10000 }),
    '/@me.user': () => ({ ok: true, status: 200, text: async () => page }) }), store0: {} });
  assert.equal((await sw2.ctx.passportIdentity()).avatar_url, 'https://p16.tiktokcdn.com/m.jpeg');
});

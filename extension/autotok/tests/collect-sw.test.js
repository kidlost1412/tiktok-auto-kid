// v1.4 collection in the REAL sw.js with a stubbed chrome.* API: a Studio page opens -> a collect run starts in a background
// window -> batches are posted to /api/ext/stats + /api/ext/comments with the identity -> the last comment id advances only after
// the app accepted the comments -> failures back off. Nothing here can post to TikTok.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function loadSw({ server, tabs = [] }) {
  const store = {};
  const onMsg = [];
  const calls = [];
  const created = [];
  const ev = () => ({ addListener() {} });
  const chrome = {
    storage: { local: {
      async get(k) { const keys = k == null ? Object.keys(store) : [].concat(k); const o = {}; for (const x of keys) if (x in store) o[x] = JSON.parse(JSON.stringify(store[x])); return o; },
      async set(o) { for (const [k, v] of Object.entries(o)) store[k] = JSON.parse(JSON.stringify(v)); },
      async remove(k) { for (const x of [].concat(k)) delete store[x]; },
    } },
    alarms: { create() {}, onAlarm: ev() },
    runtime: { onMessage: { addListener: (f) => onMsg.push(f) }, onStartup: ev(), onInstalled: ev(), getManifest: () => ({ version: '1.4.1' }) },
    tabs: { query: async () => tabs, get: async (id) => ({ id }), update: async () => {}, remove: async () => {}, sendMessage: async () => { throw new Error('no receiver'); },
      create: async (o) => { created.push(o); return { id: 9, windowId: 1 }; }, onRemoved: ev(), onReplaced: ev() },
    windows: { create: async (o) => { created.push(o); return { id: 1, tabs: [{ id: 9 }] }; }, remove: async () => {} },
  };
  async function fetch(url, init) {
    const u = new URL(url);
    calls.push({ path: u.pathname, body: init && init.body ? JSON.parse(init.body) : null });
    return server(u.pathname, calls[calls.length - 1].body, calls);
  }
  const ctx = { chrome, fetch, setTimeout, clearTimeout, AbortController, console: { log() {}, warn() {}, error() {} }, btoa, Date, URL, Promise, Object, JSON, Math, Error, encodeURIComponent, Array, Number, String };
  vm.createContext(ctx);
  store.settings = { server: 'http://127.0.0.1:1', token: 'T', polling: false, windowStrategy: 'minimized' };
  store.conn = { state: 'ok', bound: { id: 'sa-1', username: 'shop' }, helloAt: Date.now() };
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'sw.js'), 'utf8'), ctx);
  const send = (msg, tab) => new Promise((resolve) => {
    for (const f of onMsg) if (f(msg, { tab }, resolve) === true) return;
    resolve(undefined);
  });
  return { store, calls, created, send };
}
const json = (o, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => o });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const PASSPORT = { data: { username: 'Shop', user_id_str: '6800000000000000009' } };
const okServer = (fail) => async (p) => {
  if (p === '/passport/web/account/info/') return json(PASSPORT);
  if (fail && fail(p)) return json({ error: 'x', message: 'boom' }, 500);
  return json({ ok: true });
};
const OPEN = { id: 5, windowId: 2, url: 'https://www.tiktok.com/tiktokstudio/content', status: 'complete' };

async function startRun(sw) {
  await sw.send({ type: 'ready', stage: 'load', where: '/tiktokstudio/content (no hash)', state: 'complete' }, OPEN);
  await sleep(30);
  const co = sw.store.activeCollect;
  assert.ok(co, 'a collect run was recorded before any window opened');
  const hello = await sw.send({ type: 'hello' }, { id: 9, windowId: 1, url: 'https://www.tiktok.com/tiktokstudio/upload#autotok=' + co.id });
  assert.equal(hello.role, 'collect');
  assert.equal(hello.plan.windowDays, 30);
  return { co, hello };
}

test('collect: page open starts one background (minimized, unfocused) window and sends stats + comments with the identity', async () => {
  const sw = loadSw({ server: okServer() });
  const { hello } = await startRun(sw);
  const w = sw.created[0];
  assert.equal(w.state, 'minimized');
  assert.equal(w.focused, false);
  assert.match(w.url, /#autotok=collect-/);
  const tab = { id: 9, windowId: 1, url: w.url };
  const videos = [{ item_id: '7570000000000000001', views: 10 }];
  const r1 = await sw.send({ type: 'collectBatch', nonce: hello.nonce, batch: { part: 'stats', account: { followers: 5, follower_history: [4, 5] }, videos, list_complete: true } }, tab);
  assert.equal(r1.ok, true);
  const r2 = await sw.send({ type: 'collectBatch', nonce: hello.nonce, batch: { part: 'comments', comments: [{ comment_id: '7571000000000000009', item_id: '7570000000000000001', text: 'giá?' }], newest: { comment_id: '7571000000000000009', created_at: 1762850100 } } }, tab);
  assert.equal(r2.ok, true);
  await sw.send({ type: 'collectDone', nonce: hello.nonce, result: { outcome: 'collect_ok', insights: 1, errors: [] } }, tab);
  const stats = sw.calls.find((c) => c.path === '/api/ext/stats');
  assert.equal(stats.body.user_id, '6800000000000000009');
  assert.equal(stats.body.username, 'shop');
  assert.equal(stats.body.account.followers, 5);
  assert.equal(stats.body.videos.length, 1);
  assert.equal(stats.body.list_complete, true);
  assert.equal(sw.calls.find((c) => c.path === '/api/ext/comments').body.comments.length, 1);
  const cs = sw.store.collectState;
  assert.equal(cs.lastCommentId, '7571000000000000009');
  assert.equal(cs.last.ok, true);
  assert.equal(cs.fails, 0);
  assert.equal(sw.store.activeCollect, undefined);
});

test('collect: a second Studio page opening right after does not start another run (cadence + single run)', async () => {
  const sw = loadSw({ server: okServer() });
  const { hello } = await startRun(sw);
  await sw.send({ type: 'ready', stage: 'load', where: 'x', state: 'complete' }, OPEN);
  await sleep(30);
  assert.equal(sw.created.length, 1);
  await sw.send({ type: 'collectDone', nonce: hello.nonce, result: { outcome: 'collect_ok' } }, { id: 9, windowId: 1, url: '' });
  await sw.send({ type: 'ready', stage: 'load', where: 'x', state: 'complete' }, OPEN);
  await sleep(30);
  assert.equal(sw.created.length, 1, 'finished a moment ago: not due again for 20 minutes');
});

test('collect: app refusing the batch marks the run failed, keeps the old comment cursor and backs off', async () => {
  const sw = loadSw({ server: okServer((p) => p === '/api/ext/comments') });
  sw.store.collectState = { lastCommentId: '1', lastCommentTime: 5 };
  const { hello } = await startRun(sw);
  const tab = { id: 9, windowId: 1, url: '' };
  const r = await sw.send({ type: 'collectBatch', nonce: hello.nonce, batch: { part: 'comments', comments: [{ comment_id: '2', item_id: '3', text: 't' }], newest: { comment_id: '2', created_at: 9 } } }, tab);
  assert.equal(r.ok, false);
  await sw.send({ type: 'collectDone', nonce: hello.nonce, result: { outcome: 'collect_ok' } }, tab);
  const cs = sw.store.collectState;
  assert.equal(cs.lastCommentId, '1', 'cursor must not advance past comments the app did not accept');
  assert.equal(cs.last.ok, false);
  assert.equal(cs.fails, 1);
  assert.ok(cs.nextAt > Date.now(), 'backoff');
});

test('collect: foreign tab / wrong nonce cannot feed the app; no run while a posting job is active', async () => {
  const sw = loadSw({ server: okServer() });
  const { hello } = await startRun(sw);
  assert.equal((await sw.send({ type: 'collectBatch', nonce: 'bad', batch: { part: 'stats', videos: [] } }, { id: 9, windowId: 1, url: '' })).ok, false);
  assert.equal((await sw.send({ type: 'collectBatch', nonce: hello.nonce, batch: { part: 'stats', videos: [] } }, { id: 77, windowId: 1, url: '' })).ok, false);
  assert.equal(sw.calls.filter((c) => c.path === '/api/ext/stats').length, 0);
  const sw2 = loadSw({ server: okServer() });
  sw2.store.activeJob = { id: 'job-1', nonce: 'N', mode: 'post', tabId: 5, finished: false, startedAt: Date.now() };
  await sw2.send({ type: 'ready', stage: 'load', where: 'x', state: 'complete' }, OPEN);
  await sleep(30);
  assert.equal(sw2.store.activeCollect, undefined);
  assert.equal(sw2.created.length, 0);
});

test('collect: not paired / app account not enabled -> nothing opens', async () => {
  const sw = loadSw({ server: okServer() });
  sw.store.conn = { state: 'ok', bound: null };
  await sw.send({ type: 'ready', stage: 'load', where: 'x', state: 'complete' }, OPEN);
  await sleep(30);
  assert.equal(sw.created.length, 0);
});

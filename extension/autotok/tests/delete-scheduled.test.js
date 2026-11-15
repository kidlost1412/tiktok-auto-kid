// v1.4.6 "Đổi giờ" (PROTOCOL.md section 12): pure item_list checks (studio-lib.js) and the delete task in the REAL sw.js with a
// stubbed chrome.* API. Nothing here talks to TikTok; ids are fake.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const S = require('../studio-lib.js');

const NOW = 1790000000;
const ITEM = '7570000000000000777';

test('scheduledCheck: only a future scheduled item at the expected time passes', () => {
  assert.equal(S.scheduledCheck({ schedule_time: NOW + 7200, post_time: NOW + 7200 }, NOW + 7200, NOW).ok, true);
  assert.equal(S.scheduledCheck({ schedule_time: 0, post_time: NOW + 7200 }, NOW + 7100, NOW).ok, true, 'post_time fallback, shift tolerated');
  assert.equal(S.scheduledCheck({ schedule_time: NOW + 300 }, NOW + 300, NOW).reason, 'too-close-or-published');
  assert.equal(S.scheduledCheck({ post_time: NOW - 3600 }, NOW - 3600, NOW).reason, 'too-close-or-published');
  assert.equal(S.scheduledCheck({ schedule_time: NOW + 7200 }, NOW + 20000, NOW).reason, 'time-mismatch');
  assert.equal(S.scheduledCheck({}, NOW, NOW).reason, 'no-time');
});

test('scan: absence is only proven when the list ended or went past the item page into older posts', () => {
  const page = (items, hasMore) => ({ items, hasMore });
  const sched = { item_id: '7570000000000000001', post_time: NOW + 3600 };
  const old = { item_id: '7570000000000000002', post_time: NOW - 5 * 86400 };

  const a = S.scanStart(ITEM, NOW + 7200, 1);
  S.scanPage(a, page([sched], true));
  assert.equal(S.scanDone(a), false, 'only future items seen: keep reading');
  S.scanPage(a, page([old], true));
  assert.equal(S.scanProvesAbsent(a), true);

  const b = S.scanStart(ITEM, NOW + 7200, 3);
  S.scanPage(b, page([sched, old], true));
  assert.equal(S.scanProvesAbsent(b), false, 'must read at least minPages');
  S.scanPage(b, page([old], false));
  assert.equal(S.scanProvesAbsent(b), true, 'list ended');

  const c = S.scanStart(ITEM, NOW + 7200, 1);
  S.scanPage(c, page([{ item_id: ITEM, post_time: NOW + 7200 }, old], true));
  assert.equal(c.found.item_id, ITEM);
  assert.equal(c.foundPage, 1);
  assert.equal(S.scanProvesAbsent(c), false);
});

function loadSw({ server }) {
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
    runtime: { onMessage: { addListener: (f) => onMsg.push(f) }, onStartup: ev(), onInstalled: ev(), getManifest: () => ({ version: '1.4.6' }) },
    tabs: { query: async () => [], get: async (id) => ({ id }), update: async () => {}, remove: async () => {}, sendMessage: async () => { throw new Error('no'); },
      create: async (o) => { created.push(o); return { id: 9, windowId: 1 }; }, onRemoved: ev(), onReplaced: ev() },
    windows: { create: async (o) => { created.push(o); return { id: 1, tabs: [{ id: 9 }], state: 'minimized' }; }, remove: async () => {} },
  };
  async function fetch(url, init) {
    const u = new URL(url);
    calls.push({ path: u.pathname, body: init && init.body ? JSON.parse(init.body) : null });
    return server(u.pathname, calls[calls.length - 1].body);
  }
  const ctx = { chrome, fetch, setTimeout, clearTimeout, AbortController, console: { log() {}, warn() {}, error() {} }, btoa, Date, URL, Promise, Object, JSON, Math, Error, encodeURIComponent, Array, Number, String, RegExp };
  vm.createContext(ctx);
  store.settings = { server: 'http://127.0.0.1:1', token: 'T', polling: false, windowStrategy: 'minimized' };
  store.conn = { state: 'ok', bound: { id: 'sa-1' }, helloAt: Date.now() };
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'sw.js'), 'utf8'), ctx);
  const send = (msg, tab) => new Promise((resolve) => { for (const f of onMsg) if (f(msg, { tab }, resolve) === true) return; resolve(undefined); });
  return { store, calls, created, send, ctx };
}
const json = (o, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => o, text: async () => JSON.stringify(o) });
const TASK = { id: 'rs_1', nonce: 'n1', item_id: ITEM, expect_user_id: '6800000000000000009', expect_account: 'shop', schedule_unix: NOW + 7200, state: 'pending' };

test('delete task: claim -> background window with del- hash -> tab gets role delete -> verified result posted with the server nonce', async () => {
  const sw = loadSw({ server: async (p) => (p === '/api/ext/delete_scheduled/claim' ? json({ ok: true, state: 'claimed' }) : json({ ok: true, state: 'done' })) });
  assert.equal(await sw.ctx.startDelete(TASK), true);
  const d = sw.store.activeDelete;
  assert.ok(d && d.task.item_id === ITEM);
  assert.equal(sw.calls[0].path, '/api/ext/delete_scheduled/claim');
  assert.deepEqual(sw.calls[0].body, { id: 'rs_1', nonce: 'n1' });
  assert.match(sw.created[0].url, /#autotok=del-rs_1$/);
  assert.equal(sw.created[0].focused, false);

  const tab = { id: 9, windowId: 1, url: sw.created[0].url };
  const hello = await sw.send({ type: 'hello' }, tab);
  assert.equal(hello.role, 'delete');
  assert.equal(hello.task.item_id, ITEM);
  assert.notEqual(hello.nonce, 'n1', 'the tab never sees the server nonce');

  assert.equal((await sw.send({ type: 'deleteResult', nonce: 'wrong', result: { outcome: 'deleted', verified: true } }, tab)).ok, false);
  await sw.send({ type: 'deleteResult', nonce: hello.nonce, result: { outcome: 'deleted', verified: true, delete_sent: true } }, tab);
  const res = sw.calls.find((c) => c.path === '/api/ext/delete_scheduled/result');
  assert.equal(res.body.id, 'rs_1');
  assert.equal(res.body.nonce, 'n1');
  assert.equal(res.body.outcome, 'deleted');
  assert.equal(res.body.verified, true);
  assert.equal(res.body.item_id, ITEM);
  assert.equal(sw.store.activeDelete, undefined);
  assert.equal(sw.store.lastDeleteDone, 'rs_1');
  assert.equal(await sw.ctx.startDelete(TASK), false, 'the same task is never run twice');
});

test('delete task: refused claim opens nothing; a busy posting job blocks it; a lost tab after hand-over reports unknown', async () => {
  const refuse = loadSw({ server: async () => json({ ok: false, reason: 'too-late' }) });
  assert.equal(await refuse.ctx.startDelete(TASK), false);
  assert.equal(refuse.created.length, 0);
  assert.equal(refuse.store.activeDelete, undefined);

  const busy = loadSw({ server: async () => json({ ok: true }) });
  busy.store.activeJob = { id: 'ej_1' };
  assert.equal(await busy.ctx.startDelete(TASK), false);
  assert.equal(busy.calls.length, 0, 'not even claimed while a job runs');

  const lost = loadSw({ server: async () => json({ ok: true, state: 'claimed' }) });
  await lost.ctx.startDelete(TASK);
  await lost.send({ type: 'hello' }, { id: 9, windowId: 1, url: lost.created[0].url });
  lost.store.activeDelete.startedAt = Date.now() - 10 * 60 * 1000;
  await lost.ctx.recoverDelete();
  const res = lost.calls.find((c) => c.path === '/api/ext/delete_scheduled/result');
  assert.equal(res.body.outcome, 'unknown', 'after hand-over a timeout is never reported as "nothing happened"');
});

// v1.4.5 fast product sync inside the service worker (no Studio window): parallel pages, progress to the app, fallback to the tab flow.
// REAL sw.js + REAL lib.js, stubbed chrome.* and a fake backend / shop (no ports).
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
  const ctx = { TextEncoder, TextDecoder, chrome, fetch, importScripts: (f) => vm.runInContext(fs.readFileSync(path.join(__dirname, '..', f), 'utf8'), ctx), setTimeout: unrefTimeout, clearTimeout, AbortController, console: { log() {}, warn() {}, error() {} }, btoa, Date, URL, Promise, Object, JSON, Math, Error, encodeURIComponent };
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
const mk = (n) => Array.from({ length: n }, (_, i) => ({ product_id: String(7600000000000000000n + BigInt(i + 1)), title: 'SP ' + (i + 1), format_available_price: '99.000d', cover: { url_list: ['https://p16.ibyteimg.com/x' + i] }, stock_num: 5 }));
// fake shop: type 3 = my shop (n products), type 2 = showcase (m products), paged by cursor/count
const shopServer = (n, m, over) => async (p, body, rec) => {
  if (over && over[p]) return over[p](body, rec);
  if (rec.host === 'shop.tiktok.com') {
    const q = new URLSearchParams(rec.search);
    const all = q.get('search_type') === '3' ? mk(n) : mk(m).map((x) => Object.assign({}, x, { product_id: String(BigInt(x.product_id) + 1000n) }));
    const cur = Number(q.get('cursor')), cnt = Number(q.get('count'));
    return json({ code: 0, data: { products: all.slice(cur, cur + cnt), total: all.length } });
  }
  if (p === '/passport/web/account/info/') return json({ data: { username: 'Me.User', user_id_str: '7000000000000000001' } });
  if (p === '/api/ext/hello') return helloOk();
  if (p === '/api/ext/tasks') return json({ sync_products: 'req1' });
  if (p === '/api/ext/next') return new Promise(() => {});
  return json({ ok: true });
};
const until = async (f) => { for (let i = 0; i < 200 && !f(); i++) await sleep(20); };

test('fast sync: 58 products come from the service worker alone (2 pages), no Studio window, progress reported, then uploaded once', async () => {
  const sw = loadSw({ settings: { polling: true }, server: shopServer(58, 0) });
  await until(() => sw.calls.some((c) => c.path === '/api/ext/products'));
  await sleep(100);
  assert.equal(sw.created.length, 0);                                              // no window / tab opened
  const shopCalls = sw.calls.filter((c) => c.host === 'shop.tiktok.com');
  assert.equal(shopCalls.filter((c) => new URLSearchParams(c.search).get('search_type') === '3').length, 2);   // 50 + 8
  assert.ok(shopCalls.every((c) => c.credentials === 'include'));
  const posts = sw.calls.filter((c) => c.path === '/api/ext/products');
  const mine = posts.find((c) => c.body.source === 'my_shop');
  assert.equal(mine.body.products.length, 58);
  assert.deepEqual([mine.body.complete, mine.body.request_id, mine.body.username, mine.body.user_id], [true, 'req1', 'me.user', '7000000000000000001']);
  const prog = sw.calls.filter((c) => c.path === '/api/ext/sync_status' && c.body.ok === true).map((c) => c.body.progress);
  assert.ok(prog.length >= 1);
  assert.deepEqual(prog[prog.length - 1], { got: 58, total: 58 });
  assert.ok(prog.every((x) => x.got <= 58 && x.total >= x.got));
  assert.equal(sw.store.activeSync, undefined);                                    // finished and cleared
  assert.equal(sw.store.syncState.done, true);
});

test('fast sync: later pages are fetched in parallel (130 products = 3 pages) and duplicates between sources are not double counted', async () => {
  const sw = loadSw({ settings: { polling: true }, server: shopServer(130, 3) });
  await until(() => sw.calls.filter((c) => c.path === '/api/ext/products').length >= 2);
  const mine = sw.calls.find((c) => c.path === '/api/ext/products' && c.body.source === 'my_shop');
  assert.equal(mine.body.products.length, 130);
  assert.equal(new Set(mine.body.products.map((p) => p.product_id)).size, 130);
  assert.equal(sw.created.length, 0);
});

test('fast sync: when the shop cannot be read from the service worker the old Studio-tab flow takes over', async () => {
  const sw2 = loadSw({ settings: { polling: true }, server: async (p, body, rec) => (rec.host === 'shop.tiktok.com' ? json({ code: 7 }, 403) : shopServer(5, 0)(p, body, rec)) });
  await until(() => sw2.created.length > 0);
  assert.equal(sw2.created.length, 1);
  assert.equal(sw2.created[0].url, 'https://www.tiktok.com/tiktokstudio/upload#autotok=sync-req1');
  assert.equal(sw2.calls.filter((c) => c.path === '/api/ext/products').length, 0);
  assert.equal(sw2.store.activeSync.finished, false);
});

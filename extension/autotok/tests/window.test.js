// Extension-opened work windows must never steal focus (background-started Chrome has no window at all).
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load({ normalWindows, createdState = 'minimized', noGetAll = false }) {
  const calls = { tabsCreate: [], winCreate: [], winUpdate: [] };
  const ev = () => ({ addListener() {} });
  const windows = {
    create: async (o) => { calls.winCreate.push(o); return { id: 7, state: createdState, tabs: [{ id: 9 }] }; },
    update: async (id, o) => { calls.winUpdate.push([id, o]); },
    remove: async () => {},
  };
  if (!noGetAll) windows.getAll = async () => normalWindows;
  const chrome = {
    storage: { local: { async get() { return {}; }, async set() {}, async remove() {} } },
    alarms: { create() {}, onAlarm: ev() },
    runtime: { onMessage: { addListener() {} }, onStartup: ev(), onInstalled: ev() },
    tabs: { query: async () => [], get: async (id) => ({ id }), update: async () => {}, remove: async () => {}, create: async (o) => { calls.tabsCreate.push(o); return { id: 9, windowId: 1 }; }, onRemoved: ev(), onReplaced: ev() },
    windows,
  };
  const ctx = { chrome, fetch: async () => ({}), setTimeout, clearTimeout, AbortController, console: { log() {}, warn() {}, error() {} }, btoa, Date, URL, Promise, Object, JSON, Math, Error, encodeURIComponent };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'sw.js'), 'utf8'), ctx);
  return { calls, create: (strategy) => vm.runInContext('createStudioWindow', ctx)('https://www.tiktok.com/tiktokstudio/upload#autotok=x', { windowStrategy: strategy }) };
}

test("'tab' strategy with a normal window opens a background tab (active:false) in it", async () => {
  const t = load({ normalWindows: [{ id: 1 }] });
  const r = await t.create('tab');
  assert.equal(r.strategy, 'tab');
  assert.equal(JSON.stringify(t.calls.tabsCreate.map((o) => o.active)), '[false]');
  assert.equal(t.calls.winCreate.length, 0);
});

test("'tab' strategy with NO normal window uses a minimized unfocused window (no visible pop-up) and reports it as a window", async () => {
  const t = load({ normalWindows: [] });
  const r = await t.create('tab');
  assert.equal(r.strategy, 'minimized');
  assert.equal(t.calls.tabsCreate.length, 0);
  assert.equal(t.calls.winCreate[0].state, 'minimized');
  assert.equal(t.calls.winCreate[0].focused, false);
});

test('minimized strategy: a window that came up normal is minimized again', async () => {
  const t = load({ normalWindows: [], createdState: 'normal' });
  await t.create('minimized');
  assert.equal(JSON.stringify(t.calls.winUpdate), JSON.stringify([[7, { state: 'minimized', focused: false }]]));
});

test('unknown window list keeps the old behaviour (tab)', async () => {
  const t = load({ normalWindows: [], noGetAll: true });
  assert.equal((await t.create('tab')).strategy, 'tab');
});

// One reusable minimized work window: creating a window per job could take the foreground on Windows (CapCut lost focus).
function loadWork({ winState = 'minimized', existing = null } = {}) {
  const calls = { tabsCreate: [], winCreate: [] };
  const session = {};
  if (existing != null) session.workWindowId = existing;
  const ev = () => ({ addListener() {} });
  const chrome = {
    storage: {
      local: { async get() { return {}; }, async set() {}, async remove() {} },
      session: { async get(k) { return k in session ? { [k]: session[k] } : {}; }, async set(o) { Object.assign(session, o); } },
    },
    alarms: { create() {}, onAlarm: ev() },
    runtime: { onMessage: { addListener() {} }, onStartup: ev(), onInstalled: ev() },
    tabs: { query: async () => [], get: async (id) => ({ id }), update: async () => {}, remove: async () => {}, create: async (o) => { calls.tabsCreate.push(o); return { id: 20 + calls.tabsCreate.length, windowId: o.windowId }; }, onRemoved: ev(), onReplaced: ev() },
    windows: {
      create: async (o) => { calls.winCreate.push(o); return { id: 7, state: 'minimized', tabs: [{ id: 9 }] }; },
      get: async (id) => { if (id !== 7) throw new Error('No window with id'); return { id, type: 'normal', state: winState }; },
      getAll: async () => [], update: async () => {}, remove: async () => {},
    },
  };
  const ctx = { chrome, fetch: async () => ({}), setTimeout, clearTimeout, AbortController, console: { log() {}, warn() {}, error() {} }, btoa, Date, URL, Promise, Object, JSON, Math, Error, encodeURIComponent };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'sw.js'), 'utf8'), ctx);
  return { calls, session, create: () => vm.runInContext('createStudioWindow', ctx)('https://www.tiktok.com/tiktokstudio/upload#autotok=x', { windowStrategy: 'minimized' }) };
}

test('first job creates ONE minimized unfocused work window with a blank keeper tab; it is closed as a tab', async () => {
  const t = loadWork();
  const r = await t.create();
  assert.equal(t.calls.winCreate.length, 1);
  assert.equal(t.calls.winCreate[0].focused, false);
  assert.equal(t.calls.winCreate[0].state, 'minimized');
  assert.equal(JSON.stringify(t.calls.tabsCreate), JSON.stringify([{ windowId: 7, url: 'about:blank', active: false }]));
  assert.equal(t.session.workWindowId, 7);
  assert.equal(r.strategy, 'tab');
  assert.equal(r.tab.id, 9);
});

test('later jobs open as a tab inside the existing work window: no new window is ever created', async () => {
  const t = loadWork({ existing: 7 });
  const r = await t.create();
  assert.equal(t.calls.winCreate.length, 0);
  assert.equal(t.calls.tabsCreate.length, 1);
  assert.equal(t.calls.tabsCreate[0].windowId, 7);
  assert.equal(r.strategy, 'tab');
  assert.equal(r.windowId, 7);
});

test('a work window the owner restored (not minimized) or closed is not reused', async () => {
  const restored = loadWork({ existing: 7, winState: 'normal' });
  await restored.create();
  assert.equal(restored.calls.winCreate.length, 1);

  const closed = loadWork({ existing: 99 });
  await closed.create();
  assert.equal(closed.calls.winCreate.length, 1);
});

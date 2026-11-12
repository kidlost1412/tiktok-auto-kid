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

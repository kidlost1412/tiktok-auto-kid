// avatar.js: choosing the signed-in channel's avatar among images on a TikTok / Studio page.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ctx = { globalThis: null };
ctx.globalThis = ctx;
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'avatar.js'), 'utf8'), ctx);
const pick = ctx.__autotokPickAvatar;
const img = (o) => Object.assign({ src: 'https://p16-sign.tiktokcdn-us.com/tos-x/avatar-1~c5_100x100.jpeg', cls: 'arco-avatar-image', alt: '', top: 12, w: 32, h: 32 }, o);

test('header avatar is picked', () => assert.match(pick([img({})]), /avatar-1/));
test('avatars lower on the page (comments, followers) are ignored', () => assert.equal(pick([img({ top: 400 })]), ''));
test('non-TikTok-CDN, non-square, tiny or non-avatar images are ignored', () => {
  assert.equal(pick([img({ src: 'https://evil.example/avatar.jpg' })]), '');
  assert.equal(pick([img({ w: 80, h: 30 })]), '');
  assert.equal(pick([img({ w: 8, h: 8 })]), '');
  assert.equal(pick([img({ cls: 'banner', src: 'https://p16.tiktokcdn.com/tos-x/pic.jpeg' })]), '');
});
test('the highest header candidate wins', () => {
  assert.match(pick([img({ top: 100, src: 'https://p16.tiktokcdn.com/tos-x/avatar-low.jpeg' }), img({ top: 10 })]), /avatar-1/);
});

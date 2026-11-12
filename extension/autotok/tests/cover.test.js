// Per-product cover: pure helpers in lib.js (meta validation, VOD image upload parsing, body field). Never fatal by design.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const L = require('../lib.js');

const SHA = 'a'.repeat(64);
const meta = (o) => Object.assign({ url: '/api/ext/cover?id=ej_1', name: 'cover.jpg', mime: 'image/jpeg', size: 123456, sha256: SHA, field: 'cover_uri' }, o);

test('validateCoverMeta accepts a well-formed cover and defaults the field name', () => {
  assert.equal(L.validateCoverMeta(meta()).ok, true);
  assert.equal(L.validateCoverMeta(meta({ field: undefined })).field, 'cover_uri');
  assert.equal(L.validateCoverMeta(meta({ field: 'Bad Field!' })).field, 'cover_uri');
  assert.equal(L.validateCoverMeta(meta({ mime: 'image/png' })).ok, true);
});

test('validateCoverMeta rejects anything doubtful (the post then goes out with the default cover)', () => {
  for (const bad of [null, 'x', meta({ url: 'https://evil/x' }), meta({ mime: 'image/gif' }), meta({ size: 0 }), meta({ size: 6 * 1024 * 1024 }),
    meta({ size: 1.5 }), meta({ sha256: 'zz' })]) assert.equal(L.validateCoverMeta(bad).ok, false);
});

test('coverApplyPath asks VOD for an image upload of the exact size', () => {
  const p = L.coverApplyPath(4242);
  assert.match(p, /FileType=image/);
  assert.match(p, /FileSize=4242/);
  assert.doesNotMatch(p, /FileType=video/);
});

test('parseCoverApply / parseCoverCommit read the upload node and tolerate odd responses', () => {
  const ok = { Result: { InnerUploadAddress: { UploadNodes: [{ UploadHost: 'h.example', SessionKey: 'sk', StoreInfos: [{ StoreUri: 'tos-x/abc', Auth: 'au' }] }] } } };
  assert.deepEqual({ ...L.parseCoverApply(ok) }, { ok: true, host: 'h.example', uri: 'tos-x/abc', auth: 'au', sessionKey: 'sk' });
  assert.equal(L.parseCoverApply({}).ok, false);
  assert.equal(L.parseCoverApply({ Result: { InnerUploadAddress: { UploadNodes: [{ UploadHost: 'h', StoreInfos: [{}] }] } } }).ok, false);
  assert.equal(L.parseCoverCommit({ Result: { Results: [{ Uri: 'tos-x/final' }] } }), 'tos-x/final');
  assert.equal(L.parseCoverCommit({}), null);
});

const base = { creationId: 'c', videoId: 'v1', caption: 'hi', markup: 'hi', textExtra: [], visibility: 0 };

test('buildPayload without a cover is byte-identical to before; with one it sets only the configured field', () => {
  const plain = JSON.stringify(L.buildPayload(base));
  assert.equal(JSON.stringify(L.buildPayload({ ...base, coverUri: null })), plain);
  const withCover = L.buildPayload({ ...base, coverUri: 'tos-x/abc' });
  assert.equal(withCover.single_post_req_list[0].single_post_feature_info.cover_uri, 'tos-x/abc');
  const other = L.buildPayload({ ...base, coverUri: 'tos-x/abc', coverField: 'poster_uri' });
  assert.equal(other.single_post_req_list[0].single_post_feature_info.poster_uri, 'tos-x/abc');
  assert.equal('cover_uri' in other.single_post_req_list[0].single_post_feature_info, false);
  const stripped = JSON.parse(JSON.stringify(withCover)); delete stripped.single_post_req_list[0].single_post_feature_info.cover_uri;
  assert.equal(JSON.stringify(stripped), plain);
});

test('an invalid field name is never written into the body', () => {
  const p = L.buildPayload({ ...base, coverUri: 'tos-x/abc', coverField: 'a b;c' });
  assert.equal(JSON.stringify(p), JSON.stringify(L.buildPayload(base)));
});

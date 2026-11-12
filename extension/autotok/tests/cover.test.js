// Per-product cover: pure helpers in lib.js (meta validation, VOD image upload parsing, body field). Never fatal by design.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const L = require('../lib.js');

const SHA = 'a'.repeat(64);
const meta = (o) => Object.assign({ url: '/api/ext/cover?id=ej_1', name: 'cover.jpg', mime: 'image/jpeg', size: 123456, sha256: SHA, width: 1080, height: 1440 }, o);

test('validateCoverMeta accepts a well-formed cover and returns its pixel size', () => {
  const v = L.validateCoverMeta(meta());
  assert.equal(v.ok, true);
  assert.equal(v.width, 1080);
  assert.equal(v.height, 1440);
  assert.equal(L.validateCoverMeta(meta({ mime: 'image/png' })).ok, true);
  assert.equal(L.validateCoverMeta(meta({ width: 324, height: 432 })).ok, true);
});

test('validateCoverMeta rejects anything doubtful (the post then goes out with the default cover)', () => {
  for (const bad of [null, 'x', meta({ url: 'https://evil/x' }), meta({ mime: 'image/gif' }), meta({ size: 0 }), meta({ size: 6 * 1024 * 1024 }),
    meta({ size: 1.5 }), meta({ sha256: 'zz' }), meta({ width: 323 }), meta({ height: 431 }), meta({ width: undefined }), meta({ height: '1440px' })]) assert.equal(L.validateCoverMeta(bad).ok, false);
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
const COVER = { uri: 'tos-alisg-p-0037/abc', width: 1080, height: 1440 };
const info = (p) => p.single_post_req_list[0].single_post_feature_info;

test('buildPayload without a cover is byte-identical to before', () => {
  const plain = JSON.stringify(L.buildPayload(base));
  assert.equal(JSON.stringify(L.buildPayload({ ...base, cover: null })), plain);
  assert.equal('cover_info' in info(L.buildPayload(base)), false);
});

test('buildPayload with a cover sets the cover_info object exactly as Studio sends it (and nothing flat)', () => {
  const p = L.buildPayload({ ...base, cover: COVER });
  assert.equal(JSON.stringify(info(p).cover_info), JSON.stringify({ cover_type: 3, crop_type: 2, cover_width: 1080, cover_height: 1440, frame_duration: 0,
    is_cover_cut: false, isAutoCropFirstFrame: false, add_template_flag: false, cover_uri: 'tos-alisg-p-0037/abc' }));
  assert.equal('blob_url' in info(p).cover_info, false);
  assert.equal('coverProject' in info(p).cover_info, false);
  assert.equal('cover_uri' in info(p), false);
  assert.equal(info(p).poster_delay, 0);
  // everything else is untouched
  const stripped = JSON.parse(JSON.stringify(p)); delete info(stripped).cover_info;
  assert.equal(JSON.stringify(stripped), JSON.stringify(L.buildPayload(base)));
});

test('a doubtful cover (no uri, missing or too small size) never writes cover_info', () => {
  const plain = JSON.stringify(L.buildPayload(base));
  for (const bad of [{ ...COVER, uri: '' }, { ...COVER, width: 300 }, { ...COVER, height: undefined }, { uri: 'x' }]) {
    assert.equal(JSON.stringify(L.buildPayload({ ...base, cover: bad })), plain);
  }
});

// K4 cart: pure helpers in lib.js (anchor template rewriting, shop search parsing, availability, passive capture).
// The real template shape is unknown until a real capture, so these tests use a REALISTIC GUESS: an anchors entry whose
// `extra` is a nested JSON string holding product_id + title, plus plain fields. The code must work by value, not by key.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const L = require('../lib.js');

const OLD = '7512345678901234567';
const NEW = '7598765432109876543';
const SELLER = '7400000000000000001';
const OLD_NAME = 'Áo thun cotton nam form rộng';
const NEW_NAME = 'Quần short kaki nam';
const P = { product_id: NEW, product_name: NEW_NAME };

const template = () => [{
  type: 'product', id: OLD, title: OLD_NAME, anchor_title: OLD_NAME, general_type: 3, source_from: 'streamer_desktop',
  extra: JSON.stringify({ product_id: OLD, seller_id: SELLER, title: OLD_NAME, schema: `snssdk1180://ec/pdp?id=${OLD}&from=studio`, image: { url_list: ['https://p16.example/x.jpg'] } }),
  keywords: OLD_NAME, order: 1,
}];

test('buildProductAnchors replaces the id and the name everywhere, including inside the nested JSON string', () => {
  const t = template();
  const snapshot = JSON.stringify(t);
  const r = L.rewriteAnchorsDetailed(t, OLD, P);
  assert.equal(JSON.stringify(t), snapshot, 'input must not be mutated');
  const a = r.anchors[0];
  assert.equal(a.id, NEW);
  assert.equal(a.title, NEW_NAME);
  assert.equal(a.anchor_title, NEW_NAME);
  assert.equal(a.keywords, NEW_NAME);
  const extra = JSON.parse(a.extra);
  assert.deepEqual(extra, { product_id: NEW, seller_id: SELLER, title: NEW_NAME, schema: `snssdk1180://ec/pdp?id=${NEW}&from=studio`, image: { url_list: ['https://p16.example/x.jpg'] } });
  assert.equal(typeof a.extra, 'string');                        // still a JSON-encoded string
  assert.equal(typeof extra.product_id, 'string');               // ids stay strings
  const all = JSON.stringify(r.anchors);
  assert.equal(all.includes(OLD), false);
  assert.equal(all.includes(OLD_NAME), false);
  assert.ok(all.includes(SELLER));                               // unrelated ids untouched
  assert.deepEqual([r.replacedIds, r.oldNames], [3, [OLD_NAME]]);
  assert.equal(r.replacedNames > 0, true);
  assert.deepEqual(L.rewriteAnchors(t, OLD, P), r.anchors);
});

test('buildProductAnchors accepts {anchors:[...]}; with no name found only the id changes', () => {
  const r = L.rewriteAnchorsDetailed({ anchors: [{ k: OLD }, { k: 'other' }] }, OLD, P);
  assert.deepEqual(r.anchors, [{ k: NEW }, { k: 'other' }]);
  assert.deepEqual([r.replacedIds, r.replacedNames, r.oldNames], [1, 0, []]);
});

test('buildProductAnchors: id as whole value, inside a longer string, as an object key, inside arrays', () => {
  const r = L.rewriteAnchors([{ a: OLD, b: `x/${OLD}/y`, [OLD]: 1, c: [OLD, `id=${OLD}`] }], OLD, P);
  assert.deepEqual(r, [{ a: NEW, b: `x/${NEW}/y`, [NEW]: 1, c: [NEW, `id=${NEW}`] }]);
});

test('buildProductAnchors: JSON inside JSON, and a nested JSON array', () => {
  const inner = JSON.stringify({ product_id: OLD, name: OLD_NAME });
  const t = [{ title: OLD_NAME, extra: JSON.stringify({ deep: inner, list: JSON.stringify([{ pid: OLD }]) }) }];
  const r = L.rewriteAnchors(t, OLD, P);
  const e = JSON.parse(r[0].extra);
  assert.deepEqual(JSON.parse(e.deep), { product_id: NEW, name: NEW_NAME });
  assert.deepEqual(JSON.parse(e.list), [{ pid: NEW }]);
});

test('buildProductAnchors: a 19-digit id as a bare JSON number inside the nested string is rewritten as text (no precision loss)', () => {
  const extra = `{"product_id":${OLD},"title":"${OLD_NAME}","n":1}`;
  const r = L.rewriteAnchors([{ title: OLD_NAME, extra }], OLD, P);
  assert.equal(r[0].extra, `{"product_id":${NEW},"title":"${NEW_NAME}","n":1}`);
});

test('buildProductAnchors fails closed: a stale name that cannot be replaced is an error', () => {
  const extra = `{"product_id":${OLD},"title":"\\u00c1o thun cotton nam form r\\u1ed9ng"}`;   // escaped name inside a big-number string
  assert.throws(() => L.rewriteAnchors([{ title: OLD_NAME, extra }], OLD, P), (e) => e.code === 'anchor-build-failed' && /name still present/.test(e.message));
});

test('buildProductAnchors throws when the template id is not found, or inputs are not string ids', () => {
  const bad = (tpl, oldId, p, re) => assert.throws(() => L.rewriteAnchors(tpl, oldId, p), (e) => e.code === 'anchor-build-failed' && re.test(e.message), re.source);
  bad(template(), '7000000000000000999', P, /not found/);
  bad([], OLD, P, /non-empty array/);
  bad(null, OLD, P, /non-empty array/);
  bad(template(), Number(OLD), P, /template_product_id/);
  bad(template(), OLD, { product_id: Number(NEW), product_name: 'x' }, /product_id/);
  bad(template(), OLD, { product_id: 'abc', product_name: 'x' }, /product_id/);
  bad(template(), OLD, { product_id: NEW, product_name: '  ' }, /product_name/);
  bad(template(), '123', P, /template_product_id/);                 // too short: would rewrite unrelated digits
  bad([{ id: 7512345678901234000 }], OLD, P, /unsafe integer/);      // lossy number in the template
  bad([{ id: 12345678, x: OLD }], '12345678', P, /as a number/);     // the id sits in the template as a number
});

test('buildProductAnchors: same product (old == new) keeps the id, still swaps the name', () => {
  const r = L.rewriteAnchors(template(), OLD, { product_id: OLD, product_name: NEW_NAME });
  assert.equal(r[0].id, OLD);
  assert.equal(r[0].title, NEW_NAME);
  assert.equal(JSON.parse(r[0].extra).product_id, OLD);
});

test('buildPayload: anchors default to [] (unchanged body) and a given list lands in feature_common_info_list[0].anchors', () => {
  const base = { creationId: 'CrEaTiOnId_0123456789', videoId: 'v1', caption: 'x', markup: 'x', textExtra: [], visibility: 0 };
  assert.deepEqual(L.buildPayload(base).feature_common_info_list[0].anchors, []);
  assert.equal(JSON.stringify(L.buildPayload(base)), JSON.stringify(L.buildPayload(Object.assign({ anchors: [] }, base))));
  const anchors = L.rewriteAnchors(template(), OLD, P);
  assert.deepEqual(L.buildPayload(Object.assign({ anchors }, base)).feature_common_info_list[0].anchors, anchors);
});

// ---- shop search ----
const shopText = (products, total) => `{"code":0,"message":"success","data":{"products":[${products.join(',')}],"total":${total == null ? products.length : total},"added_product_ids":[]}}`;
// product_id deliberately written as a bare 19-digit NUMBER in one of them: parseKeepNumbers must keep it exact.
const prod = (id, o = {}) => `{"product_id":${o.quoted === false ? id : `"${id}"`},"title":"${o.title || 'SP ' + id}","format_available_price":"${o.price || '129.000đ'}","cover":{"thumb_url_list":["https://img/${id}.jpg"]},"stock_num":${o.stock === undefined ? 5 : o.stock},"stock_status":1,"source":3,"source_from":1}`;

test('parseShopProducts normalizes the list and keeps 19-digit ids exact (even when written as numbers)', () => {
  const r = L.parseShopProducts(shopText([prod(OLD), prod(NEW, { quoted: false, stock: '0' }), '{"title":"no id"}'], 120));
  assert.equal(r.ok, true);
  assert.deepEqual([r.total, r.rawCount, r.skipped], [120, 3, 1]);
  assert.deepEqual(r.products[0], { product_id: OLD, title: 'SP ' + OLD, price: '129.000đ', cover_url: `https://img/${OLD}.jpg`, stock_num: 5, stock_status: 1 });
  assert.equal(r.products[1].product_id, NEW);
  assert.equal(r.products[1].stock_num, 0);
  assert.equal(typeof r.products[1].product_id, 'string');
});

test('parseShopProducts: code != 0, non-JSON, missing data are errors; null products is an empty (showcase) list', () => {
  assert.equal(L.parseShopProducts('{"code":10001,"message":"x"}').reason, 'code-10001');
  assert.equal(L.parseShopProducts('<html>').reason, 'non-json');
  assert.equal(L.parseShopProducts('{"code":0}').reason, 'no-data');
  assert.equal(L.parseShopProducts('{"data":{"products":[]}}').reason, 'code-missing');
  const e = L.parseShopProducts('{"code":0,"data":{"products":null,"total":0}}');
  assert.deepEqual([e.ok, e.products.length, e.total], [true, 0, 0]);
});

test('checkProductAvailable: exact product_id + stock > 0 only', () => {
  const t = shopText([prod(OLD, { stock: 3 })]);
  assert.deepEqual([L.checkProductAvailable(t, OLD).ok, L.checkProductAvailable(t, OLD).reason], [true, 'ok']);
  assert.equal(L.checkProductAvailable(t, NEW).reason, 'not-found');                                   // other product returned: no loose match
  assert.equal(L.checkProductAvailable(shopText([prod(OLD, { stock: 0 })]), OLD).reason, 'out-of-stock');
  assert.equal(L.checkProductAvailable(shopText([prod(OLD, { stock: -1 })]), OLD).ok, false);
  assert.equal(L.checkProductAvailable(shopText([prod(OLD).replace('"stock_num":5,', '')]), OLD).reason, 'stock-unknown');
  assert.equal(L.checkProductAvailable('{"code":5}', OLD).reason, 'search-error');
  assert.equal(L.checkProductAvailable(t, Number(OLD)).reason, 'bad-id');
  assert.equal(L.checkProductAvailable(shopText([prod('7512345678901234568')]), OLD).ok, false);        // off-by-one id is not a match
});

test('shopSearchUrl matches the K4 contract', () => {
  assert.equal(L.shopSearchUrl({ type: 3, keyword: OLD, cursor: 0, count: 10 }), `https://shop.tiktok.com/api/v1/streamer_desktop/selection/search?search_type=3&keyword=${OLD}&origin=2&cursor=0&count=10&aid=1180`);
  assert.match(L.shopSearchUrl({ type: 2, cursor: 50 }), /search_type=2&keyword=&origin=2&cursor=50&count=50&aid=1180$/);
});

// ---- passive capture ----
const postBody = (anchors) => JSON.stringify({ post_common_info: { creation_id: 'c' }, feature_common_info_list: [{ anchors, privacy_setting_info: {} }], single_post_req_list: [] });

test('extractAnchorCapture: null without anchors; otherwise anchors + candidate ids (nested JSON included), keyed ones flagged', () => {
  assert.equal(L.extractAnchorCapture(postBody([])), null);
  assert.equal(L.extractAnchorCapture('not json'), null);
  assert.equal(L.extractAnchorCapture(JSON.stringify({ feature_common_info_list: [{}] })), null);
  const c = L.extractAnchorCapture(postBody(template()));
  assert.deepEqual(c.anchors, template());
  assert.deepEqual(c.candidates.sort(), [OLD, SELLER].sort());
  assert.deepEqual(c.keyed, [OLD]);                                // only product_id-keyed values (the top-level "id" is not)
});

test('extractAnchorCapture keeps big numeric ids exact (as strings)', () => {
  const body = `{"feature_common_info_list":[{"anchors":[{"product_id":${OLD},"x":1}]}]}`;
  const c = L.extractAnchorCapture(body);
  assert.equal(c.anchors[0].product_id, OLD);
  assert.deepEqual(c.keyed, [OLD]);
});

// ---- the REAL captured shape (TikTok Studio manual post with a cart) ----
const REAL = () => [{ type: 33, keyword: 'Nano Đồng Toàn Cầu 500ml', content: { product_id: '1730558895323973978', keyword: 'Nano Đồng Toàn Cầu 500ml', add_from: 2 } }];
const REAL_NEW = { product_id: '1731111111111111111', product_name: 'Bình giữ nhiệt 750ml' };

test('buildProductAnchors default = exactly the real captured shape (deepEqual)', () => {
  assert.deepEqual(L.buildProductAnchors({ product_id: '1730558895323973978', product_name: 'Nano Đồng Toàn Cầu 500ml' }), REAL());
  assert.deepEqual(L.buildProductAnchors(REAL_NEW), [{ type: 33, keyword: 'Bình giữ nhiệt 750ml', content: { product_id: '1731111111111111111', keyword: 'Bình giữ nhiệt 750ml', add_from: 2 } }]);
  assert.deepEqual(L.buildProductAnchors(REAL_NEW, null), L.buildProductAnchors(REAL_NEW));
  assert.deepEqual(L.buildProductAnchors(REAL_NEW, []), L.buildProductAnchors(REAL_NEW));
});

test('buildProductAnchors with the real template: id and keyword (both places) replaced, shape kept, result has the new content.product_id', () => {
  const r = L.buildProductAnchorsDetailed(REAL_NEW, REAL(), '1730558895323973978');
  assert.equal(r.fromTemplate, true);
  assert.deepEqual(r.anchors, [{ type: 33, keyword: 'Bình giữ nhiệt 750ml', content: { product_id: '1731111111111111111', keyword: 'Bình giữ nhiệt 750ml', add_from: 2 } }]);
  assert.deepEqual(r.anchors, L.buildProductAnchors(REAL_NEW));
  assert.equal(typeof r.anchors[0].content.product_id, 'string');
});

test('buildProductAnchors: bad id / name, and a template that does not contain its id, are anchor-build-failed', () => {
  const bad = (p, tpl, tid, re) => assert.throws(() => L.buildProductAnchors(p, tpl, tid), (e) => e.code === 'anchor-build-failed' && re.test(e.message), re.source);
  bad({ product_id: '12345', product_name: 'x' }, null, null, /product_id/);          // < 6 digits
  bad({ product_id: '1'.repeat(26), product_name: 'x' }, null, null, /product_id/);   // > 25 digits
  bad({ product_id: 1731111111111111111, product_name: 'x' }, null, null, /product_id/);
  bad({ product_id: '17311111a', product_name: 'x' }, null, null, /product_id/);
  bad({ product_id: '1731111111111111111', product_name: '' }, null, null, /product_name/);
  bad({ product_id: '1731111111111111111', product_name: 'x'.repeat(31) }, null, null, /30/);
  assert.equal(L.buildProductAnchors({ product_id: '1731111111111111111', product_name: 'x'.repeat(30) })[0].keyword.length, 30);
  bad(REAL_NEW, REAL(), '1739999999999999999', /not found/);
  bad(REAL_NEW, REAL(), undefined, /template_product_id/);
});

test('extractAnchorCapture on the real post body: anchors verbatim, product_id keyed + candidate', () => {
  const body = JSON.stringify({ post_common_info: { creation_id: 'c', enter_post_page_from: 2, post_type: 3 }, feature_common_info_list: [{ geofencing_regions: [], anchors: REAL(), content_check_id: '' }] });
  const c = L.extractAnchorCapture(body);
  assert.deepEqual(c.anchors, REAL());
  assert.deepEqual([c.keyed, c.candidates], [['1730558895323973978'], ['1730558895323973978']]);
});

// v1.4 stats + comments: pure request builders / parsers (studio-lib.js) against fixtures shaped like STUDIO-API.md (all ids / tokens fake).
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const S = require('../studio-lib.js');

const ITEM_LIST = {
  cursor: 2, has_more: true, enable_query: true, is_limited: false, status_code: 0, status_msg: '',
  extra: { now: 1762850000000, logid: 'LOGID', fatal_item_ids: [] }, log_pb: { impr_id: 'X' },
  item_list: [
    { item_id: '7570000000000000001', desc: 'Áo thun #tiktokshop', create_time: '1762800000', post_time: '1762800000', schedule_time: '0', duration: '23000',
      play_count: '1520', like_count: '88', comment_count: '7', share_count: '3', favorite_count: '12', is_pinned: false, in_review: false, cover_url: ['https://p16.example/c.jpg'] },
    { item_id: '7570000000000000002', desc: '', create_time: '1762700000', play_count: '40', like_count: '0', comment_count: '0', share_count: '0', favorite_count: '0', duration: '9000' },
    { item_id: 'not-an-id', desc: 'bad' },
  ],
};

test('parseItemList keeps item_id as string and reads string counters', () => {
  const r = S.parseItemList(ITEM_LIST);
  assert.equal(r.ok, true);
  assert.equal(r.items.length, 2);
  assert.deepEqual(r.items[0], { item_id: '7570000000000000001', desc: 'Áo thun #tiktokshop', create_time: 1762800000, post_time: 1762800000, schedule_time: 0, duration_ms: 23000,
    views: 1520, likes: 88, comments: 7, shares: 3, saves: 12 });
  assert.equal(r.items[1].post_time, 1762700000, 'post_time falls back to create_time');
  assert.equal(r.cursor, 2);
  assert.equal(r.hasMore, true);
});

test('parseItemList refuses error shapes', () => {
  assert.equal(S.parseItemList({ code: 500, message: 'Internal Server Error' }).ok, false);
  assert.equal(S.parseItemList({ status_code: 8, item_list: [] }).ok, false);
  assert.equal(S.parseItemList(null).ok, false);
  const empty = S.parseItemList({ status_code: 0, item_list: [], has_more: false, cursor: 0 });
  assert.equal(empty.ok, true);
  assert.deepEqual(empty.items, []);
});

test('itemListBody / commentsBody follow the verified schemas', () => {
  const b = S.itemListBody(50, 10);
  assert.equal(b.cursor, 50);
  assert.equal(b.size, 10);
  assert.deepEqual(b.query.sort_orders, [{ field_name: 'post_time', order: 2 }]);
  const c1 = S.commentsBody(20, 1000, 2000);
  assert.equal(c1.count, '20', 'count is a string');
  assert.equal('cursor' in c1, false, 'page 1 has no cursor (it would be a 500)');
  assert.deepEqual(c1.dateRange, { startDate: '1000', endDate: '2000' });
  assert.equal(S.commentsBody(20, 1, 2, 'abc').cursor, 'abc');
});

test('insight request types keep the "insigh_type" spelling and all 11 video types in ONE request', () => {
  const reqs = S.videoInsightRequests('7570000000000000001');
  assert.equal(reqs.length, 11);
  assert.ok(reqs.every((r) => r.insigh_type && r.aweme_id === '7570000000000000001'));
  const url = S.videoInsightUrl('7570000000000000001');
  assert.match(url, /^\/aweme\/v2\/data\/insight\/\?aid=1988&/);
  assert.match(url, /type_requests=%5B%7B%22insigh_type%22%3A%22video_info%22/);
  assert.equal(S.accountRequests()[0].insigh_type, 'follower_num');
});

test('parseAccountInsight: follower count and history', () => {
  const r = S.parseAccountInsight({ follower_num: { status: 0, value: 1234 }, follower_num_history: [{ status: 0, value: 1200 }, { status: 0, value: 1210 }, { status: 0, value: 1234 }], unique_viewer_num: {} });
  assert.deepEqual(r, { ok: true, followers: 1234, history: [1200, 1210, 1234] });
  assert.equal(S.parseAccountInsight({ follower_num: {} }).ok, false);
});

const INSIGHT = {
  video_info: { statistics: { play_count: 1520, digg_count: 88, comment_count: 7, share_count: 3, collect_count: 12 }, desc: 'x' },
  video_per_duration_realtime: { value: { value: 3.2641 }, is_after_7d: false },
  video_finish_rate_realtime: { value: { value: 0.02074 } },
  video_total_duration_realtime: { value: { value: 4961.5 } },
  video_new_follower_realtime: { value: { value: 4 } },
  video_traffic_source_percent_realtime: { value: { value: [{ key: 'For You', str_value: '91%', value: 0.91 }, { key: 'Personal Profile', value: 0.07 }, { key: 'Others', value: 0.02 }] } },
  video_retention_rate_realtime: { value: { list: [{ timestamp: 0, value: 1 }] } },
  item_search_terms: { value: [] },
};

test('parseVideoInsight reads watch time, finish rate, traffic and new followers', () => {
  const r = S.parseVideoInsight(INSIGHT);
  assert.equal(r.ok, true);
  assert.equal(r.avg_watch_s, 3.26);
  assert.equal(r.finish_rate, 0.0207);
  assert.equal(r.total_watch_s, 4961.5);
  assert.equal(r.new_followers, 4);
  assert.equal(r.views, 1520);
  assert.equal(r.saves, 12);
  assert.deepEqual(r.traffic[0], { key: 'For You', value: 0.91 });
  assert.equal(r.traffic.length, 3);
});

test('parseVideoInsight: a video still being processed is "empty", never zeros', () => {
  const r = S.parseVideoInsight({ video_info: {}, video_per_duration_realtime: {}, video_finish_rate_realtime: {}, item_search_terms: {} });
  assert.equal(r.ok, false);
  assert.equal(r.empty, true);
  assert.equal(S.parseVideoInsight({}).empty, true);
});

test('parseVideoInsight tolerates a {data: ...} wrapper', () => {
  assert.equal(S.parseVideoInsight({ status_code: 0, data: INSIGHT }).avg_watch_s, 3.26);
});

const COMMENTS = {
  hasMore: true, cursor: '20',
  comments: [
    { commentId: '7571000000000000003', text: 'Giá bao nhiêu vậy shop?', createTime: 1762850100, likeCount: 2, replyCount: 0, hasCreatorLiked: false,
      user: { uid: '6800000000000000001', uniqueId: 'khach_a', nickname: 'Khách A', avatarThumb: ['https://x'] }, item: { itemId: '7570000000000000001', desc: 'Áo thun', playCount: 1520 } },
    { commentId: '7571000000000000002', text: 'đẹp quá', createTime: 1762850000, likeCount: 0, replyCount: 1,
      user: { uid: '6800000000000000002', uniqueId: 'khach_b', nickname: 'B' }, item: { itemId: '7570000000000000002' } },
    { commentId: '7571000000000000001', text: 'old one', createTime: 1762840000, likeCount: 0, replyCount: 0, user: { uid: '1', uniqueId: 'c', nickname: 'C' }, item: { itemId: '7570000000000000001' } },
    { commentId: 'bad', text: '', item: {} },
  ],
};

test('parseComments maps commentsV2 rows and drops malformed ones', () => {
  const r = S.parseComments(COMMENTS);
  assert.equal(r.ok, true);
  assert.equal(r.comments.length, 3);
  assert.deepEqual(r.comments[0], { comment_id: '7571000000000000003', item_id: '7570000000000000001', text: 'Giá bao nhiêu vậy shop?', created_at: 1762850100, like_count: 2, reply_count: 0,
    author_id: '6800000000000000001', author_handle: 'khach_a', author_name: 'Khách A' });
  assert.equal(r.hasMore, true);
  assert.equal(r.cursor, '20');
  assert.equal(S.parseComments({ code: 500 }).ok, false);
});

test('takeNewComments stops at the last seen id', () => {
  const list = S.parseComments(COMMENTS).comments;
  const a = S.takeNewComments(list, '7571000000000000002');
  assert.deepEqual(a.fresh.map((c) => c.comment_id), ['7571000000000000003']);
  assert.equal(a.reachedSeen, true);
  const b = S.takeNewComments(list, '');
  assert.equal(b.fresh.length, 3);
  assert.equal(b.reachedSeen, false);
});

test('pickInsightTargets: only 3h..7d old, newest first, capped', () => {
  const now = 2000000000;
  const mk = (id, ageS) => ({ item_id: id, post_time: now - ageS });
  const items = [mk('a', 600), mk('b', 4 * 3600), mk('c', 6 * 86400), mk('d', 8 * 86400), mk('e', 2 * 86400)];
  assert.deepEqual(S.pickInsightTargets(items, now, 7, 3 * 3600, 40).map((i) => i.item_id), ['b', 'e', 'c']);
  assert.equal(S.pickInsightTargets(items, now, 7, 3 * 3600, 2).length, 2);
});

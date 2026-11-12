// Pure helpers for reading TikTok Studio numbers (see STUDIO-API.md): request builders + response parsers. No DOM, no network.
// Loaded in the page's MAIN world (globalThis.AutotokStudio) and in Node for the offline tests (module.exports).
// Everything here is READ ONLY: no builder produces a request that changes anything on TikTok.
(function (root) {
  'use strict';
  const COMMON = 'aid=1988&app_name=tiktok_creator_center&device_platform=web_pc&channel=tiktok_web';
  const DAY = 86400;

  const num = (v) => { if (v === null || v === undefined || v === '') return null; const n = Number(v); return Number.isFinite(n) ? n : null; };
  const int0 = (v) => { const n = num(v); return n === null ? 0 : Math.trunc(n); };
  const idStr = (v) => (typeof v === 'string' && /^[0-9]{5,25}$/.test(v) ? v : typeof v === 'number' && Number.isSafeInteger(v) ? String(v) : '');
  const obj = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? v : {});
  const root0 = (j) => { const o = obj(j); const d = obj(o.data); return Object.keys(d).length && !('follower_num' in o) && !('video_info' in o) && !('video_per_duration_realtime' in o) ? d : o; };

  // ---------- (a) item_list: POST, signed by the page ----------
  const itemListUrl = () => `/tiktok/creator/manage/item_list/v1/?${COMMON}`;
  const itemListBody = (cursor, size) => ({ cursor: Number(cursor) || 0, size: size || 50, query: { sort_orders: [{ field_name: 'post_time', order: 2 }], conditions: [], is_recent_posts: false } });

  // -> {ok, items[], cursor, hasMore, reason}. Counters are strings in the response; item_id must stay a string.
  function parseItemList(j) {
    const o = obj(j);
    if (!Array.isArray(o.item_list)) return { ok: false, reason: o.status_msg ? 'status:' + String(o.status_msg).slice(0, 80) : 'no-item_list', items: [], cursor: 0, hasMore: false };
    if (o.status_code !== undefined && Number(o.status_code) !== 0) return { ok: false, reason: 'status_code:' + o.status_code, items: [], cursor: 0, hasMore: false };
    const items = [];
    for (const it of o.item_list) {
      const x = obj(it);
      const item_id = idStr(x.item_id);
      if (!item_id) continue;
      items.push({
        item_id, desc: typeof x.desc === 'string' ? x.desc.slice(0, 2200) : '',
        create_time: int0(x.create_time), post_time: int0(x.post_time || x.create_time), schedule_time: int0(x.schedule_time),
        duration_ms: int0(x.duration), views: int0(x.play_count), likes: int0(x.like_count), comments: int0(x.comment_count),
        shares: int0(x.share_count), saves: int0(x.favorite_count),
      });
    }
    return { ok: true, items, cursor: int0(o.cursor), hasMore: o.has_more === true, reason: '' };
  }

  // ---------- (c) account: GET /aweme/v2/data/insight/, no signature ----------
  const insightUrl = (requests) => `/aweme/v2/data/insight/?${COMMON}&tz_offset=${tzOffset()}&type_requests=${encodeURIComponent(JSON.stringify(requests))}`;
  const tzOffset = () => { try { return -new Date().getTimezoneOffset() * 60; } catch (_) { return 25200; } };
  // The key really is spelled "insigh_type" (TikTok's typo).
  const accountRequests = () => [{ insigh_type: 'follower_num' }, { insigh_type: 'follower_num_history', days: 7, end_days: 1 }];

  // -> {ok, followers, history[number]}
  function parseAccountInsight(j) {
    const o = root0(j);
    const f = obj(o.follower_num);
    const followers = num(f.value);
    const h = Array.isArray(o.follower_num_history) ? o.follower_num_history.map((e) => num(obj(e).value)).filter((v) => v !== null) : [];
    return { ok: followers !== null, followers: followers === null ? null : Math.trunc(followers), history: h.map(Math.trunc) };
  }

  // ---------- (b) per-video insight: one combined GET with ALL types (single types come back empty) ----------
  const VIDEO_TYPES = ['video_info', 'video_view_realtime', 'video_total_duration_realtime', 'video_per_duration_realtime', 'video_finish_rate_realtime',
    'video_new_follower_realtime', 'video_traffic_source_percent_realtime', 'video_retention_rate_realtime', 'item_search_terms', 'video_new_followers', 'video_vv_history_7d'];
  const videoInsightRequests = (itemId) => VIDEO_TYPES.map((t) => ({ insigh_type: t, aweme_id: String(itemId) }));
  const videoInsightUrl = (itemId) => insightUrl(videoInsightRequests(itemId));

  const deepValue = (v) => { const a = obj(v); return a.value && typeof a.value === 'object' && !Array.isArray(a.value) ? num(a.value.value) : num(a.value); };

  // -> {ok, empty, avg_watch_s, finish_rate, total_watch_s, new_followers, views, likes, comments, shares, saves, traffic[{key,value}]}
  // empty = TikTok has no data yet ("Your video data is being processed"): the caller must not overwrite earlier numbers with it.
  function parseVideoInsight(j) {
    const o = root0(j);
    if (!Object.keys(o).length) return { ok: false, empty: true };
    const avg = deepValue(o.video_per_duration_realtime);
    const fin = deepValue(o.video_finish_rate_realtime);
    const tot = deepValue(o.video_total_duration_realtime);
    const nf = deepValue(o.video_new_follower_realtime) ?? deepValue(o.realtime_new_followers) ?? deepValue(o.video_new_followers);
    const views = deepValue(o.realtime_total_video_views);
    const st = obj(obj(o.video_info).statistics);
    let traffic = [];
    const t = obj(o.video_traffic_source_percent_realtime);
    const tv = t.value && !Array.isArray(t.value) ? t.value.value : t.value;
    if (Array.isArray(tv)) traffic = tv.map((e) => ({ key: String(obj(e).key || obj(e).str_value || '').slice(0, 40), value: num(obj(e).value) })).filter((e) => e.key && e.value !== null).slice(0, 12);
    const has = [avg, fin, tot, nf, views].some((v) => v !== null) || traffic.length > 0 || num(st.play_count) !== null;
    if (!has) return { ok: false, empty: true };
    const rnd = (v, d) => (v === null ? null : Math.round(v * 10 ** d) / 10 ** d);
    return {
      ok: true, empty: false, avg_watch_s: rnd(avg, 2), finish_rate: rnd(fin, 4), total_watch_s: rnd(tot, 1), new_followers: nf === null ? null : Math.trunc(nf),
      views: views === null ? num(st.play_count) : Math.trunc(views),
      likes: num(st.digg_count), comments: num(st.comment_count), shares: num(st.share_count), saves: num(st.collect_count), traffic,
    };
  }

  // ---------- (d) comments of the whole channel: POST commentsV2, signed by the page ----------
  const commentsUrl = () => `/tiktokstudio/api/web/commentsV2?${COMMON}`;
  // Page 1 has NO cursor (adding one to the first request gives 500); later pages pass the cursor string the response returned.
  function commentsBody(count, startDate, endDate, cursor) {
    const b = { count: String(count || 20), query: { searchConditions: [], filterConditions: [], sortOrders: [{ fieldName: 'create_time', order: 2 }] }, dateRange: { startDate: String(startDate), endDate: String(endDate) } };
    if (cursor !== undefined && cursor !== null && cursor !== '') b.cursor = String(cursor);
    return b;
  }

  // -> {ok, comments[], hasMore, cursor}
  function parseComments(j) {
    const o = obj(j);
    if (!Array.isArray(o.comments)) return { ok: false, comments: [], hasMore: false, cursor: '', reason: 'no-comments-array' };
    const comments = [];
    for (const c of o.comments) {
      const x = obj(c);
      const comment_id = idStr(x.commentId);
      const user = obj(x.user), item = obj(x.item);
      const item_id = idStr(item.itemId);
      const text = typeof x.text === 'string' ? x.text : '';
      if (!comment_id || !item_id || !text) continue;
      comments.push({
        comment_id, item_id, text: text.slice(0, 2000), created_at: int0(x.createTime), like_count: int0(x.likeCount), reply_count: int0(x.replyCount),
        author_id: idStr(user.uid), author_handle: typeof user.uniqueId === 'string' ? user.uniqueId.slice(0, 64) : '', author_name: typeof user.nickname === 'string' ? user.nickname.slice(0, 120) : '',
      });
    }
    return { ok: true, comments, hasMore: o.hasMore === true, cursor: typeof o.cursor === 'string' ? o.cursor : o.cursor == null ? '' : String(o.cursor), reason: '' };
  }

  // Which comments are new: newest first; stop at the last id already delivered. -> {fresh[], reachedSeen}
  function takeNewComments(list, lastSeenId) {
    const fresh = [];
    for (const c of list) { if (lastSeenId && c.comment_id === lastSeenId) return { fresh, reachedSeen: true }; fresh.push(c); }
    return { fresh, reachedSeen: false };
  }

  // Videos still worth an insight call: posted within `days`, not in the first `minAgeS` (TikTok has no numbers yet). Newest first, capped.
  function pickInsightTargets(items, nowS, days, minAgeS, cap) {
    return items.filter((i) => i.post_time > 0 && i.post_time <= nowS - (minAgeS || 0) && i.post_time >= nowS - days * DAY).sort((a, b) => b.post_time - a.post_time).slice(0, cap || 40);
  }

  const api = { COMMON, itemListUrl, itemListBody, parseItemList, insightUrl, accountRequests, parseAccountInsight, videoInsightRequests, videoInsightUrl, parseVideoInsight,
    commentsUrl, commentsBody, parseComments, takeNewComments, pickInsightTargets };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.AutotokStudio = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);

# TikTok Studio - endpoint nội bộ (đọc số liệu)

Khảo sát 2026-11-11, tab đã đăng nhập, chỉ đọc. Mọi gọi đều `fetch(url, {credentials:'include'})` TRONG TRANG tiktok.com
(content script / MAIN world), cùng origin `https://www.tiktok.com`. Giá trị msToken / X-Bogus / _signature / device_id / userId trong tài liệu này đều là placeholder.

Tham số chung (giống style `aid=1988` của api-main.js):
`aid=1988&app_name=tiktok_creator_center&device_platform=web_pc&channel=tiktok_web` (trang Studio còn gửi thêm
locale, region, tz_name, device_id, os, screen_*, browser_*; thử nghiệm cho thấy KHÔNG bắt buộc).

## Về chữ ký (quan trọng)
- Trang Studio có allowlist (`byted_acrawler` / webmssdk) tự vá fetch/XHR để gắn `msToken`, `X-Bogus`, `_signature` cho:
  `item_list/v1`, `commentsV2`, `multiGetFollowRelationCount`, `/api/comment/list/*`, `profile/upload`...
- Khi tôi gọi `fetch` từ console của trang (MAIN world) KHÔNG tự ký tham số vẫn chạy 200 -> chữ ký do hook của trang thêm.
  => Extension phải chạy ở **world: MAIN** (như api-main.js), KHÔNG chạy từ isolated world / service worker (có thể bị 500/403 vì thiếu chữ ký). Chưa kiểm chứng từ isolated world.
- Nhóm `aweme/v2/data/insight/` và `tiktok/v1/analytics/insights/` KHÔNG cần chữ ký (URL thật của trang không có msToken/X-Bogus).

## (a) Danh sách bài + số liệu mỗi video  [có ký, POST]
```
POST /tiktok/creator/manage/item_list/v1/?aid=1988&app_name=tiktok_creator_center&device_platform=web_pc&channel=tiktok_web
Content-Type: application/json
{"cursor":0,"size":50,"query":{"sort_orders":[{"field_name":"post_time","order":2}],"conditions":[],"is_recent_posts":false}}
```
Trang gọi lần đầu size=50 rồi size=10 với cursor=50 (cursor = offset số bài, kiểu number).
Response: `{cursor:60, has_more:true, enable_query, is_limited, status_code:0, status_msg, extra:{now,logid,fatal_item_ids}, log_pb, item_list:[...]}`
Mỗi item (số liệu là STRING):
`item_id, desc, create_time, post_time, schedule_time, duration(ms), play_count, like_count, comment_count, share_count, favorite_count (=saves), is_pinned, in_review, item_type, status, visibility, vid, cover_url[], play_addr[], download_info{}, permissions{}`
Phân trang: gửi lại `cursor` = giá trị `cursor` trả về, lặp tới `has_more=false`. size 50 ổn; item_list rất nặng (3 bài ~113KB) nên dùng size nhỏ vừa phải.
Tổng bài: hiện trên UI ("Posts 140"), không thấy field total.

## (c) Followers / số liệu tài khoản  [không ký, GET]
```
GET /aweme/v2/data/insight/?aid=1988&app_name=tiktok_creator_center&device_platform=web_pc&channel=tiktok_web&tz_offset=25200&type_requests=[{"insigh_type":"follower_num"},{"insigh_type":"unique_viewer_num","range":1}]
```
(chú ý tên khóa là `insigh_type` - thiếu chữ t - đúng như TikTok.) Response: `follower_num:{status,value:<number>}`, `unique_viewer_num:{status}`.
Chuỗi lịch sử (mỗi phần tử `{status,value}`, 1 phần tử/ngày):
`{"insigh_type":"follower_num_history","days":7,"end_days":1}` -> `follower_num_history[]`; tương tự `vv_history`, `pv_history`, `like_history`, `comment_history`, `share_history`, `reached_audience_history`.
`{"insigh_type":"vv_traffic_source","days":7,"end_days":1}` -> `video_page_percent:{value:[{key,str_value,value}]}` (nguồn truy cập cấp tài khoản).
Response luôn có sẵn cả loạt khóa rỗng (`object`) kể cả loại không hỏi; chỉ khóa tương ứng loại hỏi mới có dữ liệu.
Khác: `GET /tiktokstudio/api/web/user` (profile, thêm `?needProfileBio=true`), `GET /tiktokstudio/api/web/relation/multiGetFollowRelationCount?userId=<uid>` (có ký), `GET /tiktok/v1/analytics/insights/?type_requests=[{"insight_type":82,"data_date_range":1}]&time_offset=25200&is_dark_mode=false` (thẻ tổng quan, chưa giải mã).

## (b) Analytics mỗi video  [không ký, GET]
Trang `/tiktokstudio/analytics/<item_id>/overview` gọi 1 request gộp. Chỉ cần gửi đủ các type trong CÙNG 1 request (gửi lẻ từng type cho nhóm *_realtime trả rỗng):
```
GET /aweme/v2/data/insight/?aid=1988&app_name=tiktok_creator_center&device_platform=web_pc&channel=tiktok_web&tz_offset=25200&type_requests=[
 {"insigh_type":"video_info","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"video_view_realtime","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"video_total_duration_realtime","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"video_per_duration_realtime","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"video_finish_rate_realtime","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"video_new_follower_realtime","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"video_traffic_source_percent_realtime","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"video_retention_rate_realtime","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"item_search_terms","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"video_new_followers","aweme_id":"<ITEM_ID>"},
 {"insigh_type":"video_vv_history_7d","aweme_id":"<ITEM_ID>"}]
```
(JSON mảng phải URL-encode.) Các khóa trong response (đã kiểm chứng):
- `video_info.statistics{play_count,digg_count(like),comment_count,share_count,collect_count(saves)}` (kiểu number) + nhiều field khác (author, desc, create_time...).
- `video_per_duration_realtime.value.value` = average watch time (giây, vd 3.26); `realtime_average_watch_time_history.list[{key:<epoch>,value}]`.
- `video_finish_rate_realtime.value.value` = tỉ lệ xem hết (0.0207 = 2.1%); `realtime_finish_rate_history`.
- `video_total_duration_realtime.value.value` = tổng thời gian xem (giây); `realtime_total_play_time_history`.
- `realtime_total_video_views.value.value` (+ `realtime_video_view_history.list`), `realtime_new_followers.value.value` / `video_new_followers.value`.
- `video_traffic_source_percent_realtime.value.value[{key:"For You"|"Personal Profile"|"Others"...,str_value,value}]` (tỉ lệ 0-1).
- `video_retention_rate_realtime.value.list[{timestamp(ms),value}]` (đường giữ chân).
- `item_search_terms.value[{key,str_value,value}]`.
- `video_like_distribution_realtime.list[{timestamp,value}]`, `video_vv_history_7d[{value}]` (7 ngày đầu).
Mọi khóa có thêm `is_after_7d`, `is_data_delay`, `value_compare_previous_day`. Video mới (< ~vài giờ) trả rỗng/0 ("Your video data is being processed").
Thay thế: `GET /tiktok/v1/analytics/insights/?type_requests=[{"insight_type":91,"item_id":"<ID>","new_feature":1}]&time_offset=25200&is_dark_mode=false` và `GET /tiktok/v1/creator/quality_advisor/get_report_detail?item_id=<ID>` - cả hai trả chỉ `status_code:0` (không có dữ liệu) khi tôi gọi cho 2 video; bỏ qua.

## (d) Bình luận  [có ký, POST]
```
POST /tiktokstudio/api/web/commentsV2?aid=1988&app_name=tiktok_creator_center&device_platform=web_pc&channel=tiktok_web
Content-Type: application/json
{"count":"20","query":{"searchConditions":[],"filterConditions":[],"sortOrders":[{"fieldName":"create_time","order":2}]},"dateRange":{"startDate":"<epoch s>","endDate":"<epoch s>"}}
```
Response: `{hasMore:bool, cursor:"<string>", comments:[{commentId, text, textExtra[], createTime(epoch s, number), likeCount(number), replyCount(number), hasCreatorLiked, user:{uid, uniqueId, nickname, avatarThumb[]}, item:{itemId, desc, playCount, commentCount, likeCount, shareCount, favoriteCount, duration, createTime, postTime, coverUrl[], ...}}]}`
Ghi chú:
- Đây là comment của TOÀN KÊNH (mỗi comment kèm `item.itemId`); lọc theo video bằng cách lọc `item.itemId` phía client. Các thử `filterConditions` với item_id/aweme_id đoán -> 500 (chưa biết schema; bộ lọc UI: search, sortBy, repliedBy, postedBy, dateRange, followerCount).
- Trang gửi trang đầu KHÔNG có `cursor`. Thêm `cursor` vào body (cả "0", 0) -> 500; trang kế dùng giá trị `cursor` trả về (chưa kiểm chứng vì tài khoản chỉ có 1 comment trong khoảng; `hasMore:false`). `count` bắt buộc, kiểu string. `dateRange` bắt buộc.
- Danh sách trả về chỉ comment top-level; trả lời con: `GET /api/comment/list/reply/?aid=1988&comment_id=<cid>&item_id=<iid>&cursor=0&count=20` -> `{comments:[], cursor, has_more...}` (200, không ký trong thử nghiệm; tài khoản không có reply nên chưa thấy shape đầy đủ).
- GET lên `commentsV2` trả HTML (trang SPA), không phải JSON - phải POST.

## Rate / lưu ý
- Chưa thấy 429; vẫn nên giãn >= 1-2 s giữa các gọi, tuần tự, và batch nhiều type trong 1 request insight.
- 500 `{"code":500,"message":"Internal Server Error"}` = body sai schema (không phải lỗi mạng).
- Tên khóa `insigh_type` (insight cũ aweme/v2) vs `insight_type` (tiktok/v1/analytics/insights) - đừng nhầm.
- Chưa thử từ isolated world/service worker; item_list và commentsV2 phụ thuộc hook ký của trang.

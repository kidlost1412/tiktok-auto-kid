# TikTok Auto Kid backend <-> Chrome extension protocol (v1)

Binding contract between the TikTok Auto Kid backend (Laravel, `routes/fork-chrome-ext.php`, `/api/ext/*`)
and the TikTok Auto Kid Chrome extension.

- Protocol version: **1**. The backend accepts the range `[PROTOCOL_MIN, PROTOCOL_MAX] = [1, 1]`.
- Extension origin (the only CORS origin): `chrome-extension://poffpbdhahodnkoandkagilkbhaipolo`.
- All bodies are JSON (`Content-Type: application/json; charset=utf-8`), UTF-8, times are UTC.

## 1. Headers

| Header | When | Value |
| --- | --- | --- |
| `Authorization` | every `/api/ext/*` call except `pair` | `Bearer <token>` from pairing |
| `X-Autotok-Protocol` | every `/api/ext/*` call | `1` (integer). Missing = 0 = unsupported |
| `X-Requested-With` | every POST | `autotok` (the backend's CSRF guard refuses POSTs without it, 403) |
| `Range` | `GET /api/ext/video` | `bytes=<start>-<end>` |

CORS: the backend answers preflights and adds `Access-Control-Allow-Origin` only for the
extension origin and only on the extension endpoints (section 3). Allowed request headers:
`Authorization, Content-Type, X-Requested-With, X-Autotok-Protocol, Range`. Exposed response
headers: `Content-Range, Content-Length, Accept-Ranges`. The GUI-only endpoints (section 4) never
get CORS headers and refuse any request that carries an `Origin` header (403).

## 2. Errors

Extension endpoints answer errors as `{"ok": false, "error": "<code>", "message": "<Vietnamese text>"}`.

| HTTP | `error` | Meaning / what the extension does |
| --- | --- | --- |
| 400 | `bad_request` | malformed body or field. Fix the client; never retry blindly |
| 401 | `unauthorized` | token missing, unknown, or the client was removed in the GUI. Show "Cần ghép nối lại", stop polling |
| 403 | `bad_nonce` | `nonce` or `claim_token` does not match the job. Drop the job locally, never retry |
| 403 | `bad_code` | pairing code wrong; body has `tries_left` |
| 403 | `csrf` | missing `X-Requested-With` (body uses FastAPI `detail`) |
| 404 | `unknown_job` | no such job id. Keep the result locally for diagnosis, drop the job |
| 409 | `need_reload` | protocol out of range. Body has `need_reload: true`. See section 7 |
| 409 | `identity_conflict` | another active Chrome profile reports the same TikTok user. No jobs until the owner removes one in the GUI |
| 409 | `no_identity` | the last `hello` had no TikTok identity (not logged in). Log in, send `hello` again |
| 410 | `no_code` | no pairing code active (none issued, expired, used, or burnt after 5 wrong tries) |
| 500 | `persist_failed` | the backend could not write durably. For `authorize`: NOT granted, never send |

## 3. Extension endpoints (CORS for the extension origin)

### 3.1 `POST /api/ext/pair` (no bearer)
Request: `{"code": "123456", "label": "Chrome Vườn", "ext_version": "1.0.0", "protocol": 1}`
Response 200: `{"ok": true, "client_id": 3, "token": "<43 url-safe chars>"}`. The token is shown
once; the backend stores only `sha256(token)`. The extension keeps it in `chrome.storage.local`.
Errors: 403 `bad_code` (`tries_left`), 410 `no_code`, 409 `need_reload`, 400 `bad_request`.

### 3.2 `POST /api/ext/hello`
Send at startup, right after pairing, after every TikTok login change, and at least every 60 s.
Request: `{"protocol": 1, "ext_version": "1.0.0", "identity": {"username": "mt.tri.2.pin", "user_id": "7012345678901234567"} | null}`.
`identity` comes from the passport endpoint only (`data.username`, `data.user_id_str`, plus optional `avatar_url` from v1.3, https only; the app downloads it); null when
not logged in or unknown.
Response 200:
```json
{"ok": true, "client_id": 3, "protocol_min": 1, "protocol_max": 1, "need_reload": false,
 "message": "", "server_time": "2026-10-27T09:00:00Z",
 "account": {"id": 5, "username": "mt.tri.2.pin", "publisher": "chrome"} ,
 "conflict": false}
```
`account` is the backend account bound to this identity (`accounts.chrome_user_id == user_id`), or
null. `conflict` true = another client seen in the last 90 s reports the same `user_id`.
With an unsupported protocol the answer is still 200 with `need_reload: true` and a Vietnamese
`message`; the backend records the version so the GUI can show the reminder.

### 3.3 `GET /api/ext/next?wait=<0..25>`
Long poll (seconds, capped at 25). Every call counts as "seen" for readiness. Returns the oldest
`queued` job for the account bound to this client's last reported `user_id`.
- 200: the job (below). The job is now `claimed` by this client; it is never served again (no
  re-issue). The extension must keep it in durable storage and resume it after a restart.
- 204: nothing to do.
- 409 `need_reload` / `identity_conflict` / `no_identity`.

Job object:
```json
{"id": "ej_3f2a...", "nonce": "<32 hex>", "claim_token": "<32 hex>", "mode": "post", "attempt": 1,
 "caption": "xin chào #tag", "visibility": "public", "visibility_type": 0,
 "schedule_time": "2026-10-30T13:30:00Z", "schedule_unix": 1793367000,
 "options": {"allow_comment": 1, "allow_duet": 0, "allow_stitch": 0, "ai_label": 0},
 "expect_account": "mt.tri.2.pin", "expect_user_id": "7012345678901234567",
 "video": {"name": "kid-....mp4", "size": 20971520, "type": "video/mp4"},
 "limits": {"claim_within_s": 120, "heartbeat_every_s": 60, "stale_after_s": 120,
            "upload_within_s": 900, "result_within_s": 180,
            "schedule_min_ahead_s": 900, "schedule_max_shift_s": 600}}
```
- `schedule_time`/`schedule_unix` null = immediate post. Otherwise TikTok-native schedule: put
  `schedule_unix` in `feature_common_info_list[0].schedule_time`, except that when, at publish time,
  it is less than 15 min (`schedule_min_ahead_s`) away, use `now + 15 min` if that moves it by at
  most 10 min (`schedule_max_shift_s`), else fail definitely BEFORE authorize
  (`reason: "schedule-expired"`, text "Tải video quá lâu, giờ hẹn không còn hợp lệ — hãy chọn giờ mới").
  Never turn a scheduled job into an immediate post.
- `options` map 1:1 to `privacy_setting_info.allow_comment/allow_duet/allow_stitch` (0/1) and
  `ai_label: 1` -> `aigc_info: {"aigc_label_type": 1}` (absent when 0), exactly as
  `autotok/uploader.py::_payload`. `visibility_type` 0 = public, 1 = private. Friends visibility and
  private + schedule never reach the extension (refused by the backend before dispatch).
- `expect_account` + `expect_user_id`: the strict passport identity check before upload and
  before publish. Mismatch -> definite failure, nothing sent.

### 3.4 `GET /api/ext/video/meta?id=<job>` and `GET /api/ext/video?id=<job>`
Only for a job claimed by this client, in state
`claimed`, `uploading` or `ready`. Meta: `{"name", "size", "type"}`. Video: 200 full or 206 with
`Range` (`Content-Range: bytes s-e/size`), 416 for an unsatisfiable range. Read-only copy in the
backend library.

### 3.5 `POST /api/ext/progress` (heartbeat)
Request: `{"id", "nonce", "claim_token", "phase": "upload", "msg": "...", "pct": 40, "extra": {...}}`.
At least every 60 s while the job runs. Effects: `heartbeat_at = now`; `claimed -> uploading` on
the first progress; `phase: "ready"` moves `uploading|claimed -> ready` (upload finished and
committed, identity re-checked, body built). The extension MUST await the reply to the
`phase: "ready"` progress (`state: "ready"`) before calling `authorize`; the state change is
committed before that reply, so an immediate `authorize` sees it.
Response: `{"ok": true, "state": "uploading"}`. If the job was revoked:
`{"ok": false, "state": "revoked", "cancelled": true}` -> stop, close the tab, do NOT authorize, send
a `failed` result if anything is left to report. Progress for an `authorized` job is accepted
(`ok: true`) but does not extend the result deadline.

### 3.6 `POST /api/ext/authorize`
Request:
```json
{"id": "ej_...", "nonce": "...", "claim_token": "...",
 "body_sha256": "<64 lowercase hex>", "creation_id": "<creation id in the body>",
 "visibility_type": 0, "schedule_time": 1793367000,
 "identity": {"username": "mt.tri.2.pin", "user_id": "7012345678901234567"}}
```
`schedule_time` = the exact unix seconds in the body, or null for an immediate post. `identity` =
the passport identity just re-checked.
Granted only by ONE conditional database update, durable before the reply:
`state='ready' AND claim_token AND nonce match AND attempt = current attempt of the parent AND
parent.status='waiting_ext'`, plus: protocol in range, no identity conflict, `identity.user_id ==
expect_user_id`, `visibility_type` equal to the job's, `schedule_time` null for an immediate job,
and for a scheduled job `schedule_unix <= schedule_time <= schedule_unix + 600` and
`schedule_time >= now + 15 min - 60 s`.
Response 200 `{"ok": true}` or `{"ok": false, "reason": "<code>"}` with reason one of
`not-ready`, `already-authorized`, `revoked`, `terminal`, `superseded`, `bad-binding`,
`identity-mismatch`, `visibility-mismatch`, `schedule-mismatch`, `need-reload`, `identity-conflict`.
500 `persist_failed` = not granted. Only `ok: true` allows the single publish XHR. Authorization is
one-time and never undone; after it the job is never re-run.

### 3.7 `POST /api/ext/result`
Request (fields the extension knows; unknown fields are ignored):
```json
{"id", "nonce", "claim_token",
 "outcome": "posted" | "rejected" | "uncertain" | "failed",
 "definite": true, "not_sent": true, "reason": "status_code", "detail": "...",
 "http": 200, "status_code": 0, "status_msg": "", "item_id": "7701245450858351893",
 "creation_id": "...", "video_id": "v0...", "schedule_time": 1793367000,
 "response": {"...": "sanitized TikTok answer, <= 8 KiB"}, "elapsed_ms": 9876}
```
`schedule_time` = the unix seconds actually submitted (null for immediate). `not_sent` (alias
`notSent`) true = the extension knows nothing reached the publish endpoint.
Response 200 `{"ok": true, "duplicate": false, "state": "posted"}`. The first result wins and is
stored durably; later ones return `duplicate: true` and change nothing. A result is accepted from
any paired client with the right `nonce` + `claim_token`, whatever its protocol version (skew), in
every state, including after a backend restart and after the result deadline (late result).
Errors: 404 `unknown_job`, 403 `bad_nonce`. On network failure, retry with backoff until 200, 404 or 403.

Mapping to the app's job outcome:

| Child state before | `outcome` | Child state after | Parent (scheduled job) |
| --- | --- | --- | --- |
| authorized | posted | posted | succeeded (post id kept, link from `item_id`) |
| authorized | rejected | rejected | failed, definite |
| authorized | uncertain, or failed without `not_sent` | uncertain | failed + `publish_uncertain` |
| authorized | failed with `not_sent: true` | failed | failed, definite |
| claimed/uploading/ready | failed / rejected | failed | failed, definite (nothing sent) |
| claimed/uploading/ready | posted / uncertain (gate bypassed) | posted / uncertain | as for authorized; logged as an anomaly |
| uncertain (result deadline missed) | any | the real outcome | late result: see section 5 |
| revoked, posted, rejected, failed | any | unchanged | duplicate / anomaly recorded in history |

### 3.8 `POST /api/ext/cancel`
Request: `{"id", "nonce", "claim_token", "reason": "..."}`. Pre-authorization: the job is revoked
(`revoked`) and the parent fails definitely. Authorized: nothing changes, `cancel_recorded: true`.
Response `{"ok": true, "state": "revoked" | "authorized" | <terminal state>, "cancel_recorded": bool}`.

### 3.9 `GET /api/ext/job_state?id=<job>`
Response `{"ok": true, "state": "...", "authorized": bool}`. 404 `unknown_job`.

## 4. GUI-only endpoints (local app; no CORS; refused with 403 when an `Origin` header is present)

- `POST /api/ext/pair-code` -> `{"code": "123456", "expires_at": "...Z", "valid_s": 300}`. A new code
  replaces the previous one. Single use, 5 min, at most 5 wrong tries, then burnt. Kept in API
  memory only (a restart forgets it).
- `GET /api/ext/clients` -> `[{"id", "label", "tiktok_username", "tiktok_user_id", "ext_version",
  "protocol", "need_reload", "last_seen_at", "online", "conflict", "has_identity", "status",
  "created_at"}]` (`online` = seen in the last 90 s; removed clients are not listed). `status` is one
  of `ok | need_reload | offline | no_identity | conflict`. A client with `no_identity` never gets
  work (`/next` answers 409 `no_identity`) and the backend logs a warning on each such `hello`.
- `PATCH /api/ext/clients/{id} {"chrome_profile_dir": "Profile 1"}` -> 200
  `{"ok": true, "id", "chrome_profile_dir"}`. The Chrome profile folder name (as in
  `%LOCALAPPDATA%\Google\Chrome\User Data\<dir>`), matching
  `^(Default|Profile \d+|[A-Za-z0-9 _.-]{1,64})$`, no path separators, no leading/trailing space or
  dot; `""`/null clears it. 400 `bad_request` if invalid, 404 `unknown_client`. `GET /api/ext/clients`
  also returns `chrome_profile_dir` and `last_launch_at`. An extension cannot read its own profile
  folder, so only the GUI sets it (there is no `hello` field for it).
- `DELETE /api/ext/clients/{id}` -> 204. The token stops working at once (401). A job the client
  already claimed keeps its deadlines (and its result is still accepted from any paired client
  that holds the nonce and claim token).
- `POST /api/accounts/from-chrome {"client_id": 3}` -> 201 `AccountRead`. Creates an account with
  `publisher='chrome'`, `chrome_user_id` = the client's `user_id`, username = the client's TikTok
  username, no cookie file (`cookie_path` = ""). 409 if an account already has that username or
  that `chrome_user_id`; 409 if the client is offline, has no identity, or is in conflict.
- `PATCH /api/accounts/{id} {"publisher": "chrome", "client_id": 3, "confirm_username_mismatch": false}`
  binds the account to the client's TikTok user. Cookies are untouched. Needs the client online
  with an identity and no conflict; if the TikTok username differs from the account username,
  needs `confirm_username_mismatch: true` (else 409). `{"publisher": "cookies"}` switches back
  (409 if the account has no cookie file, or has `pending_ext`/`waiting_ext` jobs).
- `AccountRead` gains `publisher`, `chrome_user_id`, `ready`, `ready_reason`:
  cookies -> `ready = has_valid_session`, reason `ok` | `no_session`;
  chrome -> ready when a bound client was seen < 90 s ago, protocol in range, no conflict; reason
  `ok` | `chrome_unbound` | `chrome_offline` | `chrome_need_reload` | `chrome_conflict`.
  `has_valid_session` keeps its meaning (cookie session only).
- `/health` gains `"chrome_ext": 1, "ext_protocol_min": 1, "ext_protocol_max": 1`.

## 5. States

Child job (`extension_jobs.state`):
`queued -> claimed -> uploading -> ready -> authorized -> posted | rejected | uncertain`;
terminal side exits `revoked` (pre-authorization cancel or missed deadline) and `failed`
(definite, nothing sent). `uncertain` can still become `posted|rejected|failed` when a late result
arrives. Terminal: `posted, rejected, uncertain, revoked, failed`.

Parent (`scheduled_uploads.status`) for accounts with `publisher='chrome'`:
created (schedule, desktop submit, retry) directly as `pending_ext` `-> waiting_ext` (when due and the
account is free: attempt + 1 and the child created in the same transaction) `-> succeeded | failed`.
A Chrome account's job is never `pending` or `running`: old backend versions claim only `pending`,
a leftover `pending` row is moved to `pending_ext` by reconcile, and a database trigger
(`tr_chrome_job_never_running`, schema v4) silently refuses any update of such a row to `running`,
whatever version runs (rollback safety).

Deadlines (checked by `reconcile_ext` on every scheduler tick, at startup, on `/next` and after
each result):
- queued and not claimed 120 s after creation -> revoke -> parent failed "Chrome chưa sẵn sàng".
- claimed/uploading/ready: no heartbeat for 120 s, or 15 min since claim -> revoke -> parent failed
  definite.
- authorized and no result 180 s after authorization -> child `uncertain` -> parent failed +
  `publish_uncertain` (check TikTok before retrying). Never definite.
- A late result for the same attempt fixes the parent (posted -> succeeded with post id; rejected /
  not-sent -> failed definite; the history keeps `prior_uncertain`). A late success for a
  newer attempt that cannot have been sent yet (no child, or a child in queued..ready) withdraws it
  (the child is revoked by the same conditional update authorize races against) and marks the
  parent succeeded with the post id, so a confirmed retry never posts twice; if the newer attempt is
  already authorized, it is left alone and the late success is written to the history with its
  post id and a warning. A late success for a deleted parent goes to the history the same way.

Opening Chrome: when a child is `queued` and no client of its TikTok user is online, the backend
starts `chrome.exe --profile-directory="<dir>" --no-first-run` minimized without focus
(SW_SHOWMINNOACTIVE) and detached, at most once per child and once per 3 min per profile. chrome.exe
comes from `AUTOTOK_BROWSER_PATH` or the standard locations; `AUTOTOK_CHROME_LAUNCH=off` disables it.
After a launch the claim deadline is 180 s from the launch. Without a known profile the job fails at
the claim deadline with "Chrome chưa mở và chưa biết profile Chrome — mở Chrome hoặc chọn profile
trong Kết nối Chrome" (without chrome.exe: "Chrome chưa mở và không tìm thấy chrome.exe trên máy —
hãy mở Chrome"). All of this happens before any claim, so the publish gate is unchanged. The
columns it needs (`extension_clients.chrome_profile_dir`, `last_launch_at`,
`extension_jobs.launched_at`) come with database schema 5.

Per account: at most one non-terminal child (partial unique index). Further jobs wait in
`pending_ext`, FIFO by `scheduled_for`, then id. Other accounts are independent.

## 6. Pairing flow

1. Owner clicks "Kết nối Chrome" in the app; the GUI calls `POST /api/ext/pair-code` and shows the 6 digits.
2. Owner types them in the extension popup; the extension calls `POST /api/ext/pair`.
3. The extension stores `token` + `client_id`, calls `hello` with its passport identity.
4. The GUI lists the client (`GET /api/ext/clients`) and offers "Tạo tài khoản từ Chrome"
   (`from-chrome`) or "Đăng qua Chrome" on an existing account (`PATCH publisher`).

## 7. Version skew and `need_reload`

- Every call carries `X-Autotok-Protocol`; `hello`/`pair` also carry `protocol` in the body.
- Out of range: `hello` answers 200 with `need_reload: true` and
  `message: "Cần tải lại tiện ích (chrome://extensions → ⟳)"`; `next` and `authorize` are refused
  (409 `need_reload` / reason `need-reload`); `pair` is refused (409).
- Still accepted during skew: `progress`, `result`, `cancel`, `job_state`, `video*` for jobs the
  client already holds, so an authorized job in flight still reports its outcome.
- The popup shows the message; the GUI shows the same reminder when a client's `need_reload` is true.

## 8. Not in v1

- Direct immediate uploads (`/api/uploads/*`) answer 409 "Tài khoản đăng qua Chrome — dùng lịch/hẹn"
  for chrome accounts; use schedules / the desktop bridge.
- YouTube sources for chrome accounts are refused definitely at dispatch (nothing sent).
- The per-job `proxy` option is ignored on the Chrome path (Chrome uses its own network).
- No backend endpoint for the extension self-test ("Tự kiểm"); it only checks the identity, locally.
- Schedule window: the extension enforces TikTok's 15 min..30 days; the backend refuses before
  dispatch anything outside the app's own rules (private + schedule, beyond 10 days, or already less
  than 5 min away, i.e. no longer fixable by the 10-min shift).

## 9. Deviations from the plan contracts (C1-C6)

- C1 authorize: the conditional update also requires the protocol, identity, visibility and
  schedule checks above (stricter, never looser).
- No job re-issue (the prototype re-issued stale pre-authorization jobs): a stale job is revoked
  and fails definitely instead. Simpler; the extension resumes from its own storage.
- C4 `cookie_path`: sentinel `""` for chrome-only accounts, no table rebuild.
- C4 PATCH to chrome takes an explicit `client_id`, and a username mismatch needs
  `confirm_username_mismatch` (the account username may be a label, not the TikTok handle).
- Publisher is fixed when the job is created (`pending` for cookies, `pending_ext` for Chrome).
  Switching an account's publisher (either way) is refused with 409 while the account has jobs in
  `pending`, `running`, `pending_ext`, `waiting_ext` or an unfinished child; rows are never moved
  between publishers. A `pending_ext` job whose account is not Chrome anymore (only possible through
  an older version) fails definitely, nothing sent.

## 10. K4 cart (TikTok Shop product on the video) -- optional additions, protocol stays v1

Every field and endpoint below is optional: an app or extension without them keeps working as in sections 1-9. Extension
version 1.1.0 (adds the host permission `https://shop.tiktok.com/*`). Rule above all: a wrong product is worse than none,
so every doubt stops the job BEFORE any upload or publish (`not_sent`).

### 10.1 Job field `product` (in the `/api/ext/next` job)
`"product": null` or
`{"product_id": "7598765432109876543", "product_name": "<= 30 chars", "anchor_template": [ ...anchors... ] | null, "template_product_id": "7512345678901234567"}`.
`template_product_id` = the product the manual post behind `anchor_template` was captured from. All ids are digit STRINGS
(never numbers). `product` absent/null = the post goes out exactly as before (`anchors: []`, byte-identical body).

The cart anchor is the shape of a real Studio post: `[{"type":33,"keyword":<name>,"content":{"product_id":<id>,"keyword":<name>,"add_from":2}}]` (keyword = name shown on the video, <= 30 chars). It is built by default. `anchor_template` is OPTIONAL: when present (with `template_product_id`) it is used instead, rewritten by value, so a changed TikTok shape is followed; the result must still hold the new `product_id`.

With a `product` (modes `post` and `intercept`; `selftest` ignores it) the extension, after the identity check and before the
upload, does in this order and stops at the first failure:
1. Build (pure, `lib.buildProductAnchors(product, template?, templateProductId?)`): id must be a string matching `^[0-9]{6,25}$`, name non-empty and <= 30 chars; with a template: replaces by VALUE (key-agnostic: `product_id`, the `keyword`/title/name next to it, nested JSON strings too) and throws if the template id is absent or anything old remains.
2. Availability: `GET https://shop.tiktok.com/api/v1/streamer_desktop/selection/search?search_type=3&keyword=<product_id>&origin=2&cursor=0&count=10&aid=1180` with cookies (then `search_type=2` = showcase). The exact `product_id` must be in `data.products` and `stock_num > 0`.
3. The anchors go to `feature_common_info_list[0].anchors`. A last guard refuses to authorize a `product` job whose body has no anchors.

Failure results (all `outcome:"failed", definite:true, not_sent:true`, nothing uploaded):

| `reason` | Meaning |
| --- | --- |
| `product-unavailable` | not found in my shop / showcase, or `stock_num <= 0` (detail: `not-found`, `out-of-stock`, `stock-unknown`) |
| ~~`no-anchor-template`~~ | no longer produced: without a template the default real shape is used |
| `anchor-build-failed` | bad product_id format, empty / > 30 chars name, bad `product` object, or an unusable template (id not found in it, old id/name left over) |
| `product-check-failed` | NOT in the original K4 list: the shop API could not be read (network, HTTP != 200, `code != 0`). Nothing was proven either way, so nothing is posted; the app may retry later instead of pausing the product |

### 10.2 `GET /api/ext/tasks`
Same auth/headers as `/next`, polled in the same loop right before each `/next` AND every ~4 s while a sync is running
(so a newer request replaces it at once). Response `{"sync_products": "<request_id>" | null}`. 404 (old app) is ignored.
Every click of "Lấy sản phẩm từ shop" makes the app issue a NEW `request_id`; the app stops offering it after 10 minutes.
- A NEW `request_id` is started immediately: it abandons a still-running sync of an older id (its tab is closed, its nonce dies)
  and its retry budget starts at zero.
- The SAME `request_id` is tried at most 3 times, at least 60 s apart, and never again after one source was delivered.
  When the budget is spent the extension reports `gave-up` once (below).

### 10.2b `POST /api/ext/sync_status` (failure report, optional)
`{"request_id": "...", "ok": false, "reason": "sync-timeout" | "tab-closed" | "identity-unknown" | "open-window-failed" | "gave-up" | ...}`.
Sent when a sync attempt ends without delivering any source. The app stores the reason only if `request_id` is still the pending
request of the account bound to this Chrome, and shows it on the Giỏ hàng page. Response `{"ok": true, "recorded": <bool>}`.
An old app (404) is ignored.

### 10.3 Product sync and `POST /api/ext/products`
On `sync_products` the extension opens a (minimized) Studio tab `#autotok=sync-<request_id>`, armed in `block` mode (no
`/project/post/` can leave it), identifies the account with the passport endpoint and reads, for `search_type=3` (`my_shop`)
then `2` (`showcase`): `keyword=` empty, `count=50`, `cursor` = offset 0, 50, 100, ... until a page has < 50 products or the
offset reaches `data.total`, at most 40 pages. Then, once per COMPLETE source:
```json
{"request_id": "...", "user_id": "7000000000000000001", "username": "me.user", "source": "my_shop" | "showcase",
 "products": [{"product_id": "7600000000000000001", "title": "...", "price": "99.000đ", "cover_url": "https://...", "stock_num": 3, "stock_status": 1}],
 "complete": true}
```
A source that failed or hit the 40 page cap is NOT sent (the app would mark everything missing). A showcase with no products
is sent as an empty list. The app answers 409 when `user_id`/`username` do not match the client's account; the extension logs
it and does not retry that call. `price` = `format_available_price`; `cover_url` = `cover.thumb_url_list[0]`; ids are exact
strings (numbers of 16+ digits are read from the source text, not through a lossy float).

### 10.4 `POST /api/ext/anchor_template` (passive capture)
`{"user_id", "username", "product_id", "anchors": [...verbatim...], "captured_at": "<ISO 8601 UTC>"}`.
Sent when the OWNER posts a video by hand in TikTok Studio and the `/project/post/` request has non-empty
`feature_common_info_list[*].anchors`. hook-main.js only observes: the request goes out first, unchanged, and the body is read
afterwards in a separate task; nothing is blocked, modified, delayed or replayed, and the extension's own (armed) publishes are
never captured. `user_id`/`username` come from the passport endpoint (queried by the service worker), never from the page.
`product_id` is the id among those inside the anchors that the shop API confirms as a product (search by keyword, exact match);
if none/several are confirmed it falls back to the single value under a `product_id`-like key; if still unclear (or the two
disagree) nothing is sent and a warning is logged. The app keeps the latest template per account together with `product_id`.
The anchors are sent verbatim except that integer literals of 16+ digits become strings (JSON.parse would corrupt them).

### 10.5 Why the manifest only gains `https://shop.tiktok.com/*`
Page-context (MAIN world) fetches are governed by CORS, not by `host_permissions`. The shop GETs are tried from the Studio page
first (cookies of the tab); if the browser refuses them, the same GET (exact host + path, https, GET only, only for the active
job/sync tab) is relayed content.js -> service worker, which is not subject to CORS because of the new host permission. The
same permission serves the product confirmation of 10.4. Nothing else is added: no content script matches shop.tiktok.com.

## 11. Per-product cover and window behaviour (extension 1.4.2) -- optional, protocol stays v1

### 11.1 Job field `options.cover` and `GET /api/ext/cover?id=<job>`
Present only when the post's product has a custom cover (modes "fixed" / "random" in the app):
`"options": {..., "cover": {"url": "/api/ext/cover?id=ej_...", "name": "cover.jpg", "mime": "image/jpeg", "size": 123456, "sha256": "<64 hex>", "field": "cover_uri"}}`.
The cover is a JPEG <= 5 MB, served with the same rules as `/api/ext/video` (claiming client, job running). The extension downloads it
(size + sha256 checked), uploads it to TikTok through the same VOD pipeline as the video with `FileType=image`, and puts the resulting
uri into `single_post_req_list[0].single_post_feature_info[<field>]`. Jobs without `options.cover` are byte-identical to before.

**Never fatal.** Any problem (download, checksum, upload, bad meta) only drops the cover: the post goes out with TikTok's default
cover (`poster_delay: 0`, first frame) and the result carries `cover_status: "failed"` + `cover_warning: "<reason>"`. A successful
upload reports `cover_status: "applied"`. The body field name (`field`, default `cover_uri`) is NOT verified against a real TikTok post
yet; if TikTok ignores it the post simply has the default cover.

### 11.2 Work windows never steal focus
Job / sync / collection windows follow `windowStrategy`. A `tab` strategy with no normal window open (Chrome started in the background)
uses a minimized, unfocused window instead of letting `tabs.create` open a visible one; a minimized window that came up in the normal
state is minimized again. The extension closes what it opened.

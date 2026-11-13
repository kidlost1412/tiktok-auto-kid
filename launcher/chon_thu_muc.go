package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"sync/atomic"
	"time"
)

// Hộp chọn thư mục gốc Windows, mở từ trang "Kho riêng" của app (trình duyệt không trả được đường dẫn thật).
// POST /api/chon-thu-muc, cần X-TTA-Token như /api/restart. Body JSON tuỳ chọn: {"tieu_de": "...", "bat_dau": "<thư mục mở đầu>"}.
// Trả {"ok":true,"duong_dan":"C:\\..."} hoặc {"ok":false,"huy":true} khi người dùng bấm Huỷ.

const chonThuMucTimeout = 10 * time.Minute

// pickFolderFn mở hộp thoại thật (gán trong chon_thu_muc_windows.go). Test thay bằng hàm giả: KHÔNG bao giờ mở hộp thật trong test.
// Trả "" nếu huỷ. ctx hết hạn thì hộp phải được đóng và trả lỗi.
var pickFolderFn func(ctx context.Context, title, start string) (string, error)

// folderPicker bảo đảm mỗi lúc chỉ có một hộp thoại.
type folderPicker struct {
	busy atomic.Bool
}

func (p *folderPicker) handler(authed func(*http.Request) bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !authed(r) {
			writeJSON(w, http.StatusForbidden, map[string]any{"ok": false, "error": "forbidden"})
			return
		}
		var body struct {
			TieuDe string `json:"tieu_de"`
			BatDau string `json:"bat_dau"`
		}
		if r.Body != nil {
			if raw, _ := io.ReadAll(io.LimitReader(r.Body, 8<<10)); len(strings.TrimSpace(string(raw))) > 0 {
				if err := json.Unmarshal(raw, &body); err != nil {
					writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": "JSON không hợp lệ"})
					return
				}
			}
		}
		if pickFolderFn == nil {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"ok": false, "error": "Không hỗ trợ hộp chọn thư mục trên hệ điều hành này"})
			return
		}
		if !p.busy.CompareAndSwap(false, true) {
			writeJSON(w, http.StatusConflict, map[string]any{"ok": false, "error": "đang mở hộp chọn"})
			return
		}
		defer p.busy.Store(false)

		title := strings.TrimSpace(body.TieuDe)
		if title == "" {
			title = "Chọn thư mục"
		}
		ctx, cancel := context.WithTimeout(context.Background(), chonThuMucTimeout)
		defer cancel()
		path, err := pickFolderFn(ctx, title, strings.TrimSpace(body.BatDau))
		switch {
		case err != nil:
			writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "error": err.Error()})
		case path == "":
			writeJSON(w, http.StatusOK, map[string]any{"ok": false, "huy": true})
		default:
			writeJSON(w, http.StatusOK, map[string]any{"ok": true, "duong_dan": path})
		}
	}
}

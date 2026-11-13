package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// Hộp chọn thư mục gốc Windows, mở từ trang "Kho riêng" của app (trình duyệt không trả được đường dẫn thật).
//
// Kiểu cũ (vẫn giữ để app cũ dùng được): POST /api/chon-thu-muc, chờ tới khi người dùng chọn xong.
// Body JSON tuỳ chọn: {"tieu_de": "...", "bat_dau": "<thư mục mở đầu>"}.
// Trả {"ok":true,"duong_dan":"C:\\..."} hoặc {"ok":false,"huy":true} khi người dùng bấm Huỷ.
//
// Kiểu không chặn (app chỉ có 2 tiến trình PHP, không được giữ một tiến trình tới 10 phút):
//   POST /api/chon-thu-muc/mo      (body như trên) → mở hộp chạy nền, trả ngay {"ok":true,"id":"<số>"}; đang mở hộp khác → 409.
//   POST /api/chon-thu-muc/ket-qua {"id":"<số>"} → {"xong":false} khi còn chờ, hoặc {"xong":true, ...kết quả như kiểu cũ}.
// Cả hai cần X-TTA-Token như /api/restart.

const chonThuMucTimeout = 10 * time.Minute

// Kết quả đã xong được giữ một lúc để app kịp hỏi.
const chonThuMucGiuKetQua = 5 * time.Minute

// pickFolderFn mở hộp thoại thật (gán trong chon_thu_muc_windows.go). Test thay bằng hàm giả: KHÔNG bao giờ mở hộp thật trong test.
// Trả "" nếu huỷ. ctx hết hạn thì hộp phải được đóng và trả lỗi.
var pickFolderFn func(ctx context.Context, title, start string) (string, error)

// folderPicker bảo đảm mỗi lúc chỉ có một hộp thoại.
type folderPicker struct {
	busy atomic.Bool

	mu     sync.Mutex
	nextID int64
	jobs   map[string]*pickJob
}

type pickJob struct {
	done   bool
	result map[string]any
	at     time.Time
}

type pickBody struct {
	TieuDe string `json:"tieu_de"`
	BatDau string `json:"bat_dau"`
	ID     string `json:"id"`
}

// readPickBody đọc body JSON (có thể rỗng). false = đã trả lỗi 400.
func readPickBody(w http.ResponseWriter, r *http.Request) (pickBody, bool) {
	var body pickBody
	if r.Body != nil {
		if raw, _ := io.ReadAll(io.LimitReader(r.Body, 8<<10)); len(strings.TrimSpace(string(raw))) > 0 {
			if err := json.Unmarshal(raw, &body); err != nil {
				writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": "JSON không hợp lệ"})
				return body, false
			}
		}
	}
	return body, true
}

func pickTitle(b pickBody) string {
	if t := strings.TrimSpace(b.TieuDe); t != "" {
		return t
	}
	return "Chọn thư mục"
}

// runPick mở hộp (chặn tới khi xong) và trả mã HTTP + kết quả.
func runPick(title, start string) (int, map[string]any) {
	ctx, cancel := context.WithTimeout(context.Background(), chonThuMucTimeout)
	defer cancel()
	path, err := pickFolderFn(ctx, title, start)
	switch {
	case err != nil:
		return http.StatusInternalServerError, map[string]any{"ok": false, "error": err.Error()}
	case path == "":
		return http.StatusOK, map[string]any{"ok": false, "huy": true}
	default:
		return http.StatusOK, map[string]any{"ok": true, "duong_dan": path}
	}
}

// guard kiểm token + hệ điều hành; false = đã trả lỗi.
func guard(w http.ResponseWriter, r *http.Request, authed func(*http.Request) bool) bool {
	if !authed(r) {
		writeJSON(w, http.StatusForbidden, map[string]any{"ok": false, "error": "forbidden"})
		return false
	}
	return true
}

func notSupported(w http.ResponseWriter) bool {
	if pickFolderFn == nil {
		writeJSON(w, http.StatusNotImplemented, map[string]any{"ok": false, "error": "Không hỗ trợ hộp chọn thư mục trên hệ điều hành này"})
		return true
	}
	return false
}

func (p *folderPicker) handler(authed func(*http.Request) bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !guard(w, r, authed) {
			return
		}
		body, ok := readPickBody(w, r)
		if !ok || notSupported(w) {
			return
		}
		if !p.busy.CompareAndSwap(false, true) {
			writeJSON(w, http.StatusConflict, map[string]any{"ok": false, "error": "đang mở hộp chọn"})
			return
		}
		defer p.busy.Store(false)

		code, out := runPick(pickTitle(body), strings.TrimSpace(body.BatDau))
		writeJSON(w, code, out)
	}
}

// openHandler: mở hộp chạy nền, trả id ngay.
func (p *folderPicker) openHandler(authed func(*http.Request) bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !guard(w, r, authed) {
			return
		}
		body, ok := readPickBody(w, r)
		if !ok || notSupported(w) {
			return
		}
		if !p.busy.CompareAndSwap(false, true) {
			writeJSON(w, http.StatusConflict, map[string]any{"ok": false, "error": "đang mở hộp chọn"})
			return
		}

		p.mu.Lock()
		p.prune(time.Now())
		p.nextID++
		id := strconv.FormatInt(time.Now().UnixMilli(), 36) + "-" + strconv.FormatInt(p.nextID, 10)
		job := &pickJob{at: time.Now()}
		if p.jobs == nil {
			p.jobs = map[string]*pickJob{}
		}
		p.jobs[id] = job
		p.mu.Unlock()

		title, start := pickTitle(body), strings.TrimSpace(body.BatDau)
		go func() {
			defer p.busy.Store(false)
			res := map[string]any{"ok": false, "error": "Hộp chọn thư mục bị lỗi"}
			func() {
				defer func() {
					if rec := recover(); rec != nil {
						res = map[string]any{"ok": false, "error": "Hộp chọn thư mục bị lỗi"}
					}
				}()
				_, res = runPick(title, start)
			}()
			p.mu.Lock()
			job.done, job.result, job.at = true, res, time.Now()
			p.mu.Unlock()
		}()

		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "id": id})
	}
}

// resultHandler: hỏi kết quả theo id. Kết quả đã trả thì xoá (mỗi id chỉ nhận một lần).
func (p *folderPicker) resultHandler(authed func(*http.Request) bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !guard(w, r, authed) {
			return
		}
		body, ok := readPickBody(w, r)
		if !ok {
			return
		}
		id := strings.TrimSpace(body.ID)

		p.mu.Lock()
		defer p.mu.Unlock()
		p.prune(time.Now())
		job := p.jobs[id]
		switch {
		case id == "" || job == nil:
			writeJSON(w, http.StatusNotFound, map[string]any{"ok": false, "xong": true, "error": "Không tìm thấy lượt chọn thư mục này"})
		case !job.done:
			writeJSON(w, http.StatusOK, map[string]any{"xong": false})
		default:
			out := map[string]any{"xong": true}
			for k, v := range job.result {
				out[k] = v
			}
			delete(p.jobs, id)
			writeJSON(w, http.StatusOK, out)
		}
	}
}

// prune bỏ kết quả đã xong quá lâu không ai hỏi. Gọi khi đang giữ p.mu.
func (p *folderPicker) prune(now time.Time) {
	for id, j := range p.jobs {
		if j.done && now.Sub(j.at) > chonThuMucGiuKetQua {
			delete(p.jobs, id)
		}
	}
}

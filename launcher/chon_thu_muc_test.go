package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// Chỉ thử logic handler (token, bận, huỷ); hàm mở hộp luôn bị thay bằng hàm giả, không bao giờ mở hộp thật.
func TestChonThuMucHandler(t *testing.T) {
	old := pickFolderFn
	defer func() { pickFolderFn = old }()

	var gotTitle, gotStart string
	result := `C:\Video\Cua toi`
	pickFolderFn = func(ctx context.Context, title, start string) (string, error) {
		gotTitle, gotStart = title, start
		return result, nil
	}
	authed := func(r *http.Request) bool { return r.Header.Get("X-TTA-Token") == "tok" && r.Method == http.MethodPost }
	p := &folderPicker{}
	h := p.handler(authed)
	do := func(method, token, body string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(method, "/api/chon-thu-muc", strings.NewReader(body))
		if token != "" {
			req.Header.Set("X-TTA-Token", token)
		}
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec
	}

	if rec := do("POST", "", ""); rec.Code != http.StatusForbidden {
		t.Fatalf("thiếu token phải 403: %d", rec.Code)
	}
	if rec := do("GET", "tok", ""); rec.Code != http.StatusForbidden {
		t.Fatalf("GET phải 403: %d", rec.Code)
	}
	if rec := do("POST", "tok", "{hỏng"); rec.Code != http.StatusBadRequest {
		t.Fatalf("JSON hỏng phải 400: %d", rec.Code)
	}

	rec := do("POST", "tok", `{"tieu_de":"Chọn nè","bat_dau":"D:\\Video"}`)
	var out map[string]any
	json.Unmarshal(rec.Body.Bytes(), &out)
	if rec.Code != 200 || out["ok"] != true || out["duong_dan"] != result {
		t.Fatalf("thành công: %d %s", rec.Code, rec.Body.String())
	}
	if gotTitle != "Chọn nè" || gotStart != `D:\Video` {
		t.Fatalf("tham số: %q %q", gotTitle, gotStart)
	}

	result = ""
	rec = do("POST", "tok", "")
	out = nil
	json.Unmarshal(rec.Body.Bytes(), &out)
	if rec.Code != 200 || out["ok"] != false || out["huy"] != true {
		t.Fatalf("huỷ: %d %s", rec.Code, rec.Body.String())
	}
	if gotTitle != "Chọn thư mục" {
		t.Fatalf("tiêu đề mặc định: %q", gotTitle)
	}

	// đang bận → 409
	p.busy.Store(true)
	if rec := do("POST", "tok", ""); rec.Code != http.StatusConflict || !strings.Contains(rec.Body.String(), "đang mở hộp chọn") {
		t.Fatalf("bận phải 409: %d %s", rec.Code, rec.Body.String())
	}
	p.busy.Store(false)
	if rec := do("POST", "tok", ""); rec.Code != 200 {
		t.Fatalf("hết bận phải chạy lại được: %d", rec.Code)
	}
}

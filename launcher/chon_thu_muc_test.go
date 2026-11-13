package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
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

// Kiểu không chặn: /mo trả id ngay, /ket-qua trả "chưa xong" rồi kết quả, mỗi id chỉ nhận một lần.
func TestChonThuMucKhongChan(t *testing.T) {
	old := pickFolderFn
	defer func() { pickFolderFn = old }()

	release := make(chan string)
	pickFolderFn = func(ctx context.Context, title, start string) (string, error) {
		return <-release, nil
	}
	authed := func(r *http.Request) bool { return r.Header.Get("X-TTA-Token") == "tok" && r.Method == http.MethodPost }
	p := &folderPicker{}
	open, result := p.openHandler(authed), p.resultHandler(authed)
	call := func(h http.HandlerFunc, token, body string) (int, map[string]any) {
		req := httptest.NewRequest("POST", "/x", strings.NewReader(body))
		if token != "" {
			req.Header.Set("X-TTA-Token", token)
		}
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		var out map[string]any
		json.Unmarshal(rec.Body.Bytes(), &out)
		return rec.Code, out
	}

	if code, _ := call(open, "", ""); code != http.StatusForbidden {
		t.Fatalf("thiếu token phải 403: %d", code)
	}
	if code, _ := call(result, "", `{"id":"x"}`); code != http.StatusForbidden {
		t.Fatalf("ket-qua thiếu token phải 403: %d", code)
	}

	code, out := call(open, "tok", `{"tieu_de":"Chọn"}`)
	id, _ := out["id"].(string)
	if code != 200 || out["ok"] != true || id == "" {
		t.Fatalf("mở: %d %v", code, out)
	}
	if code, _ := call(open, "tok", ""); code != http.StatusConflict {
		t.Fatalf("đang mở hộp khác phải 409: %d", code)
	}
	if code, out := call(result, "tok", `{"id":"`+id+`"}`); code != 200 || out["xong"] != false {
		t.Fatalf("chưa chọn xong: %d %v", code, out)
	}

	release <- `D:\Video`
	deadline := time.Now().Add(3 * time.Second)
	for {
		code, out = call(result, "tok", `{"id":"`+id+`"}`)
		if out["xong"] == true || time.Now().After(deadline) {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if code != 200 || out["ok"] != true || out["duong_dan"] != `D:\Video` {
		t.Fatalf("kết quả: %d %v", code, out)
	}
	if code, _ := call(result, "tok", `{"id":"`+id+`"}`); code != http.StatusNotFound {
		t.Fatalf("id đã nhận kết quả phải 404: %d", code)
	}
	for i := 0; i < 100 && p.busy.Load(); i++ {
		time.Sleep(10 * time.Millisecond)
	}
	if p.busy.Load() {
		t.Fatal("xong phải hết bận")
	}

	// huỷ
	_, out = call(open, "tok", "")
	id, _ = out["id"].(string)
	release <- ""
	for i := 0; i < 300; i++ {
		_, out = call(result, "tok", `{"id":"`+id+`"}`)
		if out["xong"] == true {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if out["huy"] != true || out["ok"] != false {
		t.Fatalf("huỷ: %v", out)
	}
}

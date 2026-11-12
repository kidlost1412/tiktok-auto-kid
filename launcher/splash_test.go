package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestSplashProgressWeightedAndMonotonic(t *testing.T) {
	mk := func(db, p1, p2, web, q, xv Status) []progService {
		return []progService{
			{"postgres", db, false}, {"php-cgi-1", p1, false}, {"php-cgi-2", p2, false}, {"web", web, false},
			{"queue-main", q, false}, {"xuong-video", xv, true},
		}
	}
	steps := []stepState{{Name: "initdb", State: "skipped"}, {Name: "bootstrap-db", State: "pending"}}
	p0, t0 := splashProgress(steps, mk(StatusStopped, StatusStopped, StatusStopped, StatusStopped, StatusStopped, StatusStopped), "web")
	if t0 != splashTextDB {
		t.Fatalf("đầu tiên phải là kho dữ liệu: %q", t0)
	}
	steps[1].State = "ok"
	p1, t1 := splashProgress(steps, mk(StatusStarting, StatusStopped, StatusStopped, StatusStopped, StatusStopped, StatusStopped), "web")
	p2, t2 := splashProgress(steps, mk(StatusRunning, StatusStarting, StatusStarting, StatusStopped, StatusStopped, StatusStopped), "web")
	p3, t3 := splashProgress(steps, mk(StatusRunning, StatusRunning, StatusRunning, StatusRunning, StatusRunning, StatusStarting), "web")
	p4, t4 := splashProgress(steps, mk(StatusRunning, StatusRunning, StatusRunning, StatusRunning, StatusRunning, StatusRunning), "web")
	if !(p0 < p1 && p1 < p2 && p2 < p3 && p3 < p4) {
		t.Fatalf("tiến độ phải tăng dần: %.1f %.1f %.1f %.1f %.1f", p0, p1, p2, p3, p4)
	}
	if t1 != splashTextDB || t2 != splashTextWeb || t3 != splashTextVideo || t4 != splashTextAlmost {
		t.Fatalf("câu chữ sai: %q %q %q %q", t1, t2, t3, t4)
	}
	if p4 < 99.9 || p4 > 100.1 {
		t.Fatalf("tất cả xong phải ~100: %.2f", p4)
	}
}

func TestSplashProgressSkipsMissingOptional(t *testing.T) {
	svcs := []progService{{"postgres", StatusRunning, false}, {"xuong-video", StatusSkipped, true}}
	p, txt := splashProgress(nil, svcs, "web")
	if p < 99 || txt != splashTextAlmost {
		t.Fatalf("dịch vụ chưa cài không được chặn tiến độ: %.1f %q", p, txt)
	}
}

func TestSplashHTMLEmbedded(t *testing.T) {
	for _, s := range []string{"{{VERSION}}", "Thử lại", "Xem chi tiết", "Đóng", "ttaRetry", "ttaDone"} {
		if !strings.Contains(splashHTML, s) {
			t.Fatalf("splash.html thiếu %q", s)
		}
	}
}

func TestDemoFlag(t *testing.T) {
	var d demoFlag
	for in, want := range map[string]demoFlag{"true": "ok", "loi": "loi", "false": ""} {
		d.Set(in)
		if d != want {
			t.Fatalf("Set(%q) = %q, muốn %q", in, d, want)
		}
	}
	if !d.IsBoolFlag() {
		t.Fatal("phải là bool flag để -splash-demo đứng một mình")
	}
}

func TestQuitEndpoint(t *testing.T) {
	sup, cfg, root := newTestSup(t)
	called := make(chan struct{}, 2)
	h := NewStatusHandlerAll(sup, cfg, root, nil, "tok123", nil, func() error { called <- struct{}{}; return nil })
	do := func(method, host, tok string) int {
		req := httptest.NewRequest(method, "/api/quit", nil)
		req.Host = host
		if tok != "" {
			req.Header.Set("X-TTA-Token", tok)
		}
		rr := httptest.NewRecorder()
		h.ServeHTTP(rr, req)
		return rr.Code
	}
	if c := do(http.MethodPost, "127.0.0.1:8009", ""); c != http.StatusForbidden {
		t.Fatalf("thiếu token phải 403, được %d", c)
	}
	if c := do(http.MethodPost, "127.0.0.1:8009", "sai"); c != http.StatusForbidden {
		t.Fatalf("token sai phải 403, được %d", c)
	}
	if c := do(http.MethodGet, "127.0.0.1:8009", "tok123"); c != http.StatusForbidden {
		t.Fatalf("GET phải 403, được %d", c)
	}
	if c := do(http.MethodPost, "evil.example.com", "tok123"); c != http.StatusForbidden {
		t.Fatalf("Host lạ phải 403, được %d", c)
	}
	select {
	case <-called:
		t.Fatal("không được thoát khi chưa xác thực")
	default:
	}
	if c := do(http.MethodPost, "127.0.0.1:8009", "tok123"); c != http.StatusAccepted {
		t.Fatalf("hợp lệ phải 202, được %d", c)
	}
	select {
	case <-called:
	default:
		t.Fatal("quit() phải được gọi")
	}
}

func TestQuitEndpointDisabledAndBusy(t *testing.T) {
	sup, cfg, root := newTestSup(t)
	h := NewStatusHandlerFull(sup, cfg, root, nil, "tok", nil) // quit == nil => tắt
	req := httptest.NewRequest(http.MethodPost, "/api/quit", nil)
	req.Host = "127.0.0.1:8009"
	req.Header.Set("X-TTA-Token", "tok")
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusForbidden {
		t.Fatalf("không có quit phải 403, được %d", rr.Code)
	}
}

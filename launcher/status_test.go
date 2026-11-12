package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func newTestSup(t *testing.T) (*Supervisor, *Config, string) {
	t.Helper()
	cfg, err := ParseConfig([]byte(goodJSON))
	if err != nil {
		t.Fatal(err)
	}
	root := t.TempDir()
	os.MkdirAll(filepath.Join(root, "runtime", "logs"), 0o755)
	sup, err := NewSupervisor(cfg, root, NewLogger())
	if err != nil {
		t.Fatal(err)
	}
	return sup, cfg, root
}

func TestStatusPortDefault(t *testing.T) {
	c := &Config{}
	if c.StatusPortOrDefault() != 8009 {
		t.Fatal("mặc định phải là 8009")
	}
	c.StatusPort = -1
	if c.StatusPortOrDefault() != 0 {
		t.Fatal("-1 phải tắt")
	}
	c.StatusPort = 8123
	if c.StatusPortOrDefault() != 8123 {
		t.Fatal("cổng tuỳ chỉnh")
	}
}

func TestSnapshotStartingReadyError(t *testing.T) {
	sup, cfg, root := newTestSup(t)
	sup.steps = []stepState{{Name: "initdb", State: "ok"}}
	sup.states["postgres"].set(StatusRunning, "")
	sup.states["web"].set(StatusStarting, "")

	snap := BuildSnapshot(sup, cfg, root)
	if snap.State != "starting" || snap.Ready {
		t.Fatalf("phải starting: %+v", snap)
	}
	if snap.Items[0].Kind != "step" || snap.Items[0].Name != "initdb" {
		t.Fatalf("bước first_run phải đứng đầu: %+v", snap.Items)
	}

	sup.states["web"].set(StatusRunning, "")
	snap = BuildSnapshot(sup, cfg, root)
	if snap.State != "ready" || !snap.Ready || snap.AppURL != "http://localhost:8010" {
		t.Fatalf("phải ready khi web chạy: %+v", snap)
	}

	// lỗi + log cuối
	var lines []string
	for i := 1; i <= 30; i++ {
		lines = append(lines, "dòng "+string(rune('A'+i%26)))
	}
	os.WriteFile(filepath.Join(root, "runtime", "logs", "queue.log"), []byte(strings.Join(lines, "\r\n")+"\r\n"), 0o644)
	sup.states["queue"].set(StatusError, "thoát mã 1")
	snap = BuildSnapshot(sup, cfg, root)
	if snap.State != "error" || snap.Ready {
		t.Fatalf("phải error: %+v", snap)
	}
	var q StatusItem
	for _, it := range snap.Items {
		if it.Name == "queue" {
			q = it
		}
	}
	if q.State != "error" || len(q.Log) != 20 || strings.Contains(q.Log[0], "\r") {
		t.Fatalf("log lỗi sai: %+v", q)
	}
}

func TestStatusHTTP(t *testing.T) {
	sup, cfg, root := newTestSup(t)
	retried := 0
	h := NewStatusHandler(sup, cfg, root, func() { retried++ })

	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", "/api/status", nil))
	var snap StatusSnapshot
	if err := json.Unmarshal(rec.Body.Bytes(), &snap); err != nil || snap.State != "starting" {
		t.Fatalf("json: %v %s", err, rec.Body.String())
	}
	if len(snap.Items) != 3 {
		t.Fatalf("3 dịch vụ: %+v", snap.Items)
	}

	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", "/", nil))
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), "Thử lại") {
		t.Fatal("trang HTML thiếu")
	}

	// retry cần POST + header
	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", "/api/retry", nil))
	if rec.Code != http.StatusForbidden || retried != 0 {
		t.Fatal("GET retry phải bị từ chối")
	}
	rec = httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/retry", nil)
	req.Header.Set("X-TTA", "1")
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusAccepted || retried != 1 {
		t.Fatalf("retry: %d %d", rec.Code, retried)
	}
}

func TestTailLines(t *testing.T) {
	p := filepath.Join(t.TempDir(), "a.log")
	if TailLines(p, 5) != nil {
		t.Fatal("file thiếu => nil")
	}
	os.WriteFile(p, []byte("a\nb\nc\n"), 0o644)
	if got := TailLines(p, 2); len(got) != 2 || got[0] != "b" || got[1] != "c" {
		t.Fatalf("%v", got)
	}
}

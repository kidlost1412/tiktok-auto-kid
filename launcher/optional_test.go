package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TestMain chặn "bom tiến trình": tiến trình con (có TTA_HELPER) KHÔNG BAO GIỜ chạy lại bộ test,
// dù tham số -test.run có bị mất. Trước đây con chạy lại toàn bộ test → mỗi test lại đẻ con → 1.700 tiến trình, treo máy.
func TestMain(m *testing.M) {
	// Launcher tự chạy lại chính exe (--watch-pg canh Postgres, --send-break dừng dịch vụ). Trong test, "chính exe" là
	// file test → nếu để con chạy m.Run() thì mỗi con lại đẻ thêm con: bom tiến trình (treo máy 12/11). Con như vậy thoát ngay.
	for _, a := range os.Args[1:] {
		if a == "--watch-pg" || a == "-watch-pg" || a == "--send-break" || a == "-send-break" ||
			strings.HasPrefix(a, "--watch-pg=") || strings.HasPrefix(a, "-watch-pg=") ||
			strings.HasPrefix(a, "--send-break=") || strings.HasPrefix(a, "-send-break=") ||
			strings.HasPrefix(a, "--after-swap") || strings.HasPrefix(a, "-after-swap") || strings.HasPrefix(a, "--update") {
			os.Exit(0)
		}
	}
	switch os.Getenv("TTA_HELPER") {
	case "":
		os.Exit(m.Run())
	case "exit3":
		os.Exit(3)
	case "sleep":
		time.Sleep(60 * time.Second)
	}
	os.Exit(0)
}

// Tiến trình giả: giữ tên cho tham số -test.run=TestHelperProcess (việc thật nằm ở TestMain).
func TestHelperProcess(t *testing.T) {}

func helperSup(t *testing.T, svc string) (*Supervisor, string) {
	t.Helper()
	root := t.TempDir()
	os.MkdirAll(filepath.Join(root, "runtime", "logs"), 0o755)
	cfg, err := ParseConfig([]byte(svc))
	if err != nil {
		t.Fatal(err)
	}
	sup, err := NewSupervisor(cfg, root, NewLogger())
	if err != nil {
		t.Fatal(err)
	}
	return sup, root
}

func waitStatus(t *testing.T, sup *Supervisor, name string, want Status) {
	t.Helper()
	for i := 0; i < 100; i++ {
		for _, s := range sup.Statuses() {
			if s.Name == name && s.Status == want {
				return
			}
		}
		time.Sleep(100 * time.Millisecond)
	}
	t.Fatalf("%s không đạt trạng thái %v: %+v", name, want, sup.Statuses())
}
func quote(s string) string { b, _ := json.Marshal(s); return string(b) }

func TestExternalExitCodeKeepsMonitoring(t *testing.T) {
	hs := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte(`{"ok":true}`)) }))
	defer hs.Close()
	t.Setenv("TTA_HELPER", "exit3")
	sup, _ := helperSup(t, `{"app_url":"http://localhost:1","status_port":-1,"services":[{"name":"hub","cmd":`+quote(os.Args[0])+
		`,"args":["-test.run=TestHelperProcess"],"optional":true,"no_restart_exit_codes":[3],"health":{"type":"http","url":"`+hs.URL+`"}}]}`)
	if err := sup.Start(); err != nil {
		t.Fatal(err)
	}
	defer sup.Stop()
	waitStatus(t, sup, "hub", StatusExternal)
	if st, _ := sup.Summary(); st != StatusRunning {
		t.Fatalf("tổng thể phải Running, được %v", st)
	}
}

func TestOptionalMissingPathSkipped(t *testing.T) {
	sup, _ := helperSup(t, `{"app_url":"http://localhost:1","status_port":-1,"services":[{"name":"hub","cmd":"nonexist.exe","optional":true,`+
		`"requires_path":"${NOPE_DIR_XYZ}/nothing","missing_message":"Chưa cài Xưởng Video"}]}`)
	if err := sup.Start(); err != nil {
		t.Fatalf("dịch vụ tuỳ chọn thiếu không được làm hỏng cả bộ: %v", err)
	}
	defer sup.Stop()
	s := sup.Statuses()[0]
	if s.Status != StatusSkipped || s.Detail != "Chưa cài Xưởng Video" {
		t.Fatalf("%+v", s)
	}
	if err := sup.RestartService("hub"); err == nil {
		t.Fatal("vẫn chưa cài thì RestartService phải báo lỗi")
	}
}

func TestStopModeKillPid(t *testing.T) {
	t.Setenv("TTA_HELPER", "sleep")
	sup, _ := helperSup(t, `{"app_url":"http://localhost:1","status_port":-1,"services":[{"name":"hub","cmd":`+quote(os.Args[0])+
		`,"args":["-test.run=TestHelperProcess"],"optional":true,"stop":{"mode":"kill_pid"}}]}`)
	if err := sup.Start(); err != nil {
		t.Fatal(err)
	}
	waitStatus(t, sup, "hub", StatusRunning)
	done := make(chan struct{})
	go func() { sup.Stop(); close(done) }()
	select {
	case <-done:
	case <-time.After(15 * time.Second):
		t.Fatal("Stop kill_pid treo")
	}
}

func TestRestartEndpointAuth(t *testing.T) {
	t.Setenv("TTA_HELPER", "sleep")
	sup, root := helperSup(t, `{"app_url":"http://localhost:1","status_port":-1,"services":[{"name":"hub","cmd":`+quote(os.Args[0])+
		`,"args":["-test.run=TestHelperProcess"],"optional":true},{"name":"core","cmd":`+quote(os.Args[0])+`,"args":["-test.run=TestHelperProcess"]}]}`)
	if err := sup.Start(); err != nil {
		t.Fatal(err)
	}
	defer sup.Stop()
	h := NewStatusHandlerCtl(sup, sup.cfg, root, nil, "secret")
	do := func(method, target, tok, host string) int {
		r := httptest.NewRequest(method, target, nil)
		r.Host = host
		if tok != "" {
			r.Header.Set("X-TTA-Token", tok)
		}
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		return w.Code
	}
	if c := do("POST", "/api/restart?service=hub", "", "127.0.0.1:8009"); c != 403 {
		t.Fatalf("không token: %d", c)
	}
	if c := do("POST", "/api/restart?service=hub", "sai", "127.0.0.1:8009"); c != 403 {
		t.Fatalf("sai token: %d", c)
	}
	if c := do("POST", "/api/restart?service=hub", "secret", "evil.example:8009"); c != 403 {
		t.Fatalf("host lạ: %d", c)
	}
	if c := do("GET", "/api/restart?service=hub", "secret", "127.0.0.1:8009"); c != 403 {
		t.Fatalf("GET: %d", c)
	}
	if c := do("POST", "/api/restart?service=core", "secret", "127.0.0.1:8009"); c != 400 {
		t.Fatalf("dịch vụ bắt buộc không được restart lẻ: %d", c)
	}
	if c := do("POST", "/api/restart?service=hub", "secret", "127.0.0.1:8009"); c != 202 {
		t.Fatalf("hợp lệ: %d", c)
	}
	waitStatus(t, sup, "hub", StatusRunning)
	if c := do("POST", "/api/restart?service=hub", "secret", "localhost:8009"); c != 202 {
		t.Fatalf("localhost: %d", c)
	}
}

func TestVarsAndEnv(t *testing.T) {
	root := t.TempDir()
	os.WriteFile(filepath.Join(root, ".env"), []byte("XV_TEST_DIR=\"D:/hub\"\n# c\nOTHER=1\n"), 0o644)
	cfg := &Config{Vars: map[string]string{"XV_TEST_DIR": "C:/default", "XV_ONLY_CFG": "cfg"}}
	SetVars(cfg, root)
	defer SetVars(nil, "")
	if got := expand("${XV_TEST_DIR}/a ${XV_ONLY_CFG} ${ROOT} ${NOPE}", "R"); got != "D:/hub/a cfg R ${NOPE}" {
		t.Fatal(got)
	}
	t.Setenv("XV_TEST_DIR", "E:/env")
	if got := expand("${XV_TEST_DIR}", "R"); got != "E:/env" {
		t.Fatal(got)
	}
}

func TestBuildEnvPathAdd(t *testing.T) {
	env := buildEnv([]string{`Path=C:\a`, "X=1"}, map[string]string{"Y": "2"}, []string{`C:\b`, `c:\A`}, "R")
	var path string
	for _, kv := range env {
		if strings.HasPrefix(strings.ToUpper(kv), "PATH=") {
			path = kv
		}
	}
	if path != `PATH=C:\a;C:\b` {
		t.Fatal(path, env)
	}
}

func TestStopModeValidation(t *testing.T) {
	_, err := ParseConfig([]byte(`{"app_url":"http://x:1","services":[{"name":"a","cmd":"c","stop":{"mode":"bogus"}}]}`))
	if err == nil {
		t.Fatal("mode lạ phải lỗi")
	}
	if _, err := ParseConfig([]byte(`{"app_url":"http://x:1","services":[{"name":"a","cmd":"c","stop":{"mode":"kill_pid"}}]}`)); err != nil {
		t.Fatal(err)
	}
}

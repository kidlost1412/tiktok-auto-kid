package main

import (
	"bytes"
	"context"
	"crypto/subtle"
	_ "embed"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const defaultStatusPort = 8009

//go:embed assets/status.html
var statusPageHTML []byte

// StatusItem là một dòng (bước chuẩn bị hoặc dịch vụ) trên trang trạng thái.
type StatusItem struct {
	Name   string   `json:"name"`
	Kind   string   `json:"kind"`  // step | service
	State  string   `json:"state"` // pending | running | ok | skipped | error
	Detail string   `json:"detail,omitempty"`
	Log    []string `json:"log,omitempty"` // ~20 dòng log cuối khi lỗi
}

// StatusSnapshot là JSON trả về cho /api/status.
type StatusSnapshot struct {
	State   string       `json:"state"` // starting | ready | error | stopped
	Message string       `json:"message"`
	AppURL  string       `json:"app_url"`
	Ready   bool         `json:"ready"`
	Items   []StatusItem `json:"items"`
}

// StatusPortOrDefault trả cổng trang trạng thái (0 = tắt).
func (c *Config) StatusPortOrDefault() int {
	switch {
	case c.StatusPort < 0:
		return 0
	case c.StatusPort == 0:
		return defaultStatusPort
	}
	return c.StatusPort
}

// TailLines đọc tối đa n dòng cuối của file (nil nếu không có).
func TailLines(path string, n int) []string {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil {
		return nil
	}
	const maxRead = 64 << 10
	size := st.Size()
	off := int64(0)
	if size > maxRead {
		off = size - maxRead
	}
	buf := make([]byte, size-off)
	if _, err := f.ReadAt(buf, off); err != nil && len(buf) > 0 {
		return nil
	}
	text := strings.ReplaceAll(string(bytes.ToValidUTF8(buf, []byte("?"))), "\r", "")
	text = strings.TrimRight(text, "\n")
	if text == "" {
		return nil
	}
	lines := strings.Split(text, "\n")
	if off > 0 && len(lines) > 1 {
		lines = lines[1:] // dòng đầu có thể bị cắt giữa chừng
	}
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return lines
}

// webServiceName tìm dịch vụ web (health trỏ tới cổng của app_url); rỗng nếu không có.
func webServiceName(cfg *Config) string {
	u, err := url.Parse(cfg.AppURL)
	if err != nil {
		return ""
	}
	port := urlPort(u)
	for _, s := range cfg.Services {
		if s.Health == nil {
			continue
		}
		switch s.Health.Type {
		case "tcp":
			if s.Health.Port == port {
				return s.Name
			}
		case "http":
			if hu, err := url.Parse(s.Health.URL); err == nil && urlPort(hu) == port {
				return s.Name
			}
		}
	}
	return ""
}

// BuildSnapshot dựng trạng thái hiện tại từ supervisor.
func BuildSnapshot(sup *Supervisor, cfg *Config, root string) StatusSnapshot {
	snap := StatusSnapshot{AppURL: cfg.AppURL, Items: []StatusItem{}}
	for _, st := range sup.StepStatuses() {
		it := StatusItem{Name: st.Name, Kind: "step", State: st.State, Detail: st.Detail}
		if st.State == "error" {
			it.Log = TailLines(filepath.Join(root, "runtime", "logs", st.Name+".log"), 20)
		}
		snap.Items = append(snap.Items, it)
	}
	web := webServiceName(cfg)
	webUp, allUp := false, true
	for _, x := range sup.Statuses() {
		it := StatusItem{Name: x.Name, Kind: "service", Detail: x.Detail}
		switch x.Status {
		case StatusRunning:
			it.State = "ok"
		case StatusStarting:
			it.State = "running"
		case StatusExternal:
			it.State = "external"
		case StatusSkipped:
			it.State = "skipped"
		case StatusError:
			it.State = "error"
			it.Log = TailLines(filepath.Join(root, "runtime", "logs", x.Name+".log"), 20)
		default:
			it.State = "pending"
		}
		if x.Status != StatusRunning && x.Status != StatusExternal && x.Status != StatusSkipped && !sup.states[x.Name].svc.Optional {
			allUp = false
		}
		if x.Name == web && x.Status == StatusRunning {
			webUp = true
		}
		snap.Items = append(snap.Items, it)
	}
	if web == "" {
		webUp = allUp
	}
	st, msg := sup.Summary()
	snap.Message = msg
	switch {
	case st == StatusError:
		snap.State = "error"
	case webUp:
		snap.State, snap.Ready = "ready", true
		if msg == "" {
			snap.Message = "Sẵn sàng"
		}
	default:
		snap.State = "starting"
	}
	return snap
}

// NewStatusHandler tạo handler cho trang trạng thái; retry được gọi khi bấm "Thử lại".
func NewStatusHandler(sup *Supervisor, cfg *Config, root string, retry func()) http.Handler {
	return NewStatusHandlerCtl(sup, cfg, root, retry, "")
}

// loopbackHost: chống DNS rebinding, chỉ nhận Host là 127.0.0.1 / localhost / [::1].
func loopbackHost(h string) bool {
	host, _, err := net.SplitHostPort(h)
	if err != nil {
		host = h
	}
	return host == "127.0.0.1" || host == "localhost" || host == "::1" || host == "[::1]"
}

// NewStatusHandlerCtl như NewStatusHandler, thêm POST /api/restart?service=<tên> để khởi động lại một dịch vụ tuỳ chọn.
// Cần header X-TTA-Token khớp token (rỗng = tắt endpoint); token nằm trong runtime/control.token.
func NewStatusHandlerCtl(sup *Supervisor, cfg *Config, root string, retry func(), token string) http.Handler {
	return NewStatusHandlerFull(sup, cfg, root, retry, token, nil)
}

// NewStatusHandlerFull như NewStatusHandlerCtl, thêm API cập nhật (/api/update*) khi upd != nil.
func NewStatusHandlerFull(sup *Supervisor, cfg *Config, root string, retry func(), token string, upd *Updater) http.Handler {
	return NewStatusHandlerAll(sup, cfg, root, retry, token, upd, nil)
}

// NewStatusHandlerAll như NewStatusHandlerFull, thêm POST /api/quit (cùng cơ chế xác thực /api/restart):
// quit() thực hiện thoát êm (dừng dịch vụ rồi thoát); trình gỡ cài đặt dùng endpoint này. quit == nil = tắt endpoint.
func NewStatusHandlerAll(sup *Supervisor, cfg *Config, root string, retry func(), token string, upd *Updater, quit func() error) http.Handler {
	mux := http.NewServeMux()
	authed := func(r *http.Request) bool {
		return token != "" && r.Method == http.MethodPost && loopbackHost(r.Host) &&
			subtle.ConstantTimeCompare([]byte(r.Header.Get("X-TTA-Token")), []byte(token)) == 1
	}
	if upd != nil {
		registerUpdateRoutes(mux, upd, cfg.AppURL, authed)
	}
	picker := &folderPicker{}
	mux.HandleFunc("/api/chon-thu-muc", picker.handler(authed))
	mux.HandleFunc("/api/quit",func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		if !authed(r) || quit == nil {
			w.WriteHeader(http.StatusForbidden)
			fmt.Fprint(w, `{"ok":false,"error":"forbidden"}`)
			return
		}
		if err := quit(); err != nil {
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
			return
		}
		w.WriteHeader(http.StatusAccepted)
		fmt.Fprint(w, `{"ok":true}`)
	})
	mux.HandleFunc("/api/restart", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		if !authed(r) {
			w.WriteHeader(http.StatusForbidden)
			fmt.Fprint(w, `{"ok":false,"error":"forbidden"}`)
			return
		}
		if err := sup.RestartService(r.URL.Query().Get("service")); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
			return
		}
		w.WriteHeader(http.StatusAccepted)
		fmt.Fprint(w, `{"ok":true}`)
	})
	mux.HandleFunc("/api/status", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		json.NewEncoder(w).Encode(BuildSnapshot(sup, cfg, root))
	})
	mux.HandleFunc("/api/retry", func(w http.ResponseWriter, r *http.Request) {
		// header tuỳ biến buộc trình duyệt preflight => trang web khác không gọi được
		if r.Method != http.MethodPost || r.Header.Get("X-TTA") != "1" {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		if retry != nil {
			retry()
		}
		w.WriteHeader(http.StatusAccepted)
		fmt.Fprint(w, `{"ok":true}`)
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		w.Write(statusPageHTML)
	})
	return mux
}

// StatusServer là máy chủ HTTP nhỏ của trang trạng thái.
type StatusServer struct {
	srv *http.Server
	URL string
}

// StartStatusServer lắng nghe 127.0.0.1:port; lỗi nếu cổng bận.
func StartStatusServer(port int, h http.Handler) (*StatusServer, error) {
	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		return nil, err
	}
	ss := &StatusServer{srv: &http.Server{Handler: h, ReadHeaderTimeout: 5 * time.Second}, URL: fmt.Sprintf("http://127.0.0.1:%d/", port)}
	go ss.srv.Serve(ln)
	return ss, nil
}

func (s *StatusServer) Close() {
	if s == nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	s.srv.Shutdown(ctx)
}

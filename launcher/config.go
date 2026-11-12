package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
)

// Health mô tả cách kiểm tra một dịch vụ đã sẵn sàng.
type Health struct {
	Type       string `json:"type"` // "tcp" | "http"
	Port       int    `json:"port,omitempty"`
	URL        string `json:"url,omitempty"`
	TimeoutSec int    `json:"timeout_sec,omitempty"` // mặc định 90
}

// Command là một lệnh chạy một lần (first_run, stop, backup).
type Command struct {
	Name          string            `json:"name,omitempty"`
	Cmd           string            `json:"cmd"`
	Args          []string          `json:"args,omitempty"`
	Cwd           string            `json:"cwd,omitempty"`
	Env           map[string]string `json:"env,omitempty"`
	OnlyIfMissing string            `json:"only_if_missing,omitempty"`
	// Mode (chỉ dùng cho "stop" của dịch vụ): "" = chạy lệnh Cmd; "kill_pid" = chỉ diệt đúng PID của dịch vụ
	// (không diệt cây con); "ctrl_break_kill_pid" = gửi CTRL_BREAK trước rồi diệt đúng PID.
	Mode string `json:"mode,omitempty"`
}

// Service là một tiến trình chạy nền được giám sát.
type Service struct {
	Name           string            `json:"name"`
	Cmd            string            `json:"cmd"`
	Args           []string          `json:"args,omitempty"`
	Cwd            string            `json:"cwd,omitempty"`
	Env            map[string]string `json:"env,omitempty"`
	Health         *Health           `json:"health,omitempty"`
	DependsOn      []string          `json:"depends_on,omitempty"`
	Restart        string            `json:"restart,omitempty"` // always (mặc định) | on-failure | never
	Stop           *Command          `json:"stop,omitempty"`
	StopTimeoutSec int               `json:"stop_timeout_sec,omitempty"`

	// Optional: dịch vụ không bắt buộc. Lỗi/không sẵn sàng không làm hỏng cả bộ, không chặn trang trạng thái,
	// và cổng của nó không bị kiểm tra trước khi chạy.
	Optional bool `json:"optional,omitempty"`
	// RequiresPath: nếu đường dẫn này không tồn tại thì bỏ qua dịch vụ với trạng thái "Chưa cài" (MissingMessage).
	RequiresPath   string `json:"requires_path,omitempty"`
	MissingMessage string `json:"missing_message,omitempty"`
	// NoRestartExitCodes: thoát với các mã này nghĩa là đã có bản khác đang chạy ngoài launcher;
	// không khởi động lại liên tục mà chỉ theo dõi health ("Đang chạy bên ngoài").
	NoRestartExitCodes []int `json:"no_restart_exit_codes,omitempty"`
	// PathAdd: thư mục thêm vào cuối PATH (PATH của người dùng luôn được kế thừa).
	PathAdd []string `json:"path_add,omitempty"`
}

// Config là nội dung runtime/services.json.
type Config struct {
	AppURL     string `json:"app_url"`
	StatusPort int    `json:"status_port,omitempty"` // trang trạng thái khi khởi động (mặc định 8009; -1 = tắt)
	// Vars: biến mặc định cho ${TÊN}; ghi đè bằng biến môi trường hoặc dòng TÊN=giá trị trong .env của bundle.
	Vars     map[string]string `json:"vars,omitempty"`
	Services []Service         `json:"services"`
	FirstRun []Command         `json:"first_run,omitempty"`
	Backup   *Command          `json:"backup,omitempty"`
}

// LoadConfig đọc và kiểm tra file cấu hình.
func LoadConfig(path string) (*Config, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("không đọc được %s: %w", path, err)
	}
	return ParseConfig(b)
}

// ParseConfig phân tích JSON và kiểm tra hợp lệ.
func ParseConfig(b []byte) (*Config, error) {
	b = bytes.TrimPrefix(b, []byte{0xEF, 0xBB, 0xBF}) // bỏ BOM nếu có
	var c Config
	if err := json.Unmarshal(b, &c); err != nil {
		return nil, fmt.Errorf("services.json không phải JSON hợp lệ: %w", err)
	}
	if err := c.Validate(); err != nil {
		return nil, err
	}
	return &c, nil
}

// Validate kiểm tra toàn bộ cấu hình, trả về mọi lỗi tìm thấy.
func (c *Config) Validate() error {
	var errs []error
	add := func(f string, a ...any) { errs = append(errs, fmt.Errorf(f, a...)) }

	if c.AppURL == "" {
		add("thiếu app_url")
	} else if u, err := url.Parse(c.AppURL); err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		add("app_url không hợp lệ: %q", c.AppURL)
	}
	if c.StatusPort < -1 || c.StatusPort > 65535 {
		add("status_port %d không hợp lệ", c.StatusPort)
	}
	if len(c.Services) == 0 {
		add("danh sách services trống")
	}
	names := map[string]bool{}
	for i := range c.Services {
		s := &c.Services[i]
		if s.Name == "" {
			add("services[%d]: thiếu name", i)
			continue
		}
		if names[s.Name] {
			add("trùng tên dịch vụ %q", s.Name)
		}
		names[s.Name] = true
		if s.Cmd == "" {
			add("dịch vụ %q: thiếu cmd", s.Name)
		}
		switch s.Restart {
		case "", "always", "on-failure", "never":
		default:
			add("dịch vụ %q: restart %q không hợp lệ (always|on-failure|never)", s.Name, s.Restart)
		}
		if s.Health != nil {
			if e := s.Health.validate(); e != nil {
				add("dịch vụ %q: %v", s.Name, e)
			}
		}
		if s.Stop != nil {
			switch s.Stop.Mode {
			case "":
				if s.Stop.Cmd == "" {
					add("dịch vụ %q: stop thiếu cmd", s.Name)
				}
			case "kill_pid", "ctrl_break_kill_pid":
			default:
				add("dịch vụ %q: stop.mode %q không hợp lệ (kill_pid|ctrl_break_kill_pid)", s.Name, s.Stop.Mode)
			}
		}
	}
	for _, s := range c.Services {
		for _, d := range s.DependsOn {
			if d == s.Name {
				add("dịch vụ %q phụ thuộc chính nó", s.Name)
			} else if !names[d] {
				add("dịch vụ %q phụ thuộc %q nhưng không tồn tại", s.Name, d)
			}
		}
	}
	if len(errs) == 0 {
		if _, err := c.StartOrder(); err != nil {
			errs = append(errs, err)
		}
	}
	for i, f := range c.FirstRun {
		if f.Cmd == "" {
			add("first_run[%d]: thiếu cmd", i)
		}
	}
	if c.Backup != nil && c.Backup.Cmd == "" {
		add("backup: thiếu cmd")
	}
	return errors.Join(errs...)
}

func (h *Health) validate() error {
	switch h.Type {
	case "tcp":
		if h.Port < 1 || h.Port > 65535 {
			return fmt.Errorf("health tcp: port %d không hợp lệ", h.Port)
		}
	case "http":
		u, err := url.Parse(h.URL)
		if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
			return fmt.Errorf("health http: url không hợp lệ %q", h.URL)
		}
	default:
		return fmt.Errorf("health.type %q không hợp lệ (tcp|http)", h.Type)
	}
	return nil
}

// StartOrder trả về tên dịch vụ theo thứ tự phụ thuộc (phụ thuộc trước).
func (c *Config) StartOrder() ([]string, error) {
	deps := map[string][]string{}
	var all []string
	for _, s := range c.Services {
		deps[s.Name] = s.DependsOn
		all = append(all, s.Name)
	}
	return TopoOrder(all, deps)
}

// TopoOrder sắp xếp tô-pô (DFS, giữ thứ tự khai báo khi không ràng buộc);
// trả lỗi nếu có vòng phụ thuộc.
func TopoOrder(all []string, deps map[string][]string) ([]string, error) {
	const (
		white = iota
		grey
		black
	)
	color := map[string]int{}
	var order, stack []string
	var visit func(n string) error
	visit = func(n string) error {
		switch color[n] {
		case black:
			return nil
		case grey:
			i := 0
			for j, s := range stack {
				if s == n {
					i = j
				}
			}
			cyc := append(append([]string{}, stack[i:]...), n)
			return fmt.Errorf("phụ thuộc vòng tròn: %s", strings.Join(cyc, " -> "))
		}
		color[n] = grey
		stack = append(stack, n)
		for _, d := range deps[n] {
			if err := visit(d); err != nil {
				return err
			}
		}
		stack = stack[:len(stack)-1]
		color[n] = black
		order = append(order, n)
		return nil
	}
	for _, n := range all {
		if err := visit(n); err != nil {
			return nil, err
		}
	}
	return order, nil
}

// Ports trả về các cổng TCP mà cấu hình dự kiến dùng (đã khử trùng lặp).
func (c *Config) Ports() []int { return c.ports(true) }

// RequiredPorts như Ports nhưng bỏ cổng của dịch vụ tuỳ chọn (có thể đang được chương trình khác giữ hợp lệ).
func (c *Config) RequiredPorts() []int { return c.ports(false) }

func (c *Config) ports(withOptional bool) []int {
	seen := map[int]bool{}
	var out []int
	add := func(p int) {
		if p > 0 && !seen[p] {
			seen[p] = true
			out = append(out, p)
		}
	}
	if u, err := url.Parse(c.AppURL); err == nil {
		add(urlPort(u))
	}
	for _, s := range c.Services {
		if s.Health == nil || (s.Optional && !withOptional) {
			continue
		}
		if s.Health.Type == "tcp" {
			add(s.Health.Port)
		} else if u, err := url.Parse(s.Health.URL); err == nil {
			add(urlPort(u))
		}
	}
	return out
}

func urlPort(u *url.URL) int {
	if p := u.Port(); p != "" {
		n, _ := strconv.Atoi(p)
		return n
	}
	switch u.Scheme {
	case "https":
		return 443
	case "http":
		return 80
	}
	return 0
}

var (
	varsMu   sync.RWMutex
	userVars map[string]string // biến từ services.json "vars"
	varsRoot string            // thư mục bundle (để đọc .env)
	varRe    = regexp.MustCompile(`\$\{([A-Za-z_][A-Za-z0-9_]*)\}`)
)

// SetVars đặt nguồn biến cho expand: biến môi trường > .env của bundle > "vars" trong services.json.
func SetVars(cfg *Config, root string) {
	varsMu.Lock()
	defer varsMu.Unlock()
	userVars, varsRoot = nil, root
	if cfg != nil {
		userVars = cfg.Vars
	}
}

// ParseDotEnv đọc nội dung .env (KEY=VALUE, bỏ chú thích, bỏ dấu nháy bao quanh).
func ParseDotEnv(b []byte) map[string]string {
	m := map[string]string{}
	for _, ln := range strings.Split(string(bytes.TrimPrefix(b, []byte{0xEF, 0xBB, 0xBF})), "\n") {
		ln = strings.TrimSpace(ln)
		if ln == "" || strings.HasPrefix(ln, "#") {
			continue
		}
		k, v, ok := strings.Cut(ln, "=")
		if !ok {
			continue
		}
		v = strings.TrimSpace(v)
		if len(v) >= 2 && (v[0] == '"' || v[0] == 0x27) && v[len(v)-1] == v[0] {
			v = v[1 : len(v)-1]
		}
		m[strings.TrimSpace(k)] = v
	}
	return m
}

func lookupVar(name string) (string, bool) {
	if v := os.Getenv(name); v != "" {
		return v, true
	}
	varsMu.RLock()
	root, uv := varsRoot, userVars
	varsMu.RUnlock()
	if root != "" {
		if b, err := os.ReadFile(filepath.Join(root, ".env")); err == nil {
			if v := ParseDotEnv(b)[name]; v != "" {
				return v, true
			}
		}
	}
	if v := uv[name]; v != "" {
		return v, true
	}
	return "", false
}

// expand thay ${ROOT} bằng thư mục bundle và ${TÊN} bằng biến (xem SetVars); biến lạ giữ nguyên.
func expand(s, root string) string {
	if !strings.Contains(s, "${") {
		return s
	}
	return varRe.ReplaceAllStringFunc(s, func(m string) string {
		name := m[2 : len(m)-1]
		if name == "ROOT" {
			return root
		}
		if v, ok := lookupVar(name); ok {
			return v
		}
		return m
	})
}

// resolveCmd: lệnh có dấu / hoặc \ => tương đối với root (nếu chưa tuyệt đối);
// ngược lại tra trong PATH (vd "cmd", "php").
func resolveCmd(cmd, root string) string {
	cmd = expand(cmd, root)
	if strings.ContainsAny(cmd, `/\`) {
		p := filepath.FromSlash(cmd)
		if !filepath.IsAbs(p) {
			p = filepath.Join(root, p)
		}
		return p
	}
	return cmd
}

func resolveDir(cwd, root string) string {
	if cwd == "" {
		return root
	}
	p := filepath.FromSlash(expand(cwd, root))
	if !filepath.IsAbs(p) {
		p = filepath.Join(root, p)
	}
	return filepath.Clean(p)
}

func resolveArgs(args []string, root string) []string {
	out := make([]string, len(args))
	for i, a := range args {
		out[i] = expand(a, root)
	}
	return out
}

func resolveEnv(env map[string]string, root string) []string {
	var out []string
	for k, v := range env {
		out = append(out, k+"="+expand(v, root))
	}
	return out
}

// buildEnv: môi trường của launcher (kế thừa nguyên PATH) + env của dịch vụ + path_add nối cuối PATH.
func buildEnv(base []string, env map[string]string, pathAdd []string, root string) []string {
	out := append([]string(nil), base...)
	out = append(out, resolveEnv(env, root)...)
	if len(pathAdd) == 0 {
		return out
	}
	idx, cur := -1, ""
	for i, kv := range out {
		if k, v, ok := strings.Cut(kv, "="); ok && strings.EqualFold(k, "PATH") {
			idx, cur = i, v
		}
	}
	var add []string
	for _, p := range pathAdd {
		p = filepath.FromSlash(expand(p, root))
		if p != "" && !strings.Contains(";"+strings.ToLower(cur)+";", ";"+strings.ToLower(p)+";") {
			add = append(add, p)
		}
	}
	if len(add) == 0 {
		return out
	}
	np := strings.TrimRight(cur, ";")
	if np != "" {
		np += ";"
	}
	np += strings.Join(add, ";")
	if idx >= 0 {
		out[idx] = "PATH=" + np
	} else {
		out = append(out, "PATH="+np)
	}
	return out
}

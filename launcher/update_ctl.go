package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// updateEnv gom các thao tác bên ngoài mà quy trình cập nhật cần (để kiểm thử bằng bản giả).
type updateEnv struct {
	Root     string
	Log      *Logger
	Progress func(state, msg string, pct int)

	StopServices func()                                       // dừng mọi dịch vụ trừ postgres
	Backup       func() (string, error)                       // sao lưu DB (nil = bỏ qua)
	Run          func(dir, name string, args ...string) error // chạy lệnh phụ (php/pip/npm)
	Restart      func() error                                 // dừng hết rồi chạy lại hết
	PHP          string
	Python       string // python của hub (rỗng = không có)
}

func (e *updateEnv) progress(state, msg string, pct int) {
	e.Log.Printf("Cập nhật [%s] %s", state, msg)
	if e.Progress != nil {
		e.Progress(state, msg, pct)
	}
}

func (e *updateEnv) run(dir, name string, args ...string) error {
	if e.Run == nil {
		return nil
	}
	return e.Run(dir, name, args...)
}

// ApplyPackage cài gói zip đã xác minh sha256. Mọi lỗi sau khi bắt đầu thay đổi đều khôi phục snapshot và chạy lại bản cũ.
func ApplyPackage(env *updateEnv, zipPath string) error {
	root := env.Root
	cur := ReadVersion(root)

	env.progress("verifying", "Đang kiểm tra gói cập nhật…", 5)
	pkg, err := OpenPackage(zipPath)
	if err != nil {
		return err
	}
	defer pkg.Close()
	if !IsNewer(pkg.Version, cur) {
		return fmt.Errorf("gói %s không mới hơn bản đang cài (%s)", pkg.Version, cur)
	}

	env.progress("stopping", "Đang dừng các dịch vụ (giữ lại cơ sở dữ liệu)…", 15)
	if env.StopServices != nil {
		env.StopServices()
	}

	// Chưa đụng vào file nào: lỗi ở đây chỉ cần chạy lại dịch vụ.
	abortEarly := func(e error) error {
		env.progress("restarting", "Đang chạy lại bản hiện tại…", 90)
		if rerr := env.restartSafe(); rerr != nil {
			return fmt.Errorf("%v (và chạy lại dịch vụ lỗi: %v)", e, rerr)
		}
		return e
	}

	env.progress("backup", "Đang sao lưu cơ sở dữ liệu…", 25)
	backup := ""
	if env.Backup != nil {
		if backup, err = env.Backup(); err != nil {
			return abortEarly(fmt.Errorf("sao lưu dữ liệu thất bại, huỷ cập nhật: %w", err))
		}
	}

	env.progress("snapshot", "Đang lưu bản hiện tại để có thể quay lại…", 35)
	mb, merr := os.ReadFile(ManifestPath(root))
	oldManifest, _ := ParseManifest(mb)
	oldReq := fileHash(filepath.Join(root, "xuong-video", "requirements.txt"))
	oldLock := fileHash(filepath.Join(root, "xuong-video", "remotion", "package-lock.json"))
	snapDir, err := TakeSnapshot(root, cur, backup)
	if err != nil {
		return abortEarly(err)
	}

	// Từ đây có thể đã sửa file: lỗi => khôi phục.
	failRestore := func(e error) error {
		env.progress("rollback", "Có lỗi, đang khôi phục bản "+cur+"…", 88)
		msg := e.Error()
		if rerr := RestoreSnapshot(root, snapDir, pkg.Manifest, env.Log); rerr != nil {
			msg += "; khôi phục cũng lỗi: " + rerr.Error() + " (bản cũ nằm ở " + snapDir + ")"
		} else {
			msg += ". Đã khôi phục bản " + cur
		}
		env.run(root, env.PHP, "artisan", "optimize:clear")
		if rerr := env.restartSafe(); rerr != nil {
			msg += "; chạy lại dịch vụ lỗi: " + rerr.Error()
		}
		if backup != "" {
			msg += ". Bản sao lưu dữ liệu: " + backup
		}
		return errors.New(msg)
	}

	env.progress("installing", "Đang cài bản "+pkg.Version+"…", 50)
	if _, err := pkg.Extract(root, env.Log); err != nil {
		return failRestore(err)
	}
	if merr == nil {
		n := DeleteStale(root, StaleFiles(oldManifest, pkg.Manifest), env.Log)
		env.Log.Printf("Cập nhật: đã xoá %d file không còn trong bản mới", n)
	}
	newMB, err := pkg.ManifestBytes()
	if err != nil {
		return failRestore(err)
	}
	if err := os.MkdirAll(filepath.Dir(ManifestPath(root)), 0o755); err != nil {
		return failRestore(err)
	}
	if err := os.WriteFile(ManifestPath(root), newMB, 0o644); err != nil {
		return failRestore(err)
	}

	env.progress("migrating", "Đang cập nhật cơ sở dữ liệu…", 65)
	if err := env.run(root, env.PHP, "artisan", "migrate", "--force"); err != nil {
		return failRestore(fmt.Errorf("migrate lỗi: %w", err))
	}
	if err := env.run(root, env.PHP, "artisan", "optimize:clear"); err != nil {
		return failRestore(fmt.Errorf("optimize:clear lỗi: %w", err))
	}

	if fileHash(filepath.Join(root, "xuong-video", "requirements.txt")) != oldReq && fileExists(filepath.Join(root, "xuong-video", "requirements.txt")) {
		env.progress("post", "Đang cập nhật thư viện Python của Xưởng Video…", 75)
		if env.Python != "" && fileExists(env.Python) {
			if err := env.run(filepath.Join(root, "xuong-video"), env.Python, "-m", "pip", "install", "-r", "requirements.txt"); err != nil {
				return failRestore(fmt.Errorf("pip install lỗi: %w", err))
			}
		} else {
			env.Log.Printf("Cập nhật: requirements.txt đổi nhưng chưa có Python của hub, bỏ qua pip")
		}
	}
	lock := filepath.Join(root, "xuong-video", "remotion", "package-lock.json")
	if fileHash(lock) != oldLock && fileExists(lock) {
		env.progress("post", "Đang cập nhật thư viện Remotion (npm ci)…", 80)
		if npm, err := exec.LookPath("npm.cmd"); err == nil {
			if err := env.run(filepath.Dir(lock), npm, "ci"); err != nil {
				return failRestore(fmt.Errorf("npm ci lỗi: %w", err))
			}
		} else {
			env.Log.Printf("Cập nhật: package-lock.json đổi nhưng không tìm thấy npm, bỏ qua")
		}
	}

	env.progress("restarting", "Đang khởi động lại các dịch vụ…", 92)
	if err := env.restartSafe(); err != nil {
		return failRestore(fmt.Errorf("không khởi động được bản mới: %w", err))
	}
	PruneSnapshots(root, keepSnapshots)
	env.progress("done", "Đã cập nhật lên bản "+pkg.Version, 100)
	return nil
}

func (e *updateEnv) restartSafe() error {
	if e.Restart == nil {
		return nil
	}
	return e.Restart()
}

func fileExists(p string) bool {
	_, err := os.Stat(p)
	return err == nil
}

// RollbackLatest quay lại snapshot mới nhất (runtime/ban-cu). Dữ liệu (DB) giữ nguyên, chỉ đổi mã.
func RollbackLatest(env *updateEnv) error {
	root := env.Root
	snaps := ListSnapshots(root)
	if len(snaps) == 0 {
		return errors.New("chưa có bản cũ nào để quay lại")
	}
	s := snaps[0]
	env.progress("stopping", "Đang dừng các dịch vụ…", 15)
	if env.StopServices != nil {
		env.StopServices()
	}
	if env.Backup != nil {
		env.progress("backup", "Đang sao lưu cơ sở dữ liệu…", 30)
		if _, err := env.Backup(); err != nil {
			env.Log.Printf("Quay lại: sao lưu lỗi (vẫn tiếp tục): %v", err)
		}
	}
	env.progress("rollback", "Đang khôi phục bản "+s.Version+"…", 50)
	mb, _ := os.ReadFile(ManifestPath(root))
	cur, _ := ParseManifest(mb)
	if err := RestoreSnapshot(root, s.Dir, cur, env.Log); err != nil {
		env.restartSafe()
		return err
	}
	os.RemoveAll(s.Dir)
	env.run(root, env.PHP, "artisan", "optimize:clear")
	env.progress("restarting", "Đang khởi động lại các dịch vụ…", 90)
	if err := env.restartSafe(); err != nil {
		return fmt.Errorf("đã khôi phục mã nhưng không khởi động được: %w", err)
	}
	env.progress("done", "Đã quay lại bản "+s.Version, 100)
	return nil
}

// ---- Updater: trạng thái + API ----

type updatePrefs struct {
	AutoCheck       *bool     `json:"auto_check,omitempty"`
	NotifiedVersion string    `json:"notified_version,omitempty"`
	LastDaily       time.Time `json:"last_daily,omitempty"`
}

func (p updatePrefs) auto() bool { return p.AutoCheck == nil || *p.AutoCheck }

// Updater điều phối kiểm tra / tải / cài đặt / quay lại, và cho trang trạng thái hỏi tiến độ.
type Updater struct {
	root    string
	cfg     *Config
	log     *Logger
	sup     *Supervisor
	checker *UpdateChecker
	backup  func() (string, error)
	hc      *http.Client

	// OnAvailable được gọi (một lần cho mỗi phiên bản) khi phát hiện bản mới trong lần kiểm tra hằng ngày.
	OnAvailable func(version string)

	mu       sync.Mutex
	running  bool
	state    string // idle | checking | downloading | verifying | stopping | backup | snapshot | installing | migrating | post | restarting | rollback | done | error
	message  string
	percent  int
	errText  string
	from, to string
	started  time.Time
	finished time.Time
}

func NewUpdater(a *App) *Updater {
	u := &Updater{root: a.root, cfg: a.cfg, log: a.log, sup: a.sup, state: "idle",
		checker: &UpdateChecker{Root: a.root}, hc: &http.Client{}}
	u.backup = func() (string, error) { return RunBackup(a.cfg, a.root, a.log) }
	return u
}

func (u *Updater) Busy() bool {
	u.mu.Lock()
	defer u.mu.Unlock()
	return u.running
}

func prefsPath(root string) string { return filepath.Join(root, "runtime", "update-prefs.json") }

func loadPrefs(root string) updatePrefs {
	var p updatePrefs
	if b, err := os.ReadFile(prefsPath(root)); err == nil {
		json.Unmarshal(b, &p)
	}
	return p
}

func savePrefs(root string, p updatePrefs) error {
	b, _ := json.Marshal(p)
	return os.WriteFile(prefsPath(root), b, 0o644)
}

func (u *Updater) setState(state, msg string, pct int) {
	u.mu.Lock()
	u.state, u.message, u.percent = state, msg, pct
	u.mu.Unlock()
}

func (u *Updater) env() *updateEnv {
	php := resolveCmd("runtime/php/php.exe", u.root)
	e := &updateEnv{Root: u.root, Log: u.log, PHP: php, Backup: u.backup, Progress: u.setState}
	e.StopServices = func() { u.sup.StopExcept("postgres") }
	e.Restart = func() error { return u.sup.Restart() }
	var svcEnv []string
	for _, s := range u.cfg.Services {
		if s.Name == "xuong-video" {
			e.Python = resolveCmd(s.Cmd, u.root)
			svcEnv = buildEnv(os.Environ(), s.Env, s.PathAdd, u.root)
		}
	}
	if svcEnv == nil {
		svcEnv = os.Environ()
	}
	e.Run = func(dir, name string, args ...string) error { return runLogged(dir, name, args, svcEnv, u.log) }
	return e
}

// runLogged chạy lệnh ẩn, giới hạn thời gian; lỗi kèm đoạn cuối output.
func runLogged(dir, name string, args, env []string, log *Logger) error {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Dir = dir
	cmd.Env = env
	cmd.SysProcAttr = hiddenAttr()
	out, err := cmd.CombinedOutput()
	tail := strings.TrimSpace(string(out))
	if len(tail) > 600 {
		tail = tail[len(tail)-600:]
	}
	log.Printf("Chạy: %s %s -> %v", filepath.Base(name), strings.Join(args, " "), err)
	if err != nil {
		return fmt.Errorf("%v: %s", err, tail)
	}
	return nil
}

var errBusy = errors.New("đang có một thao tác cập nhật khác")

func (u *Updater) begin(state, msg string) (func(err error), error) {
	u.mu.Lock()
	if u.running {
		u.mu.Unlock()
		return nil, errBusy
	}
	u.running = true
	u.state, u.message, u.percent, u.errText = state, msg, 0, ""
	u.from, u.to = ReadVersion(u.root), ""
	u.started, u.finished = time.Now(), time.Time{}
	u.mu.Unlock()
	return func(err error) {
		u.mu.Lock()
		defer u.mu.Unlock()
		u.running = false
		u.finished = time.Now()
		if err != nil {
			u.state, u.errText, u.message = "error", err.Error(), "Cập nhật thất bại"
		} else {
			u.state, u.percent = "done", 100
		}
	}, nil
}

// StartUpdate tải bản mới nhất và cài (chạy nền).
func (u *Updater) StartUpdate() error {
	if UpdateRepo() == "" {
		return errNotConfigured
	}
	c, err := u.checker.Check(false)
	if err != nil {
		return err
	}
	if c == nil || c.Latest == nil {
		msg := "chưa có thông tin bản mới"
		if c != nil && c.Error != "" {
			msg = c.Error
		}
		return errors.New(msg)
	}
	rel := c.Latest
	if !IsNewer(rel.Version, ReadVersion(u.root)) {
		return errors.New("đang dùng bản mới nhất")
	}
	done, err := u.begin("downloading", "Đang tải bản "+rel.Version+"…")
	if err != nil {
		return err
	}
	u.mu.Lock()
	u.to = rel.Version
	u.mu.Unlock()
	go func() {
		var rerr error
		defer func() { done(rerr) }()
		defer func() {
			if r := recover(); r != nil {
				rerr = fmt.Errorf("lỗi nội bộ: %v", r)
				u.log.Printf("Cập nhật panic: %v", r)
			}
		}()
		dir := filepath.Join(u.root, "runtime", "tai-ve")
		os.RemoveAll(dir)
		zipPath, err := DownloadRelease(context.Background(), rel, dir, u.hc, func(d, t int64) {
			pct := 0
			if t > 0 {
				pct = int(d * 10 / t) // 0..10%
			}
			u.setState("downloading", fmt.Sprintf("Đang tải bản %s… %d/%d MB", rel.Version, d>>20, t>>20), pct)
		})
		if err != nil {
			rerr = fmt.Errorf("tải bản cập nhật lỗi: %w", err)
			return
		}
		defer os.RemoveAll(dir)
		rerr = ApplyPackage(u.env(), zipPath)
	}()
	return nil
}

// StartRollback quay lại bản trước (chạy nền).
func (u *Updater) StartRollback() error {
	if len(ListSnapshots(u.root)) == 0 {
		return errors.New("chưa có bản cũ nào để quay lại")
	}
	done, err := u.begin("rollback", "Đang quay lại bản trước…")
	if err != nil {
		return err
	}
	go func() {
		var rerr error
		defer func() { done(rerr) }()
		defer func() {
			if r := recover(); r != nil {
				rerr = fmt.Errorf("lỗi nội bộ: %v", r)
			}
		}()
		rerr = RollbackLatest(u.env())
	}()
	return nil
}

// Status dựng JSON cho /api/update/status (đọc cache, không gọi mạng).
func (u *Updater) Status() map[string]any {
	u.mu.Lock()
	st := map[string]any{
		"state": u.state, "message": u.message, "percent": u.percent, "error": u.errText,
		"busy": u.running, "from": u.from, "to": u.to,
	}
	u.mu.Unlock()
	cur := ReadVersion(u.root)
	repo := UpdateRepo()
	st["ok"] = true
	st["current"] = cur
	st["configured"] = repo != ""
	st["repo"] = repo
	st["auto_check"] = loadPrefs(u.root).auto()
	st["latest"] = nil
	st["update_available"] = false
	st["check_error"] = ""
	st["checked_at"] = ""
	if c := loadCheckCache(u.root); c != nil && c.Repo == repo && repo != "" {
		st["checked_at"] = c.CheckedAt.Format(time.RFC3339)
		st["check_error"] = c.Error
		if c.Latest != nil {
			st["latest"] = c.Latest
			st["update_available"] = IsNewer(c.Latest.Version, cur)
		}
	}
	snaps := ListSnapshots(u.root)
	st["can_rollback"] = len(snaps) > 0
	st["rollback_version"] = ""
	if len(snaps) > 0 {
		st["rollback_version"] = snaps[0].Version
	}
	st["launcher_pending"] = fileExists(filepath.Join(u.root, newExeName))
	return st
}

// CheckNow kiểm tra GitHub (đồng bộ).
func (u *Updater) CheckNow(force bool) error {
	_, err := u.checker.Check(force)
	return err
}

// DailyCheck: gọi định kỳ; mỗi ~24 giờ kiểm tra một lần (nếu bật) và báo khi có bản mới chưa báo.
func (u *Updater) DailyCheck() {
	p := loadPrefs(u.root)
	if !p.auto() || UpdateRepo() == "" || time.Since(p.LastDaily) < 23*time.Hour || u.Busy() {
		return
	}
	c, err := u.checker.Check(true)
	if err != nil || c == nil || c.Error != "" && c.Latest == nil {
		return
	}
	p.LastDaily = time.Now()
	if c.Latest != nil && IsNewer(c.Latest.Version, ReadVersion(u.root)) && p.NotifiedVersion != c.Latest.Version {
		p.NotifiedVersion = c.Latest.Version
		u.log.Printf("Có bản mới %s", c.Latest.Version)
		if u.OnAvailable != nil {
			u.OnAvailable(c.Latest.Version)
		}
		go u.telegram(c.Latest.Version)
	}
	savePrefs(u.root, p)
}

// telegram nhờ Laravel gửi tin (dùng cấu hình Telegram sẵn có); lỗi/không cấu hình thì bỏ qua.
func (u *Updater) telegram(ver string) {
	php := resolveCmd("runtime/php/php.exe", u.root)
	if !fileExists(php) {
		return
	}
	runLogged(u.root, php, []string{"artisan", "fork:update-notify", ver}, os.Environ(), u.log)
}

// Loop: kiểm tra sau khi khởi động ~2 phút rồi mỗi giờ xem đã đến hạn hằng ngày chưa.
func (u *Updater) Loop(quit func() bool) {
	time.Sleep(2 * time.Minute)
	for {
		if quit() {
			return
		}
		u.DailyCheck()
		time.Sleep(time.Hour)
	}
}

// AvailableVersion trả bản mới đã biết (từ cache), rỗng nếu không có.
func (u *Updater) AvailableVersion() string {
	if c := loadCheckCache(u.root); c != nil && c.Latest != nil && c.Repo == UpdateRepo() && IsNewer(c.Latest.Version, ReadVersion(u.root)) {
		return c.Latest.Version
	}
	return ""
}

// ---- HTTP ----

// allowedOrigins: nguồn web được phép đọc /api/update/status (trang Laravel ở app_url).
func allowedOrigins(appURL string) map[string]bool {
	m := map[string]bool{}
	u, err := url.Parse(appURL)
	if err != nil || u.Host == "" {
		return m
	}
	add := func(host string) {
		m[u.Scheme+"://"+host] = true
	}
	add(u.Host)
	port := u.Port()
	for _, h := range []string{"localhost", "127.0.0.1"} {
		if port != "" {
			add(h + ":" + port)
		} else {
			add(h)
		}
	}
	return m
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

// registerUpdateRoutes gắn /api/update*. authed kiểm tra token + loopback + POST.
func registerUpdateRoutes(mux *http.ServeMux, u *Updater, appURL string, authed func(*http.Request) bool) {
	origins := allowedOrigins(appURL)
	mux.HandleFunc("/api/update/status", func(w http.ResponseWriter, r *http.Request) {
		if o := r.Header.Get("Origin"); o != "" && origins[o] {
			w.Header().Set("Access-Control-Allow-Origin", o)
			w.Header().Set("Vary", "Origin")
		}
		if !loopbackHost(r.Host) {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		writeJSON(w, http.StatusOK, u.Status())
	})
	post := func(h func(w http.ResponseWriter, r *http.Request)) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			if !authed(r) {
				writeJSON(w, http.StatusForbidden, map[string]any{"ok": false, "error": "forbidden"})
				return
			}
			h(w, r)
		}
	}
	fail := func(w http.ResponseWriter, code int, err error) {
		writeJSON(w, code, map[string]any{"ok": false, "error": err.Error()})
	}
	mux.HandleFunc("/api/update/check", post(func(w http.ResponseWriter, r *http.Request) {
		if err := u.CheckNow(r.URL.Query().Get("force") == "1"); err != nil {
			fail(w, http.StatusBadRequest, err)
			return
		}
		writeJSON(w, http.StatusOK, u.Status())
	}))
	mux.HandleFunc("/api/update", post(func(w http.ResponseWriter, r *http.Request) {
		if err := u.StartUpdate(); err != nil {
			code := http.StatusBadRequest
			if err == errBusy {
				code = http.StatusConflict
			}
			fail(w, code, err)
			return
		}
		writeJSON(w, http.StatusAccepted, map[string]any{"ok": true})
	}))
	mux.HandleFunc("/api/update/rollback", post(func(w http.ResponseWriter, r *http.Request) {
		if err := u.StartRollback(); err != nil {
			code := http.StatusBadRequest
			if err == errBusy {
				code = http.StatusConflict
			}
			fail(w, code, err)
			return
		}
		writeJSON(w, http.StatusAccepted, map[string]any{"ok": true})
	}))
	mux.HandleFunc("/api/update/prefs", post(func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			AutoCheck *bool `json:"auto_check"`
		}
		if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 4096)).Decode(&body); err != nil || body.AutoCheck == nil {
			fail(w, http.StatusBadRequest, errors.New("thiếu auto_check"))
			return
		}
		p := loadPrefs(u.root)
		p.AutoCheck = body.AutoCheck
		if err := savePrefs(u.root, p); err != nil {
			fail(w, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, u.Status())
	}))
}

// runCLIUpdate: TikTokAuto.exe --update <zip>. Chạy khi launcher chưa chạy; trả mã thoát.
func runCLIUpdate(a *App, zipPath string) int {
	abs, err := filepath.Abs(zipPath)
	if err != nil || !fileExists(abs) {
		fmt.Println("Không thấy file:", zipPath)
		return 2
	}
	if err := a.sup.Start(); err != nil {
		fmt.Println("Không khởi động được dịch vụ để cập nhật:", err)
		a.sup.Stop()
		return 1
	}
	u := NewUpdater(a)
	err = ApplyPackage(u.env(), abs)
	a.sup.Stop()
	if err != nil {
		fmt.Println("LỖI:", err)
		return 1
	}
	fmt.Println("Đã cập nhật lên bản", ReadVersion(a.root))
	if fileExists(filepath.Join(a.root, newExeName)) {
		fmt.Println("Launcher mới sẽ được áp dụng ở lần mở TikTok Auto Kid tiếp theo.")
	}
	return 0
}

// ---- Thay exe khi khởi động ----

// swapNewExe: nếu có TikTokAuto.new.exe cạnh exe đang chạy thì thay thế rồi chạy lại chính mình.
// Trả true nếu đã chạy lại bản mới (tiến trình hiện tại nên thoát ngay).
func swapNewExe(self string, args []string, pid int) bool {
	dir := filepath.Dir(self)
	if !strings.EqualFold(filepath.Base(self), exeName) {
		return false
	}
	newP := filepath.Join(dir, newExeName)
	oldP := filepath.Join(dir, oldExeName)
	if !validExe(newP) {
		os.Remove(oldP) // dọn bản cũ của lần thay trước
		return false
	}
	os.Remove(oldP)
	if err := os.Rename(self, oldP); err != nil {
		return false
	}
	if err := os.Rename(newP, self); err != nil {
		os.Rename(oldP, self)
		return false
	}
	var keep []string
	for _, a := range args {
		if !strings.HasPrefix(a, "--after-swap") && !strings.HasPrefix(a, "-after-swap") {
			keep = append(keep, a)
		}
	}
	cmd := exec.Command(self, append([]string{fmt.Sprintf("--after-swap=%d", pid)}, keep...)...)
	if err := cmd.Start(); err != nil {
		// chạy lại thất bại: trả về bản cũ để người dùng vẫn mở được
		os.Rename(self, newP)
		os.Rename(oldP, self)
		return false
	}
	return true
}

// validExe: file tồn tại, đủ lớn và có chữ ký "MZ".
func validExe(p string) bool {
	f, err := os.Open(p)
	if err != nil {
		return false
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil || st.Size() < 1<<20 {
		return false
	}
	var hdr [2]byte
	if _, err := f.Read(hdr[:]); err != nil {
		return false
	}
	return hdr[0] == 'M' && hdr[1] == 'Z'
}

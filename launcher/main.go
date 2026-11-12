package main

import (
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"
)

const appTitle = "TikTok Auto Kid"

var (
	flagConsole   = flag.Bool("console", false, "chạy không có khay hệ thống, ghi log ra màn hình (để gỡ lỗi)")
	flagCheck     = flag.Bool("check", false, "kiểm tra services.json rồi thoát")
	flagAutostart = flag.Bool("autostart", false, "(nội bộ) khởi động cùng Windows: không tự mở trình duyệt")
	flagNoBrowser = flag.Bool("no-browser", false, "không tự mở trình duyệt khi khởi động xong")
	flagRoot      = flag.String("root", "", "thư mục bundle (mặc định: thư mục chứa exe)")
	flagConfig    = flag.String("config", "", "đường dẫn services.json (mặc định: <root>/runtime/services.json)")
	flagExitAfter = flag.Int("exit-after", 0, "(gỡ lỗi) tự thoát sau N giây kể từ khi khởi động xong")
	flagWatchPG   = flag.Int("watch-pg", 0, "(nội bộ) chờ PID launcher chết rồi dừng Postgres")
	flagSendBreak = flag.Int("send-break", 0, "(nội bộ) gửi CTRL_BREAK tới PID")
	flagUpdate    = flag.String("update", "", "cài gói cập nhật tiktok-auto-kid-<phiên bản>.zip (khi launcher chưa chạy) rồi thoát")
	flagAfterSwap = flag.Int("after-swap", 0, "(nội bộ) chờ PID launcher cũ thoát (sau khi thay TikTokAuto.exe)")
)

// findRoot: thư mục của exe; nếu không có runtime/services.json thì tìm ở các thư mục cha.
func findRoot(start string) (string, bool) {
	dir := start
	for i := 0; i < 5; i++ {
		if _, err := os.Stat(filepath.Join(dir, "runtime", "services.json")); err == nil {
			return dir, true
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return start, false
}

func main() {
	flag.Parse()
	if *flagSendBreak > 0 {
		os.Exit(runSendBreakHelper(uint32(*flagSendBreak)))
	}
	if *flagWatchPG > 0 {
		r, _ := filepath.Abs(*flagRoot)
		os.Exit(runPGWatchdog(uint32(*flagWatchPG), r))
	}
	if *flagConsole || *flagCheck || *flagUpdate != "" {
		attachConsole()
	}
	if *flagAfterSwap > 0 {
		waitPID(uint32(*flagAfterSwap), 15*time.Second)
	}

	root := *flagRoot
	if root == "" {
		exe, err := os.Executable()
		if err != nil {
			fatal(err.Error())
		}
		root, _ = findRoot(filepath.Dir(exe))
	}
	root, _ = filepath.Abs(root)
	cfgPath := *flagConfig
	if cfgPath == "" {
		cfgPath = filepath.Join(root, "runtime", "services.json")
	}

	cfg, err := LoadConfig(cfgPath)
	SetVars(cfg, root)
	if *flagCheck {
		os.Exit(runCheck(cfgPath, root, cfg, err))
	}
	if err != nil {
		fatal("Không đọc được cấu hình:\n" + err.Error())
	}

	if running, err := acquireSingleInstance(); err == nil && running {
		// lần chạy thứ hai: app đã lên thì mở thẳng; chưa lên thì mở trang trạng thái
		if PortInUse(urlPort(mustParseURL(cfg.AppURL))) || cfg.StatusPortOrDefault() == 0 {
			openPath(cfg.AppURL)
		} else {
			openPath(fmt.Sprintf("http://127.0.0.1:%d/", cfg.StatusPortOrDefault()))
		}
		return
	}

	if exe, err := os.Executable(); err == nil {
		if *flagUpdate == "" && !*flagConsole && swapNewExe(exe, os.Args[1:], os.Getpid()) {
			return // đã thay TikTokAuto.exe bằng bản mới và chạy lại
		}
	}

	if err := initJob(); err != nil {
		fmt.Fprintln(os.Stderr, "cảnh báo: không tạo được Job Object:", err)
	}

	writers := []io.Writer{}
	if lw, err := NewRotatingWriter(filepath.Join(root, "runtime", "logs", "launcher.log"), logMaxBytes, logKeep); err == nil {
		writers = append(writers, lw)
	}
	if *flagConsole {
		writers = append(writers, os.Stdout)
	}
	log := NewLogger(writers...)
	log.Printf("Launcher khởi động. root=%s", root)

	sup, err := NewSupervisor(cfg, root, log)
	if err != nil {
		fatal(err.Error())
	}
	app := &App{cfg: cfg, root: root, log: log, sup: sup}
	app.updater = NewUpdater(app)
	if *flagUpdate != "" {
		os.Exit(runCLIUpdate(app, *flagUpdate))
	}
	if *flagConsole {
		app.runConsole()
	} else {
		app.runTray()
	}
}

func fatal(msg string) {
	if *flagConsole || *flagCheck {
		fmt.Fprintln(os.Stderr, msg)
	} else {
		messageBox(appTitle, msg)
	}
	os.Exit(1)
}

// runCheck in báo cáo kiểm tra; trả mã thoát.
func runCheck(path, root string, cfg *Config, loadErr error) int {
	fmt.Println("Kiểm tra:", path)
	if loadErr != nil {
		fmt.Println("LỖI:", strings.ReplaceAll(loadErr.Error(), "\n", "\n     "))
		return 1
	}
	bad := 0
	exists := func(label, cmd string) {
		p := resolveCmd(cmd, root)
		if strings.ContainsAny(cmd, `/\`) {
			if _, err := os.Stat(p); err != nil {
				fmt.Printf("  THIẾU  %s: %s\n", label, p)
				bad++
				return
			}
		}
		fmt.Printf("  ok     %s: %s\n", label, p)
	}
	order, _ := cfg.StartOrder()
	fmt.Println("Thứ tự khởi động:", strings.Join(order, " -> "))
	fmt.Println("Cổng sử dụng:", cfg.Ports())
	for _, s := range cfg.Services {
		if s.RequiresPath != "" {
			if _, err := os.Stat(resolveDir(s.RequiresPath, root)); err != nil {
				fmt.Printf("  bỏ qua dịch vụ %s: chưa cài (%s)\n", s.Name, resolveDir(s.RequiresPath, root))
				continue
			}
		}
		exists("dịch vụ "+s.Name, s.Cmd)
		if s.Stop != nil {
			exists("  stop "+s.Name, s.Stop.Cmd)
		}
	}
	for _, f := range cfg.FirstRun {
		exists("first_run "+f.Name, f.Cmd)
	}
	if cfg.Backup != nil {
		exists("backup", cfg.Backup.Cmd)
	}
	if bad > 0 {
		fmt.Printf("Có %d tệp thực thi bị thiếu.\n", bad)
		return 1
	}
	fmt.Println("Cấu hình hợp lệ.")
	return 0
}

// App gom các thành phần của launcher.
type App struct {
	cfg  *Config
	root string
	log  *Logger
	sup  *Supervisor

	mu       sync.Mutex
	quitting bool
	lastMsg  string

	status     *StatusServer
	restarting bool
	updater    *Updater
}

func mustParseURL(s string) *url.URL {
	u, _ := url.Parse(s)
	if u == nil {
		u = &url.URL{}
	}
	return u
}

// openStartPage trả URL nên mở lúc khởi động/bấm "Mở": trang trạng thái nếu app chưa sẵn sàng.
func (a *App) openTarget() string {
	if a.status != nil {
		if snap := BuildSnapshot(a.sup, a.cfg, a.root); !snap.Ready {
			return a.status.URL
		}
	}
	return a.cfg.AppURL
}

// restart dừng rồi chạy lại toàn bộ dịch vụ (bỏ qua nếu đang restart).
func (a *App) restart() {
	a.mu.Lock()
	if a.restarting || a.quitting || (a.updater != nil && a.updater.Busy()) {
		a.mu.Unlock()
		return
	}
	a.restarting = true
	a.mu.Unlock()
	go func() {
		defer func() {
			a.mu.Lock()
			a.restarting = false
			a.mu.Unlock()
		}()
		a.log.Printf("Khởi động lại")
		a.sup.Stop()
		a.mu.Lock()
		q := a.quitting
		a.mu.Unlock()
		if q {
			return
		}
		if err := a.sup.Start(); err == nil {
			a.maybeDailyBackup()
		}
	}()
}

// start khởi động nền; khi xong tuỳ chọn mở trình duyệt và sao lưu hằng ngày.
func (a *App) start(openBrowser bool) {
	openBrowser = openBrowser && !*flagNoBrowser && !*flagConsole
	if port := a.cfg.StatusPortOrDefault(); port > 0 {
		ss, err := StartStatusServer(port, NewStatusHandlerFull(a.sup, a.cfg, a.root, a.restart, writeControlToken(a.root, a.log), a.updater))
		if err != nil {
			a.log.Printf("Không mở được trang trạng thái cổng %d: %v", port, err)
		} else {
			a.status = ss
			a.log.Printf("Trang trạng thái: %s", ss.URL)
			if openBrowser {
				openPath(ss.URL)
			}
		}
	}
	go func() {
		if err := a.sup.Start(); err != nil {
			a.log.Printf("Khởi động thất bại: %v", err)
			return
		}
		if openBrowser && a.status == nil {
			openPath(a.cfg.AppURL)
		}
		a.maybeDailyBackup()
	}()
}

// writeControlToken tạo token ngẫu nhiên mỗi lần chạy, lưu runtime/control.token cho app Laravel đọc
// (để gọi /api/restart trên 127.0.0.1). Trả "" nếu không ghi được (endpoint sẽ tắt).
func writeControlToken(root string, log *Logger) string {
	b := make([]byte, 24)
	if _, err := rand.Read(b); err != nil {
		return ""
	}
	tok := hex.EncodeToString(b)
	if err := os.WriteFile(filepath.Join(root, "runtime", "control.token"), []byte(tok), 0o600); err != nil {
		log.Printf("Không ghi được control.token: %v", err)
		return ""
	}
	return tok
}

func (a *App) maybeDailyBackup() {
	if a.cfg.Backup == nil || (a.updater != nil && a.updater.Busy()) {
		return
	}
	if st, _ := a.sup.Summary(); st != StatusRunning {
		return
	}
	if DailyBackupDue(BackupDir(a.root), time.Now()) {
		a.log.Printf("Sao lưu hằng ngày…")
		if _, err := RunBackup(a.cfg, a.root, a.log); err != nil {
			a.log.Printf("Sao lưu hằng ngày lỗi: %v", err)
		}
	}
}

func (a *App) isQuitting() bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.quitting
}

func (a *App) dailyLoop() {
	for range time.Tick(time.Hour) {
		a.mu.Lock()
		q := a.quitting
		a.mu.Unlock()
		if q {
			return
		}
		a.maybeDailyBackup()
	}
}

// shutdown dừng toàn bộ dịch vụ (chỉ chạy một lần).
func (a *App) shutdown() {
	a.mu.Lock()
	if a.quitting {
		a.mu.Unlock()
		return
	}
	a.quitting = true
	a.mu.Unlock()
	a.log.Printf("Đang thoát, dừng các dịch vụ…")
	a.sup.Stop()
	a.status.Close()
	a.log.Printf("Đã dừng xong.")
}

func (a *App) runConsole() {
	a.sup.Notify = func(t, m string) {}
	a.start(false)
	go a.dailyLoop()
	go a.updater.Loop(a.isQuitting)
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	var after <-chan time.Time
	if *flagExitAfter > 0 {
		after = time.After(time.Duration(*flagExitAfter) * time.Second)
	}
	// báo trạng thái định kỳ
	tick := time.NewTicker(2 * time.Second)
	defer tick.Stop()
	last := ""
	for {
		select {
		case <-sig:
			a.shutdown()
			return
		case <-after:
			a.shutdown()
			return
		case <-tick.C:
			var parts []string
			for _, s := range a.sup.Statuses() {
				parts = append(parts, s.Name+"="+s.Status.Label())
			}
			if cur := strings.Join(parts, "  "); cur != last {
				last = cur
				a.log.Printf("Trạng thái: %s", cur)
			}
		}
	}
}

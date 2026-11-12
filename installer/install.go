package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"golang.org/x/sys/windows/registry"
)

// InstallOpts là lựa chọn của người dùng ở các màn hình trước.
type InstallOpts struct {
	Dir       string `json:"dir"`
	Data      string `json:"data"`
	Desktop   bool   `json:"desktop"`
	Autostart bool   `json:"autostart"`
}

// lineState gom kết quả phân tích đầu ra của cai-dat.ps1.
type lineState struct {
	fatal string
	warns []string
}

func (a *App) startInstall(o InstallOpts) error {
	a.mu.Lock()
	if a.busy {
		a.mu.Unlock()
		return fmt.Errorf("đang chạy")
	}
	a.busy = true
	a.mu.Unlock()
	o.Dir = filepath.Clean(strings.TrimSpace(o.Dir))
	o.Data = filepath.Clean(strings.TrimSpace(o.Data))
	a.installDir = o.Dir
	a.dataDir = o.Data
	go func() {
		defer func() { a.mu.Lock(); a.busy = false; a.mu.Unlock() }()
		if *fDemo || *fDemoSan {
			a.demoInstall(o)
			return
		}
		a.doInstall(o)
	}()
	return nil
}

// parseTD đọc "##TD 42|phan-mem|thông điệp".
func parseTD(line string) (pct float64, stage, msg string, ok bool) {
	rest := strings.TrimPrefix(line, "##TD ")
	parts := strings.SplitN(rest, "|", 3)
	if len(parts) < 2 {
		return
	}
	v, err := strconv.ParseFloat(strings.TrimSpace(parts[0]), 64)
	if err != nil {
		return
	}
	pct = v
	stage = strings.TrimSpace(parts[1])
	if len(parts) == 3 {
		msg = strings.TrimSpace(parts[2])
	}
	return pct, stage, msg, true
}

func (a *App) handleLine(raw string, st *lineState) {
	line := strings.TrimRight(strings.TrimPrefix(raw, "\xef\xbb\xbf"), "\r\n ")
	if line == "" {
		return
	}
	a.logf("%s", line)
	switch {
	case strings.HasPrefix(line, "##TD-LOI"):
		st.fatal = strings.TrimSpace(strings.TrimPrefix(line, "##TD-LOI"))
		a.emit(map[string]any{"t": "log", "line": "LỖI: " + st.fatal})
	case strings.HasPrefix(line, "##TD-CB"):
		m := strings.TrimSpace(strings.TrimPrefix(line, "##TD-CB"))
		st.warns = append(st.warns, m)
		a.emit(map[string]any{"t": "warn", "msg": m})
		a.emit(map[string]any{"t": "log", "line": "Cảnh báo: " + m})
	case strings.HasPrefix(line, "##TD "):
		if p, s, m, ok := parseTD(line); ok {
			a.emit(map[string]any{"t": "progress", "pct": p, "stage": s, "msg": m})
		}
	default:
		a.emit(map[string]any{"t": "log", "line": line})
	}
}

func (a *App) logf(format string, args ...any) {
	if a.logPath == "" {
		return
	}
	f, err := os.OpenFile(a.logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	defer f.Close()
	fmt.Fprintf(f, "%s %s\r\n", time.Now().Format("2006-01-02 15:04:05"), fmt.Sprintf(format, args...))
}

func (a *App) fail(msg string) {
	a.logf("LỖI: %s", msg)
	a.emit(map[string]any{"t": "error", "msg": msg})
}

func (a *App) doInstall(o InstallOpts) {
	work := filepath.Join(os.TempDir(), "tta-setup")
	_ = os.MkdirAll(work, 0o755)
	a.logPath = filepath.Join(work, "setup.log")
	_ = os.WriteFile(a.logPath, []byte("# Nhật ký trình cài TikTok Auto Kid\r\n"), 0o644)
	a.logf("Cài vào %s ; dữ liệu %s", o.Dir, o.Data)
	a.emit(map[string]any{"t": "progress", "pct": 0, "stage": "tai-app", "msg": "Đang chuẩn bị…"})

	script := filepath.Join(work, "cai-dat.ps1")
	body := readEmbed("cai-dat.ps1")
	if !bytes.HasPrefix(body, []byte("\xef\xbb\xbf")) {
		body = append([]byte("\xef\xbb\xbf"), body...)
	}
	if err := os.WriteFile(script, body, 0o644); err != nil {
		a.fail("Không ghi được tệp cài đặt tạm: " + err.Error())
		return
	}
	dirs := shellDirs()
	desktopLnk := filepath.Join(dirs.Desktop, lnkName)
	_, err := os.Stat(desktopLnk)
	hadDesktop := err == nil

	args := []string{"-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
		"-ThuMuc", o.Dir, "-ThuMucDuLieu", o.Data, "-KhongHoi", "-TienDo"}
	if o.Autostart {
		args = append(args, "-ChayCungWindows")
	}
	if *fThuKhong {
		args = append(args, "-ThuKhong")
	}
	cmd := newHiddenCmd("powershell.exe", args...)
	stdout, _ := cmd.StdoutPipe()
	stderr, _ := cmd.StderrPipe()
	if err := cmd.Start(); err != nil {
		a.fail("Không chạy được PowerShell: " + err.Error())
		return
	}
	a.mu.Lock()
	a.cmd = cmd
	a.mu.Unlock()

	st := &lineState{}
	var stMu sync.Mutex
	var wg sync.WaitGroup
	pump := func(r io.Reader) {
		defer wg.Done()
		br := bufio.NewReaderSize(r, 1<<16)
		for {
			s, err := br.ReadString('\n')
			if s != "" {
				stMu.Lock()
				a.handleLine(s, st)
				stMu.Unlock()
			}
			if err != nil {
				return
			}
		}
	}
	wg.Add(2)
	go pump(stdout)
	go pump(stderr)
	wg.Wait()
	werr := cmd.Wait()
	a.mu.Lock()
	cancelled := a.cmd == nil
	a.cmd = nil
	a.mu.Unlock()
	if cancelled {
		a.emit(map[string]any{"t": "cancelled"})
		return
	}
	if st.fatal != "" || werr != nil {
		msg := st.fatal
		if msg == "" {
			msg = "Trình cài dừng giữa chừng (" + werr.Error() + ")."
		}
		a.fail(msg)
		return
	}

	// Sau khi script xong.
	dir := o.Dir
	data := o.Data
	ver := a.version
	if j, ok := readInstallJSON(dir); ok {
		if j.ThuMuc != "" {
			dir = j.ThuMuc
		}
		if j.DuLieu != "" {
			data = j.DuLieu
		}
		if j.PhienBan != "" {
			ver = j.PhienBan
		}
	}
	if v := readVersionFile(dir); v != "" {
		ver = v
	}
	a.installDir, a.dataDir = dir, data
	if *fThuKhong {
		a.emit(map[string]any{"t": "done", "dir": dir, "data": data, "version": ver, "dry": true, "warns": st.warns})
		return
	}
	a.emit(map[string]any{"t": "progress", "pct": 99.5, "stage": "xong", "msg": "Đang hoàn tất…"})
	var warns = st.warns
	if !o.Desktop && !hadDesktop {
		_ = os.Remove(desktopLnk)
	}
	if !o.Autostart {
		_ = os.Remove(filepath.Join(dirs.Startup, lnkName))
	}
	if err := a.registerUninstall(dir, ver); err != nil {
		warns = append(warns, "Chưa ghi được mục Gỡ cài đặt của Windows: "+err.Error())
	}
	a.emit(map[string]any{"t": "progress", "pct": 100, "stage": "xong", "msg": "Hoàn tất"})
	a.emit(map[string]any{"t": "done", "dir": dir, "data": data, "version": ver, "warns": warns})
}

// registerUninstall ghi mục Gỡ cài đặt (HKCU) và chép chính trình cài thành GoCaiDat.exe trong thư mục cài.
func (a *App) registerUninstall(dir, ver string) error {
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	dest := filepath.Join(dir, "GoCaiDat.exe")
	if !strings.EqualFold(filepath.Clean(exe), dest) {
		if err := copyFile(exe, dest); err != nil {
			return fmt.Errorf("không chép được GoCaiDat.exe: %w", err)
		}
	}
	k, _, err := registry.CreateKey(registry.CURRENT_USER, uninstallKeyPath(), registry.SET_VALUE)
	if err != nil {
		return err
	}
	defer k.Close()
	kb := dirSize(dir, nil) / 1024
	if kb > 0x7fffffff {
		kb = 0x7fffffff
	}
	strs := map[string]string{
		"DisplayName":     appName,
		"DisplayVersion":  ver,
		"Publisher":       "Kid",
		"DisplayIcon":     filepath.Join(dir, "TikTokAuto.exe"),
		"InstallLocation": dir,
		"UninstallString": `"` + dest + `" /uninstall`,
	}
	for n, v := range strs {
		if err := k.SetStringValue(n, v); err != nil {
			return err
		}
	}
	for n, v := range map[string]uint32{"EstimatedSize": uint32(kb), "NoModify": 1, "NoRepair": 1} {
		if err := k.SetDWordValue(n, v); err != nil {
			return err
		}
	}
	return nil
}

func (a *App) cancel() {
	a.mu.Lock()
	c := a.cmd
	a.cmd = nil
	a.mu.Unlock()
	if c != nil && c.Process != nil {
		_ = newHiddenCmd("taskkill", "/T", "/F", "/PID", strconv.Itoa(c.Process.Pid)).Run()
	}
}

// demoInstall mô phỏng một lần cài bằng cách đưa các dòng ##TD giả qua cùng bộ phân tích.
func (a *App) demoInstall(o InstallOpts) {
	a.logPath = ""
	type step struct {
		d    time.Duration
		line string
	}
	steps := []step{
		{500, "Kiểm tra Windows và dung lượng trống…"},
		{300, "##TD 3|tai-app|Đang kiểm tra bản mới nhất trên GitHub"},
	}
	for mb := 0; mb <= 20; mb += 2 {
		steps = append(steps, step{350, fmt.Sprintf("##TD %d|tai-app|Đang tải ứng dụng: %d / 20 MB", 5+mb*3/4, mb*12)})
	}
	steps = append(steps,
		step{500, "##TD 22|tai-app|Đang kiểm tra tệp và giải nén"},
		step{900, "##TD 25|phan-mem|Đang kiểm tra Python 3.11"},
		step{900, "##TD 32|phan-mem|Đang cài Node.js LTS"},
		step{900, "##TD 41|phan-mem|Đang cài ffmpeg"},
		step{700, "##TD-CB Claude Code chưa cài được, bạn có thể cài sau"},
		step{900, "##TD 50|phan-mem|Đang cài Claude Code"},
		step{900, "##TD 56|du-lieu|Đang dựng PHP, PostgreSQL, Caddy"},
		step{1100, "##TD 66|du-lieu|Đang tạo môi trường Python"},
		step{1100, "##TD 78|du-lieu|Đang chuẩn bị Remotion"},
		step{1100, "##TD 86|du-lieu|Đang tạo cơ sở dữ liệu"},
		step{600, "##TD 91|loi-tat|Đang tạo lối tắt"},
		step{600, "##TD 96|khoi-dong|Đang kiểm tra dịch vụ"},
	)
	st := &lineState{}
	for i, s := range steps {
		time.Sleep(s.d * time.Millisecond)
		a.handleLine(s.line, st)
		if *fDemoLoi && i == len(steps)-6 {
			a.handleLine("##TD-LOI Không tải được Node.js (mất kết nối mạng). Hãy kiểm tra Internet rồi thử lại.", st)
			a.fail(st.fatal)
			return
		}
	}
	a.handleLine("##TD 100|xong|Hoàn tất", st)
	a.emit(map[string]any{"t": "done", "dir": o.Dir, "data": o.Data, "version": a.version, "demo": true, "warns": st.warns})
}

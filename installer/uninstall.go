package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"golang.org/x/sys/windows/registry"
)

// GoInfo là thông tin hiển thị ở màn hình gỡ cài đặt.
type GoInfo struct {
	Found      bool   `json:"found"`
	Dir        string `json:"dir"`
	Data       string `json:"data"`
	Version    string `json:"version"`
	DataInside bool   `json:"dataInside"`
	DeleteOK   bool   `json:"deleteOk"`
	DeleteWhy  string `json:"deleteWhy"`
	Test       bool   `json:"test"`
}

// resolveInstallDir xác định thư mục cần gỡ.
func resolveInstallDir() string {
	switch {
	case *fThuMucGo != "":
		return filepath.Clean(*fThuMucGo)
	case *fDirGo != "":
		return filepath.Clean(*fDirGo)
	}
	if exe, err := os.Executable(); err == nil {
		d := filepath.Dir(exe)
		if strings.EqualFold(filepath.Base(exe), "GoCaiDat.exe") && installedAt(d) != nil {
			return d
		}
	}
	if in := detectInstall(); in != nil {
		return in.Dir
	}
	return ""
}

// relaunchFromTemp: GoCaiDat.exe nằm trong thư mục cài nên không tự xoá được; chép ra %TEMP% rồi chạy lại.
func relaunchFromTemp() bool {
	exe, err := os.Executable()
	if err != nil {
		return false
	}
	dir := resolveInstallDir()
	if dir == "" || !pathInside(exe, dir) {
		return false
	}
	tmp, err := os.MkdirTemp("", "tta-gocaidat-")
	if err != nil {
		return false
	}
	dst := filepath.Join(tmp, "GoCaiDat.exe")
	if err := copyFile(exe, dst); err != nil {
		return false
	}
	args := []string{"/uninstall", "-tam"}
	if testMode() {
		args = append(args, "-thu-muc-go", dir)
	} else {
		args = append(args, "-dir-go", dir)
	}
	c := exec.Command(dst, args...)
	c.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x00000008 | 0x00000200}
	return c.Start() == nil
}

var systemDirNames = []string{"WINDIR", "SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PUBLIC", "SystemDrive"}

// riskyPath từ chối đường dẫn nguy hiểm (gốc ổ đĩa, hồ sơ người dùng, thư mục Windows/Program Files, thư mục chuẩn của người dùng).
func riskyPath(p string) string {
	p = filepath.Clean(p)
	if !filepath.IsAbs(p) || filepath.VolumeName(p) == "" || strings.HasPrefix(p, `\\`) {
		return "đường dẫn không hợp lệ"
	}
	if filepath.Dir(p) == p {
		return "là gốc ổ đĩa"
	}
	lp := strings.ToLower(p)
	for _, n := range systemDirNames {
		v := os.Getenv(n)
		if v == "" {
			continue
		}
		v = strings.ToLower(filepath.Clean(v))
		if n == "SystemDrive" {
			v += `\`
		}
		if lp == v {
			return "là thư mục hệ thống hoặc hồ sơ người dùng"
		}
		// thư mục cha của hồ sơ / Windows (chứa chúng bên trong)
		if strings.HasPrefix(v, lp+`\`) {
			return "chứa thư mục hệ thống hoặc hồ sơ người dùng"
		}
	}
	if up := os.Getenv("USERPROFILE"); up != "" {
		for _, s := range []string{"Desktop", "Documents", "Downloads", "Videos", "Pictures", "Music", "OneDrive", "AppData"} {
			if lp == strings.ToLower(filepath.Join(up, s)) {
				return "là thư mục chuẩn của người dùng"
			}
		}
	}
	if win := os.Getenv("WINDIR"); win != "" && pathInside(p, win) {
		return "nằm trong thư mục Windows"
	}
	return ""
}

func safeInstallDir(dir string) error {
	if why := riskyPath(dir); why != "" {
		return fmt.Errorf("không gỡ %s vì %s", dir, why)
	}
	if installedAt(dir) == nil && !fileExists(filepath.Join(dir, "VERSION")) && !fileExists(filepath.Join(dir, "GoCaiDat.exe")) {
		return fmt.Errorf("thư mục %s không giống bản cài TikTok Auto Kid", dir)
	}
	return nil
}

func fileExists(p string) bool { _, err := os.Stat(p); return err == nil }

// dataDeleteCheck: có được phép xoá thư mục dữ liệu này không (trả "" nếu được).
func dataDeleteCheck(data, install string) string {
	if data == "" {
		return "không biết thư mục dữ liệu"
	}
	if why := riskyPath(data); why != "" {
		return "thư mục dữ liệu " + why
	}
	if pathInside(data, install) {
		return ""
	}
	if pathInside(install, data) {
		return "thư mục dữ liệu chứa cả thư mục cài"
	}
	l := strings.ToLower(filepath.Base(data))
	if !strings.Contains(l, "tiktok") && !strings.Contains(l, "xuong") && !strings.Contains(l, "tta") && !looksLikeHubData(data) {
		return "tên thư mục dữ liệu không giống của TikTok Auto Kid, nên để bạn tự xoá cho an toàn"
	}
	return ""
}

func (a *App) goInfo() GoInfo {
	if *fDemoGo {
		a.installDir = `C:\Users\Demo\AppData\Local\TikTok Auto Kid`
		gi := GoInfo{Found: true, Dir: a.installDir, Data: `D:\TikTok Auto Kid Data`, Version: a.version, DeleteOK: true}
		go func() {
			time.Sleep(1200 * time.Millisecond)
			a.emit(map[string]any{"t": "datasize", "bytes": int64(48_700_000_000)})
		}()
		return gi
	}
	dir := resolveInstallDir()
	gi := GoInfo{Dir: dir, Test: testMode()}
	if dir == "" {
		return gi
	}
	if err := safeInstallDir(dir); err != nil {
		gi.DeleteWhy = err.Error()
		return gi
	}
	gi.Found = true
	a.installDir = dir
	if in := installedAt(dir); in != nil {
		gi.Data, gi.Version = in.Data, in.Version
	}
	if gi.Version == "" {
		gi.Version = readVersionFile(dir)
	}
	gi.DataInside = gi.Data != "" && pathInside(gi.Data, dir)
	if why := dataDeleteCheck(gi.Data, dir); why != "" {
		gi.DeleteWhy = why
	} else {
		gi.DeleteOK = true
	}
	if gi.Data != "" {
		go func(d string) {
			a.emit(map[string]any{"t": "datasize", "bytes": dirSize(d, nil)})
		}(gi.Data)
	}
	return gi
}

// UninstallOpts: DeleteAll=true xoá cả dữ liệu.
type UninstallOpts struct {
	DeleteAll bool `json:"deleteAll"`
}

func (a *App) startUninstall(o UninstallOpts) error {
	a.mu.Lock()
	if a.busy {
		a.mu.Unlock()
		return fmt.Errorf("đang chạy")
	}
	a.busy = true
	a.mu.Unlock()
	go func() {
		defer func() { a.mu.Lock(); a.busy = false; a.mu.Unlock() }()
		if *fDemoGo {
			a.demoUninstall(o)
			return
		}
		a.doUninstall(o)
	}()
	return nil
}

func (a *App) step(pct float64, stage, msg string) {
	a.emit(map[string]any{"t": "progress", "pct": pct, "stage": stage, "msg": msg})
	a.logf("[%s] %s", stage, msg)
}

func (a *App) removed(item string) {
	a.emit(map[string]any{"t": "removed", "item": item})
	a.logf("đã xoá: %s", item)
}

func (a *App) doUninstall(o UninstallOpts) {
	dir := a.installDir
	if dir == "" {
		dir = resolveInstallDir()
	}
	if err := safeInstallDir(dir); err != nil {
		a.fail(err.Error())
		return
	}
	a.logPath = filepath.Join(os.TempDir(), "tta-setup-go.log")
	in := installedAt(dir)
	data := ""
	if in != nil {
		data = in.Data
	}
	if o.DeleteAll {
		if why := dataDeleteCheck(data, dir); why != "" {
			a.fail("Không thể xoá sạch dữ liệu: " + why + ".")
			return
		}
	}
	test := testMode()
	keptDir := ""

	// 1. Sao lưu nếu giữ dữ liệu.
	if !o.DeleteAll && data != "" {
		a.step(3, "sao-luu", "Đang sao lưu cơ sở dữ liệu…")
		keptDir = a.backupForKeep(dir, data, test)
	}

	// 2. Dừng ứng dụng.
	a.step(18, "dung", "Đang tắt TikTok Auto Kid…")
	a.stopApp(dir, test)

	// 3. Lối tắt, Run, Uninstall key.
	a.step(45, "loi-tat", "Đang gỡ lối tắt và mục đăng ký…")
	sd := shellDirs()
	for _, d := range []struct{ dir, label string }{{sd.Desktop, "Lối tắt ngoài màn hình"}, {sd.Programs, "Lối tắt trong Start Menu"}, {sd.Startup, "Lối tắt tự mở khi bật máy"}} {
		if d.dir == "" {
			continue
		}
		p := filepath.Join(d.dir, lnkName)
		if fileExists(p) && os.Remove(p) == nil {
			a.removed(d.label)
		}
	}
	if k, err := registry.OpenKey(registry.CURRENT_USER, runKeyPath(), registry.SET_VALUE|registry.QUERY_VALUE); err == nil {
		if _, _, e := k.GetStringValue(runValueName); e == nil {
			if k.DeleteValue(runValueName) == nil {
				a.removed("Mục tự chạy cùng Windows")
			}
		}
		k.Close()
	}
	if registry.DeleteKey(registry.CURRENT_USER, uninstallKeyPath()) == nil {
		a.removed("Mục “TikTok Auto Kid” trong Cài đặt Windows")
	}

	// 4. Xoá tệp.
	a.step(62, "xoa", "Đang xoá tệp ứng dụng…")
	if keptDir == "" && !o.DeleteAll && data != "" && pathInside(data, dir) {
		keptDir = data
	}
	if !o.DeleteAll && data != "" && pathInside(data, dir) {
		// Dữ liệu nằm trong thư mục cài: dời ra ngoài trước khi xoá thư mục cài.
		parent := filepath.Dir(dir)
		dst := filepath.Join(parent, "TikTok Auto Kid - Du lieu giu lai")
		for i := 2; fileExists(dst); i++ {
			dst = filepath.Join(parent, fmt.Sprintf("TikTok Auto Kid - Du lieu giu lai (%d)", i))
		}
		if err := os.Rename(data, dst); err != nil {
			a.fail("Không dời được dữ liệu ra khỏi thư mục cài, nên chưa xoá gì thêm: " + err.Error())
			return
		}
		keptDir = dst
		data = dst
	}
	leftover := removeAllRetry(dir)
	if leftover != nil {
		a.emit(map[string]any{"t": "log", "line": "Còn tệp đang bị chiếm dụng: " + leftover.Error() + " — sẽ xoá nốt sau vài giây."})
		scheduleDelete(dir)
	}
	a.removed("Thư mục ứng dụng: " + dir)
	if o.DeleteAll && data != "" {
		if !pathInside(data, dir) {
			a.step(80, "xoa", "Đang xoá video và dữ liệu…")
			if err := removeAllRetry(data); err != nil {
				scheduleDelete(data)
			}
		}
		a.removed("Video, sản phẩm và cơ sở dữ liệu: " + data)
	}

	// 5. Dọn dẹp.
	a.step(92, "don", "Đang dọn tệp tạm…")
	tmp := os.TempDir()
	for _, n := range []string{"tiktok-auto-kid-cai-dat", "tta-setup"} {
		p := filepath.Join(tmp, n)
		if fileExists(p) && os.RemoveAll(p) == nil {
			a.removed("Tệp tạm " + n)
		}
	}
	_ = os.Remove(filepath.Join(tmp, "tta-setup-go.log"))
	a.step(100, "don", "Hoàn tất")
	a.emit(map[string]any{"t": "done", "dir": dir, "data": data, "kept": keptDir, "deleteAll": o.DeleteAll, "test": test})
}

// backupForKeep: chạy pg_dump lần cuối (nếu CSDL đang chạy) và chép các bản sao lưu cũ vào <data>\sao-luu-app.
func (a *App) backupForKeep(dir, data string, test bool) string {
	dst := filepath.Join(data, "sao-luu-app")
	if err := os.MkdirAll(dst, 0o755); err != nil {
		a.emit(map[string]any{"t": "log", "line": "Không tạo được thư mục sao lưu: " + err.Error()})
		return ""
	}
	pg := filepath.Join(dir, "runtime", "pgsql", "bin", "pg_dump.exe")
	if !test && fileExists(pg) && portOpen(5433) {
		out := filepath.Join(dst, time.Now().Format("20060102-1504")+"-ban-cuoi.sql")
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
		c := exec.CommandContext(ctx, pg, "-h", "127.0.0.1", "-p", "5433", "-U", "postgres", "--no-owner", "-f", out, "tiktok_auto")
		c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
		if err := c.Run(); err != nil {
			a.emit(map[string]any{"t": "log", "line": "pg_dump không chạy được: " + err.Error()})
			_ = os.Remove(out)
		} else {
			a.emit(map[string]any{"t": "log", "line": "Đã sao lưu cơ sở dữ liệu: " + out})
		}
		cancel()
	}
	if es, err := os.ReadDir(filepath.Join(dir, "runtime", "backups")); err == nil {
		for _, e := range es {
			if e.IsDir() || !strings.HasSuffix(e.Name(), ".sql") {
				continue
			}
			t := filepath.Join(dst, e.Name())
			if !fileExists(t) {
				_ = copyFile(filepath.Join(dir, "runtime", "backups", e.Name()), t)
			}
		}
	}
	return dst
}

// stopApp tắt launcher (POST /api/quit), chờ cổng giải phóng, nếu không thì kết thúc tiến trình nằm trong thư mục cài.
func (a *App) stopApp(dir string, test bool) {
	if !test {
		if tok, err := os.ReadFile(filepath.Join(dir, "runtime", "control.token")); err == nil && portOpen(8009) {
			req, _ := http.NewRequest("POST", "http://127.0.0.1:8009/api/quit", nil)
			req.Header.Set("X-TTA-Token", strings.TrimSpace(string(tok)))
			cl := &http.Client{Timeout: 6 * time.Second}
			if r, err := cl.Do(req); err == nil {
				r.Body.Close()
				a.emit(map[string]any{"t": "log", "line": "Đã gửi lệnh tắt ứng dụng"})
			}
		}
		if !waitPortsFree(25 * time.Second) {
			a.emit(map[string]any{"t": "log", "line": "Ứng dụng chưa tắt hẳn, đang buộc dừng các tiến trình của nó…"})
		}
	}
	// Chỉ động tới tiến trình có file chạy nằm trong thư mục cài.
	killInside(dir, "TikTokAuto.exe")
	time.Sleep(600 * time.Millisecond)
	killInside(dir, "")
	if !test {
		waitPortsFree(10 * time.Second)
	}
	time.Sleep(500 * time.Millisecond)
}

var appPorts = []int{8009, 8010, 5433, 8765}

func waitPortsFree(max time.Duration) bool {
	end := time.Now().Add(max)
	for {
		busy := false
		for _, p := range appPorts {
			if portOpen(p) {
				busy = true
			}
		}
		if !busy {
			return true
		}
		if time.Now().After(end) {
			return false
		}
		time.Sleep(700 * time.Millisecond)
	}
}

func removeAllRetry(p string) error {
	var err error
	for i := 0; i < 6; i++ {
		// gỡ thuộc tính chỉ-đọc nếu cần
		err = os.RemoveAll(p)
		if err == nil || !fileExists(p) {
			return nil
		}
		makeWritable(p)
		time.Sleep(900 * time.Millisecond)
	}
	return err
}

func makeWritable(root string) {
	_ = filepath.WalkDir(root, func(p string, d os.DirEntry, err error) error {
		if err == nil {
			_ = os.Chmod(p, 0o666)
		}
		return nil
	})
}

// scheduleDelete xoá nốt thư mục sau khi trình gỡ đã đóng (cmd ẩn).
func scheduleDelete(p string) {
	c := exec.Command("cmd.exe", "/c", fmt.Sprintf(`ping -n 6 127.0.0.1 >nul & rmdir /s /q "%s"`, p))
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000 | 0x00000008}
	_ = c.Start()
}

// cleanupOnExit: nếu đang chạy từ bản sao tạm để gỡ thì xoá nó (cùng dữ liệu WebView2) sau khi thoát.
func (a *App) cleanupOnExit() {
	if !*fTam {
		return
	}
	exe, err := os.Executable()
	if err != nil {
		return
	}
	d := filepath.Dir(exe)
	if strings.HasPrefix(filepath.Base(d), "tta-gocaidat-") && strings.EqualFold(filepath.Base(exe), "GoCaiDat.exe") {
		scheduleDelete(d)
	}
}

func (a *App) demoUninstall(o UninstallOpts) {
	steps := []struct {
		p     float64
		stage string
		msg   string
		item  string
	}{
		{5, "dung", "Đang tắt TikTok Auto Kid…", ""},
		{25, "dung", "Đang đợi các cổng giải phóng…", ""},
		{45, "loi-tat", "Đang gỡ lối tắt và mục đăng ký…", "Lối tắt ngoài màn hình"},
		{52, "loi-tat", "Đang gỡ lối tắt và mục đăng ký…", "Lối tắt trong Start Menu"},
		{58, "loi-tat", "Đang gỡ mục đăng ký…", "Mục tự chạy cùng Windows"},
		{64, "xoa", "Đang xoá tệp ứng dụng…", ""},
		{82, "xoa", "Đang xoá tệp ứng dụng…", "Thư mục ứng dụng"},
		{94, "don", "Đang dọn tệp tạm…", "Tệp tạm"},
		{100, "don", "Hoàn tất", ""},
	}
	if !o.DeleteAll {
		a.step(3, "sao-luu", "Đang sao lưu cơ sở dữ liệu…")
		time.Sleep(1200 * time.Millisecond)
	}
	for _, s := range steps {
		time.Sleep(900 * time.Millisecond)
		a.step(s.p, s.stage, s.msg)
		if s.item != "" {
			a.removed(s.item)
		}
	}
	kept := ""
	if !o.DeleteAll {
		kept = `D:\TikTok Auto Kid Data\sao-luu-app`
	}
	a.emit(map[string]any{"t": "done", "dir": a.installDir, "data": `D:\TikTok Auto Kid Data`, "kept": kept, "deleteAll": o.DeleteAll, "demo": true})
}

// looksLikeHubData: thư mục dữ liệu hub có config.json và ít nhất một trong san-pham, ra, lich-su.
func looksLikeHubData(d string) bool {
	if !fileExists(filepath.Join(d, "config.json")) {
		return false
	}
	for _, n := range []string{"san-pham", "ra", "lich-su"} {
		if st, err := os.Stat(filepath.Join(d, n)); err == nil && st.IsDir() {
			return true
		}
	}
	return false
}

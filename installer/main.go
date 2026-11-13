// TikTok Auto Kid - trình cài đặt / gỡ cài đặt có giao diện (WebView2).
package main

import (
	"embed"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"syscall"

	webview2 "github.com/jchv/go-webview2"
)

//go:embed embed/cai-dat.ps1 embed/VERSION
var embedFS embed.FS

//go:embed ui/index.html ui/style.css ui/app.js
var uiFS embed.FS

const (
	appName = "TikTok Auto Kid"
	winW    = 900
	winH    = 600
)

// Cờ dòng lệnh (ẩn, dành cho thử nghiệm).
var (
	fDemo      = flag.Bool("demo", false, "mô phỏng cài đặt, không đụng đĩa/registry")
	fDemoGo    = flag.Bool("demo-go", false, "mô phỏng gỡ cài đặt")
	fDemoSan   = flag.Bool("demo-co-san", false, "mô phỏng: máy đã có bản cài")
	fDemoLoi   = flag.Bool("demo-loi", false, "mô phỏng: cài đặt báo lỗi giữa chừng")
	fScreen    = flag.String("screen", "", "nhảy tới màn hình (chụp ảnh)")
	fThuKhong  = flag.Bool("thu-khong", false, "chạy cai-dat.ps1 với -ThuKhong (không đổi gì)")
	fThuMucGo  = flag.String("thu-muc-go", "", "THỬ NGHIỆM: gỡ cài đặt thư mục giả này (khoá registry TEST, lối tắt giả)")
	fDirGo     = flag.String("dir-go", "", "nội bộ: thư mục cài cần gỡ (bản sao tạm)")
	fTam       = flag.Bool("tam", false, "nội bộ: đang chạy từ bản sao tạm để tự xoá")
	fPreserve  = flag.Bool("giu-cua-so", false, "không tự thoát (thử nghiệm)")
	uninstallM bool
)

// App giữ trạng thái chung giữa giao diện và Go.
type App struct {
	w       webview2.WebView
	hwnd    uintptr
	version string
	mu      sync.Mutex
	cmd     *exec.Cmd
	busy    bool
	logPath string
	tmpDir  string // thư mục chứa bản sao tạm (khi gỡ), để dọn
	// kết quả sau khi cài/gỡ
	installDir string
	dataDir    string
}

func readEmbed(name string) []byte {
	b, _ := embedFS.ReadFile("embed/" + name)
	return b
}

func embeddedVersion() string {
	v := strings.TrimSpace(strings.TrimPrefix(string(readEmbed("VERSION")), "\xef\xbb\xbf"))
	if v == "" {
		return "0.0.0"
	}
	return strings.TrimPrefix(v, "v")
}

func newHiddenCmd(name string, args ...string) *exec.Cmd {
	c := exec.Command(name, args...)
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	return c
}

func main() {
	runtime.LockOSThread()
	// "/uninstall" không phải cờ của package flag: tách ra trước.
	var rest []string
	for _, a := range os.Args[1:] {
		switch strings.ToLower(a) {
		case "/uninstall", "-uninstall", "--uninstall":
			uninstallM = true
		default:
			rest = append(rest, a)
		}
	}
	_ = flag.CommandLine.Parse(rest)
	if *fDemoGo {
		uninstallM = true
	}

	// Gỡ cài đặt: bản đang nằm trong thư mục cài thì tự sao chép ra %TEMP% rồi chạy lại từ đó.
	if uninstallM && !*fTam && !*fDemoGo {
		if relaunchFromTemp() {
			return
		}
	}

	a := &App{version: embeddedVersion()}
	a.run()
}

func (a *App) run() {
	scale := dpiScale()
	pw, ph := int32(float64(winW)*scale), int32(float64(winH)*scale)

	dataPath := filepath.Join(os.TempDir(), "tta-setup", "wv")
	if *fTam && *fDirGo != "" || *fTam && *fThuMucGo != "" {
		// bản tạm: để dữ liệu WebView2 cạnh file tạm để xoá cùng.
		if exe, err := os.Executable(); err == nil {
			dataPath = filepath.Join(filepath.Dir(exe), "wv")
		}
	}
	_ = os.MkdirAll(dataPath, 0o755)
	os.Setenv("WEBVIEW2_DEFAULT_BACKGROUND_COLOR", "FFFFFAF0")

	installFramelessHook(pw, ph)
	w := webview2.NewWithOptions(webview2.WebViewOptions{
		Debug:     false,
		DataPath:  dataPath,
		AutoFocus: true,
		WindowOptions: webview2.WindowOptions{
			Title:  appName + " - Cài đặt",
			Width:  uint(pw),
			Height: uint(ph),
			IconId: 1,
			Center: false,
		},
	})
	removeFramelessHook()
	if w == nil {
		messageBox(appName, "Máy chưa có Microsoft Edge WebView2 Runtime nên không mở được giao diện cài đặt.\n\nHãy tải bản miễn phí tại:\nhttps://go.microsoft.com/fwlink/p/?LinkId=2124703\nrồi chạy lại trình cài.")
		os.Exit(1)
	}
	defer w.Destroy()
	a.w = w
	a.hwnd = uintptr(w.Window())
	frameless(a.hwnd, pw, ph)
	decorateWindow(a.hwnd)
	a.bind()

	html := a.buildHTML()
	w.SetHtml(html)
	foreground(a.hwnd)
	w.Run()
	a.cleanupOnExit()
}

func (a *App) buildHTML() string {
	idx, _ := uiFS.ReadFile("ui/index.html")
	css, _ := uiFS.ReadFile("ui/style.css")
	js, _ := uiFS.ReadFile("ui/app.js")
	s := string(idx)
	s = strings.Replace(s, "/*CSS*/", string(css), 1)
	s = strings.Replace(s, "/*JS*/", string(js), 1)
	return s
}

// emit gửi một sự kiện sang giao diện.
func (a *App) emit(v map[string]any) {
	b, err := json.Marshal(v)
	if err != nil {
		return
	}
	js := "window.__ev && window.__ev(" + string(b) + ")"
	a.w.Dispatch(func() { a.w.Eval(js) })
}

func (a *App) bind() {
	w := a.w
	_ = w.Bind("ttaInfo", a.info)
	_ = w.Bind("ttaCheckPath", a.checkPath)
	_ = w.Bind("ttaPickFolder", a.pick)
	_ = w.Bind("ttaStartInstall", a.startInstall)
	_ = w.Bind("ttaCancel", a.cancel)
	_ = w.Bind("ttaOpenLog", a.openLog)
	_ = w.Bind("ttaLaunchApp", a.launchApp)
	_ = w.Bind("ttaGoInfo", a.goInfo)
	_ = w.Bind("ttaGoEntry", func() bool { return !*fTam && relaunchFromTemp() })
	_ = w.Bind("ttaStartUninstall", a.startUninstall)
	_ = w.Bind("ttaOpenPath", func(p string) { shellOpen(p) })
	_ = w.Bind("ttaDrag", func() { dragWindow(a.hwnd) })
	_ = w.Bind("ttaMinimize", func() { minimizeWindow(a.hwnd) })
	_ = w.Bind("ttaClose", func() { a.w.Destroy() })
}

// Info là dữ liệu khởi động cho giao diện.
type Info struct {
	Version     string     `json:"version"`
	Mode        string     `json:"mode"`
	Screen      string     `json:"screen"`
	Demo        bool       `json:"demo"`
	Test        bool       `json:"test"`
	DefaultDir  string     `json:"defaultDir"`
	DefaultData string     `json:"defaultData"`
	BestDrive   string     `json:"bestDrive"`
	Drives      []Drive    `json:"drives"`
	Installed   *Installed `json:"installed"`
}

func (a *App) info() Info {
	in := Info{
		Version:    a.version,
		Mode:       "install",
		Screen:     *fScreen,
		Demo:       *fDemo || *fDemoGo || *fDemoSan || *fDemoLoi,
		Test:       *fThuMucGo != "",
		DefaultDir: defaultInstallDir(),
	}
	if uninstallM {
		in.Mode = "go"
	}
	in.Drives = fixedDrives()
	var best uint64
	for _, d := range in.Drives {
		if d.Free >= best {
			best = d.Free
			in.BestDrive = d.Letter
		}
	}
	if in.BestDrive != "" {
		in.DefaultData = in.BestDrive + `:\TikTok Auto Kid Data`
	} else {
		in.DefaultData = filepath.Join(os.Getenv("LOCALAPPDATA"), "TikTok Auto Kid Data")
	}
	if *fDemoSan {
		in.Installed = &Installed{Dir: defaultInstallDir(), Data: in.DefaultData, Version: "1.1.2"}
	} else if !in.Demo {
		in.Installed = detectInstall()
	}
	return in
}

func defaultInstallDir() string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = filepath.Join(os.Getenv("USERPROFILE"), "AppData", "Local")
	}
	return filepath.Join(base, appName)
}

// PathCheck là kết quả kiểm tra một đường dẫn người dùng chọn.
type PathCheck struct {
	Path     string `json:"path"`
	Valid    bool   `json:"valid"`
	Error    string `json:"error"`
	Warn     string `json:"warn"`
	Free     uint64 `json:"free"`
	NonASCII bool   `json:"nonAscii"`
	Suggest  string `json:"suggest"`
}

const (
	needAppBytes   = 2 << 30
	adviseDataByte = 50 << 30
)

func isASCII(s string) bool {
	for _, r := range s {
		if r > 127 {
			return false
		}
	}
	return true
}

func (a *App) checkPath(kind, path string) PathCheck {
	r := PathCheck{Path: strings.TrimSpace(path)}
	p := filepath.Clean(r.Path)
	r.Path = p
	if r.Path == "" || r.Path == "." || filepath.VolumeName(p) == "" || strings.HasPrefix(p, `\\`) || !filepath.IsAbs(p) {
		r.Error = "Hãy chọn một thư mục trên ổ đĩa của máy (ví dụ D:\\TikTok Auto Kid)."
		return r
	}
	if filepath.Dir(p) == p {
		r.Error = "Không nên cài thẳng vào gốc ổ đĩa. Hãy chọn một thư mục con."
		r.Suggest = filepath.Join(p+`\`, defaultName(kind))
		return r
	}
	r.NonASCII = !isASCII(p)
	r.Free = freeForPath(p)
	if r.NonASCII {
		r.Warn = "Đường dẫn có chữ có dấu hoặc ký tự đặc biệt. Một số công cụ làm video (Remotion, ffmpeg) có thể bị lỗi. Nên chọn đường dẫn không dấu."
		r.Suggest = filepath.Join(filepath.VolumeName(p)+`\`, defaultName(kind))
	}
	if kind == "app" {
		if r.Free < needAppBytes {
			r.Error = "Ổ đĩa này không đủ chỗ trống (cần khoảng 2 GB)."
			return r
		}
		if es, err := os.ReadDir(p); err == nil && len(es) > 0 {
			// Chỉ có "runtime" (nhật ký của lần cài trước bị dừng) thì vẫn coi là thư mục trống.
			if !isOurInstall(p) && !onlyRuntime(es) {
				r.Error = "Thư mục này đã có tệp khác và chưa phải bản cài TikTok Auto Kid."
				r.Suggest = filepath.Join(p, appName)
				return r
			}
		}
	} else {
		if r.Free < 1<<30 {
			r.Error = "Ổ đĩa này gần như hết chỗ trống."
			return r
		}
		if r.Free < adviseDataByte && r.Warn == "" {
			r.Warn = "Ổ này còn ít chỗ trống. Video làm ra khá nặng, nên chọn ổ còn trống từ 50 GB trở lên."
		}
	}
	r.Valid = true
	return r
}

func defaultName(kind string) string {
	if kind == "app" {
		return appName
	}
	return appName + " Data"
}

func onlyRuntime(es []os.DirEntry) bool {
	for _, e := range es {
		if !strings.EqualFold(e.Name(), "runtime") {
			return false
		}
	}
	return true
}

func isOurInstall(dir string) bool {
	_, e1 := os.Stat(filepath.Join(dir, "VERSION"))
	_, e2 := os.Stat(filepath.Join(dir, "artisan"))
	return e1 == nil && e2 == nil
}

// pick mở hộp thoại chọn thư mục, tự thêm thư mục con an toàn để gỡ cài đặt không xoá nhầm thư mục của người dùng.
func (a *App) pick(kind string) (string, error) {
	title := "Chọn thư mục cài ứng dụng"
	if kind == "data" {
		title = "Chọn nơi lưu video và dữ liệu"
	}
	p, err := pickFolder(a.hwnd, title)
	if err != nil || p == "" {
		return "", err
	}
	p = filepath.Clean(p)
	if !strings.Contains(strings.ToLower(filepath.Base(p)), "tiktok auto kid") {
		p = filepath.Join(p, defaultName(kind))
	}
	return p, nil
}

func (a *App) launchApp() error {
	dir := a.installDir
	if dir == "" {
		return fmt.Errorf("chưa biết thư mục cài")
	}
	exe := filepath.Join(dir, "TikTokAuto.exe")
	c := exec.Command(exe)
	c.Dir = dir
	c.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x00000008 | 0x00000200} // DETACHED | NEW_PROCESS_GROUP
	return c.Start()
}

func (a *App) openLog() {
	cands := []string{}
	if a.installDir != "" {
		cands = append(cands, filepath.Join(a.installDir, "runtime", "logs", "cai-dat.log"))
	}
	cands = append(cands, a.logPath)
	for _, c := range cands {
		if c == "" {
			continue
		}
		if _, err := os.Stat(c); err == nil {
			revealInExplorer(c)
			return
		}
	}
}

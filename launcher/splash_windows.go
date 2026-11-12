//go:build windows

package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"runtime/debug"
	"strings"
	"sync"
	"time"
	"unsafe"

	webview2 "github.com/jchv/go-webview2"
	"golang.org/x/sys/windows"
)

const (
	splashW = 760
	splashH = 460
)

var (
	user32                    = windows.NewLazySystemDLL("user32.dll")
	gdi32                     = windows.NewLazySystemDLL("gdi32.dll")
	dwmapi                    = windows.NewLazySystemDLL("dwmapi.dll")
	procSetWindowPos          = user32.NewProc("SetWindowPos")
	procShowWindow            = user32.NewProc("ShowWindow")
	procSetForegroundWindow   = user32.NewProc("SetForegroundWindow")
	procGetSystemMetrics      = user32.NewProc("GetSystemMetrics")
	procReleaseCapture        = user32.NewProc("ReleaseCapture")
	procSendMessageW          = user32.NewProc("SendMessageW")
	procSetWindowRgn          = user32.NewProc("SetWindowRgn")
	procSetDpiAwarenessCtx    = user32.NewProc("SetProcessDpiAwarenessContext")
	procGetDpiForSystem       = user32.NewProc("GetDpiForSystem")
	procCreateRoundRectRgn    = gdi32.NewProc("CreateRoundRectRgn")
	procDwmSetWindowAttribute = dwmapi.NewProc("DwmSetWindowAttribute")
)

// setDPIAware bật DPI-aware (per-monitor v2) cho cả tiến trình để màn hình chào sắc nét ở 125%/150%.
func setDPIAware() {
	if procSetDpiAwarenessCtx.Find() == nil {
		procSetDpiAwarenessCtx.Call(^uintptr(3)) // DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
	}
}

func systemDPI() int {
	if procGetDpiForSystem.Find() == nil {
		if r, _, _ := procGetDpiForSystem.Call(); r >= 96 {
			return int(r)
		}
	}
	return 96
}

// Splash là màn hình chào WebView2 không khung. Mọi thao tác UI chạy trên một luồng riêng.
type Splash struct {
	version string
	// các hàm gọi lại (chạy ở goroutine riêng)
	OnRetry   func()
	OnDetails func()
	OnClose   func() // người dùng bấm "Đóng" (hoặc đóng cửa sổ)

	mu        sync.Mutex
	wv        webview2.WebView
	loaded    bool
	abandoned bool
	lastPct   float64
	lastText  string
	mode      string // load | ready | error
	lastMsg   string
	fast      bool
	openCh    chan bool
	doneCh    chan struct{}
	onFinish  func()
	showOnce  sync.Once
	finishing sync.Once
}

func NewSplash(version string) *Splash {
	return &Splash{version: version, openCh: make(chan bool, 1), doneCh: make(chan struct{}), mode: "load"}
}

// splashDataDir: thư mục dữ liệu WebView2 (ngoài thư mục cài đặt).
func splashDataDir() string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	return filepath.Join(base, "TikTokAutoKid", "WebView2")
}

// Open tạo cửa sổ và chờ tới khi hiện được (true) hoặc thất bại/quá hạn (false).
// Thất bại bất kỳ lý do gì chỉ trả false, không ảnh hưởng việc khởi động.
func (s *Splash) Open(timeout time.Duration) bool {
	go s.run()
	select {
	case ok := <-s.openCh:
		return ok
	case <-time.After(timeout):
		s.mu.Lock()
		s.abandoned = true
		wv := s.wv
		s.mu.Unlock()
		if wv != nil {
			wv.Dispatch(func() { wv.Destroy() })
		}
		return false
	}
}

func (s *Splash) signalOpen(ok bool) {
	select {
	case s.openCh <- ok:
	default:
	}
}

func (s *Splash) run() {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("splash panic: %v %s", r, debug.Stack())
			s.signalOpen(false)
		}
		select {
		case <-s.doneCh:
		default:
			close(s.doneCh)
		}
		s.mu.Lock()
		s.mode = "closed"
		fin := s.onFinish
		s.mu.Unlock()
		if fin != nil {
			go fin()
		}
	}()
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	// WebView2 cần COM kiểu STA trên luồng giao diện
	if err := windows.CoInitializeEx(0, windows.COINIT_APARTMENTTHREADED); err == nil {
		defer windows.CoUninitialize()
	}
	setDPIAware()
	if d := os.Getenv("TTA_SPLASH_DEBUG"); d != "" { // gỡ lỗi: ghi log của thư viện WebView2 ra tệp
		if f, err := os.Create(d); err == nil {
			log.SetOutput(f)
			defer f.Close()
		}
	}

	scale := float64(systemDPI()) / 96
	w, h := int(splashW*scale+0.5), int(splashH*scale+0.5)
	sx, _, _ := procGetSystemMetrics.Call(0)
	sy, _, _ := procGetSystemMetrics.Call(1)
	x, y := (int(sx)-w)/2, (int(sy)-h)/2
	if y > 40 {
		y -= 20 // hơi cao hơn tâm cho cân mắt
	}

	wv := webview2.NewWithOptions(webview2.WebViewOptions{
		DataPath: splashDataDir(),
		OnLoaded: s.onLoaded,
		WindowOptions: webview2.WindowOptions{
			Title: appTitle, Width: uint(w), Height: uint(h), Popup: true, X: x, Y: y,
		},
	})
	if wv == nil {
		log.Printf("splash: không tạo được WebView2")
		s.signalOpen(false)
		return
	}
	s.mu.Lock()
	s.wv = wv
	abandoned := s.abandoned
	s.mu.Unlock()
	if abandoned {
		wv.Destroy()
		wv.Run()
		return
	}
	hwnd := uintptr(wv.Window())
	// góc bo tròn/bóng đổ (khi cần cắt vùng cho Windows 10)
	roundWindow(hwnd, w, h, scale)

	wv.Bind("ttaRetry", func() { go s.cb(s.OnRetry) })
	wv.Bind("ttaDetails", func() { go s.cb(s.OnDetails) })
	wv.Bind("ttaClose", func() {
		s.Close()
		go s.cb(s.OnClose)
	})
	wv.Bind("ttaDone", func() { s.Close() })
	wv.Bind("ttaDrag", func() {
		procReleaseCapture.Call()
		procSendMessageW.Call(hwnd, 0x00A1, 2, 0) // WM_NCLBUTTONDOWN, HTCAPTION
	})
	html := strings.ReplaceAll(splashHTML, "{{VERSION}}", htmlEscape(s.version))
	wv.SetHtml(html)
	wv.Run()
}

func (s *Splash) cb(f func()) {
	if f != nil {
		f()
	}
}

func htmlEscape(v string) string {
	return strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&quot;").Replace(v)
}

// roundWindow: Windows 11 bo góc + đổ bóng qua DWM; Windows 10 thì cắt vùng bo tròn.
func roundWindow(hwnd uintptr, w, h int, scale float64) {
	build := windows.RtlGetVersion().BuildNumber
	if build >= 22000 {
		pref := uint32(2) // DWMWCP_ROUND
		procDwmSetWindowAttribute.Call(hwnd, 33, uintptr(unsafe.Pointer(&pref)), 4)
		return
	}
	r := int(26 * scale)
	rgn, _, _ := procCreateRoundRectRgn.Call(0, 0, uintptr(w+1), uintptr(h+1), uintptr(r), uintptr(r))
	if rgn != 0 {
		procSetWindowRgn.Call(hwnd, rgn, 1)
	}
}

// onLoaded chạy trên luồng UI khi trang tải xong: hiện cửa sổ rồi đẩy trạng thái đang giữ.
func (s *Splash) onLoaded() {
	s.showOnce.Do(func() {
		s.mu.Lock()
		wv := s.wv
		abandoned := s.abandoned
		s.mu.Unlock()
		if wv == nil || abandoned {
			return
		}
		hwnd := uintptr(wv.Window())
		procShowWindow.Call(hwnd, 5)                                               // SW_SHOW
		procSetWindowPos.Call(hwnd, ^uintptr(0), 0, 0, 0, 0, 0x0001|0x0002|0x0010) // HWND_TOPMOST, NOSIZE|NOMOVE|NOACTIVATE
		procSetForegroundWindow.Call(hwnd)
		wv.ShowContent()
		s.mu.Lock()
		s.loaded = true
		s.mu.Unlock()
		s.eval("splash.start()")
		s.flush()
		s.signalOpen(true)
	})
}

// flush đẩy lại trạng thái cuối cùng (những lần gọi trước khi trang tải xong).
func (s *Splash) flush() {
	s.mu.Lock()
	mode, pct, text, msg, fast := s.mode, s.lastPct, s.lastText, s.lastMsg, s.fast
	s.mu.Unlock()
	if text != "" {
		s.eval(fmt.Sprintf("splash.set(%.2f,%s)", pct, jsStr(text)))
	}
	switch mode {
	case "ready":
		s.eval(fmt.Sprintf("splash.ready(%v)", fast))
	case "error":
		s.eval("splash.fail(" + jsStr(msg) + ")")
	}
}

func jsStr(v string) string {
	b, _ := json.Marshal(v)
	return strings.NewReplacer(" ", ` `, " ", ` `).Replace(string(b))
}

// eval chạy JS trên luồng UI (bỏ qua nếu cửa sổ chưa/không còn).
func (s *Splash) eval(js string) {
	s.mu.Lock()
	wv, loaded := s.wv, s.loaded
	s.mu.Unlock()
	if wv == nil || !loaded {
		return
	}
	wv.Dispatch(func() { wv.Eval(js) })
}

// Update cập nhật tiến độ (0..100) và dòng trạng thái.
func (s *Splash) Update(pct float64, text string) {
	s.mu.Lock()
	if s.mode != "load" {
		s.mu.Unlock()
		return
	}
	if pct > s.lastPct {
		s.lastPct = pct
	}
	s.lastText = text
	p := s.lastPct
	s.mu.Unlock()
	s.eval(fmt.Sprintf("splash.set(%.2f,%s)", p, jsStr(text)))
}

// Ready chạy hiệu ứng "Sẵn sàng!", mờ dần rồi đóng cửa sổ; sau đó gọi after (goroutine riêng).
// fast = bản rút gọn (~0,8 giây) cho lần mở thứ hai.
func (s *Splash) Ready(fast bool, after func()) {
	if s.Closed() { // người dùng đã tắt cửa sổ trước đó
		if after != nil {
			go after()
		}
		return
	}
	s.mu.Lock()
	s.mode, s.fast, s.onFinish = "ready", fast, after
	s.mu.Unlock()
	s.eval(fmt.Sprintf("splash.ready(%v)", fast))
	// chốt an toàn: nếu JS không báo xong thì vẫn đóng
	go func() {
		select {
		case <-s.doneCh:
		case <-time.After(5 * time.Second):
			s.Close()
		}
	}()
}

// Fail chuyển sang thẻ lỗi (tiếng Việt, kèm nút Thử lại / Xem chi tiết / Đóng).
func (s *Splash) Fail(msg string) {
	s.mu.Lock()
	s.mode, s.lastMsg = "error", msg
	s.mu.Unlock()
	s.eval("splash.fail(" + jsStr(msg) + ")")
}

// Reset quay lại trạng thái đang tải (sau khi bấm Thử lại).
func (s *Splash) Reset() {
	s.mu.Lock()
	s.mode, s.lastPct, s.lastText, s.lastMsg = "load", 0, "", ""
	s.mu.Unlock()
	s.eval("splash.reset()")
}

// Closed cho biết cửa sổ đã đóng.
func (s *Splash) Closed() bool {
	select {
	case <-s.doneCh:
		return true
	default:
		return false
	}
}

// Wait chặn tới khi cửa sổ đóng.
func (s *Splash) Wait() { <-s.doneCh }

// Close đóng cửa sổ (an toàn gọi nhiều lần, từ mọi luồng).
func (s *Splash) Close() {
	s.mu.Lock()
	wv := s.wv
	s.mu.Unlock()
	if wv == nil {
		return
	}
	s.finishing.Do(func() {
		wv.Dispatch(func() { wv.Destroy() })
	})
}

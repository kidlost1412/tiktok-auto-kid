package main

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

var (
	user32   = windows.NewLazySystemDLL("user32.dll")
	dwmapi   = windows.NewLazySystemDLL("dwmapi.dll")
	ole32    = windows.NewLazySystemDLL("ole32.dll")
	kernel32 = windows.NewLazySystemDLL("kernel32.dll")

	pSetWindowsHookEx     = user32.NewProc("SetWindowsHookExW")
	pUnhookWindowsHookEx  = user32.NewProc("UnhookWindowsHookEx")
	pCallNextHookEx       = user32.NewProc("CallNextHookEx")
	pGetClassName         = user32.NewProc("GetClassNameW")
	pReleaseCapture       = user32.NewProc("ReleaseCapture")
	pSendMessage          = user32.NewProc("SendMessageW")
	pShowWindow           = user32.NewProc("ShowWindow")
	pGetDpiForSystem      = user32.NewProc("GetDpiForSystem")
	pSystemParametersInfo = user32.NewProc("SystemParametersInfoW")
	pSetForegroundWindow  = user32.NewProc("SetForegroundWindow")
	pMessageBox           = user32.NewProc("MessageBoxW")
	pDwmSetWindowAttr     = dwmapi.NewProc("DwmSetWindowAttribute")
	pDwmExtendFrame       = dwmapi.NewProc("DwmExtendFrameIntoClientArea")
	pCoInitializeEx       = ole32.NewProc("CoInitializeEx")
	pCoCreateInstance     = ole32.NewProc("CoCreateInstance")
	pCoTaskMemFree        = ole32.NewProc("CoTaskMemFree")
	pGetCurrentThreadID   = kernel32.NewProc("GetCurrentThreadId")
)

// ---------------------------------------------------------------- ổ đĩa

// Drive là một ổ cứng cố định.
type Drive struct {
	Letter string `json:"letter"`
	Label  string `json:"label"`
	Free   uint64 `json:"free"`
	Total  uint64 `json:"total"`
}

func fixedDrives() []Drive {
	mask, _ := windows.GetLogicalDrives()
	var out []Drive
	for i := 0; i < 26; i++ {
		if mask&(1<<uint(i)) == 0 {
			continue
		}
		root := fmt.Sprintf("%c:\\", 'A'+i)
		p, _ := windows.UTF16PtrFromString(root)
		if windows.GetDriveType(p) != windows.DRIVE_FIXED {
			continue
		}
		free, total := diskSpace(root)
		if total == 0 {
			continue
		}
		var label [261]uint16
		_ = windows.GetVolumeInformation(p, &label[0], uint32(len(label)), nil, nil, nil, nil, 0)
		out = append(out, Drive{Letter: fmt.Sprintf("%c", 'A'+i), Label: windows.UTF16ToString(label[:]), Free: free, Total: total})
	}
	return out
}

func diskSpace(path string) (free, total uint64) {
	p, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return 0, 0
	}
	var f, t, tf uint64
	if err := windows.GetDiskFreeSpaceEx(p, &f, &t, &tf); err != nil {
		return 0, 0
	}
	return f, t
}

// freeForPath trả dung lượng trống của ổ chứa path (dù path chưa tồn tại).
func freeForPath(path string) uint64 {
	vol := filepath.VolumeName(path)
	if vol == "" {
		return 0
	}
	f, _ := diskSpace(vol + `\`)
	return f
}

// ---------------------------------------------------------------- cửa sổ không viền

type createStruct struct {
	CreateParams uintptr
	Instance     uintptr
	Menu         uintptr
	Parent       uintptr
	Cy, Cx       int32
	Y, X         int32
	Style        int32
	Name         uintptr
	Class        uintptr
	ExStyle      uint32
}

type cbtCreateWnd struct {
	Cs          *createStruct
	InsertAfter uintptr
}

const (
	wsPopup       = 0x80000000
	wsMinimizeBox = 0x00020000
	wsSysMenu     = 0x00080000
	wsClipSibl    = 0x04000000
	wsClipChild   = 0x02000000
)

var hookHandle uintptr
var hookWidth, hookHeight int32

// installFramelessHook sửa kiểu cửa sổ "webview" ngay lúc tạo: không viền, đúng kích thước, giữa màn hình
// (tránh nháy thanh tiêu đề). Gọi trước khi tạo webview, gỡ bằng removeFramelessHook.
func installFramelessHook(w, h int32) {
	hookWidth, hookHeight = w, h
	cb := windows.NewCallback(func(nCode int32, wParam, lParam uintptr) uintptr {
		if nCode == 3 { // HCBT_CREATEWND
			var name [32]uint16
			pGetClassName.Call(wParam, uintptr(unsafe.Pointer(&name[0])), 32)
			if windows.UTF16ToString(name[:]) == "webview" {
				cbt := (*cbtCreateWnd)(ptr(lParam))
				cs := cbt.Cs
				// Style không đổi được ở đây; chỉ đặt cửa sổ ngoài màn hình để không nháy thanh tiêu đề.
				cs.Cx, cs.Cy = hookWidth, hookHeight
				cs.X, cs.Y = -32000, -32000
			}
		}
		r, _, _ := pCallNextHookEx.Call(0, uintptr(nCode), wParam, lParam)
		return r
	})
	tid, _, _ := pGetCurrentThreadID.Call()
	hookHandle, _, _ = pSetWindowsHookEx.Call(5, cb, 0, tid) // WH_CBT
}

func removeFramelessHook() {
	if hookHandle != 0 {
		pUnhookWindowsHookEx.Call(hookHandle)
		hookHandle = 0
	}
}

func decorateWindow(hwnd uintptr) {
	pref := uint32(2) // DWMWCP_ROUND
	pDwmSetWindowAttr.Call(hwnd, 33, uintptr(unsafe.Pointer(&pref)), 4)
	margins := [4]int32{1, 1, 1, 1}
	pDwmExtendFrame.Call(hwnd, uintptr(unsafe.Pointer(&margins[0])))
}

func dragWindow(hwnd uintptr) {
	pReleaseCapture.Call()
	pSendMessage.Call(hwnd, 0x00A1, 2, 0) // WM_NCLBUTTONDOWN, HTCAPTION
}

func minimizeWindow(hwnd uintptr) { pShowWindow.Call(hwnd, 6) }

func foreground(hwnd uintptr) { pSetForegroundWindow.Call(hwnd) }

func dpiScale() float64 {
	if pGetDpiForSystem.Find() != nil {
		return 1
	}
	d, _, _ := pGetDpiForSystem.Call()
	if d < 96 {
		return 1
	}
	return float64(d) / 96
}

func messageBox(title, text string) {
	t, _ := windows.UTF16PtrFromString(text)
	c, _ := windows.UTF16PtrFromString(title)
	pMessageBox.Call(0, uintptr(unsafe.Pointer(t)), uintptr(unsafe.Pointer(c)), 0x10)
}

// ---------------------------------------------------------------- chọn thư mục (IFileOpenDialog)

type guid struct {
	D1 uint32
	D2 uint16
	D3 uint16
	D4 [8]byte
}

var (
	clsidFileOpenDialog = guid{0xDC1C5A9C, 0xE88A, 0x4DDE, [8]byte{0xA5, 0xA1, 0x60, 0xF8, 0x2A, 0x20, 0xAE, 0xF7}}
	iidFileOpenDialog   = guid{0xd57c7288, 0xd4ad, 0x4768, [8]byte{0xbe, 0x02, 0x9d, 0x96, 0x95, 0x32, 0xd9, 0x60}}
)

func vcall(obj uintptr, idx int, args ...uintptr) uintptr {
	vtbl := *(*uintptr)(ptr(obj))
	fn := *(*uintptr)(ptr(vtbl + uintptr(idx)*unsafe.Sizeof(uintptr(0))))
	r, _, _ := syscall.SyscallN(fn, append([]uintptr{obj}, args...)...)
	return r
}

// pickFolder mở hộp thoại chọn thư mục của Windows. Trả "" nếu người dùng huỷ.
func pickFolder(owner uintptr, title string) (string, error) {
	pCoInitializeEx.Call(0, 2)
	var dlg uintptr
	hr, _, _ := pCoCreateInstance.Call(uintptr(unsafe.Pointer(&clsidFileOpenDialog)), 0, 1,
		uintptr(unsafe.Pointer(&iidFileOpenDialog)), uintptr(unsafe.Pointer(&dlg)))
	if hr != 0 || dlg == 0 {
		return "", fmt.Errorf("không mở được hộp thoại chọn thư mục (0x%x)", hr)
	}
	defer vcall(dlg, 2) // Release
	var opts uint32
	vcall(dlg, 10, uintptr(unsafe.Pointer(&opts))) // GetOptions
	vcall(dlg, 9, uintptr(opts|0x20|0x40))         // SetOptions: PICKFOLDERS | FORCEFILESYSTEM
	t, _ := windows.UTF16PtrFromString(title)
	vcall(dlg, 17, uintptr(unsafe.Pointer(t))) // SetTitle
	if r := vcall(dlg, 3, owner); r != 0 {     // Show
		return "", nil // huỷ (0x800704C7) hoặc lỗi
	}
	var item uintptr
	if r := vcall(dlg, 20, uintptr(unsafe.Pointer(&item))); r != 0 || item == 0 { // GetResult
		return "", nil
	}
	defer vcall(item, 2)
	var pw *uint16
	if r := vcall(item, 5, 0x80058000, uintptr(unsafe.Pointer(&pw))); r != 0 || pw == nil { // GetDisplayName(FILESYSPATH)
		return "", nil
	}
	defer pCoTaskMemFree.Call(uintptr(unsafe.Pointer(pw)))
	return windows.UTF16PtrToString(pw), nil
}

// ---------------------------------------------------------------- tiến trình

type procInfo struct {
	PID  uint32
	Exe  string
	Path string
}

func listProcs() []procInfo {
	snap, err := windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPPROCESS, 0)
	if err != nil {
		return nil
	}
	defer windows.CloseHandle(snap)
	var pe windows.ProcessEntry32
	pe.Size = uint32(unsafe.Sizeof(pe))
	var out []procInfo
	if err := windows.Process32First(snap, &pe); err != nil {
		return nil
	}
	for {
		p := procInfo{PID: pe.ProcessID, Exe: windows.UTF16ToString(pe.ExeFile[:])}
		if h, err := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, pe.ProcessID); err == nil {
			buf := make([]uint16, 1024)
			n := uint32(len(buf))
			if windows.QueryFullProcessImageName(h, 0, &buf[0], &n) == nil {
				p.Path = windows.UTF16ToString(buf[:n])
			}
			windows.CloseHandle(h)
		}
		out = append(out, p)
		if err := windows.Process32Next(snap, &pe); err != nil {
			break
		}
	}
	return out
}

func pathInside(p, dir string) bool {
	p = strings.ToLower(filepath.Clean(p))
	dir = strings.ToLower(filepath.Clean(dir))
	return p == dir || strings.HasPrefix(p, dir+`\`)
}

// killInside kết thúc mọi tiến trình có file chạy nằm TRONG dir (không đụng gì ngoài dir). TikTokAuto.exe chết trước.
// Trả về số tiến trình đã kết thúc.
func killInside(dir string, only string) int {
	self := uint32(os.Getpid())
	n := 0
	for _, p := range listProcs() {
		if p.PID == self || p.Path == "" || !pathInside(p.Path, dir) {
			continue
		}
		if only != "" && !strings.EqualFold(p.Exe, only) {
			continue
		}
		if h, err := windows.OpenProcess(windows.PROCESS_TERMINATE, false, p.PID); err == nil {
			if windows.TerminateProcess(h, 1) == nil {
				n++
			}
			windows.CloseHandle(h)
		}
	}
	return n
}

func portOpen(port int) bool {
	c, err := net.DialTimeout("tcp", fmt.Sprintf("127.0.0.1:%d", port), 300*time.Millisecond)
	if err != nil {
		return false
	}
	c.Close()
	return true
}

func shellOpen(target string) {
	verb, _ := windows.UTF16PtrFromString("open")
	t, _ := windows.UTF16PtrFromString(target)
	_ = windows.ShellExecute(0, verb, t, nil, nil, windows.SW_SHOWNORMAL)
}

func revealInExplorer(path string) {
	cmd := newHiddenCmd("explorer.exe", "/select,"+path)
	_ = cmd.Start()
}

// ptr đổi địa chỉ do Windows/COM trả về (uintptr) thành con trỏ.
func ptr(u uintptr) unsafe.Pointer { return *(*unsafe.Pointer)(unsafe.Pointer(&u)) }

var (
	pSetWindowLongPtr = user32.NewProc("SetWindowLongPtrW")
	pSetWindowPos     = user32.NewProc("SetWindowPos")
)

// frameless bỏ thanh tiêu đề/viền gốc, đặt đúng kích thước và căn giữa vùng làm việc.
func frameless(hwnd uintptr, w, h int32) {
	style := uint32(wsPopup | wsMinimizeBox | wsSysMenu | wsClipSibl | wsClipChild | 0x10000000)
	pSetWindowLongPtr.Call(hwnd, ^uintptr(15), uintptr(style)) // GWL_STYLE = -16
	var rc windows.Rect
	pSystemParametersInfo.Call(0x30, 0, uintptr(unsafe.Pointer(&rc)), 0)
	x := rc.Left + (rc.Right-rc.Left-w)/2
	y := rc.Top + (rc.Bottom-rc.Top-h)/2
	// SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
	pSetWindowPos.Call(hwnd, 0, uintptr(x), uintptr(y), uintptr(w), uintptr(h), 0x0004|0x0020|0x0040)
}

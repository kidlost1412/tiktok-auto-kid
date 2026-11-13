//go:build windows

package main

import (
	"context"
	"fmt"
	"runtime"
	"syscall"
	"unsafe"

	"golang.org/x/sys/windows"
)

// Bản sao (không import chéo module) của pickFolder trong installer/winapi_windows.go, thêm: luồng OS riêng + COM STA,
// cửa sổ chủ tạm thời luôn nằm trên cùng để hộp thoại không bị trình duyệt che, thư mục mở đầu, hạn chót.

var (
	ole32ctm   = windows.NewLazySystemDLL("ole32.dll")
	shell32ctm = windows.NewLazySystemDLL("shell32.dll")

	pctmCoInitializeEx  = ole32ctm.NewProc("CoInitializeEx")
	pctmCoUninitialize  = ole32ctm.NewProc("CoUninitialize")
	pctmCoCreateInst    = ole32ctm.NewProc("CoCreateInstance")
	pctmCoTaskMemFree   = ole32ctm.NewProc("CoTaskMemFree")
	pctmShItemFromParse = shell32ctm.NewProc("SHCreateItemFromParsingName")

	pctmCreateWindowEx = user32.NewProc("CreateWindowExW")
	pctmDestroyWindow  = user32.NewProc("DestroyWindow")
	pctmShowWindow     = user32.NewProc("ShowWindow")
	pctmSetForeground  = user32.NewProc("SetForegroundWindow")
	pctmKeybdEvent     = user32.NewProc("keybd_event")
	pctmEndDialog      = user32.NewProc("PostMessageW")
	pctmFindWindow     = user32.NewProc("FindWindowW")

	ctmClsidFileOpenDialog = ctmGUID{0xDC1C5A9C, 0xE88A, 0x4DDE, [8]byte{0xA5, 0xA1, 0x60, 0xF8, 0x2A, 0x20, 0xAE, 0xF7}}
	ctmIidFileOpenDialog   = ctmGUID{0xd57c7288, 0xd4ad, 0x4768, [8]byte{0xbe, 0x02, 0x9d, 0x96, 0x95, 0x32, 0xd9, 0x60}}
	ctmIidShellItem        = ctmGUID{0x43826D1E, 0xE718, 0x42EE, [8]byte{0xBC, 0x55, 0xA1, 0xE2, 0x61, 0xC3, 0x7B, 0xFE}}
)

type ctmGUID struct {
	D1 uint32
	D2 uint16
	D3 uint16
	D4 [8]byte
}

func init() { pickFolderFn = pickFolderDialog }

func ctmVcall(obj uintptr, idx int, args ...uintptr) uintptr {
	vtbl := *(*uintptr)(ctmPtr(obj))
	fn := *(*uintptr)(ctmPtr(vtbl + uintptr(idx)*unsafe.Sizeof(uintptr(0))))
	r, _, _ := syscall.SyscallN(fn, append([]uintptr{obj}, args...)...)
	return r
}

func ctmPtr(u uintptr) unsafe.Pointer { return *(*unsafe.Pointer)(unsafe.Pointer(&u)) }

type folderResult struct {
	path string
	err  error
}

// pickFolderDialog chạy hộp thoại trên một luồng OS riêng và đợi kết quả (hoặc ctx hết hạn: đóng hộp rồi báo lỗi).
func pickFolderDialog(ctx context.Context, title, start string) (string, error) {
	out := make(chan folderResult, 1)
	titleKey := fmt.Sprintf("tta-chon-%d", windows.GetCurrentProcessId())
	go func() {
		runtime.LockOSThread()
		defer runtime.UnlockOSThread()
		p, err := pickFolderOnThread(title, start, titleKey)
		out <- folderResult{p, err}
	}()
	select {
	case r := <-out:
		return r.path, r.err
	case <-ctx.Done():
		// Đóng hộp bằng WM_CLOSE gửi tới cửa sổ chủ tạm (tìm theo tên lớp duy nhất) rồi đợi luồng kết thúc.
		class, _ := windows.UTF16PtrFromString("STATIC")
		if name, err := windows.UTF16PtrFromString(titleKey); err == nil {
			if h, _, _ := pctmFindWindow.Call(uintptr(unsafe.Pointer(class)), uintptr(unsafe.Pointer(name))); h != 0 {
				pctmEndDialog.Call(h, 0x0010, 0, 0)
			}
		}
		return "", fmt.Errorf("hộp chọn thư mục mở quá lâu nên đã đóng")
	}
}

func pickFolderOnThread(title, start, cls string) (string, error) {
	if hr, _, _ := pctmCoInitializeEx.Call(0, 2); hr == 0 || hr == 1 { // S_OK / S_FALSE
		defer pctmCoUninitialize.Call()
	}

	// Cửa sổ chủ ẩn danh, luôn trên cùng (lớp STATIC có sẵn; tên cửa sổ là khoá để tìm khi quá hạn).
	owner := createTopmostOwner(cls)
	if owner != 0 {
		defer pctmDestroyWindow.Call(owner)
		bringForeground(owner)
	}

	var dlg uintptr
	hr, _, _ := pctmCoCreateInst.Call(uintptr(unsafe.Pointer(&ctmClsidFileOpenDialog)), 0, 1,
		uintptr(unsafe.Pointer(&ctmIidFileOpenDialog)), uintptr(unsafe.Pointer(&dlg)))
	if hr != 0 || dlg == 0 {
		return "", fmt.Errorf("không mở được hộp thoại chọn thư mục (0x%x)", hr)
	}
	defer ctmVcall(dlg, 2) // Release

	var opts uint32
	ctmVcall(dlg, 10, uintptr(unsafe.Pointer(&opts))) // GetOptions
	ctmVcall(dlg, 9, uintptr(opts|0x20|0x40))         // SetOptions: PICKFOLDERS | FORCEFILESYSTEM
	if t, err := windows.UTF16PtrFromString(title); err == nil {
		ctmVcall(dlg, 17, uintptr(unsafe.Pointer(t))) // SetTitle
	}
	if start != "" {
		if sp, err := windows.UTF16PtrFromString(start); err == nil {
			var si uintptr
			if r, _, _ := pctmShItemFromParse.Call(uintptr(unsafe.Pointer(sp)), 0, uintptr(unsafe.Pointer(&ctmIidShellItem)), uintptr(unsafe.Pointer(&si))); r == 0 && si != 0 {
				ctmVcall(dlg, 12, si) // SetFolder
				ctmVcall(si, 2)       // Release
			}
		}
	}
	if r := ctmVcall(dlg, 3, owner); r != 0 { // Show: huỷ (0x800704C7) hoặc lỗi
		return "", nil
	}
	var item uintptr
	if r := ctmVcall(dlg, 20, uintptr(unsafe.Pointer(&item))); r != 0 || item == 0 { // GetResult
		return "", nil
	}
	defer ctmVcall(item, 2)
	var pw *uint16
	if r := ctmVcall(item, 5, 0x80058000, uintptr(unsafe.Pointer(&pw))); r != 0 || pw == nil { // GetDisplayName(FILESYSPATH)
		return "", nil
	}
	defer pctmCoTaskMemFree.Call(uintptr(unsafe.Pointer(pw)))
	return windows.UTF16PtrToString(pw), nil
}

func createTopmostOwner(name string) uintptr {
	class, _ := windows.UTF16PtrFromString("STATIC")
	n, _ := windows.UTF16PtrFromString(name)
	const wsPopupStyle = 0x80000000
	const exTopmostTool = 0x00000008 | 0x00000080 // WS_EX_TOPMOST | WS_EX_TOOLWINDOW
	h, _, _ := pctmCreateWindowEx.Call(exTopmostTool, uintptr(unsafe.Pointer(class)), uintptr(unsafe.Pointer(n)),
		wsPopupStyle, 0, 0, 0, 0, 0, 0, 0, 0)
	return h
}

// bringForeground: Windows chỉ cho tiến trình "vừa có thao tác phím" giành foreground; giả lập nhấn Alt rồi nhả.
func bringForeground(hwnd uintptr) {
	pctmShowWindow.Call(hwnd, 5) // SW_SHOW (kích thước 0, vô hình nhưng hợp lệ làm chủ)
	pctmKeybdEvent.Call(0x12, 0, 0, 0)
	pctmKeybdEvent.Call(0x12, 0, 0x0002, 0) // KEYEVENTF_KEYUP
	pctmSetForeground.Call(hwnd)
}

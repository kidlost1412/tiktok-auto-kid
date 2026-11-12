//go:build windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
	"golang.org/x/sys/windows/registry"
)

const (
	runKeyPath   = `Software\Microsoft\Windows\CurrentVersion\Run`
	runValueName = "TikTokAuto"
	mutexName    = `Local\TikTokAutoLauncher`
)

var (
	kernel32                 = windows.NewLazySystemDLL("kernel32.dll")
	procAttachConsole        = kernel32.NewProc("AttachConsole")
	procFreeConsole          = kernel32.NewProc("FreeConsole")
	procSetConsoleCtrlHander = kernel32.NewProc("SetConsoleCtrlHandler")
	procGenerateCtrlEvent    = kernel32.NewProc("GenerateConsoleCtrlEvent")

	jobHandle windows.Handle
)

// initJob tạo Job Object KILL_ON_JOB_CLOSE: mọi tiến trình con bị diệt khi launcher chết.
func initJob() error {
	h, err := windows.CreateJobObject(nil, nil)
	if err != nil {
		return err
	}
	var info windows.JOBOBJECT_EXTENDED_LIMIT_INFORMATION
	// BREAKAWAY_OK: tiến trình con tạo bằng CREATE_BREAKAWAY_FROM_JOB (vd batch của Xưởng Video) thoát khỏi job và sống sót khi dịch vụ khởi động lại.
	info.BasicLimitInformation.LimitFlags = windows.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | windows.JOB_OBJECT_LIMIT_BREAKAWAY_OK
	if _, err := windows.SetInformationJobObject(h, windows.JobObjectExtendedLimitInformation,
		uintptr(unsafe.Pointer(&info)), uint32(unsafe.Sizeof(info))); err != nil {
		windows.CloseHandle(h)
		return err
	}
	jobHandle = h
	return nil
}

func assignJob(pid int) error {
	if jobHandle == 0 {
		return nil
	}
	h, err := windows.OpenProcess(windows.PROCESS_SET_QUOTA|windows.PROCESS_TERMINATE, false, uint32(pid))
	if err != nil {
		return err
	}
	defer windows.CloseHandle(h)
	return windows.AssignProcessToJobObject(jobHandle, h)
}

// childAttr: ẩn cửa sổ console, tạo nhóm tiến trình riêng (để gửi CTRL_BREAK).
func childAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{
		HideWindow:    true,
		CreationFlags: windows.CREATE_NO_WINDOW | windows.CREATE_NEW_PROCESS_GROUP,
	}
}

func hiddenAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{HideWindow: true, CreationFlags: windows.CREATE_NO_WINDOW}
}

// hiddenCmd tạo lệnh chạy ngầm, không cửa sổ.
func hiddenCmd(name string, args ...string) *exec.Cmd {
	c := exec.Command(name, args...)
	c.SysProcAttr = hiddenAttr()
	return c
}

// sendCtrlBreak gửi CTRL_BREAK tới nhóm tiến trình pid. Việc attach console làm
// trong một tiến trình phụ (chính exe này, cờ --send-break) để không đụng console của launcher.
func sendCtrlBreak(pid int) {
	self, err := os.Executable()
	if err != nil {
		return
	}
	c := exec.Command(self, "--send-break", strconv.Itoa(pid))
	c.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.DETACHED_PROCESS}
	if err := c.Start(); err != nil {
		return
	}
	done := make(chan struct{})
	go func() { c.Wait(); close(done) }()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		c.Process.Kill()
	}
}

// runSendBreakHelper chạy trong tiến trình phụ: attach console của pid và gửi CTRL_BREAK.
func runSendBreakHelper(pid uint32) int {
	procFreeConsole.Call()
	if r, _, _ := procAttachConsole.Call(uintptr(pid)); r == 0 {
		return 1
	}
	procSetConsoleCtrlHander.Call(0, 1) // bỏ qua tín hiệu cho chính tiến trình phụ
	procGenerateCtrlEvent.Call(uintptr(windows.CTRL_BREAK_EVENT), uintptr(pid))
	time.Sleep(300 * time.Millisecond)
	procFreeConsole.Call()
	return 0
}

// killTree diệt tiến trình và toàn bộ cây con.
func killTree(pid int) {
	hiddenCmd("taskkill", "/T", "/F", "/PID", strconv.Itoa(pid)).Run()
}

// acquireSingleInstance trả true nếu đã có launcher khác đang chạy.
func acquireSingleInstance() (alreadyRunning bool, err error) {
	name, _ := windows.UTF16PtrFromString(mutexName)
	_, err = windows.CreateMutex(nil, false, name) // giữ handle đến khi thoát
	if err == windows.ERROR_ALREADY_EXISTS {
		return true, nil
	}
	return false, err
}

// attachConsole gắn console của tiến trình cha (cho --console/--check trong exe windowsgui).
func attachConsole() {
	procAttachConsole.Call(^uintptr(0)) // ATTACH_PARENT_PROCESS
	h, _ := windows.GetStdHandle(windows.STD_OUTPUT_HANDLE)
	if h == 0 || h == windows.InvalidHandle {
		if f, err := os.OpenFile("CONOUT$", os.O_WRONLY, 0); err == nil {
			os.Stdout = f
			os.Stderr = f
		}
	}
}

// openPath mở URL hoặc thư mục bằng ứng dụng mặc định.
func openPath(target string) {
	verb, _ := windows.UTF16PtrFromString("open")
	t, _ := windows.UTF16PtrFromString(target)
	windows.ShellExecute(0, verb, t, nil, nil, windows.SW_SHOWNORMAL)
}

func messageBox(title, text string) {
	t, _ := windows.UTF16PtrFromString(title)
	m, _ := windows.UTF16PtrFromString(text)
	windows.MessageBox(0, m, t, windows.MB_OK|windows.MB_ICONWARNING|windows.MB_SETFOREGROUND|windows.MB_TOPMOST)
}

func autostartEnabled() bool {
	k, err := registry.OpenKey(registry.CURRENT_USER, runKeyPath, registry.QUERY_VALUE)
	if err != nil {
		return false
	}
	defer k.Close()
	_, _, err = k.GetStringValue(runValueName)
	return err == nil
}

// setAutostart bật/tắt chạy cùng Windows (chỉ người dùng hiện tại, HKCU).
func setAutostart(on bool) error {
	k, _, err := registry.CreateKey(registry.CURRENT_USER, runKeyPath, registry.SET_VALUE|registry.QUERY_VALUE)
	if err != nil {
		return err
	}
	defer k.Close()
	if !on {
		if err := k.DeleteValue(runValueName); err != nil && err != registry.ErrNotExist {
			return err
		}
		return nil
	}
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	return k.SetStringValue(runValueName, fmt.Sprintf(`"%s" --autostart`, exe))
}

// portOwner cố gắng cho biết tên tiến trình đang chiếm cổng; "" nếu không rõ.
func portOwner(port int) string {
	out, err := hiddenCmd("netstat", "-ano", "-p", "TCP").Output()
	if err != nil {
		return ""
	}
	pid, ok := ParseNetstatListeners(string(out))[port]
	if !ok {
		return ""
	}
	out, err = hiddenCmd("tasklist", "/FI", fmt.Sprintf("PID eq %d", pid), "/FO", "CSV", "/NH").Output()
	if err != nil {
		return fmt.Sprintf("PID %d", pid)
	}
	if n := ParseTasklistName(string(out)); n != "" {
		return fmt.Sprintf("%s (PID %d)", n, pid)
	}
	return fmt.Sprintf("PID %d", pid)
}

// listenerPID trả PID đang LISTEN trên cổng (0 nếu không rõ).
func listenerPID(port int) int {
	out, err := hiddenCmd("netstat", "-ano", "-p", "TCP").Output()
	if err != nil {
		return 0
	}
	return ParseNetstatListeners(string(out))[port]
}

// procImagePath trả đường dẫn exe của tiến trình ("" nếu không đọc được).
func procImagePath(pid int) string {
	h, err := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, uint32(pid))
	if err != nil {
		return ""
	}
	defer windows.CloseHandle(h)
	buf := make([]uint16, 1024)
	n := uint32(len(buf))
	if windows.QueryFullProcessImageName(h, 0, &buf[0], &n) != nil {
		return ""
	}
	return windows.UTF16ToString(buf[:n])
}

// startPGWatchdog chạy tiến trình phụ (nằm ngoài Job Object) chờ launcher chết rồi dừng Postgres.
func startPGWatchdog(root string) {
	self, err := os.Executable()
	if err != nil {
		return
	}
	c := exec.Command(self, "--watch-pg", strconv.Itoa(os.Getpid()), "--root", root)
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: windows.DETACHED_PROCESS | windows.CREATE_NO_WINDOW | windows.CREATE_NEW_PROCESS_GROUP}
	if c.Start() == nil {
		go c.Wait()
	}
}

// runPGWatchdog: chờ PID launcher kết thúc, rồi pg_ctl stop nếu còn postmaster.pid.
func runPGWatchdog(launcherPID uint32, root string) int {
	h, err := windows.OpenProcess(windows.SYNCHRONIZE, false, launcherPID)
	if err != nil {
		return 0 // launcher đã chết sẵn hoặc không mở được: không làm gì
	}
	windows.WaitForSingleObject(h, windows.INFINITE)
	windows.CloseHandle(h)
	pgCtlStop(root)
	return 0
}

// pgCtlStop dừng Postgres của bundle (nếu có postmaster.pid). Trả true nếu lệnh thành công.
func pgCtlStop(root string) bool {
	data := filepath.Join(root, "runtime", "data", "pg")
	if _, err := os.Stat(filepath.Join(data, "postmaster.pid")); err != nil {
		return true
	}
	ctl := filepath.Join(root, "runtime", "pgsql", "bin", "pg_ctl.exe")
	return hiddenCmd(ctl, "stop", "-D", data, "-m", "fast", "-w", "-t", "60").Run() == nil
}

// waitPID chờ tiến trình pid thoát (tối đa d); không mở được tiến trình thì coi như đã thoát.
func waitPID(pid uint32, d time.Duration) {
	h, err := windows.OpenProcess(windows.SYNCHRONIZE, false, pid)
	if err != nil {
		return
	}
	defer windows.CloseHandle(h)
	windows.WaitForSingleObject(h, uint32(d/time.Millisecond))
}

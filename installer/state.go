package main

import (
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/sys/windows"
	"golang.org/x/sys/windows/registry"
)

// Installed mô tả một bản cài sẵn có.
type Installed struct {
	Dir       string `json:"dir"`
	Data      string `json:"data"`
	Version   string `json:"version"`
	Autostart bool   `json:"autostart"`
}

type installJSON struct {
	ThuMuc          string `json:"thu_muc"`
	DuLieu          string `json:"du_lieu"`
	PhienBan        string `json:"phien_ban"`
	ChayCungWindows bool   `json:"chay_cung_windows"`
}

func testMode() bool { return *fThuMucGo != "" }

func uninstallKeyName() string {
	if testMode() {
		return "TikTokAutoKid-TEST"
	}
	return "TikTokAutoKid"
}

func uninstallKeyPath() string {
	return `Software\Microsoft\Windows\CurrentVersion\Uninstall\` + uninstallKeyName()
}

// runKeyPath là khoá Run mà launcher ghi (giá trị "TikTokAuto"); khi thử nghiệm dùng khoá giả.
func runKeyPath() string {
	if testMode() {
		return `Software\TikTokAutoKidTEST\Run`
	}
	return `Software\Microsoft\Windows\CurrentVersion\Run`
}

const runValueName = "TikTokAuto"

func readInstallJSON(dir string) (installJSON, bool) {
	b, err := os.ReadFile(filepath.Join(dir, "runtime", "install.json"))
	if err != nil {
		return installJSON{}, false
	}
	b = []byte(strings.TrimPrefix(string(b), "\xef\xbb\xbf"))
	var j installJSON
	if json.Unmarshal(b, &j) != nil {
		return installJSON{}, false
	}
	return j, true
}

func readVersionFile(dir string) string {
	b, err := os.ReadFile(filepath.Join(dir, "VERSION"))
	if err != nil {
		return ""
	}
	return strings.TrimPrefix(strings.TrimSpace(strings.TrimPrefix(string(b), "\xef\xbb\xbf")), "v")
}

func installedAt(dir string) *Installed {
	if dir == "" {
		return nil
	}
	_, e1 := os.Stat(filepath.Join(dir, "TikTokAuto.exe"))
	j, ok := readInstallJSON(dir)
	if e1 != nil && !ok {
		return nil
	}
	in := &Installed{Dir: dir, Data: j.DuLieu, Version: j.PhienBan, Autostart: j.ChayCungWindows}
	if v := readVersionFile(dir); v != "" {
		in.Version = v
	}
	if in.Data == "" {
		d := filepath.Join(dir, "du-lieu", "xuong-video")
		if st, err := os.Stat(d); err == nil && st.IsDir() {
			in.Data = d
		}
	}
	return in
}

// detectInstall tìm bản cài qua registry rồi qua thư mục mặc định.
func detectInstall() *Installed {
	if k, err := registry.OpenKey(registry.CURRENT_USER, uninstallKeyPath(), registry.QUERY_VALUE); err == nil {
		loc, _, _ := k.GetStringValue("InstallLocation")
		k.Close()
		if in := installedAt(loc); in != nil {
			return in
		}
	}
	return installedAt(defaultInstallDir())
}

// shellDirs là nơi đặt lối tắt. Khi thử nghiệm gỡ: thư mục giả, không đụng lối tắt thật.
type shellDirsT struct{ Desktop, Programs, Startup string }

func shellDirs() shellDirsT {
	if testMode() {
		base := filepath.Join(filepath.Dir(filepath.Clean(*fThuMucGo)), "fake-shell")
		return shellDirsT{filepath.Join(base, "Desktop"), filepath.Join(base, "Programs"), filepath.Join(base, "Startup")}
	}
	get := func(id *windows.KNOWNFOLDERID) string {
		p, _ := windows.KnownFolderPath(id, 0)
		return p
	}
	return shellDirsT{get(windows.FOLDERID_Desktop), get(windows.FOLDERID_Programs), get(windows.FOLDERID_Startup)}
}

const lnkName = "TikTok Auto Kid.lnk"

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		return err
	}
	return out.Close()
}

// dirSize cộng dung lượng thư mục (bỏ qua lỗi). Dừng sớm nếu stop() trả true.
func dirSize(dir string, stop func() bool) int64 {
	var n int64
	_ = filepath.WalkDir(dir, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if stop != nil && stop() {
			return filepath.SkipAll
		}
		if !d.IsDir() {
			if fi, e := d.Info(); e == nil {
				n += fi.Size()
			}
		}
		return nil
	})
	return n
}

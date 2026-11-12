package main

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func TestCompareVersions(t *testing.T) {
	cases := []struct {
		a, b string
		want int
	}{
		{"1.0.0", "1.0.0", 0},
		{"1.0.1", "1.0.0", 1},
		{"1.0.0", "1.1.0", -1},
		{"v2.0.0", "1.9.9", 1},
		{"1.10.0", "1.9.0", 1}, // so số, không so chuỗi
		{"1.2", "1.2.0", 0},
		{"1.0.0-rc.1", "1.0.0", -1},
		{"1.0.0-rc.2", "1.0.0-rc.10", -1},
		{"1.0.0-alpha", "1.0.0-beta", -1},
		{"1.0.0+build5", "1.0.0", 0},
	}
	for _, c := range cases {
		got, err := CompareVersions(c.a, c.b)
		if err != nil || got != c.want {
			t.Errorf("CompareVersions(%q,%q)=%d,%v muốn %d", c.a, c.b, got, err, c.want)
		}
	}
	for _, bad := range []string{"", "abc", "1.2.3.4", "1..2", "01.2.3", "1.2.x", "-1.0.0"} {
		if _, err := ParseVersion(bad); err == nil {
			t.Errorf("%q phải bị từ chối", bad)
		}
	}
	if !IsNewer("1.0.1", "1.0.0") || IsNewer("1.0.0", "1.0.0") || IsNewer("garbage", "1.0.0") {
		t.Error("IsNewer sai")
	}
}

func TestReadVersion(t *testing.T) {
	root := t.TempDir()
	if ReadVersion(root) != "0.0.0" {
		t.Fatal("thiếu VERSION phải là 0.0.0")
	}
	os.WriteFile(filepath.Join(root, "VERSION"), []byte("\xef\xbb\xbfv1.4.2\r\n"), 0o644)
	if v := ReadVersion(root); v != "1.4.2" {
		t.Fatalf("got %q", v)
	}
	os.WriteFile(filepath.Join(root, "VERSION"), []byte("rác"), 0o644)
	if ReadVersion(root) != "0.0.0" {
		t.Fatal("VERSION hỏng phải là 0.0.0")
	}
}

func TestNormalizeRelRejects(t *testing.T) {
	for _, bad := range []string{"", "../x", "a/../../x", "/etc/passwd", `C:\Windows\x`, "C:/x", `..\x`, "a/./b", "a//b", "x:stream", "a\x00b", "dir/.."} {
		if _, err := NormalizeRel(bad); err == nil {
			t.Errorf("%q phải bị từ chối", bad)
		}
	}
	if n, err := NormalizeRel(`app\Fork\X.php`); err != nil || n != "app/Fork/X.php" {
		t.Errorf("chuẩn hoá: %q %v", n, err)
	}
}

func TestIsProtected(t *testing.T) {
	prot := []string{
		".env", ".env.production", "runtime/services.json", "runtime/php/php.exe", "storage/app/x", "storage/framework/cache/a",
		"du-lieu/video.mp4", "xuong-video/tai-khoan/a.json", "xuong-video/.venv/Scripts/python.exe", "node_modules/x/y.js",
		"xuong-video/remotion/node_modules/a", "TikTokAuto.exe", "Runtime/PHP/php.exe", "sub/.env", ".git/config", "dist/a.zip",
	}
	for _, p := range prot {
		if !IsProtected(p) {
			t.Errorf("%s phải được bảo vệ", p)
		}
	}
	free := []string{"app/Http/X.php", "vendor/laravel/a.php", "public/build/app.js", ".env.example", "VERSION", "TikTokAuto.new.exe",
		"xuong-video/requirements.txt", "xuong-video/app/server.py", "composer.json"}
	for _, p := range free {
		if IsProtected(p) {
			t.Errorf("%s không được bảo vệ", p)
		}
	}
}

func TestStaleFilesExcludesProtected(t *testing.T) {
	oldM := []string{"app/A.php", "app/B.php", "runtime/x", ".env", "storage/a", "vendor/v/old.php", "release-manifest.txt"}
	newM := []string{"app/A.php", "vendor/v/new.php"}
	got := StaleFiles(oldM, newM)
	want := []string{"app/B.php", "vendor/v/old.php"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v want %v", got, want)
	}
}

func TestSafeDeleteNeverEscapes(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "install")
	os.MkdirAll(filepath.Join(root, "app", "sub"), 0o755)
	os.MkdirAll(filepath.Join(root, "runtime"), 0o755)
	outside := filepath.Join(base, "outside.txt")
	os.WriteFile(outside, []byte("giữ"), 0o644)
	os.WriteFile(filepath.Join(root, ".env"), []byte("SECRET=1"), 0o644)
	os.WriteFile(filepath.Join(root, "runtime", "services.json"), []byte("{}"), 0o644)
	os.WriteFile(filepath.Join(root, "app", "sub", "old.php"), []byte("x"), 0o644)

	for _, bad := range []string{"../outside.txt", `..\outside.txt`, outside, ".env", "runtime/services.json", "runtime"} {
		if err := SafeDelete(root, bad); err == nil {
			t.Errorf("SafeDelete(%q) phải lỗi", bad)
		}
	}
	for _, p := range []string{outside, filepath.Join(root, ".env"), filepath.Join(root, "runtime", "services.json")} {
		if _, err := os.Stat(p); err != nil {
			t.Errorf("%s đã bị xoá nhầm", p)
		}
	}
	// thư mục không bị xoá, chỉ file thường
	if err := SafeDelete(root, "app"); err == nil {
		t.Error("không được xoá thư mục")
	}
	// file hợp lệ bị xoá, thư mục rỗng được dọn, root còn nguyên
	if err := SafeDelete(root, "app/sub/old.php"); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(root, "app", "sub")); err == nil {
		t.Error("thư mục rỗng phải được dọn")
	}
	if _, err := os.Stat(root); err != nil {
		t.Fatal("root bị xoá")
	}
	// DeleteStale bỏ qua đường dẫn xấu và tiếp tục
	log := NewLogger()
	os.MkdirAll(filepath.Join(root, "app"), 0o755)
	os.WriteFile(filepath.Join(root, "app", "z.php"), []byte("x"), 0o644)
	n := DeleteStale(root, []string{"../outside.txt", ".env", "app/z.php"}, log)
	if n != 1 {
		t.Errorf("DeleteStale xoá %d, muốn 1", n)
	}
	if _, err := os.Stat(outside); err != nil {
		t.Error("file ngoài bị xoá")
	}
}

func TestSafeDeleteRefusesJunctionEscape(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "install")
	outDir := filepath.Join(base, "outdir")
	os.MkdirAll(root, 0o755)
	os.MkdirAll(outDir, 0o755)
	victim := filepath.Join(outDir, "victim.txt")
	os.WriteFile(victim, []byte("x"), 0o644)
	if err := os.Symlink(outDir, filepath.Join(root, "link")); err != nil {
		t.Skip("không tạo được symlink:", err)
	}
	if err := SafeDelete(root, "link/victim.txt"); err == nil {
		t.Error("phải từ chối đi qua symlink ra ngoài")
	}
	if _, err := os.Stat(victim); err != nil {
		t.Error("file ngoài bị xoá qua symlink")
	}
}

// ---- zip helpers ----

type zf struct{ name, body string }

func makeZip(t *testing.T, files []zf) string {
	t.Helper()
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	for _, f := range files {
		w, err := zw.Create(f.name)
		if err != nil {
			t.Fatal(err)
		}
		w.Write([]byte(f.body))
	}
	zw.Close()
	p := filepath.Join(t.TempDir(), "pkg.zip")
	os.WriteFile(p, buf.Bytes(), 0o644)
	return p
}

func releaseFiles(ver string, files map[string]string) []zf {
	var out []zf
	var names []string
	out = append(out, zf{"VERSION", ver + "\n"})
	names = append(names, "VERSION")
	for n, b := range files {
		out = append(out, zf{n, b})
		names = append(names, n)
	}
	out = append(out, zf{manifestName, strings.Join(names, "\n") + "\n"})
	return out
}

func TestOpenPackageZipSlip(t *testing.T) {
	for _, evil := range []string{"../evil.txt", "a/../../evil.txt", "/abs/evil.txt", `..\evil.txt`, "C:/evil.txt", `C:\evil.txt`} {
		files := releaseFiles("1.1.0", map[string]string{"app/ok.php": "x"})
		files = append(files, zf{evil, "pwn"})
		p := makeZip(t, files)
		if pkg, err := OpenPackage(p); err == nil {
			pkg.Close()
			t.Errorf("zip chứa %q phải bị từ chối", evil)
		}
	}
	// manifest chứa đường dẫn xấu
	p := makeZip(t, []zf{{"VERSION", "1.1.0"}, {manifestName, "VERSION\n../evil\n"}})
	if pkg, err := OpenPackage(p); err == nil {
		pkg.Close()
		t.Error("manifest xấu phải bị từ chối")
	}
	// manifest liệt kê file không có trong gói
	p = makeZip(t, []zf{{"VERSION", "1.1.0"}, {manifestName, "VERSION\napp/missing.php\n"}})
	if pkg, err := OpenPackage(p); err == nil {
		pkg.Close()
		t.Error("manifest lệch gói phải bị từ chối")
	}
	// thiếu manifest / VERSION
	if pkg, err := OpenPackage(makeZip(t, []zf{{"VERSION", "1.1.0"}})); err == nil {
		pkg.Close()
		t.Error("thiếu manifest phải bị từ chối")
	}
	if pkg, err := OpenPackage(makeZip(t, []zf{{manifestName, "x\n"}, {"x", "1"}})); err == nil {
		pkg.Close()
		t.Error("thiếu VERSION phải bị từ chối")
	}
}

func TestExtractSkipsProtectedAndStaysInside(t *testing.T) {
	root := t.TempDir()
	os.WriteFile(filepath.Join(root, ".env"), []byte("SECRET=keep"), 0o644)
	os.MkdirAll(filepath.Join(root, "runtime"), 0o755)
	os.WriteFile(filepath.Join(root, "runtime", "control.token"), []byte("tok"), 0o644)
	files := releaseFiles("1.1.0", map[string]string{
		"app/New.php": "<?php", ".env": "SECRET=evil", "runtime/control.token": "evil", "storage/app/x": "evil",
	})
	pkg, err := OpenPackage(makeZip(t, files))
	if err != nil {
		t.Fatal(err)
	}
	defer pkg.Close()
	written, err := pkg.Extract(root, NewLogger())
	if err != nil {
		t.Fatal(err)
	}
	if b, _ := os.ReadFile(filepath.Join(root, ".env")); string(b) != "SECRET=keep" {
		t.Error(".env bị ghi đè")
	}
	if b, _ := os.ReadFile(filepath.Join(root, "runtime", "control.token")); string(b) != "tok" {
		t.Error("runtime bị ghi đè")
	}
	if _, err := os.Stat(filepath.Join(root, "storage", "app", "x")); err == nil {
		t.Error("storage bị ghi")
	}
	if _, err := os.Stat(filepath.Join(root, "app", "New.php")); err != nil {
		t.Error("file thường phải được giải nén")
	}
	for _, w := range written {
		if IsProtected(w) {
			t.Errorf("đã ghi file được bảo vệ %s", w)
		}
	}
}

func TestSHA256Mismatch(t *testing.T) {
	body := []byte("nội dung gói giả")
	sum := sha256.Sum256(body)
	good := hex.EncodeToString(sum[:])
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/z.zip":
			w.Write(body)
		case "/good.sha256":
			w.Write([]byte(good + "  tiktok-auto-kid-1.1.0.zip\n"))
		case "/bad.sha256":
			w.Write([]byte(strings.Repeat("0", 64) + "\n"))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()
	old := allowedDownloadHost
	allowedDownloadHost = func(string) bool { return true }
	defer func() { allowedDownloadHost = old }()

	dir := t.TempDir()
	rel := &ReleaseInfo{Version: "1.1.0", ZipName: "tiktok-auto-kid-1.1.0.zip", ZipURL: srv.URL + "/z.zip", SHAURL: srv.URL + "/good.sha256"}
	p, err := DownloadRelease(context.Background(), rel, dir, srv.Client(), nil)
	if err != nil {
		t.Fatalf("mã đúng phải qua: %v", err)
	}
	if _, err := os.Stat(p); err != nil {
		t.Fatal("thiếu file đã tải")
	}
	rel.SHAURL = srv.URL + "/bad.sha256"
	dir2 := t.TempDir()
	p2, err := DownloadRelease(context.Background(), rel, dir2, srv.Client(), nil)
	if err == nil || !strings.Contains(err.Error(), "sha256") {
		t.Fatalf("sai mã phải huỷ, got %v", err)
	}
	if p2 != "" {
		t.Error("không được trả đường dẫn khi sai mã")
	}
	if ents, _ := os.ReadDir(dir2); len(ents) != 0 {
		t.Error("file sai mã phải bị xoá")
	}
	if _, err := ParseSHA256File([]byte("không có mã")); err == nil {
		t.Error("file .sha256 rác phải lỗi")
	}
}

func TestDownloadRejectsNonGitHub(t *testing.T) {
	rel := &ReleaseInfo{ZipName: "a.zip", ZipURL: "https://evil.example.com/a.zip", SHAURL: "https://evil.example.com/a.sha256"}
	if _, err := DownloadRelease(context.Background(), rel, t.TempDir(), nil, nil); err == nil {
		t.Error("phải từ chối host lạ")
	}
	if allowedDownloadHost("http://github.com/x") || !allowedDownloadHost("https://github.com/x") ||
		!allowedDownloadHost("https://objects.githubusercontent.com/x") || allowedDownloadHost("https://github.com.evil.io/x") {
		t.Error("allowedDownloadHost sai")
	}
}

func TestParseRelease(t *testing.T) {
	js := `{"tag_name":"v1.2.0","body":"- sửa lỗi","html_url":"https://github.com/o/r/releases/tag/v1.2.0","assets":[
	 {"name":"tiktok-auto-kid-1.2.0.zip","browser_download_url":"https://github.com/o/r/releases/download/v1.2.0/tiktok-auto-kid-1.2.0.zip","size":10},
	 {"name":"tiktok-auto-kid-1.2.0.zip.sha256","browser_download_url":"https://github.com/o/r/releases/download/v1.2.0/tiktok-auto-kid-1.2.0.zip.sha256","size":90}]}`
	r, err := ParseRelease([]byte(js))
	if err != nil || r.Version != "1.2.0" || r.ZipURL == "" || r.SHAURL == "" {
		t.Fatalf("%+v %v", r, err)
	}
	if _, err := ParseRelease([]byte(strings.Replace(js, ".zip.sha256\"", ".zip.txt\"", 1))); err == nil {
		t.Error("thiếu .sha256 phải lỗi")
	}
	if _, err := ParseRelease([]byte(`{"tag_name":"nightly","assets":[]}`)); err == nil {
		t.Error("tag không phải phiên bản phải lỗi")
	}
}

func TestUpdateRepoPlaceholder(t *testing.T) {
	t.Setenv("UPDATE_REPO", "CHUA_CAU_HINH/tiktok-auto-kid")
	if UpdateRepo() != "" {
		t.Error("placeholder = chưa cấu hình")
	}
	t.Setenv("UPDATE_REPO", "owner/tiktok-auto-kid")
	if UpdateRepo() != "owner/tiktok-auto-kid" {
		t.Error("repo hợp lệ")
	}
	t.Setenv("UPDATE_REPO", "../x")
	if UpdateRepo() != "" {
		t.Error("repo sai dạng phải bị từ chối")
	}
}

// ---- quy trình đầy đủ với bản giả ----

func setupInstall(t *testing.T) string {
	root := t.TempDir()
	os.MkdirAll(filepath.Join(root, "runtime"), 0o755)
	os.MkdirAll(filepath.Join(root, "app"), 0o755)
	os.WriteFile(filepath.Join(root, "VERSION"), []byte("1.0.0\n"), 0o644)
	os.WriteFile(filepath.Join(root, "app", "keep.php"), []byte("v1"), 0o644)
	os.WriteFile(filepath.Join(root, "app", "removed.php"), []byte("old only"), 0o644)
	os.WriteFile(filepath.Join(root, "mine.txt"), []byte("người dùng tự thêm"), 0o644)
	os.WriteFile(filepath.Join(root, ".env"), []byte("SECRET=1"), 0o644)
	os.WriteFile(ManifestPath(root), []byte("VERSION\napp/keep.php\napp/removed.php\n"), 0o644)
	return root
}

func fakeEnv(root string) (*updateEnv, *[]string) {
	var calls []string
	return &updateEnv{
		Root: root, Log: NewLogger(), PHP: "php",
		StopServices: func() { calls = append(calls, "stop") },
		Backup:       func() (string, error) { calls = append(calls, "backup"); return "backup.sql", nil },
		Run: func(dir, name string, args ...string) error {
			calls = append(calls, name+" "+strings.Join(args, " "))
			return nil
		},
		Restart: func() error { calls = append(calls, "restart"); return nil },
	}, &calls
}

func TestApplyPackageSuccess(t *testing.T) {
	root := setupInstall(t)
	zp := makeZip(t, releaseFiles("1.1.0", map[string]string{"app/keep.php": "v2", "app/new.php": "new"}))
	env, calls := fakeEnv(root)
	if err := ApplyPackage(env, zp); err != nil {
		t.Fatal(err)
	}
	read := func(p string) string { b, _ := os.ReadFile(filepath.Join(root, p)); return string(b) }
	if read("VERSION") != "1.1.0\n" || read("app/keep.php") != "v2" || read("app/new.php") != "new" {
		t.Error("file mới chưa được cài")
	}
	if _, err := os.Stat(filepath.Join(root, "app", "removed.php")); err == nil {
		t.Error("file không còn trong bản mới phải bị xoá")
	}
	if read("mine.txt") == "" || read(".env") != "SECRET=1" {
		t.Error("file người dùng/.env bị đụng")
	}
	if !strings.Contains(read("runtime/release-manifest.txt"), "app/new.php") {
		t.Error("manifest mới chưa ghi")
	}
	joined := strings.Join(*calls, "|")
	for _, want := range []string{"stop", "backup", "php artisan migrate --force", "php artisan optimize:clear", "restart"} {
		if !strings.Contains(joined, want) {
			t.Errorf("thiếu bước %q trong %s", want, joined)
		}
	}
	if snaps := ListSnapshots(root); len(snaps) != 1 || snaps[0].Version != "1.0.0" {
		t.Errorf("snapshot sai: %+v", snaps)
	}
}

func TestApplyPackageFailureRestores(t *testing.T) {
	root := setupInstall(t)
	zp := makeZip(t, releaseFiles("1.1.0", map[string]string{"app/keep.php": "v2", "app/new.php": "new"}))
	env, calls := fakeEnv(root)
	env.Run = func(dir, name string, args ...string) error {
		*calls = append(*calls, name+" "+strings.Join(args, " "))
		if len(args) > 1 && args[1] == "migrate" {
			return errors.New("migration hỏng")
		}
		return nil
	}
	err := ApplyPackage(env, zp)
	if err == nil || !strings.Contains(err.Error(), "migrate") || !strings.Contains(err.Error(), "Đã khôi phục bản 1.0.0") {
		t.Fatalf("lỗi: %v", err)
	}
	read := func(p string) string { b, _ := os.ReadFile(filepath.Join(root, p)); return string(b) }
	if read("VERSION") != "1.0.0\n" || read("app/keep.php") != "v1" || read("app/removed.php") != "old only" {
		t.Error("chưa khôi phục đủ bản cũ")
	}
	if _, err := os.Stat(filepath.Join(root, "app", "new.php")); err == nil {
		t.Error("file bản mới thêm phải bị gỡ")
	}
	if read("mine.txt") == "" || read(".env") != "SECRET=1" {
		t.Error("file người dùng/.env bị đụng")
	}
	if read("runtime/release-manifest.txt") != "VERSION\napp/keep.php\napp/removed.php\n" {
		t.Error("manifest cũ chưa trả lại")
	}
	if (*calls)[len(*calls)-1] != "restart" {
		t.Errorf("phải chạy lại dịch vụ cuối cùng: %v", *calls)
	}
}

func TestApplyPackageRejectsOlderAndBackupFailure(t *testing.T) {
	root := setupInstall(t)
	env, calls := fakeEnv(root)
	if err := ApplyPackage(env, makeZip(t, releaseFiles("1.0.0", map[string]string{"app/keep.php": "x"}))); err == nil {
		t.Error("cùng phiên bản phải từ chối")
	}
	if len(*calls) != 0 {
		t.Error("không được dừng dịch vụ khi gói bị từ chối")
	}
	env.Backup = func() (string, error) { return "", errors.New("pg_dump lỗi") }
	err := ApplyPackage(env, makeZip(t, releaseFiles("1.1.0", map[string]string{"app/keep.php": "v2"})))
	if err == nil || !strings.Contains(err.Error(), "sao lưu") {
		t.Fatalf("got %v", err)
	}
	if b, _ := os.ReadFile(filepath.Join(root, "app", "keep.php")); string(b) != "v1" {
		t.Error("sao lưu lỗi thì không được đụng file")
	}
	if (*calls)[len(*calls)-1] != "restart" {
		t.Error("phải chạy lại dịch vụ sau khi huỷ")
	}
}

func TestRollbackLatest(t *testing.T) {
	root := setupInstall(t)
	env, _ := fakeEnv(root)
	if err := RollbackLatest(env); err == nil {
		t.Fatal("chưa có snapshot phải lỗi")
	}
	if err := ApplyPackage(env, makeZip(t, releaseFiles("1.1.0", map[string]string{"app/keep.php": "v2", "app/new.php": "n"}))); err != nil {
		t.Fatal(err)
	}
	if err := RollbackLatest(env); err != nil {
		t.Fatal(err)
	}
	if b, _ := os.ReadFile(filepath.Join(root, "VERSION")); string(b) != "1.0.0\n" {
		t.Error("VERSION chưa về 1.0.0")
	}
	if _, err := os.Stat(filepath.Join(root, "app", "new.php")); err == nil {
		t.Error("app/new.php phải bị gỡ")
	}
	if len(ListSnapshots(root)) != 0 {
		t.Error("snapshot đã dùng phải được xoá")
	}
}

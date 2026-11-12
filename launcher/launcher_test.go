package main

import (
	"net"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

const goodJSON = `{
 "app_url":"http://localhost:8010",
 "services":[
  {"name":"web","cmd":"runtime/php/php.exe","args":["artisan","serve"],"health":{"type":"http","url":"http://127.0.0.1:8010/up"},"depends_on":["postgres"]},
  {"name":"postgres","cmd":"runtime/pgsql/bin/postgres.exe","health":{"type":"tcp","port":5433},"stop":{"cmd":"runtime/pgsql/bin/pg_ctl.exe","args":["stop"]}},
  {"name":"queue","cmd":"runtime/php/php.exe","depends_on":["web"],"health":null}
 ],
 "first_run":[{"name":"initdb","cmd":"x","only_if_missing":"runtime/data/pg"}],
 "backup":{"cmd":"runtime/pgsql/bin/pg_dump.exe"}
}`

func TestParseConfigOK(t *testing.T) {
	c, err := ParseConfig([]byte(goodJSON))
	if err != nil {
		t.Fatal(err)
	}
	if len(c.Services) != 3 || c.Services[1].Stop == nil || c.Backup == nil {
		t.Fatalf("parse sai: %+v", c)
	}
	if got, want := c.Ports(), []int{8010, 5433}; !reflect.DeepEqual(got, want) {
		t.Fatalf("ports %v != %v", got, want)
	}
	// BOM được chấp nhận
	if _, err := ParseConfig(append([]byte{0xEF, 0xBB, 0xBF}, goodJSON...)); err != nil {
		t.Fatalf("BOM: %v", err)
	}
}

func TestParseConfigInvalid(t *testing.T) {
	cases := map[string]string{
		"không phải JSON":     `{`,
		"thiếu app_url":       `{"services":[{"name":"a","cmd":"x"}]}`,
		"app_url sai":         `{"app_url":"abc","services":[{"name":"a","cmd":"x"}]}`,
		"services trống":      `{"app_url":"http://localhost:1"}`,
		"thiếu cmd":           `{"app_url":"http://localhost:1","services":[{"name":"a"}]}`,
		"trùng tên":           `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x"},{"name":"a","cmd":"x"}]}`,
		"phụ thuộc không có":  `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x","depends_on":["b"]}]}`,
		"restart sai":         `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x","restart":"foo"}]}`,
		"health tcp sai port": `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x","health":{"type":"tcp"}}]}`,
		"health http sai url": `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x","health":{"type":"http","url":"zzz"}}]}`,
		"health type lạ":      `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x","health":{"type":"udp"}}]}`,
		"vòng phụ thuộc":      `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x","depends_on":["b"]},{"name":"b","cmd":"x","depends_on":["a"]}]}`,
		"phụ thuộc chính nó":  `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x","depends_on":["a"]}]}`,
		"stop thiếu cmd":      `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x","stop":{}}]}`,
		"first_run thiếu cmd": `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x"}],"first_run":[{}]}`,
		"backup thiếu cmd":    `{"app_url":"http://localhost:1","services":[{"name":"a","cmd":"x"}],"backup":{}}`,
	}
	for name, js := range cases {
		if _, err := ParseConfig([]byte(js)); err == nil {
			t.Errorf("%s: phải báo lỗi", name)
		}
	}
}

func TestStartOrder(t *testing.T) {
	c, _ := ParseConfig([]byte(goodJSON))
	order, err := c.StartOrder()
	if err != nil {
		t.Fatal(err)
	}
	if want := []string{"postgres", "web", "queue"}; !reflect.DeepEqual(order, want) {
		t.Fatalf("order %v != %v", order, want)
	}
}

func TestTopoOrderCycleAndStability(t *testing.T) {
	_, err := TopoOrder([]string{"a", "b", "c"}, map[string][]string{"a": {"b"}, "b": {"c"}, "c": {"a"}})
	if err == nil || !strings.Contains(err.Error(), "vòng") {
		t.Fatalf("phải phát hiện vòng, got %v", err)
	}
	o, err := TopoOrder([]string{"x", "y", "z"}, nil)
	if err != nil || !reflect.DeepEqual(o, []string{"x", "y", "z"}) {
		t.Fatalf("giữ thứ tự khai báo: %v %v", o, err)
	}
	// kim cương: d phụ thuộc b,c; b,c phụ thuộc a
	o, err = TopoOrder([]string{"d", "c", "b", "a"}, map[string][]string{"d": {"b", "c"}, "b": {"a"}, "c": {"a"}})
	if err != nil {
		t.Fatal(err)
	}
	pos := map[string]int{}
	for i, n := range o {
		pos[n] = i
	}
	if !(pos["a"] < pos["b"] && pos["a"] < pos["c"] && pos["b"] < pos["d"] && pos["c"] < pos["d"]) || len(o) != 4 {
		t.Fatalf("thứ tự sai: %v", o)
	}
}

func TestBackoff(t *testing.T) {
	b := NewBackoff(time.Second, 60*time.Second)
	want := []time.Duration{1, 2, 4, 8, 16, 32, 60, 60}
	for i, w := range want {
		if got := b.Next(); got != w*time.Second {
			t.Fatalf("lần %d: %v != %v", i, got, w*time.Second)
		}
	}
	b.Reset()
	if got := b.Next(); got != time.Second {
		t.Fatalf("sau Reset: %v", got)
	}
}

func TestLogRotation(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "a.log")
	w, err := NewRotatingWriter(p, 100, 3)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 10; i++ {
		line := strings.Repeat(string(rune('0'+i)), 49) + "\n" // 50 byte
		if _, err := w.Write([]byte(line)); err != nil {
			t.Fatal(err)
		}
	}
	w.Close()
	ents, _ := os.ReadDir(dir)
	if len(ents) != 3 {
		t.Fatalf("phải giữ đúng 3 file, có %d", len(ents))
	}
	for _, n := range []string{"a.log", "a.log.1", "a.log.2"} {
		st, err := os.Stat(filepath.Join(dir, n))
		if err != nil || st.Size() > 100 {
			t.Fatalf("%s: %v size=%v", n, err, st)
		}
	}
	// file mới nhất chứa dòng cuối
	b, _ := os.ReadFile(p)
	if !strings.Contains(string(b), strings.Repeat("9", 49)) {
		t.Fatalf("log hiện tại thiếu dòng mới nhất: %q", b)
	}
	if _, err := os.Stat(p + ".3"); err == nil {
		t.Fatal("không được có .3")
	}
}

func TestPortInUse(t *testing.T) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	port := l.Addr().(*net.TCPAddr).Port
	if !PortInUse(port) {
		t.Fatal("cổng đang nghe phải báo bị chiếm")
	}
	l.Close()
	if PortInUse(port) {
		t.Fatal("cổng đã đóng phải báo rảnh")
	}
}

func TestParseNetstatAndTasklist(t *testing.T) {
	out := "Active Connections\r\n\r\n  Proto  Local Address          Foreign Address        State           PID\r\n" +
		"  TCP    0.0.0.0:8010           0.0.0.0:0              LISTENING       4321\r\n" +
		"  TCP    [::]:5433              [::]:0                 LISTENING       99\r\n" +
		"  TCP    127.0.0.1:50000        127.0.0.1:8010         ESTABLISHED     4321\r\n"
	m := ParseNetstatListeners(out)
	if m[8010] != 4321 || m[5433] != 99 || len(m) != 2 {
		t.Fatalf("netstat: %v", m)
	}
	if n := ParseTasklistName("\"php.exe\",\"4321\",\"Console\",\"1\",\"50,000 K\"\r\n"); n != "php.exe" {
		t.Fatalf("tasklist: %q", n)
	}
	if n := ParseTasklistName("INFO: No tasks are running"); n != "" {
		t.Fatalf("tasklist rỗng: %q", n)
	}
}

func TestBackupHelpers(t *testing.T) {
	dir := t.TempDir()
	now := time.Date(2026, 3, 5, 10, 30, 0, 0, time.Local)
	if !DailyBackupDue(dir, now) {
		t.Fatal("chưa có backup => đến hạn")
	}
	if BackupName(now) != "20260305-1030.sql" {
		t.Fatalf("tên: %s", BackupName(now))
	}
	os.WriteFile(filepath.Join(dir, BackupName(now)), []byte("x"), 0o644)
	if DailyBackupDue(dir, now) {
		t.Fatal("đã có backup hôm nay")
	}
	if !DailyBackupDue(dir, now.Add(24*time.Hour)) {
		t.Fatal("ngày hôm sau phải đến hạn")
	}
	for i := 0; i < 20; i++ {
		d := time.Date(2026, 1, 1+i, 8, 0, 0, 0, time.Local)
		os.WriteFile(filepath.Join(dir, BackupName(d)), []byte("x"), 0o644)
	}
	PruneBackups(dir, 14)
	ents, _ := os.ReadDir(dir)
	if len(ents) != 14 {
		t.Fatalf("còn %d file, mong 14", len(ents))
	}
	if _, err := os.Stat(filepath.Join(dir, "20260101-0800.sql")); err == nil {
		t.Fatal("bản cũ nhất phải bị xoá")
	}
	if _, err := os.Stat(filepath.Join(dir, BackupName(now))); err != nil {
		t.Fatal("bản mới nhất phải còn")
	}
}

func TestResolve(t *testing.T) {
	root := `C:\app`
	if got := resolveCmd("runtime/php/php.exe", root); got != `C:\app\runtime\php\php.exe` {
		t.Fatal(got)
	}
	if got := resolveCmd("cmd", root); got != "cmd" {
		t.Fatal(got)
	}
	if got := resolveCmd("${ROOT}/x.exe", root); !strings.HasSuffix(got, "x.exe") {
		t.Fatal(got)
	}
	if got := resolveDir(".", root); got != `C:\app` {
		t.Fatal(got)
	}
}

func TestFindRoot(t *testing.T) {
	d := t.TempDir()
	os.MkdirAll(filepath.Join(d, "runtime"), 0o755)
	os.WriteFile(filepath.Join(d, "runtime", "services.json"), []byte("{}"), 0o644)
	sub := filepath.Join(d, "a", "b")
	os.MkdirAll(sub, 0o755)
	if r, ok := findRoot(sub); !ok || r != d {
		t.Fatalf("findRoot: %s %v", r, ok)
	}
	if _, ok := findRoot(t.TempDir()); ok {
		t.Fatal("không được tìm thấy")
	}
}

func TestIsOurPostgres(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "runtime", "data", "pg")
	pf := "740\r\n" + filepath.ToSlash(dir) + "\r\n1794376957\r\n5433\r\n"
	if !IsOurPostgres(pf, 740, dir) {
		t.Fatal("phải nhận ra postgres của mình")
	}
	if IsOurPostgres(pf, 741, dir) {
		t.Fatal("PID lệch không được nhận")
	}
	if IsOurPostgres(pf, 740, `D:\other\data`) {
		t.Fatal("thư mục khác không được nhận")
	}
	if _, _, ok := ParsePostmasterPID("abc\n"); ok {
		t.Fatal("file hỏng phải false")
	}
	if !PathUnder(`C:\Some Dir\App\runtime\caddy.exe`, `c:/some dir/app`) || PathUnder(`C:\Some Dir\App2\x.exe`, `C:\Some Dir\App`) {
		t.Fatal("PathUnder sai")
	}
}

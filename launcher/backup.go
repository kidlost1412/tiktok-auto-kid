package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

const keepBackups = 14

var backupMu sync.Mutex

// BackupDir là thư mục chứa các bản sao lưu.
func BackupDir(root string) string { return filepath.Join(root, "runtime", "backups") }

// BackupName tạo tên file theo yyyyMMdd-HHmm.
func BackupName(t time.Time) string { return t.Format("20060102-1504") + ".sql" }

// DailyBackupDue trả true nếu hôm nay (theo now) chưa có bản sao lưu nào.
func DailyBackupDue(dir string, now time.Time) bool {
	prefix := now.Format("20060102") + "-"
	ents, _ := os.ReadDir(dir)
	for _, e := range ents {
		if !e.IsDir() && strings.HasPrefix(e.Name(), prefix) && strings.HasSuffix(e.Name(), ".sql") {
			return false
		}
	}
	return true
}

// PruneBackups giữ lại keep bản mới nhất (theo tên), xoá phần còn lại.
func PruneBackups(dir string, keep int) {
	ents, _ := os.ReadDir(dir)
	var names []string
	for _, e := range ents {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".sql") {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	for len(names) > keep {
		os.Remove(filepath.Join(dir, names[0]))
		names = names[1:]
	}
}

// RunBackup chạy lệnh backup của cấu hình. Nếu một đối số chứa "{out}" thì nó được
// thay bằng đường dẫn file đích; ngược lại stdout của lệnh được ghi vào file đích.
func RunBackup(cfg *Config, root string, log *Logger) (string, error) {
	if cfg.Backup == nil {
		return "", fmt.Errorf("chưa cấu hình sao lưu (backup) trong services.json")
	}
	backupMu.Lock()
	defer backupMu.Unlock()

	dir := BackupDir(root)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	final := filepath.Join(dir, BackupName(time.Now()))
	part := final + ".part"
	defer os.Remove(part)

	args := resolveArgs(cfg.Backup.Args, root)
	useOut := false
	for i, a := range args {
		if strings.Contains(a, "{out}") {
			args[i] = strings.ReplaceAll(a, "{out}", part)
			useOut = true
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	cmd := exec.CommandContext(ctx, resolveCmd(cfg.Backup.Cmd, root), args...)
	cmd.Dir = resolveDir(cfg.Backup.Cwd, root)
	cmd.Env = append(os.Environ(), resolveEnv(cfg.Backup.Env, root)...)
	cmd.SysProcAttr = hiddenAttr()
	var stderr strings.Builder
	cmd.Stderr = &stderr
	var f *os.File
	if !useOut {
		var err error
		if f, err = os.Create(part); err != nil {
			return "", err
		}
		cmd.Stdout = f
	}
	err := cmd.Run()
	if f != nil {
		f.Close()
	}
	if err != nil {
		return "", fmt.Errorf("lệnh sao lưu lỗi: %v %s", err, strings.TrimSpace(stderr.String()))
	}
	st, err := os.Stat(part)
	if err != nil || st.Size() == 0 {
		return "", fmt.Errorf("file sao lưu rỗng")
	}
	if err := os.Rename(part, final); err != nil {
		return "", err
	}
	PruneBackups(dir, keepBackups)
	log.Printf("Đã sao lưu: %s (%d byte)", final, st.Size())
	return final, nil
}

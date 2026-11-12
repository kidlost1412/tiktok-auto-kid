package main

import (
	"fmt"
	"net"
	"regexp"
	"strings"
	"time"
)

// PortInUse trả true nếu cổng TCP đã có tiến trình khác dùng.
func PortInUse(port int) bool {
	l, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		return true
	}
	l.Close()
	// trường hợp tiến trình khác chỉ lắng nghe trên một địa chỉ khác
	if c, err := net.DialTimeout("tcp", fmt.Sprintf("127.0.0.1:%d", port), 300*time.Millisecond); err == nil {
		c.Close()
		return true
	}
	return false
}

var netstatLine = regexp.MustCompile(`(?i)^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$`)

// ParseNetstatListeners đọc đầu ra "netstat -ano -p TCP", trả về map cổng -> PID đang LISTEN.
func ParseNetstatListeners(out string) map[int]int {
	m := map[int]int{}
	for _, ln := range strings.Split(out, "\n") {
		g := netstatLine.FindStringSubmatch(strings.TrimRight(ln, "\r"))
		if g == nil {
			continue
		}
		var port, pid int
		fmt.Sscan(g[1], &port)
		fmt.Sscan(g[2], &pid)
		if _, ok := m[port]; !ok {
			m[port] = pid
		}
	}
	return m
}

// ParseTasklistName đọc đầu ra "tasklist /FO CSV /NH", trả về tên tiến trình đầu tiên.
func ParseTasklistName(out string) string {
	line := strings.TrimSpace(strings.SplitN(out, "\n", 2)[0])
	if !strings.HasPrefix(line, `"`) {
		return ""
	}
	return strings.SplitN(line[1:], `"`, 2)[0]
}

// ParsePostmasterPID đọc nội dung postmaster.pid: dòng 1 là PID, dòng 2 là thư mục dữ liệu.
func ParsePostmasterPID(content string) (pid int, dataDir string, ok bool) {
	lines := strings.Split(strings.ReplaceAll(content, "\r", ""), "\n")
	if len(lines) < 2 {
		return 0, "", false
	}
	if _, err := fmt.Sscan(strings.TrimSpace(lines[0]), &pid); err != nil || pid <= 0 {
		return 0, "", false
	}
	return pid, strings.TrimSpace(lines[1]), true
}

func normPath(p string) string {
	p = strings.ToLower(strings.ReplaceAll(p, "/", `\`))
	return strings.TrimRight(p, `\`)
}

// SamePath so sánh hai đường dẫn Windows không phân biệt hoa thường và kiểu gạch.
func SamePath(a, b string) bool { return a != "" && normPath(a) == normPath(b) }

// PathUnder trả true nếu path nằm trong thư mục root.
func PathUnder(path, root string) bool {
	p, r := normPath(path), normPath(root)
	return r != "" && strings.HasPrefix(p, r+`\`)
}

// IsOurPostgres: postmaster.pid khớp PID đang giữ cổng và thư mục dữ liệu là của bundle này.
func IsOurPostgres(pidFile string, ownerPID int, dataDir string) bool {
	pid, dir, ok := ParsePostmasterPID(pidFile)
	return ok && pid == ownerPID && SamePath(dir, dataDir)
}

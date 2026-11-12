package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// ReadVersion đọc file VERSION ở thư mục gốc bundle ("0.0.0" nếu thiếu/hỏng).
func ReadVersion(root string) string {
	b, err := os.ReadFile(filepath.Join(root, "VERSION"))
	if err != nil {
		return "0.0.0"
	}
	v := strings.TrimSpace(strings.TrimPrefix(string(b), "\xef\xbb\xbf"))
	if _, err := ParseVersion(v); err != nil {
		return "0.0.0"
	}
	return strings.TrimPrefix(strings.TrimPrefix(v, "v"), "V")
}

// Version là semver rút gọn: major.minor.patch[-tiền-phát-hành][+build].
type Version struct {
	Core [3]int
	Pre  []string
}

// ParseVersion nhận "1.2.3", "v1.2.3", "1.2", "1.2.3-rc.1", "1.2.3+build".
func ParseVersion(s string) (Version, error) {
	var v Version
	orig := s
	s = strings.TrimSpace(s)
	s = strings.TrimPrefix(strings.TrimPrefix(s, "v"), "V")
	if i := strings.IndexByte(s, '+'); i >= 0 {
		s = s[:i]
	}
	if i := strings.IndexByte(s, '-'); i >= 0 {
		v.Pre = strings.Split(s[i+1:], ".")
		s = s[:i]
		if len(v.Pre) == 1 && v.Pre[0] == "" {
			return v, fmt.Errorf("phiên bản không hợp lệ: %q", orig)
		}
	}
	parts := strings.Split(s, ".")
	if s == "" || len(parts) > 3 {
		return v, fmt.Errorf("phiên bản không hợp lệ: %q", orig)
	}
	for i, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil || n < 0 || p == "" || (len(p) > 1 && p[0] == '0') {
			return v, fmt.Errorf("phiên bản không hợp lệ: %q", orig)
		}
		v.Core[i] = n
	}
	return v, nil
}

// CompareVersions trả -1, 0, 1 (a so với b). Bản có hậu tố tiền-phát-hành nhỏ hơn bản chính thức cùng số.
func CompareVersions(a, b string) (int, error) {
	va, err := ParseVersion(a)
	if err != nil {
		return 0, err
	}
	vb, err := ParseVersion(b)
	if err != nil {
		return 0, err
	}
	for i := 0; i < 3; i++ {
		if va.Core[i] != vb.Core[i] {
			if va.Core[i] < vb.Core[i] {
				return -1, nil
			}
			return 1, nil
		}
	}
	switch {
	case len(va.Pre) == 0 && len(vb.Pre) == 0:
		return 0, nil
	case len(va.Pre) == 0:
		return 1, nil
	case len(vb.Pre) == 0:
		return -1, nil
	}
	for i := 0; i < len(va.Pre) && i < len(vb.Pre); i++ {
		x, y := va.Pre[i], vb.Pre[i]
		nx, ex := strconv.Atoi(x)
		ny, ey := strconv.Atoi(y)
		switch {
		case ex == nil && ey == nil:
			if nx != ny {
				if nx < ny {
					return -1, nil
				}
				return 1, nil
			}
		case ex == nil:
			return -1, nil // số < chữ
		case ey == nil:
			return 1, nil
		case x != y:
			if x < y {
				return -1, nil
			}
			return 1, nil
		}
	}
	switch {
	case len(va.Pre) < len(vb.Pre):
		return -1, nil
	case len(va.Pre) > len(vb.Pre):
		return 1, nil
	}
	return 0, nil
}

// IsNewer: latest mới hơn current (lỗi phân tích => false).
func IsNewer(latest, current string) bool {
	c, err := CompareVersions(latest, current)
	return err == nil && c > 0
}

package main

import "testing"

// php-cgi tự nghỉ sau PHP_FCGI_MAX_REQUESTS lượt và thoát mã 0: không được coi là sự cố (không bật cảnh báo).
func TestCleanRecycle(t *testing.T) {
	cases := []struct {
		restart string
		code    int
		want    bool
	}{
		{"", 0, true},
		{"always", 0, true},
		{"always", 1, false},
		{"", 255, false},
		{"on-failure", 0, false},
		{"never", 0, false},
	}
	for _, c := range cases {
		if got := cleanRecycle(Service{Restart: c.restart}, c.code); got != c.want {
			t.Errorf("restart=%q code=%d: được %v, cần %v", c.restart, c.code, got, c.want)
		}
	}
}

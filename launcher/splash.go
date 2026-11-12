package main

import (
	_ "embed"
	"strings"
)

//go:embed assets/splash.html
var splashHTML string

// Các dòng trạng thái thân thiện trên màn hình chào.
const (
	splashTextStart  = "Đang khởi động…"
	splashTextDB     = "Đang mở kho dữ liệu…"
	splashTextWeb    = "Đang bật máy chủ…"
	splashTextVideo  = "Đang đánh thức Xưởng Video…"
	splashTextAlmost = "Sắp xong…"
	splashTextReady  = "Sẵn sàng!"
)

// progService là phần dữ liệu của một dịch vụ mà việc tính tiến độ cần.
type progService struct {
	Name     string
	Status   Status
	Optional bool
}

// svcCategory phân loại dịch vụ để chọn câu chữ và trọng số: db | web | video | other.
func svcCategory(name, webName string) string {
	n := strings.ToLower(name)
	switch {
	case strings.Contains(n, "postgres"), strings.Contains(n, "pgsql"), n == "db", n == "pg":
		return "db"
	case strings.Contains(n, "xuong"), strings.Contains(n, "video"):
		return "video"
	case name == webName, strings.Contains(n, "php"), strings.Contains(n, "caddy"), strings.Contains(n, "nginx"), n == "web":
		return "web"
	}
	return "other"
}

func categoryText(cat string) string {
	switch cat {
	case "db":
		return splashTextDB
	case "web":
		return splashTextWeb
	case "video":
		return splashTextVideo
	}
	return splashTextWeb
}

func categoryWeight(cat string) float64 {
	switch cat {
	case "db":
		return 24
	case "web":
		return 14
	case "video":
		return 14
	}
	return 3
}

func serviceFrac(st Status) float64 {
	switch st {
	case StatusRunning, StatusExternal, StatusSkipped:
		return 1
	case StatusStarting, StatusError:
		return 0.35
	}
	return 0
}

// splashProgress đổi trạng thái thật của supervisor thành (phần trăm 0..100, câu chữ).
// Có trọng số theo từng dịch vụ; các bước first_run tính chung một phần. Chưa tính "bò nhẹ" (việc đó do JS làm).
func splashProgress(steps []stepState, svcs []progService, webName string) (float64, string) {
	type item struct {
		w, f float64
		text string
	}
	items := []item{{w: 4, f: 1, text: splashTextStart}}
	if len(steps) > 0 {
		each := 10.0 / float64(len(steps))
		for _, s := range steps {
			f := 0.0
			switch s.State {
			case "ok", "skipped":
				f = 1
			case "running":
				f = 0.5
			}
			items = append(items, item{each, f, splashTextDB})
		}
	}
	anyStarted := false
	for _, s := range svcs {
		if s.Status == StatusSkipped {
			continue
		}
		cat := svcCategory(s.Name, webName)
		w := categoryWeight(cat)
		if cat == "web" && s.Name != webName {
			w = 8 // php-cgi... chia nhỏ, riêng "web" (health của app) nặng hơn
		}
		items = append(items, item{w, serviceFrac(s.Status), categoryText(cat)})
		if s.Status != StatusStopped {
			anyStarted = true
		}
	}
	if !anyStarted && len(steps) == 0 {
		items[0].f = 0.3
	}
	var total, done float64
	text := ""
	remain := 0.0
	for _, it := range items {
		total += it.w
		done += it.w * it.f
		if it.f < 1 {
			remain += it.w * (1 - it.f)
			if text == "" {
				text = it.text
			}
		}
	}
	if total == 0 {
		return 0, splashTextStart
	}
	pct := done / total * 100
	if text == "" || remain/total*100 < 8 {
		text = splashTextAlmost
	}
	return pct, text
}

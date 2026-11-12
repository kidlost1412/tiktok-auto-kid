package main

import (
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"time"
)

// demoFlag cho phép -splash-demo (không giá trị = mô phỏng thành công) và -splash-demo=loi (mô phỏng lỗi).
type demoFlag string

func (d *demoFlag) String() string { return string(*d) }
func (d *demoFlag) Set(v string) error {
	switch v {
	case "", "false", "0":
		*d = ""
	case "true", "1":
		*d = "ok"
	default:
		*d = demoFlag(v)
	}
	return nil
}
func (d *demoFlag) IsBoolFlag() bool { return true }

// splashDisabled: đặt TTA_NO_SPLASH=1 để tắt hẳn màn hình chào (gỡ lỗi / máy không có WebView2).
func splashDisabled() bool { return os.Getenv("TTA_NO_SPLASH") != "" }

// splashHolder trao kết quả tạo màn hình chào (sp == nil nếu không tạo được).
type splashHolder struct {
	done chan struct{}
	sp   *Splash
}

// startSplashAsync tạo màn hình chào ở nền (không chặn việc khởi động dịch vụ).
func (a *App) startSplashAsync() *splashHolder {
	h := &splashHolder{done: make(chan struct{})}
	atomic.StoreInt32(&a.splashOn, 1) // trong lúc chờ: không bật hộp thoại lỗi, thẻ lỗi của splash sẽ thay
	go func() {
		defer close(h.done)
		sp := NewSplash(ReadVersion(a.root))
		if sp.Open(12 * time.Second) {
			h.sp = sp
		} else {
			a.log.Printf("Không tạo được màn hình chào (WebView2): chạy không splash")
			atomic.StoreInt32(&a.splashOn, 0)
		}
	}()
	return h
}

// startAsync chạy sup.Start() ở nền; kết quả gửi vào kênh.
func (a *App) startAsync() <-chan error {
	ch := make(chan error, 1)
	go func() {
		err := a.sup.Start()
		if err != nil {
			a.log.Printf("Khởi động thất bại: %v", err)
		}
		ch <- err
		if err == nil {
			a.maybeDailyBackup()
		}
	}()
	return ch
}

// runWithSplash: khởi động dịch vụ, hiển thị tiến độ thật trên splash; xong thì mở trình duyệt.
func (a *App) runWithSplash(h *splashHolder) {
	resCh := a.startAsync()
	<-h.done
	sp := h.sp
	if sp == nil {
		// quay về cách cũ: mở trang trạng thái ngay, báo lỗi bằng hộp thoại
		if a.status != nil {
			openPath(a.status.URL)
		}
		if err := <-resCh; err != nil {
			if _, msg := a.sup.Summary(); msg != "" && a.sup.Notify != nil {
				a.sup.Notify(appTitle+" – Lỗi", msg)
			}
			return
		}
		if a.status == nil {
			openPath(a.cfg.AppURL)
		}
		return
	}
	sp.OnRetry = func() { a.splashRetry(sp) }
	sp.OnDetails = func() { openPath(a.detailsTarget()) }
	sp.OnClose = func() { atomic.StoreInt32(&a.splashOn, 0) }
	a.driveSplash(sp, resCh)
}

// detailsTarget: trang trạng thái (có log) hoặc thư mục log.
func (a *App) detailsTarget() string {
	if a.status != nil {
		return a.status.URL
	}
	return filepath.Join(a.root, "runtime", "logs")
}

func (a *App) currentProgress() (float64, string) {
	sts := a.sup.Statuses()
	svcs := make([]progService, 0, len(sts))
	for _, s := range sts {
		svcs = append(svcs, progService{Name: s.Name, Status: s.Status, Optional: a.sup.states[s.Name].svc.Optional})
	}
	return splashProgress(a.sup.StepStatuses(), svcs, webServiceName(a.cfg))
}

// optionalStarting: có dịch vụ tuỳ chọn (vd Xưởng Video) đang khởi động.
func (a *App) optionalStarting() bool {
	for _, s := range a.sup.Statuses() {
		if s.Status == StatusStarting && a.sup.states[s.Name].svc.Optional {
			return true
		}
	}
	return false
}

// driveSplash đẩy tiến độ thật cho tới khi khởi động xong (Ready) hoặc lỗi (thẻ lỗi).
func (a *App) driveSplash(sp *Splash, resCh <-chan error) {
	tick := time.NewTicker(120 * time.Millisecond)
	defer tick.Stop()
	for {
		select {
		case err := <-resCh:
			if err != nil {
				if a.isQuitting() {
					sp.Close()
					return
				}
				_, msg := a.sup.Summary()
				if msg == "" {
					msg = err.Error()
				}
				// trên màn hình chào đã có nút "Thử lại" (thay cho mục "Khởi động lại" ở khay)
				sp.Fail(strings.ReplaceAll(msg, `chọn "Khởi động lại"`, `bấm "Thử lại"`))
				return
			}
			// chờ tối đa 10 giây cho dịch vụ tuỳ chọn đang khởi động (Xưởng Video) để câu chữ đúng thực tế
			for end := time.Now().Add(10 * time.Second); time.Now().Before(end) && a.optionalStarting() && !sp.Closed(); {
				p, t := a.currentProgress()
				sp.Update(p, t)
				time.Sleep(150 * time.Millisecond)
			}
			sp.Update(97, splashTextAlmost)
			sp.Ready(false, func() {
				atomic.StoreInt32(&a.splashOn, 0)
				openPath(a.cfg.AppURL)
			})
			return
		case <-tick.C:
			p, t := a.currentProgress()
			sp.Update(p, t)
		}
	}
}

// splashRetry: bấm "Thử lại" trên thẻ lỗi => dừng sạch rồi chạy lại, vẫn trên cùng màn hình chào.
func (a *App) splashRetry(sp *Splash) {
	a.mu.Lock()
	if a.restarting || a.quitting {
		a.mu.Unlock()
		return
	}
	a.restarting = true
	a.mu.Unlock()
	go func() {
		a.log.Printf("Thử lại từ màn hình chào")
		a.sup.Stop()
		sp.Reset()
		resCh := a.startAsync()
		a.mu.Lock()
		a.restarting = false
		a.mu.Unlock()
		a.driveSplash(sp, resCh)
	}()
}

// quickSplashThenOpen: lần chạy thứ hai khi app đã chạy — splash ~0,8 giây ("Sẵn sàng!") rồi mở trình duyệt.
func quickSplashThenOpen(root, target string) {
	if splashDisabled() {
		openPath(target)
		return
	}
	sp := NewSplash(ReadVersion(root))
	if !sp.Open(8 * time.Second) {
		openPath(target)
		return
	}
	fin := make(chan struct{})
	sp.Ready(true, func() {
		openPath(target)
		close(fin)
	})
	select {
	case <-fin:
	case <-time.After(10 * time.Second):
		openPath(target)
	}
}

// runSplashDemo chỉ hiện splash với tiến độ mô phỏng (mode "loi" => thẻ lỗi ở lần đầu; "nhanh" => bản rút gọn của lần chạy thứ hai). Không đụng dịch vụ hay khoá single-instance.
func runSplashDemo(mode string) int {
	root := ""
	if exe, err := os.Executable(); err == nil {
		root, _ = findRoot(filepath.Dir(exe))
	}
	sp := NewSplash(ReadVersion(root))
	if !sp.Open(20 * time.Second) {
		return 2
	}
	if mode == "nhanh" { // xem trước splash của lần chạy thứ hai (không mở trình duyệt)
		sp.Ready(true, nil)
		sp.Wait()
		return 0
	}
	var attempt int32
	var run func()
	run = func() {
		n := atomic.AddInt32(&attempt, 1)
		go simulateStartup(sp, mode == "loi" && n == 1)
	}
	sp.OnRetry = func() { sp.Reset(); run() }
	sp.OnDetails = func() {}
	run()
	sp.Wait()
	return 0
}

// simulateStartup chạy kịch bản khởi động giả qua đúng hàm tính tiến độ như thật.
func simulateStartup(sp *Splash, fail bool) {
	type sim struct {
		name       string
		opt        bool
		start, run float64 // giây
	}
	plan := []sim{
		{"postgres", false, 0.3, 2.2},
		{"php-cgi-1", false, 2.2, 3.4}, {"php-cgi-2", false, 2.2, 3.6},
		{"web", false, 3.6, 4.8},
		{"queue-main", false, 4.8, 5.3}, {"queue-social", false, 4.8, 5.4}, {"scheduler", false, 4.8, 5.5},
		{"chrome-launcher", false, 5.4, 5.8},
		{"xuong-video", true, 5.8, 7.6},
	}
	begin := time.Now()
	for {
		if sp.Closed() {
			return
		}
		el := time.Since(begin).Seconds()
		svcs := make([]progService, 0, len(plan))
		for _, p := range plan {
			st := StatusStopped
			switch {
			case el >= p.run:
				st = StatusRunning
			case el >= p.start:
				st = StatusStarting
			}
			svcs = append(svcs, progService{Name: p.name, Status: st, Optional: p.opt})
		}
		if fail && el > 4.4 {
			sp.Fail("Cổng 8010 đang bị chiếm bởi một chương trình khác (PID 4242). Hãy tắt chương trình đó rồi bấm \"Thử lại\".")
			return
		}
		pct, text := splashProgress(nil, svcs, "web")
		sp.Update(pct, text)
		if el >= 7.7 {
			sp.Update(97, splashTextAlmost)
			time.Sleep(500 * time.Millisecond)
			sp.Ready(false, nil)
			return
		}
		time.Sleep(100 * time.Millisecond)
	}
}

package main

import (
	_ "embed"
	"path/filepath"
	"strings"
	"sync/atomic"
	"time"

	"fyne.io/systray"
)

//go:embed assets/icon.ico
var iconData []byte

func (a *App) runTray() {
	a.onQuit = systray.Quit
	a.sup.Notify = func(title, msg string) {
		if atomic.LoadInt32(&a.splashOn) == 1 {
			return // lỗi lúc khởi động đã hiện trên thẻ lỗi của màn hình chào
		}
		a.mu.Lock()
		dup := a.lastMsg == msg
		a.lastMsg = msg
		a.mu.Unlock()
		if !dup {
			go messageBox(title, msg)
		}
	}
	systray.Run(a.onReady, func() {})
}

func (a *App) onReady() {
	systray.SetIcon(iconData)
	systray.SetTitle(appTitle)
	systray.SetTooltip(appTitle + " – Đang khởi động")
	systray.SetOnTapped(func() { openPath(a.openTarget()) })

	mOpen := systray.AddMenuItem("Mở "+appTitle, "Mở ứng dụng trong trình duyệt")
	systray.AddSeparator()
	var svcItems []*systray.MenuItem
	for _, s := range a.sup.Statuses() {
		it := systray.AddMenuItem(s.Name+": "+s.Status.Label(), "")
		it.Disable()
		svcItems = append(svcItems, it)
	}
	mSummary := systray.AddMenuItem("", "")
	mSummary.Disable()
	mSummary.Hide()
	systray.AddSeparator()
	mUpdate := systray.AddMenuItem("Cập nhật…", "Mở trang Cập nhật trong app")
	mRestart := systray.AddMenuItem("Khởi động lại", "Dừng rồi chạy lại toàn bộ dịch vụ")
	mLogs := systray.AddMenuItem("Mở thư mục log", "")
	mBackup := systray.AddMenuItem("Sao lưu dữ liệu ngay", "")
	mAuto := systray.AddMenuItemCheckbox("Chạy cùng Windows", "Tự chạy khi đăng nhập Windows", autostartEnabled())
	systray.AddSeparator()
	mQuit := systray.AddMenuItem("Thoát", "Dừng mọi dịch vụ và thoát")

	refresh := func() {
		for i, s := range a.sup.Statuses() {
			t := s.Name + ": " + s.Status.Label()
			if s.Detail != "" {
				t += " (" + s.Detail + ")"
			}
			svcItems[i].SetTitle(t)
		}
		st, detail := a.sup.Summary()
		tip := appTitle + " – " + map[Status]string{
			StatusRunning: "Đang chạy", StatusStarting: "Đang khởi động", StatusError: "Lỗi", StatusStopped: "Đã dừng"}[st]
		if detail != "" {
			tip += ": " + detail
			mSummary.SetTitle(detail)
			mSummary.Show()
		} else {
			mSummary.Hide()
		}
		if v := a.updater.AvailableVersion(); v != "" {
			mUpdate.SetTitle("Có bản mới " + v + " – Cập nhật")
			tip += " (có bản mới " + v + ")"
		} else {
			mUpdate.SetTitle("Cập nhật…")
		}
		if len(tip) > 120 {
			tip = tip[:117] + "..."
		}
		systray.SetTooltip(tip)
	}
	a.sup.OnChange = func() {}
	go func() {
		for range time.Tick(time.Second) {
			refresh()
		}
	}()

	go func() {
		for {
			select {
			case <-mOpen.ClickedCh:
				openPath(a.openTarget())
			case <-mLogs.ClickedCh:
				openPath(filepath.Join(a.root, "runtime", "logs"))
			case <-mUpdate.ClickedCh:
				openPath(strings.TrimRight(a.cfg.AppURL, "/") + "/settings/cap-nhat")
			case <-mRestart.ClickedCh:
				a.restart()
			case <-mBackup.ClickedCh:
				mBackup.Disable()
				go func() {
					defer mBackup.Enable()
					if p, err := RunBackup(a.cfg, a.root, a.log); err != nil {
						a.log.Printf("Sao lưu lỗi: %v", err)
						messageBox(appTitle, "Sao lưu thất bại:\n"+err.Error())
					} else {
						messageBox(appTitle, "Đã sao lưu dữ liệu vào:\n"+p)
					}
				}()
			case <-mAuto.ClickedCh:
				want := !mAuto.Checked()
				if err := setAutostart(want); err != nil {
					messageBox(appTitle, "Không đổi được cài đặt: "+err.Error())
				} else if want {
					mAuto.Check()
				} else {
					mAuto.Uncheck()
				}
			case <-mQuit.ClickedCh:
				if a.updater.Busy() {
					go messageBox(appTitle, "Đang cập nhật, vui lòng chờ xong rồi hãy thoát.")
					continue
				}
				mQuit.Disable()
				systray.SetTooltip(appTitle + " – Đang dừng…")
				go func() {
					a.shutdown()
					systray.Quit()
				}()
			}
		}
	}()

	a.start(!*flagAutostart)
	go a.dailyLoop()
	go a.updater.Loop(a.isQuitting)
}

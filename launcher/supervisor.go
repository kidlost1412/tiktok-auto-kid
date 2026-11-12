package main

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"
)

type Status int

const (
	StatusStopped Status = iota
	StatusStarting
	StatusRunning
	StatusError
	StatusExternal // đang chạy bên ngoài launcher (chỉ theo dõi health)
	StatusSkipped  // chưa cài (thiếu requires_path)
)

func (s Status) Label() string {
	switch s {
	case StatusRunning:
		return "● Đang chạy"
	case StatusStarting:
		return "◐ Đang khởi động"
	case StatusError:
		return "● Lỗi"
	case StatusExternal:
		return "◉ Đang chạy bên ngoài"
	case StatusSkipped:
		return "○ Chưa cài"
	}
	return "○ Đã dừng"
}

// SvcStatus là ảnh chụp trạng thái một dịch vụ cho giao diện.
type SvcStatus struct {
	Name   string
	Status Status
	Detail string
}

const (
	defaultHealthTimeout = 90 * time.Second
	logMaxBytes          = 5 << 20
	logKeep              = 3
	stableAfter          = 60 * time.Second
)

type svcState struct {
	svc    Service
	mu     sync.Mutex
	status Status
	detail string
	ready  chan struct{} // đóng khi lần đầu đạt healthy
	once   sync.Once
	stop   chan struct{} // đóng để yêu cầu dừng
	done   chan struct{} // đóng khi vòng giám sát kết thúc
	loop   bool          // đã có vòng giám sát chạy
}

func (st *svcState) set(s Status, detail string) {
	st.mu.Lock()
	st.status, st.detail = s, detail
	st.mu.Unlock()
}

func (st *svcState) get() (Status, string) {
	st.mu.Lock()
	defer st.mu.Unlock()
	return st.status, st.detail
}

// Supervisor khởi động, giám sát và dừng các dịch vụ theo services.json.
type Supervisor struct {
	cfg      *Config
	root     string
	log      *Logger
	order    []string
	states   map[string]*svcState
	OnChange func()
	Notify   func(title, msg string)

	mu        sync.Mutex
	quit      chan struct{}
	startDone chan struct{}
	lastErr   string
	phase     string // mô tả bước đang làm
	steps     []stepState
	wdOnce    sync.Once
	started   bool                 // đã khởi động xong lần đầu (từ đây mới báo lỗi do dịch vụ chết bất ngờ)
	lastCrash map[string]time.Time // chống báo lặp một dịch vụ
}

// stepState là trạng thái một bước first_run (cho trang trạng thái).
type stepState struct {
	Name   string
	State  string // pending | running | ok | skipped | error
	Detail string
}

func (s *Supervisor) setStep(i int, state, detail string) {
	s.mu.Lock()
	if i >= 0 && i < len(s.steps) {
		s.steps[i].State, s.steps[i].Detail = state, detail
	}
	s.mu.Unlock()
}

// StepStatuses trả bản sao trạng thái các bước first_run.
func (s *Supervisor) StepStatuses() []stepState {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]stepState(nil), s.steps...)
}

func stepName(step Command) string {
	if step.Name != "" {
		return step.Name
	}
	return filepath.Base(step.Cmd)
}

func NewSupervisor(cfg *Config, root string, log *Logger) (*Supervisor, error) {
	order, err := cfg.StartOrder()
	if err != nil {
		return nil, err
	}
	SetVars(cfg, root)
	s := &Supervisor{cfg: cfg, root: root, log: log, order: order, states: map[string]*svcState{}}
	for _, sv := range cfg.Services {
		s.states[sv.Name] = &svcState{svc: sv}
	}
	return s, nil
}

func (s *Supervisor) changed() {
	if s.OnChange != nil {
		s.OnChange()
	}
}

func (s *Supervisor) notify(title, msg string) {
	s.log.Printf("%s: %s", title, msg)
	if s.Notify != nil {
		s.Notify(title, msg)
	}
}

// Statuses trả trạng thái các dịch vụ theo thứ tự khởi động.
func (s *Supervisor) Statuses() []SvcStatus {
	var out []SvcStatus
	for _, n := range s.order {
		st, d := s.states[n].get()
		out = append(out, SvcStatus{n, st, d})
	}
	return out
}

// Summary trả về tình trạng tổng thể và dòng mô tả.
func (s *Supervisor) Summary() (Status, string) {
	s.mu.Lock()
	lastErr, phase := s.lastErr, s.phase
	s.mu.Unlock()
	if lastErr != "" {
		return StatusError, lastErr
	}
	all := StatusRunning
	for _, x := range s.Statuses() {
		if s.states[x.Name].svc.Optional {
			continue // dịch vụ tuỳ chọn không làm hỏng/giữ chậm cả bộ
		}
		switch x.Status {
		case StatusError:
			return StatusError, fmt.Sprintf("Dịch vụ %s gặp lỗi", x.Name)
		case StatusStarting, StatusStopped:
			all = StatusStarting
		}
	}
	if phase != "" {
		return StatusStarting, phase
	}
	return all, ""
}

func (s *Supervisor) setPhase(p string) {
	s.mu.Lock()
	s.phase = p
	s.mu.Unlock()
	s.changed()
}

func (s *Supervisor) fail(msg string) error {
	s.mu.Lock()
	s.lastErr, s.phase = msg, ""
	s.mu.Unlock()
	s.notify(appTitle+" – Lỗi", msg)
	s.changed()
	return errors.New(msg)
}

// CheckPorts kiểm tra các cổng sắp dùng; trả về thông báo cho cổng bị chiếm.
func (s *Supervisor) CheckPorts() []string {
	var msgs []string
	for _, p := range s.cfg.RequiredPorts() {
		if PortInUse(p) {
			owner := portOwner(p)
			m := fmt.Sprintf("Cổng %d đang bị chiếm bởi %s", p, orUnknown(owner))
			msgs = append(msgs, m)
		}
	}
	return msgs
}

// reclaimStale dọn tiến trình còn sót của chính bundle này đang giữ cổng:
// Postgres (đúng thư mục dữ liệu) dừng bằng pg_ctl; dịch vụ khác có exe nằm trong bundle thì diệt.
// Tiến trình lạ giữ nguyên để CheckPorts báo lỗi.
func (s *Supervisor) reclaimStale() {
	data := filepath.Join(s.root, "runtime", "data", "pg")
	for _, p := range s.cfg.RequiredPorts() {
		if !PortInUse(p) {
			continue
		}
		pid := listenerPID(p)
		if pid <= 0 {
			continue
		}
		img := procImagePath(pid)
		if b, err := os.ReadFile(filepath.Join(data, "postmaster.pid")); err == nil && IsOurPostgres(string(b), pid, data) {
			s.log.Printf("Cổng %d: Postgres cũ của bundle (PID %d) còn chạy, dừng sạch…", p, pid)
			if !pgCtlStop(s.root) {
				s.log.Printf("pg_ctl stop thất bại")
			}
			continue
		}
		if img != "" && PathUnder(img, s.root) {
			s.log.Printf("Cổng %d: tiến trình cũ của bundle %s (PID %d), diệt", p, img, pid)
			killTree(pid)
			time.Sleep(500 * time.Millisecond)
		}
	}
}

func orUnknown(s string) string {
	if s == "" {
		return "một chương trình khác"
	}
	return s
}

// Start chạy first_run rồi khởi động các dịch vụ theo thứ tự; chặn đến khi xong hoặc lỗi.
func (s *Supervisor) Start() error {
	s.mu.Lock()
	s.quit = make(chan struct{})
	s.startDone = make(chan struct{})
	quit, done := s.quit, s.startDone
	s.lastErr, s.phase = "", "Đang kiểm tra"
	s.started = false
	s.steps = nil
	for _, step := range s.cfg.FirstRun {
		s.steps = append(s.steps, stepState{Name: stepName(step), State: "pending"})
	}
	s.mu.Unlock()
	defer close(done)
	s.changed()

	s.setPhase("Dọn Postgres còn sót lại…")
	s.reclaimStale()
	s.setPhase("Đang kiểm tra")
	s.wdOnce.Do(func() { startPGWatchdog(s.root) })

	if msgs := s.CheckPorts(); len(msgs) > 0 {
		return s.fail(msgs[0] + ". Hãy tắt chương trình đó rồi chọn \"Khởi động lại\".")
	}

	for i, step := range s.cfg.FirstRun {
		select {
		case <-quit:
			return errors.New("đã huỷ")
		default:
		}
		name := stepName(step)
		if step.OnlyIfMissing != "" {
			p := resolveDir(step.OnlyIfMissing, s.root)
			if _, err := os.Stat(p); err == nil {
				s.setStep(i, "skipped", "")
				continue
			}
		}
		s.setPhase("Đang chuẩn bị: " + name)
		s.setStep(i, "running", "")
		if err := s.runStep(step, name, quit); err != nil {
			s.setStep(i, "error", err.Error())
			return s.fail(fmt.Sprintf("Bước chuẩn bị \"%s\" thất bại (%v). Xem runtime\\logs\\%s.log", name, err, name))
		}
		s.setStep(i, "ok", "")
	}

	for _, n := range s.order {
		st := s.states[n]
		s.setPhase("Đang khởi động " + n)
		if !s.launch(st) {
			continue // bỏ qua (chưa cài) hoặc tuỳ chọn: không chờ
		}
		if st.svc.Optional {
			continue
		}
		to := defaultHealthTimeout
		if h := st.svc.Health; h != nil && h.TimeoutSec > 0 {
			to = time.Duration(h.TimeoutSec) * time.Second
		}
		select {
		case <-st.ready:
		case <-quit:
			return errors.New("đã huỷ")
		case <-time.After(to):
			s.stopAll()
			return s.fail(fmt.Sprintf("Dịch vụ %s không sẵn sàng sau %d giây. Xem runtime\\logs\\%s.log", n, int(to.Seconds()), n))
		}
	}
	s.mu.Lock()
	s.phase = ""
	s.started = true
	s.mu.Unlock()
	s.log.Printf("Tất cả dịch vụ đã sẵn sàng")
	s.changed()
	return nil
}

// launch khởi tạo trạng thái và chạy vòng giám sát của một dịch vụ.
// Trả false nếu dịch vụ bị bỏ qua vì chưa cài (requires_path không tồn tại).
func (s *Supervisor) launch(st *svcState) bool {
	sv := st.svc
	st.mu.Lock()
	st.ready = make(chan struct{})
	st.once = sync.Once{}
	st.stop = make(chan struct{})
	st.done = make(chan struct{})
	if sv.RequiresPath != "" {
		if _, err := os.Stat(resolveDir(sv.RequiresPath, s.root)); err != nil {
			msg := sv.MissingMessage
			if msg == "" {
				msg = "Chưa cài"
			}
			st.loop = false
			st.status, st.detail = StatusSkipped, msg
			close(st.done)
			st.mu.Unlock()
			s.log.Printf("%s: bỏ qua (%s): thiếu %s", sv.Name, msg, resolveDir(sv.RequiresPath, s.root))
			s.changed()
			return false
		}
	}
	st.loop = true
	st.status, st.detail = StatusStarting, ""
	st.mu.Unlock()
	go s.runLoop(st)
	return true
}

// RestartService dừng rồi chạy lại một dịch vụ tuỳ chọn (không đụng các dịch vụ khác).
func (s *Supervisor) RestartService(name string) error {
	st, ok := s.states[name]
	if !ok || !st.svc.Optional {
		return fmt.Errorf("dịch vụ %q không được phép khởi động lại từ xa", name)
	}
	s.mu.Lock()
	busy := s.quit == nil
	s.mu.Unlock()
	if busy {
		return errors.New("launcher đang dừng hoặc chưa khởi động")
	}
	st.mu.Lock()
	running := st.loop
	stop, done := st.stop, st.done
	st.loop = false
	st.mu.Unlock()
	if running {
		s.log.Printf("Khởi động lại dịch vụ %s…", name)
		close(stop)
		<-done
	}
	if !s.launch(st) {
		return errors.New(st.detail)
	}
	return nil
}

// Stop dừng mọi dịch vụ theo thứ tự ngược (graceful rồi kill).
func (s *Supervisor) Stop() {
	s.mu.Lock()
	quit, done := s.quit, s.startDone
	s.quit = nil
	s.started = false
	s.mu.Unlock()
	if quit != nil {
		close(quit)
		<-done
	}
	s.stopAll()
}

func (s *Supervisor) stopAll() { s.stopAllExcept("") }

// StopExcept dừng mọi dịch vụ trừ keep (vd "postgres" để còn sao lưu/migrate khi cập nhật).
// Sau đó Start() không dùng được ngay: gọi Stop() (dừng nốt keep) rồi Start().
func (s *Supervisor) StopExcept(keep string) {
	s.mu.Lock()
	quit, done := s.quit, s.startDone
	s.quit = nil
	s.mu.Unlock()
	if quit != nil {
		close(quit)
		<-done
	}
	s.stopAllExcept(keep)
}

func (s *Supervisor) stopAllExcept(keep string) {
	for i := len(s.order) - 1; i >= 0; i-- {
		st := s.states[s.order[i]]
		if keep != "" && st.svc.Name == keep {
			continue
		}
		st.mu.Lock()
		running := st.loop
		st.loop = false
		stop, done := st.stop, st.done
		st.mu.Unlock()
		if !running {
			continue
		}
		s.log.Printf("Đang dừng %s…", st.svc.Name)
		close(stop)
		<-done
		st.set(StatusStopped, "")
		s.changed()
	}
}

func (s *Supervisor) Restart() error {
	s.Stop()
	return s.Start()
}

// runStep chạy một lệnh first_run, ghi log vào runtime/logs/<name>.log.
func (s *Supervisor) runStep(step Command, name string, quit <-chan struct{}) error {
	w, err := NewRotatingWriter(filepath.Join(s.root, "runtime", "logs", name+".log"), logMaxBytes, logKeep)
	if err != nil {
		return err
	}
	defer w.Close()
	fmt.Fprintf(w, "=== %s chạy lúc %s ===\n", name, time.Now().Format(time.RFC3339))
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go func() {
		select {
		case <-quit:
			cancel()
		case <-ctx.Done():
		}
	}()
	cmd := exec.CommandContext(ctx, resolveCmd(step.Cmd, s.root), resolveArgs(step.Args, s.root)...)
	cmd.Dir = resolveDir(step.Cwd, s.root)
	cmd.Env = append(os.Environ(), resolveEnv(step.Env, s.root)...)
	cmd.SysProcAttr = hiddenAttr()
	cmd.Stdout, cmd.Stderr = w, w
	cmd.WaitDelay = 5 * time.Second
	s.log.Printf("first_run: %s", name)
	return cmd.Run()
}

func (s *Supervisor) spawn(st *svcState, w *RotatingWriter) (*exec.Cmd, error) {
	sv := st.svc
	cmd := exec.Command(resolveCmd(sv.Cmd, s.root), resolveArgs(sv.Args, s.root)...)
	cmd.Dir = resolveDir(sv.Cwd, s.root)
	cmd.Env = buildEnv(os.Environ(), sv.Env, sv.PathAdd, s.root)
	cmd.SysProcAttr = childAttr()
	cmd.Stdout, cmd.Stderr = w, w
	cmd.WaitDelay = 5 * time.Second
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	if err := assignJob(cmd.Process.Pid); err != nil {
		s.log.Printf("%s: không gán được vào Job Object: %v", sv.Name, err)
	}
	return cmd, nil
}

// runLoop giám sát một dịch vụ: chạy, chờ healthy, restart có backoff khi chết.
func (s *Supervisor) runLoop(st *svcState) {
	defer close(st.done)
	sv := st.svc
	w, err := NewRotatingWriter(filepath.Join(s.root, "runtime", "logs", sv.Name+".log"), logMaxBytes, logKeep)
	if err != nil {
		st.set(StatusError, err.Error())
		s.log.Printf("%s: không mở được log: %v", sv.Name, err)
		<-st.stop
		return
	}
	defer w.Close()
	bo := NewBackoff(time.Second, 60*time.Second)

	for {
		st.set(StatusStarting, "")
		s.changed()
		fmt.Fprintf(w, "=== %s khởi động lúc %s ===\n", sv.Name, time.Now().Format(time.RFC3339))
		cmd, err := s.spawn(st, w)
		if err != nil {
			s.log.Printf("%s: không khởi động được: %v", sv.Name, err)
			fmt.Fprintf(w, "LỖI khởi động: %v\n", err)
			st.set(StatusError, err.Error())
			s.changed()
			if !s.wait(st, bo.Next()) {
				return
			}
			continue
		}
		started := time.Now()
		s.log.Printf("%s: đã chạy (PID %d)", sv.Name, cmd.Process.Pid)
		exited := make(chan error, 1)
		go func() { exited <- cmd.Wait() }()
		hctx, hcancel := context.WithCancel(context.Background())
		go s.watchHealth(hctx, st, exited)

		select {
		case err := <-exited:
			hcancel()
			code := 0
			var ee *exec.ExitError
			if errors.As(err, &ee) {
				code = ee.ExitCode()
			}
			s.log.Printf("%s: đã thoát (mã %d, sau %s)", sv.Name, code, time.Since(started).Round(time.Second))
			fmt.Fprintf(w, "=== %s thoát, mã %d ===\n", sv.Name, code)
			select {
			case <-st.stop:
				return
			default:
			}
			if containsInt(sv.NoRestartExitCodes, code) {
				s.log.Printf("%s: mã %d = đã có bản khác đang chạy ngoài launcher, chỉ theo dõi health", sv.Name, code)
				fmt.Fprintf(w, "=== %s: chạy bên ngoài, chỉ theo dõi ===\n", sv.Name)
				if !s.monitorExternal(st) {
					return
				}
				bo.Reset()
				continue
			}
			st.set(StatusError, fmt.Sprintf("thoát mã %d", code))
			s.changed()
			s.crashNotify(sv, code)
			switch sv.Restart {
			case "never":
				return
			case "on-failure":
				if code == 0 {
					st.set(StatusStopped, "")
					s.changed()
					return
				}
			}
			if time.Since(started) > stableAfter {
				bo.Reset()
			}
			d := bo.Next()
			s.log.Printf("%s: khởi động lại sau %s", sv.Name, d)
			if !s.wait(st, d) {
				return
			}
		case <-st.stop:
			hcancel()
			s.terminate(st, cmd, exited, w)
			return
		}
	}
}

// crashNotify báo (một lần mỗi 10 phút cho mỗi dịch vụ) khi dịch vụ chính chết bất ngờ SAU khi đã khởi động xong.
// Trong lúc khởi động không báo từng dịch vụ: lỗi khởi động hiện gọn trên màn hình chào / qua fail().
func (s *Supervisor) crashNotify(sv Service, code int) {
	if sv.Optional {
		return
	}
	s.mu.Lock()
	if !s.started || s.quit == nil {
		s.mu.Unlock()
		return
	}
	if s.lastCrash == nil {
		s.lastCrash = map[string]time.Time{}
	}
	if t, ok := s.lastCrash[sv.Name]; ok && time.Since(t) < 10*time.Minute {
		s.mu.Unlock()
		return
	}
	s.lastCrash[sv.Name] = time.Now()
	s.mu.Unlock()
	s.notify(appTitle+" – Cảnh báo", fmt.Sprintf("Dịch vụ %s vừa dừng bất ngờ (mã %d). Chương trình đang tự chạy lại.", sv.Name, code))
}

func containsInt(a []int, v int) bool {
	for _, x := range a {
		if x == v {
			return true
		}
	}
	return false
}

// monitorExternal theo dõi health của bản chạy ngoài launcher. Trả false khi có yêu cầu dừng;
// trả true khi bản ngoài biến mất (health hỏng liên tiếp) để launcher tự chạy lại dịch vụ.
func (s *Supervisor) monitorExternal(st *svcState) bool {
	h := st.svc.Health
	fails := 0
	for {
		if h == nil || CheckHealth(h) {
			fails = 0
			if cur, _ := st.get(); cur != StatusExternal {
				st.set(StatusExternal, "đang chạy bên ngoài launcher")
				st.once.Do(func() { close(st.ready) })
				s.changed()
			}
		} else {
			fails++
			if fails >= 3 {
				s.log.Printf("%s: bản chạy ngoài đã tắt, chạy lại", st.svc.Name)
				return true
			}
		}
		select {
		case <-time.After(5 * time.Second):
		case <-st.stop:
			return false
		}
	}
}

func (s *Supervisor) wait(st *svcState, d time.Duration) bool {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-t.C:
		return true
	case <-st.stop:
		return false
	}
}

// watchHealth đánh dấu Running khi dịch vụ sẵn sàng; không có health => sau 1 giây còn sống.
func (s *Supervisor) watchHealth(ctx context.Context, st *svcState, exited <-chan error) {
	h := st.svc.Health
	if h == nil {
		select {
		case <-time.After(time.Second):
		case <-ctx.Done():
			return
		}
	} else {
		for !CheckHealth(h) {
			select {
			case <-time.After(500 * time.Millisecond):
			case <-ctx.Done():
				return
			}
		}
	}
	if ctx.Err() != nil {
		return
	}
	st.set(StatusRunning, "")
	st.once.Do(func() { close(st.ready) })
	s.changed()
}

// CheckHealth thực hiện một lần kiểm tra sức khoẻ.
func CheckHealth(h *Health) bool {
	switch h.Type {
	case "tcp":
		c, err := net.DialTimeout("tcp", fmt.Sprintf("127.0.0.1:%d", h.Port), time.Second)
		if err != nil {
			return false
		}
		c.Close()
		return true
	case "http":
		cl := &http.Client{Timeout: 3 * time.Second,
			CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
		r, err := cl.Get(h.URL)
		if err != nil {
			return false
		}
		r.Body.Close()
		return r.StatusCode < 500
	}
	return false
}

// terminate dừng một tiến trình: lệnh stop (nếu có) -> CTRL_BREAK -> kill cả cây.
func (s *Supervisor) terminate(st *svcState, cmd *exec.Cmd, exited <-chan error, w *RotatingWriter) {
	sv := st.svc
	pid := cmd.Process.Pid
	grace := 8 * time.Second
	if sv.StopTimeoutSec > 0 {
		grace = time.Duration(sv.StopTimeoutSec) * time.Second
	}
	waitExit := func(d time.Duration) bool {
		select {
		case <-exited:
			return true
		case <-time.After(d):
			return false
		}
	}
	if sv.Stop != nil && sv.Stop.Mode != "" {
		// chỉ diệt đúng PID dịch vụ, không diệt cây con (tiến trình con tách job như batch phải sống tiếp)
		if sv.Stop.Mode == "ctrl_break_kill_pid" {
			sendCtrlBreak(pid)
			if waitExit(grace) {
				return
			}
		}
		cmd.Process.Kill()
		waitExit(5 * time.Second)
		return
	}
	if sv.Stop != nil {
		sc := exec.Command(resolveCmd(sv.Stop.Cmd, s.root), resolveArgs(sv.Stop.Args, s.root)...)
		sc.Dir = resolveDir(sv.Stop.Cwd, s.root)
		sc.Env = append(os.Environ(), resolveEnv(sv.Stop.Env, s.root)...)
		sc.SysProcAttr = hiddenAttr()
		sc.Stdout, sc.Stderr = w, w
		sc.WaitDelay = 5 * time.Second
		done := make(chan error, 1)
		if err := sc.Start(); err != nil {
			s.log.Printf("%s: lệnh stop lỗi: %v", sv.Name, err)
		} else {
			go func() { done <- sc.Wait() }()
			select {
			case err := <-done:
				if err != nil {
					s.log.Printf("%s: lệnh stop trả lỗi: %v", sv.Name, err)
				}
			case <-time.After(30 * time.Second):
				sc.Process.Kill()
			}
			if sv.StopTimeoutSec == 0 {
				grace = 30 * time.Second
			}
			if waitExit(grace) {
				return
			}
			s.log.Printf("%s: không thoát sau lệnh stop, buộc dừng", sv.Name)
		}
	} else {
		sendCtrlBreak(pid)
		if waitExit(grace) {
			return
		}
		s.log.Printf("%s: không thoát sau %s, buộc dừng", sv.Name, grace)
	}
	killTree(pid)
	if !waitExit(5 * time.Second) {
		cmd.Process.Kill()
		waitExit(2 * time.Second)
	}
}

// dummysvc là tiến trình giả dùng để thử launcher.
//
//	-mode serve   : mở HTTP trên -port (có /shutdown), thoát êm khi nhận CTRL_BREAK
//	-mode idle    : chạy mãi (tuỳ chọn -ignore-break)
//	-mode stop    : gọi POST /shutdown tới -port (dùng làm lệnh "stop")
//	-mode touch   : tạo file/thư mục -file (dùng làm first_run)
//	-mode dump    : in vài dòng SQL giả ra stdout (dùng làm backup)
package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"time"
)

func main() {
	mode := flag.String("mode", "serve", "serve|idle|stop|touch|dump")
	port := flag.Int("port", 0, "cổng HTTP")
	delay := flag.Duration("delay", 0, "chờ trước khi mở cổng (mô phỏng khởi động chậm)")
	crashAfter := flag.Duration("crash-after", 0, "thoát mã 1 sau khoảng này (thử restart/backoff)")
	ignoreBreak := flag.Bool("ignore-break", false, "bỏ qua CTRL_BREAK (thử buộc dừng)")
	file := flag.String("file", "", "đường dẫn cho -mode touch")
	flag.Parse()

	switch *mode {
	case "touch":
		if err := os.MkdirAll(filepath.Dir(*file), 0o755); err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
		if err := os.WriteFile(*file, []byte("ok"), 0o644); err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
		fmt.Println("đã tạo", *file)
	case "dump":
		fmt.Println("-- dummy dump")
		fmt.Println("CREATE TABLE demo(id int);")
		fmt.Println("INSERT INTO demo VALUES (1);")
	case "stop":
		r, err := http.Post(fmt.Sprintf("http://127.0.0.1:%d/shutdown", *port), "text/plain", nil)
		if err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
		r.Body.Close()
		fmt.Println("đã gửi lệnh dừng")
	case "idle", "serve":
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, os.Interrupt)
		quit := make(chan struct{})
		var srv *http.Server
		if *mode == "serve" {
			time.Sleep(*delay)
			mux := http.NewServeMux()
			mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, "dummysvc ok") })
			mux.HandleFunc("/shutdown", func(w http.ResponseWriter, r *http.Request) {
				fmt.Fprintln(w, "bye")
				go func() { time.Sleep(100 * time.Millisecond); close(quit) }()
			})
			srv = &http.Server{Addr: fmt.Sprintf("127.0.0.1:%d", *port), Handler: mux}
			go func() {
				if err := srv.ListenAndServe(); err != http.ErrServerClosed {
					fmt.Println("lỗi:", err)
					os.Exit(2)
				}
			}()
		}
		fmt.Println("dummysvc chạy, mode =", *mode, "port =", *port)
		var crash <-chan time.Time
		if *crashAfter > 0 {
			crash = time.After(*crashAfter)
		}
		for {
			select {
			case <-sig:
				if *ignoreBreak {
					fmt.Println("nhận CTRL_BREAK nhưng bỏ qua")
					continue
				}
				fmt.Println("nhận CTRL_BREAK, thoát êm")
				shutdown(srv)
				return
			case <-quit:
				fmt.Println("nhận lệnh stop, thoát êm")
				shutdown(srv)
				return
			case <-crash:
				fmt.Println("giả lập crash")
				os.Exit(1)
			}
		}
	}
}

func shutdown(srv *http.Server) {
	if srv == nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
}

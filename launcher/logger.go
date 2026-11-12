package main

import (
	"fmt"
	"io"
	"sync"
	"time"
)

// Logger ghi log của chính launcher (runtime/logs/launcher.log và tuỳ chọn stdout).
type Logger struct {
	mu  sync.Mutex
	out []io.Writer
}

func NewLogger(w ...io.Writer) *Logger { return &Logger{out: w} }

func (l *Logger) Printf(format string, a ...any) {
	line := fmt.Sprintf("%s %s\n", time.Now().Format("2006-01-02 15:04:05"), fmt.Sprintf(format, a...))
	l.mu.Lock()
	defer l.mu.Unlock()
	for _, w := range l.out {
		io.WriteString(w, line)
	}
}

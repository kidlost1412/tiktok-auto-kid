package main

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
)

// RotatingWriter ghi log vào file, xoay vòng khi vượt maxBytes, giữ keep file
// (file hiện tại + keep-1 file cũ: .1, .2, ...).
type RotatingWriter struct {
	path     string
	maxBytes int64
	keep     int
	mu       sync.Mutex
	f        *os.File
	size     int64
}

func NewRotatingWriter(path string, maxBytes int64, keep int) (*RotatingWriter, error) {
	if keep < 1 {
		keep = 1
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return nil, err
	}
	w := &RotatingWriter{path: path, maxBytes: maxBytes, keep: keep}
	if err := w.open(); err != nil {
		return nil, err
	}
	return w, nil
}

func (w *RotatingWriter) open() error {
	f, err := os.OpenFile(w.path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	st, err := f.Stat()
	if err != nil {
		f.Close()
		return err
	}
	w.f, w.size = f, st.Size()
	return nil
}

func (w *RotatingWriter) rotate() error {
	w.f.Close()
	w.f = nil
	os.Remove(fmt.Sprintf("%s.%d", w.path, w.keep-1))
	for i := w.keep - 2; i >= 1; i-- {
		os.Rename(fmt.Sprintf("%s.%d", w.path, i), fmt.Sprintf("%s.%d", w.path, i+1))
	}
	if w.keep > 1 {
		os.Rename(w.path, w.path+".1")
	} else {
		os.Remove(w.path)
	}
	return w.open()
}

func (w *RotatingWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.f == nil {
		if err := w.open(); err != nil {
			return 0, err
		}
	}
	if w.size > 0 && w.size+int64(len(p)) > w.maxBytes {
		if err := w.rotate(); err != nil {
			return 0, err
		}
	}
	n, err := w.f.Write(p)
	w.size += int64(n)
	return n, err
}

func (w *RotatingWriter) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.f == nil {
		return nil
	}
	err := w.f.Close()
	w.f = nil
	return err
}

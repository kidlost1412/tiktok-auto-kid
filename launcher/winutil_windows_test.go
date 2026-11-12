//go:build windows

package main

import (
	"os/exec"
	"testing"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

func TestJobFlagsAndKillOnClose(t *testing.T) {
	if err := initJob(); err != nil {
		t.Fatal(err)
	}
	var info windows.JOBOBJECT_EXTENDED_LIMIT_INFORMATION
	if err := windows.QueryInformationJobObject(jobHandle, windows.JobObjectExtendedLimitInformation,
		uintptr(unsafe.Pointer(&info)), uint32(unsafe.Sizeof(info)), nil); err != nil {
		t.Fatal(err)
	}
	f := info.BasicLimitInformation.LimitFlags
	if f&windows.JOB_OBJECT_LIMIT_BREAKAWAY_OK == 0 || f&windows.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE == 0 {
		t.Fatalf("thiếu cờ job: %#x", f)
	}
	c := exec.Command("ping", "-n", "60", "127.0.0.1")
	c.SysProcAttr = hiddenAttr()
	if err := c.Start(); err != nil {
		t.Fatal(err)
	}
	if err := assignJob(c.Process.Pid); err != nil {
		t.Fatal(err)
	}
	exited := make(chan struct{})
	go func() { c.Wait(); close(exited) }()
	windows.CloseHandle(jobHandle) // giống launcher chết: KILL_ON_JOB_CLOSE phải diệt tiến trình con thường
	jobHandle = 0
	select {
	case <-exited:
	case <-time.After(10 * time.Second):
		c.Process.Kill()
		t.Fatal("tiến trình con thường không bị diệt khi đóng job")
	}
}

//go:build !windows

package snapshots

import (
	"os"
	"syscall"
)

func processExists(pid int) bool {
	process, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	return process.Signal(syscall.Signal(0)) == nil
}

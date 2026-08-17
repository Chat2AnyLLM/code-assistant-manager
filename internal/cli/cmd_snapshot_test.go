package cli_test

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/chat2anyllm/code-agent-manager/internal/cli"
)

func TestSnapshotHelpListsOperations(t *testing.T) {
	stdout, stderr, code := execute(t, "snapshot", "--help")
	if code != 0 {
		t.Fatalf("exit=%d stderr=%s", code, stderr)
	}
	for _, command := range []string{"create", "list", "show", "diff", "restore"} {
		if !strings.Contains(stdout, command) {
			t.Fatalf("snapshot help missing %q:\n%s", command, stdout)
		}
	}
}

func TestSnapshotCreateListShowAndJSON(t *testing.T) {
	home := isolatedHome(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("instructions\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	stdout, stderr, code := execute(t, "snapshot", "create", "--agent", "claude", "--name", "baseline", "--format", "json")
	if code != 0 {
		t.Fatalf("create exit=%d stderr=%s", code, stderr)
	}
	var created struct {
		Manifest struct {
			ID string `json:"id"`
		} `json:"manifest"`
	}
	if err := json.Unmarshal([]byte(stdout), &created); err != nil {
		t.Fatalf("invalid create JSON: %v\n%s", err, stdout)
	}
	if created.Manifest.ID == "" {
		t.Fatal("create JSON has no ID")
	}

	stdout, stderr, code = execute(t, "snapshot", "list", "--format", "json")
	if code != 0 || !strings.Contains(stdout, created.Manifest.ID) {
		t.Fatalf("list exit=%d stderr=%s stdout=%s", code, stderr, stdout)
	}
	stdout, stderr, code = execute(t, "snapshot", "show", "baseline")
	if code != 0 || !strings.Contains(stdout, "Integrity: verified") || !strings.Contains(stdout, "claude") {
		t.Fatalf("show exit=%d stderr=%s stdout=%s", code, stderr, stdout)
	}
}

func TestSnapshotCreateValidatesFlags(t *testing.T) {
	isolatedHome(t)
	tests := [][]string{
		{"snapshot", "create", "--scope", "invalid"},
		{"snapshot", "create", "--scope", "project"},
		{"snapshot", "create", "--agent", "unknown"},
		{"snapshot", "create", "--format", "yaml"},
	}
	for _, args := range tests {
		_, stderr, code := execute(t, args...)
		if code == 0 || stderr == "" {
			t.Fatalf("args=%v exit=%d stderr=%q", args, code, stderr)
		}
	}
}

func TestSnapshotDiffExitStatuses(t *testing.T) {
	home := isolatedHome(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("before\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	stdout, stderr, code := execute(t, "snapshot", "create", "--agent", "claude", "--name", "diff-test")
	if code != 0 {
		t.Fatalf("create exit=%d stderr=%s stdout=%s", code, stderr, stdout)
	}
	stdout, stderr, code = execute(t, "snapshot", "diff", "diff-test", "--format", "json")
	if code != 0 || stderr != "" {
		t.Fatalf("clean diff exit=%d stderr=%s stdout=%s", code, stderr, stdout)
	}
	var clean map[string]any
	if err := json.Unmarshal([]byte(stdout), &clean); err != nil {
		t.Fatalf("invalid diff JSON: %v", err)
	}

	if err := os.WriteFile(path, []byte("after\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	stdout, stderr, code = execute(t, "snapshot", "diff", "diff-test")
	if code != 1 || stderr != "" || !strings.Contains(stdout, "M\tclaude") {
		t.Fatalf("drift diff exit=%d stderr=%s stdout=%s", code, stderr, stdout)
	}
	_, stderr, code = execute(t, "snapshot", "diff", "missing")
	if code != 2 || !strings.Contains(stderr, "not found") {
		t.Fatalf("failed diff exit=%d stderr=%s", code, stderr)
	}
	_, stderr, code = execute(t, "snapshot", "diff", "diff-test", "--format", "yaml")
	if code != 2 || !strings.Contains(stderr, "unsupported") {
		t.Fatalf("format diff exit=%d stderr=%s", code, stderr)
	}
	for _, args := range [][]string{{"snapshot", "diff"}, {"snapshot", "diff", "one", "two"}, {"snapshot", "diff", "diff-test", "--unknown"}} {
		_, stderr, code = execute(t, args...)
		if code != 2 || stderr == "" {
			t.Fatalf("invalid diff args=%v exit=%d stderr=%s", args, code, stderr)
		}
	}
}

func TestSnapshotRestoreDryRunAndNonInteractiveConsent(t *testing.T) {
	home := isolatedHome(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("before\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	_, stderr, code := execute(t, "snapshot", "create", "--agent", "claude", "--name", "restore-test")
	if code != 0 {
		t.Fatal(stderr)
	}
	if err := os.WriteFile(path, []byte("after\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	stdout, stderr, code := execute(t, "snapshot", "restore", "restore-test", "--dry-run")
	if code != 0 || !strings.Contains(stdout, "dry run") {
		t.Fatalf("dry run exit=%d stderr=%s stdout=%s", code, stderr, stdout)
	}
	assertCLIFile(t, path, "after\n")

	_, stderr, code = execute(t, "snapshot", "restore", "restore-test")
	if code != 1 || !strings.Contains(stderr, "requires --yes") {
		t.Fatalf("noninteractive exit=%d stderr=%s", code, stderr)
	}
	assertCLIFile(t, path, "after\n")

	stdout, stderr, code = execute(t, "snapshot", "restore", "restore-test", "--yes")
	if code != 0 || !strings.Contains(stdout, "Restored 1 targets") {
		t.Fatalf("restore exit=%d stderr=%s stdout=%s", code, stderr, stdout)
	}
	assertCLIFile(t, path, "before\n")
}

func TestSnapshotRestoreInteractiveConfirmationAndCancellation(t *testing.T) {
	home := isolatedHome(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("before\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	_, stderr, code := execute(t, "snapshot", "create", "--agent", "claude", "--name", "interactive")
	if code != 0 {
		t.Fatal(stderr)
	}

	run := func(input string) (string, string, int) {
		var out, errOut bytes.Buffer
		interactive := true
		app := cli.New(cli.Options{Version: "test", Stdout: &out, Stderr: &errOut, Stdin: strings.NewReader(input), Interactive: &interactive})
		code := app.Run([]string{"snapshot", "restore", "interactive"})
		return out.String(), errOut.String(), code
	}
	if err := os.WriteFile(path, []byte("cancel\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	stdout, _, code := run("n\n")
	if code != 0 || !strings.Contains(stdout, "cancelled") {
		t.Fatalf("cancel exit=%d stdout=%s", code, stdout)
	}
	assertCLIFile(t, path, "cancel\n")

	stdout, stderr, code = run("yes\n")
	if code != 0 || !strings.Contains(stderr, "Restore 1 targets?") || !strings.Contains(stdout, "Restored") {
		t.Fatalf("confirm exit=%d stderr=%s stdout=%s", code, stderr, stdout)
	}
	assertCLIFile(t, path, "before\n")
}

func TestSnapshotRestoreExactRemovesAddedTarget(t *testing.T) {
	home := isolatedHome(t)
	path := filepath.Join(home, ".gemini", "GEMINI.md")
	_, stderr, code := execute(t, "snapshot", "create", "--agent", "gemini", "--name", "absent")
	if code != 0 {
		t.Fatal(stderr)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("extra\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	_, stderr, code = execute(t, "snapshot", "restore", "absent", "--exact", "--yes")
	if code != 0 {
		t.Fatalf("exact restore exit=%d stderr=%s", code, stderr)
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("exact restore retained target: %v", err)
	}
}

func assertCLIFile(t *testing.T, path, want string) {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != want {
		t.Fatalf("%s=%q want %q", path, data, want)
	}
}

package snapshots

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRestoreConservativeAndExact(t *testing.T) {
	service, home := testService(t)
	claude := filepath.Join(home, ".claude", "CLAUDE.md")
	gemini := filepath.Join(home, ".gemini", "GEMINI.md")
	writeTestFile(t, claude, "snapshot\n")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude", "gemini"}})
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, claude, "drift\n")
	writeTestFile(t, gemini, "extra\n")

	plan, err := service.PlanRestore(snapshot.Manifest.ID, ResolveOptions{}, false)
	if err != nil {
		t.Fatal(err)
	}
	if plan.ChangeCount() != 1 || plan.Actions[1].Type != RestorePreserveExtra {
		t.Fatalf("unexpected conservative plan: %#v", plan)
	}
	if err := service.ApplyRestore(plan); err != nil {
		t.Fatal(err)
	}
	assertFileContent(t, claude, "snapshot\n")
	assertFileContent(t, gemini, "extra\n")

	exact, err := service.PlanRestore(snapshot.Manifest.ID, ResolveOptions{}, true)
	if err != nil {
		t.Fatal(err)
	}
	if exact.ChangeCount() != 1 || exact.Actions[1].Type != RestoreRemove {
		t.Fatalf("unexpected exact plan: %#v", exact)
	}
	if err := service.ApplyRestore(exact); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Lstat(gemini); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("extra file still exists: %v", err)
	}
}

func TestRestorePlanIsPureAndDetectsRace(t *testing.T) {
	service, home := testService(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	writeTestFile(t, path, "snapshot\n")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}})
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, path, "drift\n")
	plan, err := service.PlanRestore(snapshot.Manifest.ID, ResolveOptions{}, false)
	if err != nil {
		t.Fatal(err)
	}
	assertFileContent(t, path, "drift\n")
	if _, err := os.Stat(filepath.Join(service.root, journalFilename)); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("planning created a journal: %v", err)
	}
	writeTestFile(t, path, "raced\n")
	if err := service.ApplyRestore(plan); err == nil || !strings.Contains(err.Error(), "changed after planning") {
		t.Fatalf("expected race rejection, got %v", err)
	}
	assertFileContent(t, path, "raced\n")
}

func TestRestoreReplacesSymlinkWithoutChangingTarget(t *testing.T) {
	service, home := testService(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	writeTestFile(t, path, "snapshot\n")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(path); err != nil {
		t.Fatal(err)
	}
	external := filepath.Join(home, "external.md")
	writeTestFile(t, external, "external\n")
	if err := os.Symlink(external, path); err != nil {
		t.Fatal(err)
	}
	plan, err := service.PlanRestore(snapshot.Manifest.ID, ResolveOptions{}, false)
	if err != nil {
		t.Fatal(err)
	}
	if !plan.Actions[0].ReplacesLink {
		t.Fatalf("plan did not report link replacement: %#v", plan.Actions[0])
	}
	if err := service.ApplyRestore(plan); err != nil {
		t.Fatal(err)
	}
	info, err := os.Lstat(path)
	if err != nil {
		t.Fatal(err)
	}
	if !info.Mode().IsRegular() {
		t.Fatalf("destination remains a link: %v", info.Mode())
	}
	assertFileContent(t, path, "snapshot\n")
	assertFileContent(t, external, "external\n")
}

func TestRestoreRollsBackAppliedActions(t *testing.T) {
	service, home := testService(t)
	claude := filepath.Join(home, ".claude", "CLAUDE.md")
	gemini := filepath.Join(home, ".gemini", "GEMINI.md")
	writeTestFile(t, claude, "snapshot-c\n")
	writeTestFile(t, gemini, "snapshot-g\n")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude", "gemini"}})
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, claude, "before-c\n")
	writeTestFile(t, gemini, "before-g\n")
	plan, err := service.PlanRestore(snapshot.Manifest.ID, ResolveOptions{}, false)
	if err != nil {
		t.Fatal(err)
	}

	realRename := service.ops.rename
	calls := 0
	service.ops.rename = func(from, to string) error {
		if strings.Contains(filepath.Base(from), ".cam-restore-") {
			calls++
			if calls == 2 {
				return errors.New("injected rename failure")
			}
		}
		return realRename(from, to)
	}
	err = service.ApplyRestore(plan)
	if err == nil || !strings.Contains(err.Error(), "rolled back") {
		t.Fatalf("expected rolled-back failure, got %v", err)
	}
	assertFileContent(t, claude, "before-c\n")
	assertFileContent(t, gemini, "before-g\n")
	if _, err := os.Stat(filepath.Join(service.root, journalFilename)); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("successful rollback retained journal: %v", err)
	}
}

func TestRecoverInterruptedRestore(t *testing.T) {
	service, home := testService(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	writeTestFile(t, path, "before\n")
	action := restoreAction{view: RestoreAction{Path: path}}
	recovery, recoveryPath, err := service.createRecovery([]restoreAction{action})
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, path, "partially-applied\n")
	journal := RestoreJournal{
		Version: SchemaVersion, ID: recovery.ID, SnapshotID: "snapshot-any", RecoveryPath: recoveryPath,
		CreatedAt: service.now().UTC(), Current: 1,
		Actions: []journalAction{{Path: path, Post: stateToken{State: StatePresent, NodeType: NodeRegular, Digest: digestBytes([]byte("partially-applied\n")), Size: int64(len("partially-applied\n")), Mode: 0o600}}},
	}
	if err := service.writeJournal(journal); err != nil {
		t.Fatal(err)
	}
	if err := service.Recover(); err != nil {
		t.Fatal(err)
	}
	assertFileContent(t, path, "before\n")
}

func TestRestoreRejectsSymlinkAncestor(t *testing.T) {
	service, home := testService(t)
	outside := t.TempDir()
	if err := os.Symlink(outside, filepath.Join(home, ".claude")); err != nil {
		t.Fatal(err)
	}
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}})
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, filepath.Join(outside, "CLAUDE.md"), "drift\n")
	if _, err := service.PlanRestore(snapshot.Manifest.ID, ResolveOptions{}, true); err == nil || !strings.Contains(err.Error(), "ancestor") {
		t.Fatalf("expected symlink ancestor rejection, got %v", err)
	}
}

func assertFileContent(t *testing.T, path, want string) {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != want {
		t.Fatalf("%s = %q, want %q", path, data, want)
	}
}

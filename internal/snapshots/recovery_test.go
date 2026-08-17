//go:build !windows

package snapshots

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestLockReclaimsStaleProcessOwner(t *testing.T) {
	service, _ := testService(t)
	if err := os.MkdirAll(service.root, 0o700); err != nil {
		t.Fatal(err)
	}
	lockPath := filepath.Join(service.root, ".lock")
	if err := os.WriteFile(lockPath, []byte("99999999\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	old := service.now().Add(-staleLockGracePeriod - time.Second)
	if err := os.Chtimes(lockPath, old, old); err != nil {
		t.Fatal(err)
	}
	unlock, err := service.lock()
	if err != nil {
		t.Fatalf("stale lock was not reclaimed: %v", err)
	}
	unlock()
}

func TestRecoverRefusesThirdPartyEditToCompletedAction(t *testing.T) {
	service, home := testService(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	writeTestFile(t, path, "before\n")
	recovery, recoveryPath, err := service.createRecovery([]restoreAction{{view: RestoreAction{Path: path}}})
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, path, "third-party\n")
	journal := RestoreJournal{
		Version: SchemaVersion, ID: recovery.ID, SnapshotID: "snapshot-any", RecoveryPath: recoveryPath,
		CreatedAt: service.now().UTC(), Current: 1,
		Actions: []journalAction{{Path: path, Post: stateToken{State: StatePresent, NodeType: NodeRegular, Digest: digestBytes([]byte("intended\n")), Size: int64(len("intended\n")), Mode: 0o600}}},
	}
	if err := service.writeJournal(journal); err != nil {
		t.Fatal(err)
	}
	err = service.Recover()
	if err == nil || !strings.Contains(err.Error(), "refusing automatic rollback") {
		t.Fatalf("expected completed-action third-state refusal, got %v", err)
	}
	assertFileContent(t, path, "third-party\n")
}

func TestRecoverAmbiguousApplyingActionRefusesThirdState(t *testing.T) {
	service, home := testService(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	writeTestFile(t, path, "before\n")
	recovery, recoveryPath, err := service.createRecovery([]restoreAction{{view: RestoreAction{Path: path}}})
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, path, "third-party\n")
	journal := RestoreJournal{
		Version: SchemaVersion, ID: recovery.ID, SnapshotID: "snapshot-any", RecoveryPath: recoveryPath,
		CreatedAt: service.now().UTC(), Current: 0, Applying: true,
		Actions: []journalAction{{Path: path, Post: stateToken{State: StatePresent, NodeType: NodeRegular, Digest: digestBytes([]byte("intended\n")), Size: int64(len("intended\n")), Mode: 0o600}}},
	}
	if err := service.writeJournal(journal); err != nil {
		t.Fatal(err)
	}
	err = service.Recover()
	if err == nil || !strings.Contains(err.Error(), "refusing automatic recovery") {
		t.Fatalf("expected ambiguous recovery refusal, got %v", err)
	}
	assertFileContent(t, path, "third-party\n")
	if _, err := os.Stat(filepath.Join(service.root, journalFilename)); err != nil {
		t.Fatalf("journal was not retained: %v", err)
	}
}

func TestRestorePlanningDoesNotRecoverPendingJournal(t *testing.T) {
	service, home := testService(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	writeTestFile(t, path, "before\n")
	recovery, recoveryPath, err := service.createRecovery([]restoreAction{{view: RestoreAction{Path: path}}})
	if err != nil {
		t.Fatal(err)
	}
	journal := RestoreJournal{
		Version: SchemaVersion, ID: recovery.ID, SnapshotID: "snapshot-any", RecoveryPath: recoveryPath,
		CreatedAt: service.now().UTC(), Actions: []journalAction{{Path: path, Post: stateToken{State: StateAbsent}}},
	}
	if err := service.writeJournal(journal); err != nil {
		t.Fatal(err)
	}
	if _, err := service.PlanRestore("anything", ResolveOptions{}, false); err == nil || !strings.Contains(err.Error(), "unfinished recovery") {
		t.Fatalf("planning did not report pending recovery: %v", err)
	}
	if _, err := os.Stat(filepath.Join(service.root, journalFilename)); err != nil {
		t.Fatalf("planning mutated the recovery journal: %v", err)
	}
}

func TestReadOnlyOperationsReportPendingRecovery(t *testing.T) {
	service, home := testService(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	writeTestFile(t, path, "before\n")
	recovery, recoveryPath, err := service.createRecovery([]restoreAction{{view: RestoreAction{Path: path}}})
	if err != nil {
		t.Fatal(err)
	}
	journal := RestoreJournal{
		Version: SchemaVersion, ID: recovery.ID, SnapshotID: "snapshot-any", RecoveryPath: recoveryPath,
		CreatedAt: service.now().UTC(), Actions: []journalAction{{Path: path, Post: stateToken{State: StateAbsent}}},
	}
	if err := service.writeJournal(journal); err != nil {
		t.Fatal(err)
	}
	if _, err := service.List(); err == nil || !strings.Contains(err.Error(), "unfinished recovery") {
		t.Fatalf("list did not report pending recovery: %v", err)
	}
	if _, err := service.Show("anything"); err == nil || !strings.Contains(err.Error(), "unfinished recovery") {
		t.Fatalf("show did not report pending recovery: %v", err)
	}
}

func TestApplyRejectsEmptyForgedPlan(t *testing.T) {
	service, _ := testService(t)
	if err := service.ApplyRestore(RestorePlan{}); err == nil || !strings.Contains(err.Error(), "not executable") {
		t.Fatalf("expected forged empty-plan rejection, got %v", err)
	}
}

func TestApplyRejectsModifiedRestorePlan(t *testing.T) {
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
	plan.Actions[0].Path = filepath.Join(home, "unrelated")
	if err := service.ApplyRestore(plan); err == nil || !strings.Contains(err.Error(), "modified") {
		t.Fatalf("expected modified-plan rejection, got %v", err)
	}
	plan, err = service.PlanRestore(snapshot.Manifest.ID, ResolveOptions{}, false)
	if err != nil {
		t.Fatal(err)
	}
	plan.SnapshotID = "snapshot-forged"
	if err := service.ApplyRestore(plan); err == nil || !strings.Contains(err.Error(), "not executable") {
		t.Fatalf("expected modified snapshot-id rejection, got %v", err)
	}
	plan, err = service.PlanRestore(snapshot.Manifest.ID, ResolveOptions{}, false)
	if err != nil {
		t.Fatal(err)
	}
	plan.Exact = true
	if err := service.ApplyRestore(plan); err == nil || !strings.Contains(err.Error(), "not executable") {
		t.Fatalf("expected modified exact-mode rejection, got %v", err)
	}
	assertFileContent(t, path, "drift\n")
}

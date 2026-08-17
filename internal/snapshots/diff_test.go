package snapshots

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDiffClassifiesDriftAndRendersText(t *testing.T) {
	service, home := testService(t)
	claude := filepath.Join(home, ".claude", "CLAUDE.md")
	gemini := filepath.Join(home, ".gemini", "GEMINI.md")
	writeTestFile(t, claude, "one\ntwo\n")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude", "gemini"}})
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, claude, "one\nchanged\n")
	writeTestFile(t, gemini, "added\n")
	result, err := service.Diff(snapshot.Manifest.ID, ResolveOptions{})
	if err != nil {
		t.Fatal(err)
	}
	if result.Summary.Changed != 1 || result.Summary.Added != 1 || !result.HasDrift() {
		t.Fatalf("unexpected summary: %#v", result.Summary)
	}
	if !strings.Contains(result.Entries[0].TextDiff, "-two") || !strings.Contains(result.Entries[0].TextDiff, "+changed") {
		t.Fatalf("unexpected text diff: %q", result.Entries[0].TextDiff)
	}

	if err := os.Remove(claude); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(gemini); err != nil {
		t.Fatal(err)
	}
	result, err = service.Diff(snapshot.Manifest.ID, ResolveOptions{})
	if err != nil {
		t.Fatal(err)
	}
	if result.Summary.Missing != 1 || result.Summary.Unchanged != 1 {
		t.Fatalf("unexpected missing summary: %#v", result.Summary)
	}
}

func TestDiffDetectsLineEndingsAndSkipsBinaryPatch(t *testing.T) {
	service, home := testService(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	writeTestFile(t, path, "one\r\n")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}})
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, path, "one\n")
	result, err := service.Diff(snapshot.Manifest.ID, ResolveOptions{})
	if err != nil {
		t.Fatal(err)
	}
	if result.Summary.Changed != 1 {
		t.Fatalf("line endings were normalized: %#v", result)
	}

	if err := os.WriteFile(path, []byte{0, 1, 2}, 0o600); err != nil {
		t.Fatal(err)
	}
	result, err = service.Diff(snapshot.Manifest.ID, ResolveOptions{})
	if err != nil {
		t.Fatal(err)
	}
	if result.Entries[0].TextDiff != "" {
		t.Fatalf("binary content got a text patch: %q", result.Entries[0].TextDiff)
	}
}

func TestDiffRebasesProjectSnapshot(t *testing.T) {
	service, _ := testService(t)
	first := t.TempDir()
	second := t.TempDir()
	writeTestFile(t, filepath.Join(first, "CLAUDE.md"), "same\n")
	writeTestFile(t, filepath.Join(second, "CLAUDE.md"), "same\n")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeProject, ProjectDir: first, Agents: []string{"claude"}})
	if err != nil {
		t.Fatal(err)
	}
	result, err := service.Diff(snapshot.Manifest.ID, ResolveOptions{ProjectDir: second})
	if err != nil {
		t.Fatal(err)
	}
	if result.Summary.Unchanged != 1 || result.Entries[0].Path != filepath.Join(second, "CLAUDE.md") {
		t.Fatalf("unexpected rebased result: %#v", result)
	}
	if err := os.RemoveAll(first); err != nil {
		t.Fatal(err)
	}
	if _, err := service.Diff(snapshot.Manifest.ID, ResolveOptions{}); err == nil || !strings.Contains(err.Error(), "supply --project-dir") {
		t.Fatalf("expected unavailable project guidance, got %v", err)
	}
}

func TestDiffReportsUnsupportedCurrentNode(t *testing.T) {
	service, home := testService(t)
	path := filepath.Join(home, ".claude", "CLAUDE.md")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(path, 0o700); err != nil {
		t.Fatal(err)
	}
	result, err := service.Diff(snapshot.Manifest.ID, ResolveOptions{})
	if err != nil {
		t.Fatal(err)
	}
	if result.Summary.Unsupported != 1 || result.Entries[0].Status != DriftUnsupported {
		t.Fatalf("unexpected unsupported result: %#v", result)
	}
}

func TestJoinBeneathRejectsEscape(t *testing.T) {
	if _, err := joinBeneath(t.TempDir(), "../escape"); err == nil {
		t.Fatal("expected escaped locator rejection")
	}
}

func TestUnifiedDiffNoTrailingNewline(t *testing.T) {
	patch := unifiedDiff([]byte("before"), []byte("after"))
	if strings.Count(patch, "No newline at end of file") != 2 {
		t.Fatalf("missing no-newline markers: %q", patch)
	}
}

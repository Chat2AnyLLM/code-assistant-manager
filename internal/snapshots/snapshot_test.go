package snapshots

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func testService(t *testing.T) (*Service, string) {
	t.Helper()
	home := t.TempDir()
	t.Setenv("HOME", home)
	root := filepath.Join(home, "cam", "snapshots")
	service := NewServiceAt(root)
	service.now = func() time.Time { return time.Date(2026, 8, 17, 12, 0, 0, 123, time.UTC) }
	service.random = strings.NewReader(strings.Repeat("abcdefghijklmnopqrstuvwxyz", 100))
	return service, home
}

func writeTestFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

func TestCreateCapturesPresentAbsentAndSharedTargets(t *testing.T) {
	service, home := testService(t)
	writeTestFile(t, filepath.Join(home, ".claude", "CLAUDE.md"), "claude\n")

	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"gemini", "claude", "claude"}, Name: "baseline"})
	if err != nil {
		t.Fatal(err)
	}
	if snapshot.Manifest.Name != "baseline" || len(snapshot.Manifest.Entries) != 2 {
		t.Fatalf("unexpected manifest: %#v", snapshot.Manifest)
	}
	if snapshot.Manifest.Entries[0].Owners[0] != "claude" || snapshot.Manifest.Entries[0].State != StatePresent {
		t.Fatalf("unexpected present entry: %#v", snapshot.Manifest.Entries[0])
	}
	if snapshot.Manifest.Entries[1].Owners[0] != "gemini" || snapshot.Manifest.Entries[1].State != StateAbsent {
		t.Fatalf("unexpected absent entry: %#v", snapshot.Manifest.Entries[1])
	}

	project := t.TempDir()
	writeTestFile(t, filepath.Join(project, "AGENTS.md"), "shared\n")
	shared, err := service.Create(CreateOptions{Scope: ScopeProject, ProjectDir: project, Agents: []string{"codex", "opencode", "amp"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(shared.Manifest.Entries) != 1 {
		t.Fatalf("expected one deduplicated target, got %d", len(shared.Manifest.Entries))
	}
	owners := strings.Join(shared.Manifest.Entries[0].Owners, ",")
	if owners != "amp,codex,opencode" {
		t.Fatalf("unexpected owners %q", owners)
	}
}

func TestCreateValidatesSelectionBeforePublishing(t *testing.T) {
	service, _ := testService(t)
	tests := []CreateOptions{
		{Scope: Scope("other")},
		{Scope: ScopeProject},
		{Scope: ScopeUser, ProjectDir: t.TempDir()},
		{Scope: ScopeUser, Agents: []string{"unknown"}},
		{Scope: ScopeUser, Name: "../bad"},
	}
	for _, options := range tests {
		if _, err := service.Create(options); err == nil {
			t.Fatalf("expected error for %#v", options)
		}
	}
	items, err := service.List()
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 0 {
		t.Fatalf("invalid creates published %d snapshots", len(items))
	}
}

func TestCreateCapturesSymlinkAndRejectsUnsupportedNode(t *testing.T) {
	service, home := testService(t)
	target := filepath.Join(home, "managed.md")
	writeTestFile(t, target, "linked\n")
	link := filepath.Join(home, ".claude", "CLAUDE.md")
	if err := os.MkdirAll(filepath.Dir(link), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, link); err != nil {
		t.Fatal(err)
	}
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}})
	if err != nil {
		t.Fatal(err)
	}
	entry := snapshot.Manifest.Entries[0]
	if entry.NodeType != NodeSymlink || entry.SymlinkTarget != target || entry.Digest != digestBytes([]byte("linked\n")) {
		t.Fatalf("unexpected link entry: %#v", entry)
	}

	if err := os.Remove(link); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(link, 0o700); err != nil {
		t.Fatal(err)
	}
	if _, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}}); err == nil || !strings.Contains(err.Error(), "unsupported file type") {
		t.Fatalf("expected unsupported-node error, got %v", err)
	}
}

func TestStoreListShowReferenceAndIntegrity(t *testing.T) {
	service, home := testService(t)
	writeTestFile(t, filepath.Join(home, ".claude", "CLAUDE.md"), "one\n")
	first, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}, Name: "same"})
	if err != nil {
		t.Fatal(err)
	}
	service.now = func() time.Time { return time.Date(2026, 8, 17, 12, 1, 0, 0, time.UTC) }
	service.random = strings.NewReader(strings.Repeat("mnopqrstuvwx", 100))
	second, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}, Name: "same"})
	if err != nil {
		t.Fatal(err)
	}
	list, err := service.List()
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 2 || list[0].Manifest.ID != second.Manifest.ID {
		t.Fatalf("unexpected list ordering: %#v", list)
	}
	shown, err := service.Show(first.Manifest.ID[:24])
	if err != nil || shown.Manifest.ID != first.Manifest.ID {
		t.Fatalf("prefix show failed: %#v %v", shown, err)
	}
	if _, err := service.Show("same"); err == nil || !strings.Contains(err.Error(), "ambiguous") {
		t.Fatalf("expected ambiguous name, got %v", err)
	}

	entry := first.Manifest.Entries[0]
	object := filepath.Join(service.root, first.Manifest.ID, objectsDirectory, "sha256", entry.Digest)
	if err := os.WriteFile(object, []byte("corrupt"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := service.Show(first.Manifest.ID); err == nil || !strings.Contains(err.Error(), "integrity") {
		t.Fatalf("expected integrity error, got %v", err)
	}
}

func TestStoreRejectsManifestTraversalAndUnsupportedVersion(t *testing.T) {
	service, home := testService(t)
	writeTestFile(t, filepath.Join(home, ".claude", "CLAUDE.md"), "one\n")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}})
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(service.root, snapshot.Manifest.ID, manifestFilename)
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var manifest Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		t.Fatal(err)
	}
	manifest.Entries[0].Locator = "../escape"
	bad, _ := json.Marshal(manifest)
	if err := os.WriteFile(path, bad, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := service.Show(snapshot.Manifest.ID); err == nil || !strings.Contains(err.Error(), "unsafe locator") {
		t.Fatalf("expected traversal rejection, got %v", err)
	}

	manifest.Entries[0].Locator = filepath.ToSlash(filepath.Join(".claude", "CLAUDE.md"))
	manifest.Version = 99
	bad, _ = json.Marshal(manifest)
	if err := os.WriteFile(path, bad, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := service.Show(snapshot.Manifest.ID); err == nil || !strings.Contains(err.Error(), "unsupported schema version") {
		t.Fatalf("expected version rejection, got %v", err)
	}
}

func TestStorePermissionsAndIgnoresStaging(t *testing.T) {
	service, home := testService(t)
	writeTestFile(t, filepath.Join(home, ".claude", "CLAUDE.md"), "one\n")
	snapshot, err := service.Create(CreateOptions{Scope: ScopeUser, Agents: []string{"claude"}})
	if err != nil {
		t.Fatal(err)
	}
	for _, path := range []string{service.root, filepath.Join(service.root, snapshot.Manifest.ID)} {
		info, err := os.Stat(path)
		if err != nil {
			t.Fatal(err)
		}
		if info.Mode().Perm()&0o077 != 0 {
			t.Fatalf("directory %s is too permissive: %o", path, info.Mode().Perm())
		}
	}
	manifestInfo, err := os.Stat(filepath.Join(service.root, snapshot.Manifest.ID, manifestFilename))
	if err != nil {
		t.Fatal(err)
	}
	if manifestInfo.Mode().Perm()&0o077 != 0 {
		t.Fatalf("manifest is too permissive: %o", manifestInfo.Mode().Perm())
	}
	if err := os.Mkdir(filepath.Join(service.root, ".staging-dead"), 0o700); err != nil {
		t.Fatal(err)
	}
	list, err := service.List()
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 1 {
		t.Fatalf("staging directory was listed: %#v", list)
	}
}

func TestParseScope(t *testing.T) {
	if scope, err := ParseScope(""); err != nil || scope != ScopeUser {
		t.Fatalf("default scope = %q, %v", scope, err)
	}
	if _, err := ParseScope("invalid"); err == nil {
		t.Fatal("expected invalid scope error")
	}
}

func TestReadTargetMissing(t *testing.T) {
	token, data, err := readTarget(filepath.Join(t.TempDir(), "missing"))
	if err != nil || token.State != StateAbsent || data != nil {
		t.Fatalf("unexpected missing state: %#v %q %v", token, data, err)
	}
}

func TestExclusiveStoreLock(t *testing.T) {
	service, _ := testService(t)
	unlock, err := service.lock()
	if err != nil {
		t.Fatal(err)
	}
	defer unlock()
	if _, err := service.lock(); err == nil || !strings.Contains(err.Error(), "in progress") {
		t.Fatalf("expected lock contention, got %v", err)
	}
}

func TestWriteObjectRejectsWrongDigest(t *testing.T) {
	if err := writeObject(t.TempDir(), strings.Repeat("0", 64), []byte("x")); err == nil {
		t.Fatal("expected digest mismatch")
	}
}

func TestStoreReportsMissingManifest(t *testing.T) {
	service, _ := testService(t)
	if err := os.MkdirAll(filepath.Join(service.root, "snapshot-bad"), 0o700); err != nil {
		t.Fatal(err)
	}
	_, err := service.List()
	if err == nil || !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("expected missing manifest error, got %v", err)
	}
}

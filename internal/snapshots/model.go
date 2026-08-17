// Package snapshots captures, compares, and restores coding-agent instruction state.
package snapshots

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const SchemaVersion = 1

type Scope string

const (
	ScopeUser    Scope = "user"
	ScopeProject Scope = "project"
	ScopeAll     Scope = "all"
)

type EntryState string

const (
	StatePresent EntryState = "present"
	StateAbsent  EntryState = "absent"
)

type NodeType string

const (
	NodeRegular NodeType = "regular"
	NodeSymlink NodeType = "symlink"
)

type Selection struct {
	Scope       Scope    `json:"scope"`
	Agents      []string `json:"agents"`
	ProjectRoot string   `json:"projectRoot,omitempty"`
}

type Manifest struct {
	Version   int       `json:"version"`
	ID        string    `json:"id"`
	Name      string    `json:"name,omitempty"`
	CreatedAt time.Time `json:"createdAt"`
	Selection Selection `json:"selection"`
	Entries   []Entry   `json:"entries"`
}

type Entry struct {
	Owners        []string   `json:"owners"`
	Kind          string     `json:"kind"`
	Scope         Scope      `json:"scope"`
	Locator       string     `json:"locator"`
	CapturedPath  string     `json:"capturedPath"`
	State         EntryState `json:"state"`
	NodeType      NodeType   `json:"nodeType,omitempty"`
	SymlinkTarget string     `json:"symlinkTarget,omitempty"`
	Digest        string     `json:"digest,omitempty"`
	Size          int64      `json:"size,omitempty"`
	Mode          uint32     `json:"mode,omitempty"`
}

type CreateOptions struct {
	Name       string
	Scope      Scope
	Agents     []string
	ProjectDir string
}

type ResolveOptions struct {
	ProjectDir string
}

type Snapshot struct {
	Manifest  Manifest `json:"manifest"`
	Integrity string   `json:"integrity"`
}

type DriftStatus string

const (
	DriftUnchanged   DriftStatus = "unchanged"
	DriftAdded       DriftStatus = "added"
	DriftMissing     DriftStatus = "missing"
	DriftChanged     DriftStatus = "changed"
	DriftUnreadable  DriftStatus = "unreadable"
	DriftUnsupported DriftStatus = "unsupported"
)

type DriftResult struct {
	SnapshotID string       `json:"snapshotId"`
	Entries    []DriftEntry `json:"entries"`
	Summary    DriftSummary `json:"summary"`
}

type DriftEntry struct {
	Owners         []string    `json:"owners"`
	Scope          Scope       `json:"scope"`
	Locator        string      `json:"locator"`
	Path           string      `json:"path"`
	Status         DriftStatus `json:"status"`
	SnapshotDigest string      `json:"snapshotDigest,omitempty"`
	CurrentDigest  string      `json:"currentDigest,omitempty"`
	SnapshotSize   int64       `json:"snapshotSize,omitempty"`
	CurrentSize    int64       `json:"currentSize,omitempty"`
	TextDiff       string      `json:"textDiff,omitempty"`
	Error          string      `json:"error,omitempty"`
}

type DriftSummary struct {
	Unchanged   int `json:"unchanged"`
	Added       int `json:"added"`
	Missing     int `json:"missing"`
	Changed     int `json:"changed"`
	Unreadable  int `json:"unreadable"`
	Unsupported int `json:"unsupported"`
}

func (r DriftResult) HasDrift() bool {
	return r.Summary.Added+r.Summary.Missing+r.Summary.Changed+r.Summary.Unreadable+r.Summary.Unsupported > 0
}

type RestoreActionType string

const (
	RestoreReplace       RestoreActionType = "replace"
	RestoreRemove        RestoreActionType = "remove"
	RestorePreserveExtra RestoreActionType = "preserve-extra"
	RestoreUnchanged     RestoreActionType = "unchanged"
)

type RestorePlan struct {
	SnapshotID        string          `json:"snapshotId"`
	Exact             bool            `json:"exact"`
	Actions           []RestoreAction `json:"actions"`
	executable        []restoreAction
	planned           bool
	plannedSnapshotID string
	plannedExact      bool
}

type RestoreAction struct {
	Owners       []string          `json:"owners"`
	Scope        Scope             `json:"scope"`
	Locator      string            `json:"locator"`
	Path         string            `json:"path"`
	Type         RestoreActionType `json:"type"`
	ReplacesLink bool              `json:"replacesLink,omitempty"`
}

type restoreAction struct {
	view     RestoreAction
	expected stateToken
	entry    Entry
}

func (p RestorePlan) ChangeCount() int {
	n := 0
	for _, action := range p.Actions {
		if action.Type == RestoreReplace || action.Type == RestoreRemove {
			n++
		}
	}
	return n
}

type stateToken struct {
	State      EntryState `json:"state"`
	NodeType   NodeType   `json:"nodeType,omitempty"`
	Digest     string     `json:"digest,omitempty"`
	Size       int64      `json:"size,omitempty"`
	Mode       uint32     `json:"mode,omitempty"`
	LinkTarget string     `json:"linkTarget,omitempty"`
}

type RecoveryManifest struct {
	Version   int             `json:"version"`
	ID        string          `json:"id"`
	CreatedAt time.Time       `json:"createdAt"`
	Entries   []RecoveryEntry `json:"entries"`
}

type RecoveryEntry struct {
	Path  string     `json:"path"`
	State stateToken `json:"state"`
}

type RestoreJournal struct {
	Version      int             `json:"version"`
	ID           string          `json:"id"`
	SnapshotID   string          `json:"snapshotId"`
	RecoveryPath string          `json:"recoveryPath"`
	CreatedAt    time.Time       `json:"createdAt"`
	Current      int             `json:"current"`
	Applying     bool            `json:"applying"`
	Actions      []journalAction `json:"actions"`
	Completed    bool            `json:"completed"`
}

type journalAction struct {
	Path string     `json:"path"`
	Post stateToken `json:"post"`
}

func ParseScope(value string) (Scope, error) {
	scope := Scope(strings.ToLower(strings.TrimSpace(value)))
	if scope == "" {
		return ScopeUser, nil
	}
	switch scope {
	case ScopeUser, ScopeProject, ScopeAll:
		return scope, nil
	default:
		return "", fmt.Errorf("snapshots: unsupported scope %q (want user, project, or all)", value)
	}
}

func validateName(name string) error {
	if name == "" {
		return nil
	}
	if len(name) > 128 {
		return errors.New("snapshots: name must be at most 128 bytes")
	}
	if name == "." || name == ".." || strings.ContainsAny(name, "/\\\x00\r\n") {
		return fmt.Errorf("snapshots: invalid name %q", name)
	}
	for _, r := range name {
		if r < 0x20 || r == 0x7f {
			return fmt.Errorf("snapshots: invalid name %q", name)
		}
	}
	return nil
}

func digestBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func validDigest(value string) bool {
	if len(value) != sha256.Size*2 {
		return false
	}
	_, err := hex.DecodeString(value)
	return err == nil && value == strings.ToLower(value)
}

func sortManifest(manifest *Manifest) {
	sort.Strings(manifest.Selection.Agents)
	for i := range manifest.Entries {
		sort.Strings(manifest.Entries[i].Owners)
	}
	sort.Slice(manifest.Entries, func(i, j int) bool {
		a, b := manifest.Entries[i], manifest.Entries[j]
		if a.Scope != b.Scope {
			return a.Scope < b.Scope
		}
		if a.Locator != b.Locator {
			return a.Locator < b.Locator
		}
		return strings.Join(a.Owners, "\x00") < strings.Join(b.Owners, "\x00")
	})
}

func validateRelativeLocator(locator string) error {
	if locator == "" || strings.ContainsRune(locator, 0) || filepath.IsAbs(filepath.FromSlash(locator)) {
		return fmt.Errorf("snapshots: unsafe locator %q", locator)
	}
	clean := filepath.Clean(filepath.FromSlash(locator))
	if clean == "." || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return fmt.Errorf("snapshots: unsafe locator %q", locator)
	}
	if filepath.ToSlash(clean) != locator {
		return fmt.Errorf("snapshots: non-canonical locator %q", locator)
	}
	return nil
}

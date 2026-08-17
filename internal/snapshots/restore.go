package snapshots

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/chat2anyllm/code-agent-manager/internal/pathutil"
)

const (
	recoveryDirectory = "recovery"
	journalFilename   = "restore-journal.json"
)

func (s *Service) PlanRestore(reference string, options ResolveOptions, exact bool) (RestorePlan, error) {
	if err := s.requireNoPendingRecovery(); err != nil {
		return RestorePlan{}, err
	}
	snapshot, err := s.Show(reference)
	if err != nil {
		return RestorePlan{}, err
	}
	resolved, err := resolveEntries(snapshot.Manifest, options)
	if err != nil {
		return RestorePlan{}, err
	}
	plan := RestorePlan{
		SnapshotID: snapshot.Manifest.ID, Exact: exact, Actions: make([]RestoreAction, 0, len(resolved)),
		planned: true, plannedSnapshotID: snapshot.Manifest.ID, plannedExact: exact,
	}
	for _, item := range resolved {
		token, _, err := readTarget(item.path)
		if err != nil {
			return RestorePlan{}, fmt.Errorf("snapshots: inspect restore target %q: %w", item.path, err)
		}
		action := RestoreAction{
			Owners:       append([]string(nil), item.entry.Owners...),
			Scope:        item.entry.Scope,
			Locator:      item.entry.Locator,
			Path:         item.path,
			ReplacesLink: token.NodeType == NodeSymlink,
		}
		switch {
		case item.entry.State == StatePresent && token.State == StatePresent && item.entry.Digest == token.Digest && item.entry.Size == token.Size:
			action.Type = RestoreUnchanged
		case item.entry.State == StatePresent:
			action.Type = RestoreReplace
		case token.State == StateAbsent:
			action.Type = RestoreUnchanged
		case exact:
			action.Type = RestoreRemove
		default:
			action.Type = RestorePreserveExtra
		}
		if action.Type == RestoreReplace || action.Type == RestoreRemove {
			if err := validateRestoreDestination(action); err != nil {
				return RestorePlan{}, err
			}
		}
		plan.Actions = append(plan.Actions, action)
		plan.executable = append(plan.executable, restoreAction{view: action, expected: token, entry: item.entry})
	}
	return plan, nil
}

func validateRestoreDestination(action RestoreAction) error {
	var root string
	switch action.Scope {
	case ScopeUser:
		root = pathutil.Home()
	case ScopeProject:
		root = strings.TrimSuffix(action.Path, filepath.FromSlash(action.Locator))
		root = filepath.Clean(root)
	default:
		return fmt.Errorf("snapshots: invalid restore scope %q", action.Scope)
	}
	if err := ensureNoSymlinkAncestors(root, action.Path); err != nil {
		return err
	}
	parent := filepath.Dir(action.Path)
	for current := parent; ; current = filepath.Dir(current) {
		info, err := os.Lstat(current)
		if err == nil {
			if !info.IsDir() {
				return fmt.Errorf("snapshots: restore parent %q is not a directory", current)
			}
			break
		}
		if !errors.Is(err, fs.ErrNotExist) {
			return err
		}
		next := filepath.Dir(current)
		if next == current {
			return fmt.Errorf("snapshots: cannot find existing parent for %q", action.Path)
		}
	}
	return nil
}

func (s *Service) ApplyRestore(plan RestorePlan) error {
	if !plan.planned || plan.SnapshotID != plan.plannedSnapshotID || plan.Exact != plan.plannedExact || len(plan.executable) != len(plan.Actions) {
		return errors.New("snapshots: restore plan is not executable; create a fresh plan")
	}
	for i := range plan.executable {
		if !sameRestoreAction(plan.executable[i].view, plan.Actions[i]) {
			return errors.New("snapshots: restore plan was modified after planning")
		}
	}
	if plan.ChangeCount() == 0 {
		return nil
	}
	unlock, err := s.lock()
	if err != nil {
		return err
	}
	defer unlock()
	if err := s.recoverLocked(); err != nil {
		return err
	}
	snapshot, err := s.loadByID(plan.SnapshotID, true)
	if err != nil {
		return err
	}

	actions := make([]restoreAction, 0, plan.ChangeCount())
	for i, action := range plan.executable {
		if !sameRestoreAction(action.view, plan.Actions[i]) {
			return errors.New("snapshots: restore plan was modified after planning")
		}
		if action.view.Type != RestoreReplace && action.view.Type != RestoreRemove {
			continue
		}
		current, _, err := readTarget(action.view.Path)
		if err != nil {
			return fmt.Errorf("snapshots: recheck %q: %w", action.view.Path, err)
		}
		if !sameStateToken(current, action.expected) {
			return fmt.Errorf("snapshots: restore target %q changed after planning", action.view.Path)
		}
		if err := validateRestoreDestination(action.view); err != nil {
			return err
		}
		actions = append(actions, action)
	}

	recovery, recoveryPath, err := s.createRecovery(actions)
	if err != nil {
		return err
	}
	journal := RestoreJournal{
		Version:      SchemaVersion,
		ID:           recovery.ID,
		SnapshotID:   snapshot.Manifest.ID,
		RecoveryPath: recoveryPath,
		CreatedAt:    s.now().UTC(),
		Current:      0,
		Actions:      make([]journalAction, len(actions)),
	}
	for i, action := range actions {
		journal.Actions[i] = journalAction{Path: action.view.Path, Post: desiredState(action)}
	}
	if err := s.writeJournal(journal); err != nil {
		return err
	}

	for i, action := range actions {
		journal.Current = i
		journal.Applying = true
		if err := s.writeJournal(journal); err != nil {
			return s.rollbackAfterError(journal, fmt.Errorf("snapshots: record restore progress: %w", err))
		}
		if err := s.applyAction(snapshot.Manifest.ID, action); err != nil {
			return s.rollbackAfterError(journal, fmt.Errorf("snapshots: apply %s to %q: %w", action.view.Type, action.view.Path, err))
		}
		journal.Current = i + 1
		journal.Applying = false
		if err := s.writeJournal(journal); err != nil {
			return s.rollbackAfterError(journal, fmt.Errorf("snapshots: record completed restore action: %w", err))
		}
	}
	journal.Completed = true
	if err := s.writeJournal(journal); err != nil {
		return s.rollbackAfterError(journal, fmt.Errorf("snapshots: complete restore journal: %w", err))
	}
	if err := s.ops.remove(filepath.Join(s.root, journalFilename)); err != nil && !errors.Is(err, fs.ErrNotExist) {
		return fmt.Errorf("snapshots: remove completed restore journal: %w", err)
	}
	return syncDirectory(s.root)
}

func (s *Service) Recover() error {
	unlock, err := s.lock()
	if err != nil {
		return err
	}
	defer unlock()
	return s.recoverLocked()
}

func (s *Service) recoverLocked() error {
	journal, err := s.readJournal()
	if errors.Is(err, fs.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	if journal.Completed {
		if err := os.Remove(filepath.Join(s.root, journalFilename)); err != nil && !errors.Is(err, fs.ErrNotExist) {
			return err
		}
		return nil
	}
	if err := s.rollback(journal); err != nil {
		return fmt.Errorf("snapshots: unfinished restore %s could not be recovered; recovery data retained at %s: %w", journal.ID, journal.RecoveryPath, err)
	}
	return nil
}

func (s *Service) createRecovery(actions []restoreAction) (RecoveryManifest, string, error) {
	id, err := s.newID("restore")
	if err != nil {
		return RecoveryManifest{}, "", err
	}
	path := filepath.Join(s.root, recoveryDirectory, id)
	if err := os.MkdirAll(path, 0o700); err != nil {
		return RecoveryManifest{}, "", err
	}
	recovery := RecoveryManifest{Version: SchemaVersion, ID: id, CreatedAt: s.now().UTC(), Entries: make([]RecoveryEntry, 0, len(actions))}
	for _, action := range actions {
		token, data, err := readTarget(action.view.Path)
		if err != nil {
			return RecoveryManifest{}, path, err
		}
		if token.State == StatePresent {
			if err := writeObject(path, token.Digest, data); err != nil {
				return RecoveryManifest{}, path, err
			}
		}
		recovery.Entries = append(recovery.Entries, RecoveryEntry{Path: action.view.Path, State: token})
	}
	if err := writeJSONAtomic(filepath.Join(path, manifestFilename), recovery, 0o600); err != nil {
		return RecoveryManifest{}, path, err
	}
	if err := syncTree(path); err != nil {
		return RecoveryManifest{}, path, err
	}
	return recovery, path, nil
}

func desiredState(action restoreAction) stateToken {
	if action.view.Type == RestoreRemove {
		return stateToken{State: StateAbsent}
	}
	return stateToken{State: StatePresent, NodeType: NodeRegular, Digest: action.entry.Digest, Size: action.entry.Size, Mode: 0o600}
}

func (s *Service) applyAction(snapshotID string, action restoreAction) error {
	switch action.view.Type {
	case RestoreReplace:
		data, err := s.readObject(snapshotID, action.entry.Digest)
		if err != nil {
			return err
		}
		return s.replacePath(action.view.Path, data)
	case RestoreRemove:
		if err := s.ops.remove(action.view.Path); err != nil && !errors.Is(err, fs.ErrNotExist) {
			return err
		}
		return syncDirectory(filepath.Dir(action.view.Path))
	default:
		return fmt.Errorf("unsupported action %q", action.view.Type)
	}
}

func (s *Service) replacePath(path string, data []byte) error {
	parent := filepath.Dir(path)
	if err := os.MkdirAll(parent, 0o700); err != nil {
		return err
	}
	temp, err := os.CreateTemp(parent, ".cam-restore-*")
	if err != nil {
		return err
	}
	tempPath := temp.Name()
	ok := false
	defer func() {
		_ = temp.Close()
		if !ok {
			_ = os.Remove(tempPath)
		}
	}()
	if err := temp.Chmod(0o600); err != nil {
		return err
	}
	if _, err := temp.Write(data); err != nil {
		return err
	}
	if err := temp.Sync(); err != nil {
		return err
	}
	if err := temp.Close(); err != nil {
		return err
	}
	if err := s.ops.rename(tempPath, path); err != nil {
		return err
	}
	ok = true
	return syncDirectory(parent)
}

func (s *Service) rollbackAfterError(journal RestoreJournal, cause error) error {
	if err := s.rollback(journal); err != nil {
		return fmt.Errorf("%w; rollback failed and recovery data was retained at %s: %v", cause, journal.RecoveryPath, err)
	}
	return fmt.Errorf("%w; applied changes were rolled back", cause)
}

func (s *Service) rollback(journal RestoreJournal) error {
	recovery, err := s.readRecoveryManifest(journal.RecoveryPath, journal.ID)
	if err != nil {
		return err
	}
	if len(recovery.Entries) != len(journal.Actions) {
		return errors.New("snapshots: recovery entry count does not match restore journal")
	}
	for i := range recovery.Entries {
		if recovery.Entries[i].Path != journal.Actions[i].Path {
			return errors.New("snapshots: recovery destinations do not match restore journal")
		}
	}
	limit := min(journal.Current, len(recovery.Entries))
	if journal.Applying {
		if journal.Current >= len(recovery.Entries) || journal.Current >= len(journal.Actions) {
			return errors.New("snapshots: invalid in-progress restore journal")
		}
		live, _, readErr := readTarget(recovery.Entries[journal.Current].Path)
		if readErr != nil {
			return readErr
		}
		pre := recovery.Entries[journal.Current].State
		post := journal.Actions[journal.Current].Post
		switch {
		case sameStateToken(live, pre):
		case sameStateToken(live, post):
			limit = journal.Current + 1
		default:
			return fmt.Errorf("snapshots: restore target %q changed during interrupted action; refusing automatic recovery", recovery.Entries[journal.Current].Path)
		}
	}
	var rollbackErrors []error
	for i := limit - 1; i >= 0; i-- {
		entry := recovery.Entries[i]
		live, _, readErr := readTarget(entry.Path)
		if readErr != nil {
			rollbackErrors = append(rollbackErrors, fmt.Errorf("inspect %q before rollback: %w", entry.Path, readErr))
			continue
		}
		if sameStateToken(live, entry.State) {
			continue
		}
		if i >= len(journal.Actions) || !sameStateToken(live, journal.Actions[i].Post) {
			rollbackErrors = append(rollbackErrors, fmt.Errorf("restore target %q changed after restore; refusing automatic rollback", entry.Path))
			continue
		}
		if entry.State.State == StateAbsent {
			if err := s.ops.remove(entry.Path); err != nil && !errors.Is(err, fs.ErrNotExist) {
				rollbackErrors = append(rollbackErrors, fmt.Errorf("remove %q: %w", entry.Path, err))
				continue
			}
			if err := syncDirectory(filepath.Dir(entry.Path)); err != nil {
				rollbackErrors = append(rollbackErrors, fmt.Errorf("sync rollback removal %q: %w", entry.Path, err))
			}
			continue
		}
		data, err := readRecoveryObject(journal.RecoveryPath, entry.State.Digest)
		if err != nil {
			rollbackErrors = append(rollbackErrors, err)
			continue
		}
		if err := s.restorePreimage(entry.Path, entry.State, data); err != nil {
			rollbackErrors = append(rollbackErrors, fmt.Errorf("restore %q: %w", entry.Path, err))
		}
	}
	if len(rollbackErrors) > 0 {
		return errors.Join(rollbackErrors...)
	}
	if err := os.Remove(filepath.Join(s.root, journalFilename)); err != nil && !errors.Is(err, fs.ErrNotExist) {
		return err
	}
	return syncDirectory(s.root)
}

func (s *Service) restorePreimage(path string, token stateToken, data []byte) error {
	if token.NodeType == NodeSymlink {
		parent := filepath.Dir(path)
		if err := os.MkdirAll(parent, 0o700); err != nil {
			return err
		}
		temp := filepath.Join(parent, fmt.Sprintf(".cam-restore-link-%d", os.Getpid()))
		_ = os.Remove(temp)
		if err := os.Symlink(token.LinkTarget, temp); err != nil {
			return err
		}
		if err := s.ops.rename(temp, path); err != nil {
			_ = os.Remove(temp)
			return err
		}
		return syncDirectory(parent)
	}
	if err := s.replacePath(path, data); err != nil {
		return err
	}
	mode := fs.FileMode(token.Mode)
	if mode == 0 {
		mode = 0o600
	}
	if err := os.Chmod(path, mode); err != nil {
		return err
	}
	return syncDirectory(filepath.Dir(path))
}

func (s *Service) readRecoveryManifest(path, expectedID string) (RecoveryManifest, error) {
	expectedRoot := filepath.Join(s.root, recoveryDirectory)
	cleanPath, err := filepath.Abs(path)
	if err != nil {
		return RecoveryManifest{}, err
	}
	cleanRoot, err := filepath.Abs(expectedRoot)
	if err != nil {
		return RecoveryManifest{}, err
	}
	relative, err := filepath.Rel(cleanRoot, cleanPath)
	if err != nil || relative != expectedID || filepath.Base(cleanPath) != expectedID {
		return RecoveryManifest{}, errors.New("snapshots: recovery path escapes the snapshot store")
	}
	data, err := os.ReadFile(filepath.Join(cleanPath, manifestFilename))
	if err != nil {
		return RecoveryManifest{}, err
	}
	var manifest RecoveryManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return RecoveryManifest{}, err
	}
	if manifest.Version != SchemaVersion || manifest.ID != expectedID || filepath.Base(cleanPath) != manifest.ID {
		return RecoveryManifest{}, errors.New("snapshots: invalid recovery manifest")
	}
	for i, entry := range manifest.Entries {
		if filepath.Clean(entry.Path) != entry.Path || !filepath.IsAbs(entry.Path) {
			return RecoveryManifest{}, fmt.Errorf("snapshots: invalid recovery path at entry %d", i)
		}
		if entry.State.State == StatePresent && (!validDigest(entry.State.Digest) || entry.State.Size < 0) {
			return RecoveryManifest{}, fmt.Errorf("snapshots: invalid recovery state at entry %d", i)
		}
		if entry.State.State != StatePresent && entry.State.State != StateAbsent {
			return RecoveryManifest{}, fmt.Errorf("snapshots: invalid recovery state at entry %d", i)
		}
	}
	return manifest, nil
}

func readRecoveryObject(root, digest string) ([]byte, error) {
	if !validDigest(digest) {
		return nil, fmt.Errorf("snapshots: invalid recovery digest %q", digest)
	}
	data, err := os.ReadFile(filepath.Join(root, objectsDirectory, "sha256", digest))
	if err != nil {
		return nil, err
	}
	if digestBytes(data) != digest {
		return nil, fmt.Errorf("snapshots: recovery object %s failed integrity verification", digest)
	}
	return data, nil
}

func (s *Service) writeJournal(journal RestoreJournal) error {
	return writeJSONAtomic(filepath.Join(s.root, journalFilename), journal, 0o600)
}

func (s *Service) readJournal() (RestoreJournal, error) {
	data, err := os.ReadFile(filepath.Join(s.root, journalFilename))
	if err != nil {
		return RestoreJournal{}, err
	}
	var journal RestoreJournal
	if err := json.Unmarshal(data, &journal); err != nil {
		return RestoreJournal{}, fmt.Errorf("snapshots: decode restore journal: %w", err)
	}
	if journal.Version != SchemaVersion || journal.ID == "" || journal.RecoveryPath == "" || journal.Current < 0 || journal.Current > len(journal.Actions) {
		return RestoreJournal{}, errors.New("snapshots: invalid restore journal")
	}
	if journal.Applying && journal.Current >= len(journal.Actions) {
		return RestoreJournal{}, errors.New("snapshots: invalid in-progress restore journal")
	}
	for _, action := range journal.Actions {
		if !filepath.IsAbs(action.Path) || filepath.Clean(action.Path) != action.Path || (action.Post.State != StatePresent && action.Post.State != StateAbsent) {
			return RestoreJournal{}, errors.New("snapshots: invalid restore journal action")
		}
	}
	return journal, nil
}

func sameRestoreAction(a, b RestoreAction) bool {
	return a.Scope == b.Scope && a.Locator == b.Locator && a.Path == b.Path && a.Type == b.Type &&
		a.ReplacesLink == b.ReplacesLink && strings.Join(a.Owners, "\x00") == strings.Join(b.Owners, "\x00")
}

func sameStateToken(a, b stateToken) bool {
	return a.State == b.State && a.NodeType == b.NodeType && a.Digest == b.Digest && a.Size == b.Size && a.LinkTarget == b.LinkTarget
}

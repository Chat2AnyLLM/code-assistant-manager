package snapshots

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/chat2anyllm/code-agent-manager/internal/pathutil"
)

const (
	manifestFilename     = "manifest.json"
	objectsDirectory     = "objects"
	staleLockGracePeriod = 5 * time.Second
)

type Service struct {
	root   string
	now    func() time.Time
	random io.Reader
	ops    fileOps
}

type fileOps struct {
	rename func(string, string) error
	remove func(string) error
}

func NewService() *Service {
	return NewServiceAt(filepath.Join(pathutil.ConfigDir(), "snapshots"))
}

func NewServiceAt(root string) *Service {
	return &Service{
		root:   root,
		now:    time.Now,
		random: rand.Reader,
		ops: fileOps{
			rename: os.Rename,
			remove: os.Remove,
		},
	}
}

func (s *Service) Root() string {
	return s.root
}

func (s *Service) Create(options CreateOptions) (Snapshot, error) {
	unlock, err := s.lock()
	if err != nil {
		return Snapshot{}, err
	}
	defer unlock()
	if err := s.recoverLocked(); err != nil {
		return Snapshot{}, err
	}
	targets, selection, err := discover(options)
	if err != nil {
		return Snapshot{}, err
	}

	id, err := s.newID("snapshot")
	if err != nil {
		return Snapshot{}, err
	}
	manifest := Manifest{
		Version:   SchemaVersion,
		ID:        id,
		Name:      options.Name,
		CreatedAt: s.now().UTC(),
		Selection: selection,
		Entries:   make([]Entry, len(targets)),
	}
	for i := range targets {
		manifest.Entries[i] = targets[i].entry
	}
	sortManifest(&manifest)

	if err := os.MkdirAll(s.root, 0o700); err != nil {
		return Snapshot{}, fmt.Errorf("snapshots: create store: %w", err)
	}
	if err := ensurePrivateDirectory(s.root); err != nil {
		return Snapshot{}, err
	}
	stage := filepath.Join(s.root, ".staging-"+id)
	if err := os.Mkdir(stage, 0o700); err != nil {
		return Snapshot{}, fmt.Errorf("snapshots: create staging directory: %w", err)
	}
	published := false
	defer func() {
		if !published {
			_ = os.RemoveAll(stage)
		}
	}()

	for _, target := range targets {
		if target.entry.State != StatePresent {
			continue
		}
		if err := writeObject(stage, target.entry.Digest, target.data); err != nil {
			return Snapshot{}, err
		}
	}
	if err := writeJSONAtomic(filepath.Join(stage, manifestFilename), manifest, 0o600); err != nil {
		return Snapshot{}, fmt.Errorf("snapshots: write manifest: %w", err)
	}
	if err := syncTree(stage); err != nil {
		return Snapshot{}, err
	}
	finalPath := filepath.Join(s.root, id)
	if err := s.ops.rename(stage, finalPath); err != nil {
		return Snapshot{}, fmt.Errorf("snapshots: publish %s: %w", id, err)
	}
	published = true
	if err := syncDirectory(s.root); err != nil {
		return Snapshot{}, err
	}
	return Snapshot{Manifest: manifest, Integrity: "verified"}, nil
}

func (s *Service) List() ([]Snapshot, error) {
	if err := s.requireNoPendingRecovery(); err != nil {
		return nil, err
	}
	entries, err := os.ReadDir(s.root)
	if errors.Is(err, fs.ErrNotExist) {
		return []Snapshot{}, nil
	}
	if err != nil {
		return nil, fmt.Errorf("snapshots: list store: %w", err)
	}
	result := make([]Snapshot, 0)
	for _, entry := range entries {
		if !entry.IsDir() || !strings.HasPrefix(entry.Name(), "snapshot-") {
			continue
		}
		snapshot, err := s.loadByID(entry.Name(), true)
		if err != nil {
			return nil, err
		}
		result = append(result, snapshot)
	}
	sort.Slice(result, func(i, j int) bool {
		if result[i].Manifest.CreatedAt.Equal(result[j].Manifest.CreatedAt) {
			return result[i].Manifest.ID > result[j].Manifest.ID
		}
		return result[i].Manifest.CreatedAt.After(result[j].Manifest.CreatedAt)
	})
	return result, nil
}

func (s *Service) Show(reference string) (Snapshot, error) {
	if err := s.requireNoPendingRecovery(); err != nil {
		return Snapshot{}, err
	}
	id, err := s.resolveReference(reference)
	if err != nil {
		return Snapshot{}, err
	}
	return s.loadByID(id, true)
}

func (s *Service) resolveReference(reference string) (string, error) {
	reference = strings.TrimSpace(reference)
	if reference == "" {
		return "", errors.New("snapshots: snapshot reference is required")
	}
	entries, err := os.ReadDir(s.root)
	if errors.Is(err, fs.ErrNotExist) {
		return "", fmt.Errorf("snapshots: snapshot %q not found", reference)
	}
	if err != nil {
		return "", fmt.Errorf("snapshots: list store: %w", err)
	}
	var exactID string
	var prefixes, names []string
	for _, entry := range entries {
		if !entry.IsDir() || !strings.HasPrefix(entry.Name(), "snapshot-") {
			continue
		}
		id := entry.Name()
		manifest, err := s.readManifest(id)
		if err != nil {
			return "", err
		}
		if id == reference {
			exactID = id
		}
		if strings.HasPrefix(id, reference) {
			prefixes = append(prefixes, id)
		}
		if manifest.Name == reference {
			names = append(names, id)
		}
	}
	if exactID != "" {
		return exactID, nil
	}
	matches := prefixes
	if len(matches) == 0 {
		matches = names
	}
	if len(matches) == 1 {
		return matches[0], nil
	}
	if len(matches) > 1 {
		sort.Strings(matches)
		return "", fmt.Errorf("snapshots: reference %q is ambiguous: %s", reference, strings.Join(matches, ", "))
	}
	return "", fmt.Errorf("snapshots: snapshot %q not found", reference)
}

func (s *Service) loadByID(id string, verifyObjects bool) (Snapshot, error) {
	manifest, err := s.readManifest(id)
	if err != nil {
		return Snapshot{}, err
	}
	if verifyObjects {
		if err := s.verifyObjects(id, manifest); err != nil {
			return Snapshot{}, err
		}
	}
	return Snapshot{Manifest: manifest, Integrity: "verified"}, nil
}

func (s *Service) readManifest(id string) (Manifest, error) {
	if filepath.Base(id) != id || !strings.HasPrefix(id, "snapshot-") {
		return Manifest{}, fmt.Errorf("snapshots: invalid snapshot id %q", id)
	}
	path := filepath.Join(s.root, id, manifestFilename)
	data, err := os.ReadFile(path)
	if err != nil {
		return Manifest{}, fmt.Errorf("snapshots: read manifest %s: %w", id, err)
	}
	var manifest Manifest
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&manifest); err != nil {
		return Manifest{}, fmt.Errorf("snapshots: decode manifest %s: %w", id, err)
	}
	if decoder.Decode(&struct{}{}) != io.EOF {
		return Manifest{}, fmt.Errorf("snapshots: manifest %s contains trailing data", id)
	}
	if err := validateManifest(manifest, id); err != nil {
		return Manifest{}, err
	}
	return manifest, nil
}

func validateManifest(manifest Manifest, directoryID string) error {
	if manifest.Version != SchemaVersion {
		return fmt.Errorf("snapshots: snapshot %s uses unsupported schema version %d", directoryID, manifest.Version)
	}
	if manifest.ID != directoryID {
		return fmt.Errorf("snapshots: manifest id %q does not match directory %q", manifest.ID, directoryID)
	}
	if manifest.CreatedAt.IsZero() || manifest.CreatedAt.Location() != time.UTC {
		return fmt.Errorf("snapshots: manifest %s has invalid creation time", directoryID)
	}
	if err := validateName(manifest.Name); err != nil {
		return err
	}
	if manifest.Selection.Scope != ScopeUser && manifest.Selection.Scope != ScopeProject && manifest.Selection.Scope != ScopeAll {
		return fmt.Errorf("snapshots: manifest %s has invalid selection scope %q", directoryID, manifest.Selection.Scope)
	}
	if (manifest.Selection.Scope == ScopeProject || manifest.Selection.Scope == ScopeAll) && manifest.Selection.ProjectRoot == "" {
		return fmt.Errorf("snapshots: manifest %s is missing its captured project root", directoryID)
	}
	if !sort.StringsAreSorted(manifest.Selection.Agents) || hasDuplicateStrings(manifest.Selection.Agents) {
		return fmt.Errorf("snapshots: manifest %s has non-canonical agents", directoryID)
	}
	previous := ""
	for i, entry := range manifest.Entries {
		if err := validateEntry(entry); err != nil {
			return fmt.Errorf("snapshots: manifest %s entry %d: %w", directoryID, i, err)
		}
		key := string(entry.Scope) + "\x00" + entry.Locator + "\x00" + strings.Join(entry.Owners, "\x00")
		if previous != "" && key <= previous {
			return fmt.Errorf("snapshots: manifest %s entries are not strictly ordered", directoryID)
		}
		previous = key
	}
	return nil
}

func validateEntry(entry Entry) error {
	if entry.Kind != "instruction" {
		return fmt.Errorf("unsupported kind %q", entry.Kind)
	}
	if entry.Scope != ScopeUser && entry.Scope != ScopeProject {
		return fmt.Errorf("invalid scope %q", entry.Scope)
	}
	if err := validateRelativeLocator(entry.Locator); err != nil {
		return err
	}
	if len(entry.Owners) == 0 || !sort.StringsAreSorted(entry.Owners) || hasDuplicateStrings(entry.Owners) {
		return errors.New("owners must be non-empty, sorted, and unique")
	}
	for _, owner := range entry.Owners {
		if strings.TrimSpace(owner) != owner || owner == "" || strings.ContainsAny(owner, "/\\\x00") {
			return fmt.Errorf("invalid owner %q", owner)
		}
	}
	switch entry.State {
	case StateAbsent:
		if entry.Digest != "" || entry.Size != 0 || entry.NodeType != "" || entry.SymlinkTarget != "" || entry.Mode != 0 {
			return errors.New("absent entry contains present-file metadata")
		}
	case StatePresent:
		if !validDigest(entry.Digest) || entry.Size < 0 {
			return errors.New("present entry has invalid digest or size")
		}
		if entry.NodeType != NodeRegular && entry.NodeType != NodeSymlink {
			return fmt.Errorf("present entry has invalid node type %q", entry.NodeType)
		}
		if entry.NodeType == NodeRegular && entry.SymlinkTarget != "" {
			return errors.New("regular entry contains symbolic-link metadata")
		}
	default:
		return fmt.Errorf("invalid state %q", entry.State)
	}
	return nil
}

func (s *Service) verifyObjects(id string, manifest Manifest) error {
	verified := make(map[string]int64)
	for _, entry := range manifest.Entries {
		if entry.State != StatePresent {
			continue
		}
		if size, ok := verified[entry.Digest]; ok {
			if size != entry.Size {
				return fmt.Errorf("snapshots: content object %s in %s has inconsistent manifest sizes", entry.Digest, id)
			}
			continue
		}
		data, err := s.readObject(id, entry.Digest)
		if err != nil {
			return err
		}
		if int64(len(data)) != entry.Size || digestBytes(data) != entry.Digest {
			return fmt.Errorf("snapshots: content object %s in %s failed integrity verification", entry.Digest, id)
		}
		verified[entry.Digest] = entry.Size
	}
	return nil
}

func (s *Service) readObject(id, digest string) ([]byte, error) {
	if !validDigest(digest) {
		return nil, fmt.Errorf("snapshots: invalid object digest %q", digest)
	}
	path := filepath.Join(s.root, id, objectsDirectory, "sha256", digest)
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("snapshots: read content object %s: %w", digest, err)
	}
	return data, nil
}

func writeObject(root, digest string, data []byte) error {
	if digestBytes(data) != digest {
		return fmt.Errorf("snapshots: object digest mismatch for %s", digest)
	}
	dir := filepath.Join(root, objectsDirectory, "sha256")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("snapshots: create object directory: %w", err)
	}
	path := filepath.Join(dir, digest)
	if _, err := os.Stat(path); err == nil {
		return nil
	} else if !errors.Is(err, fs.ErrNotExist) {
		return err
	}
	if err := writeFileExclusive(path, data, 0o600); err != nil {
		return fmt.Errorf("snapshots: write content object %s: %w", digest, err)
	}
	return nil
}

func (s *Service) newID(prefix string) (string, error) {
	var suffix [6]byte
	if _, err := io.ReadFull(s.random, suffix[:]); err != nil {
		return "", fmt.Errorf("snapshots: generate id: %w", err)
	}
	return fmt.Sprintf("%s-%s-%s", prefix, s.now().UTC().Format("20060102T150405.000000000Z"), hex.EncodeToString(suffix[:])), nil
}

func hasDuplicateStrings(values []string) bool {
	for i := 1; i < len(values); i++ {
		if values[i] == values[i-1] {
			return true
		}
	}
	return false
}

func ensurePrivateDirectory(path string) error {
	info, err := os.Stat(path)
	if err != nil {
		return fmt.Errorf("snapshots: inspect directory %q: %w", path, err)
	}
	if !info.IsDir() {
		return fmt.Errorf("snapshots: %q is not a directory", path)
	}
	if err := os.Chmod(path, 0o700); err != nil {
		return fmt.Errorf("snapshots: secure directory %q: %w", path, err)
	}
	return nil
}

func writeFileExclusive(path string, data []byte, mode fs.FileMode) error {
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, mode)
	if err != nil {
		return err
	}
	ok := false
	defer func() {
		_ = file.Close()
		if !ok {
			_ = os.Remove(path)
		}
	}()
	if _, err := file.Write(data); err != nil {
		return err
	}
	if err := file.Sync(); err != nil {
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	ok = true
	return nil
}

func writeJSONAtomic(path string, value any, mode fs.FileMode) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	temp, err := os.CreateTemp(dir, ".tmp-*")
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
	if err := temp.Chmod(mode); err != nil {
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
	if err := os.Rename(tempPath, path); err != nil {
		return err
	}
	ok = true
	return syncDirectory(dir)
}

func syncTree(root string) error {
	return filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !entry.IsDir() {
			return nil
		}
		return syncDirectory(path)
	})
}

func syncDirectory(path string) error {
	dir, err := os.Open(path)
	if err != nil {
		return err
	}
	defer dir.Close()
	return dir.Sync()
}

func (s *Service) requireNoPendingRecovery() error {
	journal, err := s.readJournal()
	if errors.Is(err, fs.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	if !journal.Completed {
		return fmt.Errorf("snapshots: restore %s has unfinished recovery at %s; run a mutating snapshot command to recover it", journal.ID, journal.RecoveryPath)
	}
	return nil
}

func (s *Service) lock() (func(), error) {
	if err := os.MkdirAll(s.root, 0o700); err != nil {
		return nil, fmt.Errorf("snapshots: create store: %w", err)
	}
	lockPath := filepath.Join(s.root, ".lock")
	file, err := os.OpenFile(lockPath, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if errors.Is(err, fs.ErrExist) {
		data, readErr := os.ReadFile(lockPath)
		stale := readErr != nil
		if readErr == nil {
			var pid int
			_, scanErr := fmt.Sscanf(string(data), "%d", &pid)
			stale = scanErr != nil || pid <= 0 || !processExists(pid)
		}
		if stale {
			info, statErr := os.Stat(lockPath)
			if statErr == nil && s.now().Sub(info.ModTime()) >= staleLockGracePeriod {
				if removeErr := os.Remove(lockPath); removeErr == nil {
					file, err = os.OpenFile(lockPath, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
				}
			}
		}
	}
	if err != nil {
		if errors.Is(err, fs.ErrExist) {
			return nil, errors.New("snapshots: another mutating snapshot operation is in progress")
		}
		return nil, fmt.Errorf("snapshots: acquire store lock: %w", err)
	}
	_, _ = fmt.Fprintf(file, "%d\n", os.Getpid())
	_ = file.Sync()
	_ = file.Close()
	return func() { _ = os.Remove(lockPath) }, nil
}

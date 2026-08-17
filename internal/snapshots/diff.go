package snapshots

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"unicode/utf8"

	"github.com/chat2anyllm/code-agent-manager/internal/entities"
	"github.com/chat2anyllm/code-agent-manager/internal/pathutil"
)

func (s *Service) Diff(reference string, options ResolveOptions) (DriftResult, error) {
	snapshot, err := s.Show(reference)
	if err != nil {
		return DriftResult{}, err
	}
	resolved, err := resolveEntries(snapshot.Manifest, options)
	if err != nil {
		return DriftResult{}, err
	}
	result := DriftResult{SnapshotID: snapshot.Manifest.ID, Entries: make([]DriftEntry, 0, len(resolved))}
	for _, item := range resolved {
		drift := DriftEntry{
			Owners:         append([]string(nil), item.entry.Owners...),
			Scope:          item.entry.Scope,
			Locator:        item.entry.Locator,
			Path:           item.path,
			SnapshotDigest: item.entry.Digest,
			SnapshotSize:   item.entry.Size,
		}
		token, current, err := readTarget(item.path)
		if err != nil {
			drift.Status = classifyReadError(err)
			drift.Error = err.Error()
			addDriftSummary(&result.Summary, drift.Status)
			result.Entries = append(result.Entries, drift)
			continue
		}
		drift.CurrentDigest = token.Digest
		drift.CurrentSize = token.Size
		switch {
		case item.entry.State == StateAbsent && token.State == StateAbsent:
			drift.Status = DriftUnchanged
		case item.entry.State == StateAbsent && token.State == StatePresent:
			drift.Status = DriftAdded
		case item.entry.State == StatePresent && token.State == StateAbsent:
			drift.Status = DriftMissing
		case item.entry.Digest == token.Digest && item.entry.Size == token.Size:
			drift.Status = DriftUnchanged
		default:
			drift.Status = DriftChanged
			snapshotData, err := s.readObject(snapshot.Manifest.ID, item.entry.Digest)
			if err != nil {
				return DriftResult{}, err
			}
			if textContent(snapshotData) && textContent(current) {
				drift.TextDiff = unifiedDiff(snapshotData, current)
			}
		}
		addDriftSummary(&result.Summary, drift.Status)
		result.Entries = append(result.Entries, drift)
	}
	return result, nil
}

func addDriftSummary(summary *DriftSummary, status DriftStatus) {
	switch status {
	case DriftUnchanged:
		summary.Unchanged++
	case DriftAdded:
		summary.Added++
	case DriftMissing:
		summary.Missing++
	case DriftChanged:
		summary.Changed++
	case DriftUnreadable:
		summary.Unreadable++
	case DriftUnsupported:
		summary.Unsupported++
	}
}

func classifyReadError(err error) DriftStatus {
	if strings.Contains(err.Error(), "unsupported file type") || strings.Contains(err.Error(), "resolves to unsupported") {
		return DriftUnsupported
	}
	return DriftUnreadable
}

type resolvedEntry struct {
	entry Entry
	path  string
}

func resolveEntries(manifest Manifest, options ResolveOptions) ([]resolvedEntry, error) {
	projectRoot := ""
	if manifest.Selection.Scope == ScopeProject || manifest.Selection.Scope == ScopeAll {
		candidate := options.ProjectDir
		if candidate == "" {
			candidate = manifest.Selection.ProjectRoot
			if candidate == "" {
				return nil, errors.New("snapshots: snapshot has project entries; supply --project-dir")
			}
		}
		var err error
		projectRoot, err = existingDirectory(candidate)
		if err != nil {
			if options.ProjectDir == "" {
				return nil, fmt.Errorf("snapshots: captured project is unavailable; supply --project-dir: %w", err)
			}
			return nil, err
		}
	}

	seen := make(map[string]Entry)
	resolved := make([]resolvedEntry, 0, len(manifest.Entries))
	for _, entry := range manifest.Entries {
		if err := validateRelativeLocator(entry.Locator); err != nil {
			return nil, err
		}
		path, err := resolveCanonicalEntry(entry, projectRoot)
		if err != nil {
			return nil, err
		}
		if previous, ok := seen[path]; ok {
			if previous.State != entry.State || previous.Digest != entry.Digest {
				return nil, fmt.Errorf("snapshots: entries resolve to conflicting destination %q", path)
			}
			continue
		}
		seen[path] = entry
		resolved = append(resolved, resolvedEntry{entry: entry, path: path})
	}
	sort.Slice(resolved, func(i, j int) bool {
		if resolved[i].entry.Scope != resolved[j].entry.Scope {
			return resolved[i].entry.Scope < resolved[j].entry.Scope
		}
		return resolved[i].entry.Locator < resolved[j].entry.Locator
	})
	return resolved, nil
}

func resolveCanonicalEntry(entry Entry, projectRoot string) (string, error) {
	if len(entry.Owners) == 0 {
		return "", errors.New("snapshots: entry has no owners")
	}
	level := entities.InstallLevel(entry.Scope)
	var expected string
	for _, owner := range entry.Owners {
		path, err := entities.InstructionPath(owner, level, projectRoot)
		if err != nil {
			return "", fmt.Errorf("snapshots: resolve %s %s target: %w", owner, entry.Scope, err)
		}
		path, err = filepath.Abs(path)
		if err != nil {
			return "", err
		}
		if expected == "" {
			expected = filepath.Clean(path)
		} else if filepath.Clean(path) != expected {
			return "", fmt.Errorf("snapshots: owners for %s resolve to conflicting destinations", entry.Locator)
		}
	}
	root := pathutil.Home()
	if entry.Scope == ScopeProject {
		if projectRoot == "" {
			return "", errors.New("snapshots: project entry has no project root")
		}
		root = projectRoot
	}
	located, err := joinBeneath(root, entry.Locator)
	if err != nil {
		return "", err
	}
	if expected != located {
		return "", fmt.Errorf("snapshots: locator %q does not match canonical target for %s", entry.Locator, strings.Join(entry.Owners, ","))
	}
	return expected, nil
}

func joinBeneath(root, locator string) (string, error) {
	if root == "" {
		return "", errors.New("snapshots: target root is empty")
	}
	absoluteRoot, err := filepath.Abs(root)
	if err != nil {
		return "", err
	}
	path := filepath.Join(absoluteRoot, filepath.FromSlash(locator))
	relative, err := filepath.Rel(absoluteRoot, path)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("snapshots: locator %q escapes root %q", locator, absoluteRoot)
	}
	return filepath.Clean(path), nil
}

func textContent(data []byte) bool {
	return utf8.Valid(data) && !strings.ContainsRune(string(data), 0)
}

func unifiedDiff(before, after []byte) string {
	a := splitLines(string(before))
	b := splitLines(string(after))
	type cell struct{ length int }
	table := make([][]cell, len(a)+1)
	for i := range table {
		table[i] = make([]cell, len(b)+1)
	}
	for i := len(a) - 1; i >= 0; i-- {
		for j := len(b) - 1; j >= 0; j-- {
			if a[i] == b[j] {
				table[i][j].length = table[i+1][j+1].length + 1
			} else if table[i+1][j].length >= table[i][j+1].length {
				table[i][j].length = table[i+1][j].length
			} else {
				table[i][j].length = table[i][j+1].length
			}
		}
	}
	var builder strings.Builder
	builder.WriteString("--- snapshot\n+++ current\n")
	fmt.Fprintf(&builder, "@@ -1,%d +1,%d @@\n", len(a), len(b))
	for i, j := 0, 0; i < len(a) || j < len(b); {
		switch {
		case i < len(a) && j < len(b) && a[i] == b[j]:
			writeDiffLine(&builder, ' ', a[i])
			i++
			j++
		case j == len(b) || (i < len(a) && table[i+1][j].length >= table[i][j+1].length):
			writeDiffLine(&builder, '-', a[i])
			i++
		default:
			writeDiffLine(&builder, '+', b[j])
			j++
		}
	}
	return builder.String()
}

func splitLines(value string) []string {
	if value == "" {
		return nil
	}
	lines := strings.SplitAfter(value, "\n")
	if lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	return lines
}

func writeDiffLine(builder *strings.Builder, prefix byte, line string) {
	builder.WriteByte(prefix)
	builder.WriteString(strings.TrimSuffix(line, "\n"))
	builder.WriteByte('\n')
	if line != "" && !strings.HasSuffix(line, "\n") {
		builder.WriteString("\\ No newline at end of file\n")
	}
}

func ensureNoSymlinkAncestors(root, destination string) error {
	root, err := filepath.Abs(root)
	if err != nil {
		return err
	}
	parent := filepath.Dir(destination)
	relative, err := filepath.Rel(root, parent)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return fmt.Errorf("snapshots: destination %q escapes root %q", destination, root)
	}
	current := root
	if info, err := os.Lstat(current); err == nil && info.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("snapshots: destination root %q is a symbolic link", current)
	}
	for _, component := range strings.Split(relative, string(filepath.Separator)) {
		if component == "" || component == "." {
			continue
		}
		current = filepath.Join(current, component)
		info, err := os.Lstat(current)
		if errors.Is(err, fs.ErrNotExist) {
			break
		}
		if err != nil {
			return err
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("snapshots: destination ancestor %q is a symbolic link", current)
		}
		if !info.IsDir() {
			return fmt.Errorf("snapshots: destination ancestor %q is not a directory", current)
		}
	}
	return nil
}

package snapshots

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/chat2anyllm/code-agent-manager/internal/entities"
	"github.com/chat2anyllm/code-agent-manager/internal/pathutil"
)

type capturedTarget struct {
	entry Entry
	data  []byte
}

func discover(options CreateOptions) ([]capturedTarget, Selection, error) {
	if err := validateName(options.Name); err != nil {
		return nil, Selection{}, err
	}
	scope := options.Scope
	if scope == "" {
		scope = ScopeUser
	}
	if scope != ScopeUser && scope != ScopeProject && scope != ScopeAll {
		return nil, Selection{}, fmt.Errorf("snapshots: unsupported scope %q", scope)
	}

	projectRoot := ""
	if scope == ScopeProject || scope == ScopeAll {
		if options.ProjectDir == "" {
			return nil, Selection{}, errors.New("snapshots: --project-dir is required for project or all scope")
		}
		var err error
		projectRoot, err = existingDirectory(options.ProjectDir)
		if err != nil {
			return nil, Selection{}, err
		}
	} else if options.ProjectDir != "" {
		return nil, Selection{}, errors.New("snapshots: --project-dir requires project or all scope")
	}

	known := entities.InstructionApps()
	knownSet := make(map[string]struct{}, len(known))
	for _, agent := range known {
		knownSet[agent] = struct{}{}
	}
	agents := append([]string(nil), options.Agents...)
	if len(agents) == 0 {
		agents = known
	}
	seenAgents := make(map[string]struct{}, len(agents))
	normalizedAgents := make([]string, 0, len(agents))
	for _, agent := range agents {
		agent = strings.ToLower(strings.TrimSpace(agent))
		if _, ok := knownSet[agent]; !ok {
			return nil, Selection{}, fmt.Errorf("snapshots: unknown instruction agent %q", agent)
		}
		if _, duplicate := seenAgents[agent]; duplicate {
			continue
		}
		seenAgents[agent] = struct{}{}
		normalizedAgents = append(normalizedAgents, agent)
	}
	sort.Strings(normalizedAgents)

	type logicalTarget struct {
		agent   string
		scope   Scope
		path    string
		locator string
	}
	var logical []logicalTarget
	for _, agent := range normalizedAgents {
		levels := entities.InstructionAppLevels(agent)
		for _, level := range levels {
			levelScope := Scope(level)
			if !scopeIncludes(scope, levelScope) {
				continue
			}
			path, err := entities.InstructionPath(agent, level, projectRoot)
			if err != nil {
				return nil, Selection{}, fmt.Errorf("snapshots: resolve %s %s target: %w", agent, level, err)
			}
			path, err = filepath.Abs(path)
			if err != nil {
				return nil, Selection{}, fmt.Errorf("snapshots: normalize %q: %w", path, err)
			}
			locator, err := locatorFor(levelScope, path, projectRoot)
			if err != nil {
				return nil, Selection{}, err
			}
			logical = append(logical, logicalTarget{agent: agent, scope: levelScope, path: filepath.Clean(path), locator: locator})
		}
	}

	byPath := make(map[string]*capturedTarget)
	for _, target := range logical {
		if existing, ok := byPath[target.path]; ok {
			if existing.entry.Scope != target.scope || existing.entry.Locator != target.locator {
				return nil, Selection{}, fmt.Errorf("snapshots: target %q resolves from conflicting logical assets", target.path)
			}
			existing.entry.Owners = append(existing.entry.Owners, target.agent)
			continue
		}
		token, data, err := readTarget(target.path)
		if err != nil {
			return nil, Selection{}, fmt.Errorf("snapshots: capture %q: %w", target.path, err)
		}
		entry := Entry{
			Owners:        []string{target.agent},
			Kind:          "instruction",
			Scope:         target.scope,
			Locator:       target.locator,
			CapturedPath:  target.path,
			State:         token.State,
			NodeType:      token.NodeType,
			SymlinkTarget: token.LinkTarget,
			Digest:        token.Digest,
			Size:          token.Size,
			Mode:          token.Mode,
		}
		byPath[target.path] = &capturedTarget{entry: entry, data: data}
	}

	targets := make([]capturedTarget, 0, len(byPath))
	for _, target := range byPath {
		sort.Strings(target.entry.Owners)
		targets = append(targets, *target)
	}
	sort.Slice(targets, func(i, j int) bool {
		if targets[i].entry.Scope != targets[j].entry.Scope {
			return targets[i].entry.Scope < targets[j].entry.Scope
		}
		return targets[i].entry.Locator < targets[j].entry.Locator
	})
	selection := Selection{Scope: scope, Agents: normalizedAgents, ProjectRoot: projectRoot}
	return targets, selection, nil
}

func scopeIncludes(selection, candidate Scope) bool {
	return selection == ScopeAll || selection == candidate
}

func existingDirectory(path string) (string, error) {
	expanded := pathutil.Expand(path)
	absolute, err := filepath.Abs(expanded)
	if err != nil {
		return "", fmt.Errorf("snapshots: resolve project directory %q: %w", path, err)
	}
	info, err := os.Stat(absolute)
	if err != nil {
		return "", fmt.Errorf("snapshots: project directory %q: %w", absolute, err)
	}
	if !info.IsDir() {
		return "", fmt.Errorf("snapshots: project directory %q is not a directory", absolute)
	}
	return filepath.Clean(absolute), nil
}

func locatorFor(scope Scope, path, projectRoot string) (string, error) {
	var root string
	switch scope {
	case ScopeUser:
		root = pathutil.Home()
	case ScopeProject:
		root = projectRoot
	default:
		return "", fmt.Errorf("snapshots: invalid entry scope %q", scope)
	}
	root, err := filepath.Abs(root)
	if err != nil {
		return "", fmt.Errorf("snapshots: resolve locator root: %w", err)
	}
	relative, err := filepath.Rel(root, path)
	if err != nil {
		return "", fmt.Errorf("snapshots: locate %q beneath %q: %w", path, root, err)
	}
	locator := filepath.ToSlash(relative)
	if err := validateRelativeLocator(locator); err != nil {
		return "", fmt.Errorf("snapshots: target %q is outside its %s root: %w", path, scope, err)
	}
	return locator, nil
}

func readTarget(path string) (stateToken, []byte, error) {
	info, err := os.Lstat(path)
	if errors.Is(err, fs.ErrNotExist) {
		return stateToken{State: StateAbsent}, nil, nil
	}
	if err != nil {
		return stateToken{}, nil, err
	}

	token := stateToken{State: StatePresent, Mode: uint32(info.Mode().Perm())}
	if info.Mode().IsRegular() {
		token.NodeType = NodeRegular
	} else if info.Mode()&os.ModeSymlink != 0 {
		token.NodeType = NodeSymlink
		token.LinkTarget, err = os.Readlink(path)
		if err != nil {
			return stateToken{}, nil, err
		}
		resolved, err := os.Stat(path)
		if err != nil {
			return stateToken{}, nil, fmt.Errorf("resolve symbolic link: %w", err)
		}
		if !resolved.Mode().IsRegular() {
			return stateToken{}, nil, fmt.Errorf("symbolic link resolves to unsupported %s", resolved.Mode().Type())
		}
		token.Mode = uint32(resolved.Mode().Perm())
	} else {
		return stateToken{}, nil, fmt.Errorf("unsupported file type %s", info.Mode().Type())
	}

	data, err := os.ReadFile(path)
	if err != nil {
		return stateToken{}, nil, err
	}
	token.Digest = digestBytes(data)
	token.Size = int64(len(data))
	return token, data, nil
}

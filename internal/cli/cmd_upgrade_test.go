package cli_test

import (
	"strings"
	"testing"
)

// `cam upgrade <tool> --dry-run` previews the upgrade for a single target.
func TestUpgradeDryRunForSpecificTool(t *testing.T) {
	isolatedHome(t)
	stdout, _, code := execute(t, "upgrade", "claude", "--dry-run")
	if code != 0 {
		t.Fatalf("exit = %d", code)
	}
	if !strings.Contains(stdout, "Would upgrade claude") {
		t.Fatalf("missing dry-run header:\n%s", stdout)
	}
	if !strings.Contains(stdout, "claude-code") {
		t.Fatalf("missing resolved tool key:\n%s", stdout)
	}
}

// `cam upgrade <tool>,<tool> --dry-run` resolves aliases in input order.
func TestUpgradeDryRunForMultipleTargets(t *testing.T) {
	isolatedHome(t)
	stdout, _, code := execute(t, "upgrade", "codex,claude", "--dry-run")
	if code != 0 {
		t.Fatalf("exit = %d", code)
	}
	if !strings.Contains(stdout, "Would upgrade codex,claude") {
		t.Fatalf("missing dry-run header:\n%s", stdout)
	}
	codex := strings.Index(stdout, "  - openai-codex\n")
	claude := strings.Index(stdout, "  - claude-code\n")
	if codex < 0 || claude < 0 {
		t.Fatalf("missing resolved targets:\n%s", stdout)
	}
	if codex > claude {
		t.Fatalf("targets not listed in input order:\n%s", stdout)
	}
}

// Repeated keys and aliases resolve to one canonical tool.
func TestUpgradeDryRunDeduplicatesMultipleTargets(t *testing.T) {
	isolatedHome(t)
	stdout, _, code := execute(t, "upgrade", "codex,openai-codex,claude,codex", "--dry-run")
	if code != 0 {
		t.Fatalf("exit = %d", code)
	}
	if got := strings.Count(stdout, "  - openai-codex\n"); got != 1 {
		t.Fatalf("openai-codex listed %d times, want 1:\n%s", got, stdout)
	}
	if got := strings.Count(stdout, "  - claude-code\n"); got != 1 {
		t.Fatalf("claude-code listed %d times, want 1:\n%s", got, stdout)
	}
}

// `cam upgrade all --dry-run` previews the upgrade across every enabled tool.
func TestUpgradeAllDryRunCoversEveryEnabledTool(t *testing.T) {
	isolatedHome(t)
	stdout, _, code := execute(t, "upgrade", "all", "--dry-run")
	if code != 0 {
		t.Fatalf("exit = %d", code)
	}
	if !strings.Contains(stdout, "Would upgrade all") {
		t.Fatalf("missing 'Would upgrade all'\n%s", stdout)
	}
	for _, want := range []string{"claude-code", "openai-codex", "gemini-cli", "qwen-code"} {
		if !strings.Contains(stdout, want) {
			t.Fatalf("missing tool %q in upgrade list:\n%s", want, stdout)
		}
	}
}

// `cam u` alias mirrors `cam upgrade`.
func TestUpgradeAliasU(t *testing.T) {
	isolatedHome(t)
	stdout, _, code := execute(t, "u", "gemini-cli", "--dry-run")
	if code != 0 {
		t.Fatalf("exit = %d", code)
	}
	if !strings.Contains(stdout, "Would upgrade gemini-cli") {
		t.Fatalf("alias output:\n%s", stdout)
	}
}

// Unknown targets fail loud.
func TestUpgradeRejectsUnknownTarget(t *testing.T) {
	isolatedHome(t)
	_, stderr, code := execute(t, "upgrade", "ghostly", "--dry-run")
	if code == 0 {
		t.Fatal("expected non-zero exit")
	}
	if !strings.Contains(stderr, "Unknown target") {
		t.Fatalf("stderr missing Unknown target: %s", stderr)
	}
}

func TestUpgradeRejectsInvalidTargetLists(t *testing.T) {
	tests := []struct {
		name    string
		target  string
		wantErr string
	}{
		{name: "unknown target", target: "codex,ghostly", wantErr: "Unknown target: ghostly"},
		{name: "empty target", target: "codex,,claude", wantErr: "Invalid target list: empty target"},
		{name: "all with named target", target: "all,codex", wantErr: "Invalid target list: all must be used alone"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			isolatedHome(t)
			stdout, stderr, code := execute(t, "upgrade", tt.target, "--dry-run")
			if code == 0 {
				t.Fatal("expected non-zero exit")
			}
			if stdout != "" {
				t.Fatalf("stdout = %q, want no planned operations", stdout)
			}
			if !strings.Contains(stderr, tt.wantErr) {
				t.Fatalf("stderr missing %q: %s", tt.wantErr, stderr)
			}
		})
	}
}

// `cam upgrade --help` advertises multi-target syntax and its flags.
func TestUpgradeHelpDocumentsFlags(t *testing.T) {
	isolatedHome(t)
	stdout, _, code := execute(t, "upgrade", "--help")
	if code != 0 {
		t.Fatalf("exit = %d", code)
	}
	for _, want := range []string{"upgrade [TARGET[,TARGET...]]", "--dry-run", "--verbose"} {
		if !strings.Contains(stdout, want) {
			t.Fatalf("help missing %q:\n%s", want, stdout)
		}
	}
}

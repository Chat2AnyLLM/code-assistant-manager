package cli

import (
	"errors"
	"fmt"
	"strings"

	"github.com/spf13/cobra"

	"github.com/chat2anyllm/code-agent-manager/internal/tools"
)

// lifecycleCommand provides install/upgrade/uninstall against the tools.yaml
// registry.  The three verbs share a single implementation because Python
// treats them as aliases internally — install and upgrade do the same npm/
// curl install, uninstall removes the package or binary.
func (a *App) lifecycleCommand(name, alias string) *cobra.Command {
	var (
		dryRun  bool
		verbose bool
		force   bool
	)
	title := strings.ToTitle(name[:1]) + name[1:]
	use := name + " [TARGET]"
	if name == "upgrade" {
		use = name + " [TARGET[,TARGET...]]"
	}
	cmd := &cobra.Command{
		Use:     use,
		Aliases: []string{alias},
		Short:   title + " tools",
		Args:    cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			target := "all"
			if len(args) > 0 {
				target = args[0]
			}
			registry, err := tools.LoadDefault()
			if err != nil {
				return err
			}
			var candidates []tools.Tool
			if name == "upgrade" {
				candidates, err = pickUpgradeTargets(registry, target)
			} else {
				candidates, err = pickTargets(registry, target)
			}
			if err != nil {
				return err
			}
			out := cmd.OutOrStdout()
			errw := cmd.ErrOrStderr()
			if dryRun {
				fmt.Fprintf(out, "Would %s %s\n", name, target)
				for _, tool := range candidates {
					fmt.Fprintf(out, "  - %s\n", tool.Name)
				}
				return nil
			}
			failures := 0
			for _, tool := range candidates {
				switch name {
				case "install", "upgrade":
					fmt.Fprintf(out, "%s %s ...\n", title, tool.Name)
					code, err := tools.Install(tool, nil, ifVerbose(out, verbose), errw)
					if errors.Is(err, tools.ErrNoInstallCommand) {
						fmt.Fprintf(out, "  %s has no install_cmd; skipping\n", tool.Name)
						continue
					}
					if err != nil || code != 0 {
						failures++
						fmt.Fprintf(errw, "  failed (exit %d): %v\n", code, err)
						continue
					}
					fmt.Fprintf(out, "  %s OK\n", tool.Name)
				case "uninstall":
					if !force {
						fmt.Fprintf(out, "Uninstalling %s (use --force to skip prompt next time)\n", tool.Name)
					}
					code, msg, err := tools.Uninstall(tool, nil, ifVerbose(out, verbose), errw)
					if err != nil || code != 0 {
						failures++
						fmt.Fprintf(errw, "  failed (exit %d): %s — %v\n", code, msg, err)
						continue
					}
					fmt.Fprintf(out, "  %s: %s\n", tool.Name, msg)
				default:
					return fmt.Errorf("unknown lifecycle verb: %s", name)
				}
			}
			if failures > 0 {
				return fmt.Errorf("%d of %d operations failed", failures, len(candidates))
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Print planned action without executing it")
	cmd.Flags().BoolVarP(&verbose, "verbose", "v", false, "Show installer output")
	if name == "uninstall" {
		cmd.Flags().BoolVarP(&force, "force", "f", false, "Skip confirmation prompts")
		cmd.Flags().Bool("keep-config", false, "Keep configuration files (placeholder)")
	}
	return cmd
}

func ifVerbose(out interface{ Write(p []byte) (int, error) }, verbose bool) interface{ Write(p []byte) (int, error) } {
	if verbose {
		return out
	}
	return discardWriter{}
}

type discardWriter struct{}

func (discardWriter) Write(p []byte) (int, error) { return len(p), nil }

func pickUpgradeTargets(registry *tools.Registry, targetList string) ([]tools.Tool, error) {
	targets := strings.Split(targetList, ",")
	for i, target := range targets {
		targets[i] = strings.TrimSpace(target)
		if targets[i] == "" {
			return nil, errors.New("Invalid target list: empty target")
		}
	}
	if len(targets) == 1 {
		return pickTargets(registry, targets[0])
	}

	seen := make(map[string]struct{}, len(targets))
	candidates := make([]tools.Tool, 0, len(targets))
	for _, target := range targets {
		if target == "all" {
			return nil, errors.New("Invalid target list: all must be used alone")
		}
		resolved, err := pickTargets(registry, target)
		if err != nil {
			return nil, err
		}
		tool := resolved[0]
		if _, ok := seen[tool.Name]; ok {
			continue
		}
		seen[tool.Name] = struct{}{}
		candidates = append(candidates, tool)
	}
	return candidates, nil
}

func pickTargets(registry *tools.Registry, target string) ([]tools.Tool, error) {
	if target == "all" {
		out := []tools.Tool{}
		for _, name := range registry.EnabledNames() {
			out = append(out, registry.Tools[name])
		}
		return out, nil
	}
	if t, ok := registry.Get(target); ok {
		return []tools.Tool{t}, nil
	}
	if t, ok := registry.ByCLICommand(target); ok {
		return []tools.Tool{t}, nil
	}
	return nil, fmt.Errorf("Unknown target: %s", target)
}

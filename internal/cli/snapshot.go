package cli

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"

	"github.com/chat2anyllm/code-agent-manager/internal/snapshots"
	"github.com/spf13/cobra"
)

const (
	snapshotFormatText = "text"
	snapshotFormatJSON = "json"
)

func (a *App) snapshotCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "snapshot",
		Short: "Capture, compare, and restore coding-agent instruction state",
		Args:  cobra.NoArgs,
	}
	cmd.AddCommand(
		a.snapshotCreateCommand(),
		a.snapshotListCommand(),
		a.snapshotShowCommand(),
		a.snapshotDiffCommand(),
		a.snapshotRestoreCommand(),
	)
	return cmd
}

func (a *App) snapshotCreateCommand() *cobra.Command {
	var name, scopeValue, projectDir, format string
	var agents []string
	cmd := &cobra.Command{
		Use:   "create",
		Short: "Create an immutable snapshot",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := validateSnapshotFormat(format); err != nil {
				return err
			}
			scope, err := snapshots.ParseScope(scopeValue)
			if err != nil {
				return err
			}
			snapshot, err := snapshots.NewService().Create(snapshots.CreateOptions{
				Name: name, Scope: scope, Agents: agents, ProjectDir: projectDir,
			})
			if err != nil {
				return err
			}
			if format == snapshotFormatJSON {
				return writeSnapshotJSON(cmd.OutOrStdout(), snapshot)
			}
			fmt.Fprintf(cmd.OutOrStdout(), "Created snapshot %s", snapshot.Manifest.ID)
			if snapshot.Manifest.Name != "" {
				fmt.Fprintf(cmd.OutOrStdout(), " (%s)", snapshot.Manifest.Name)
			}
			fmt.Fprintf(cmd.OutOrStdout(), " with %d targets\n", len(snapshot.Manifest.Entries))
			return nil
		},
	}
	cmd.Flags().StringVar(&name, "name", "", "Human-readable snapshot name")
	cmd.Flags().StringVar(&scopeValue, "scope", string(snapshots.ScopeUser), "Capture scope: user, project, or all")
	cmd.Flags().StringSliceVar(&agents, "agent", nil, "Agent to capture (repeatable or comma-separated)")
	cmd.Flags().StringVar(&projectDir, "project-dir", "", "Project root for project or all scope")
	cmd.Flags().StringVar(&format, "format", snapshotFormatText, "Output format: text or json")
	return cmd
}

func (a *App) snapshotListCommand() *cobra.Command {
	var format string
	cmd := &cobra.Command{
		Use:   "list",
		Short: "List stored snapshots",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := validateSnapshotFormat(format); err != nil {
				return err
			}
			items, err := snapshots.NewService().List()
			if err != nil {
				return err
			}
			if format == snapshotFormatJSON {
				return writeSnapshotJSON(cmd.OutOrStdout(), items)
			}
			if len(items) == 0 {
				fmt.Fprintln(cmd.OutOrStdout(), "No snapshots found.")
				return nil
			}
			for _, item := range items {
				fmt.Fprintf(cmd.OutOrStdout(), "%s\t%s\t%s\t%d targets\n",
					item.Manifest.ID, item.Manifest.Name, item.Manifest.CreatedAt.Format("2006-01-02T15:04:05Z07:00"), len(item.Manifest.Entries))
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&format, "format", snapshotFormatText, "Output format: text or json")
	return cmd
}

func (a *App) snapshotShowCommand() *cobra.Command {
	var format string
	cmd := &cobra.Command{
		Use:   "show <snapshot>",
		Short: "Inspect and verify a snapshot",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := validateSnapshotFormat(format); err != nil {
				return err
			}
			snapshot, err := snapshots.NewService().Show(args[0])
			if err != nil {
				return err
			}
			if format == snapshotFormatJSON {
				return writeSnapshotJSON(cmd.OutOrStdout(), snapshot)
			}
			renderSnapshot(cmd.OutOrStdout(), snapshot)
			return nil
		},
	}
	cmd.Flags().StringVar(&format, "format", snapshotFormatText, "Output format: text or json")
	return cmd
}

func (a *App) snapshotDiffCommand() *cobra.Command {
	var format, projectDir string
	cmd := &cobra.Command{
		Use:   "diff <snapshot>",
		Short: "Show drift from a snapshot",
		Args: func(cmd *cobra.Command, args []string) error {
			if err := cobra.ExactArgs(1)(cmd, args); err != nil {
				return withExitStatus(2, err)
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := validateSnapshotFormat(format); err != nil {
				return withExitStatus(2, err)
			}
			result, err := snapshots.NewService().Diff(args[0], snapshots.ResolveOptions{ProjectDir: projectDir})
			if err != nil {
				return withExitStatus(2, err)
			}
			if format == snapshotFormatJSON {
				if err := writeSnapshotJSON(cmd.OutOrStdout(), result); err != nil {
					return withExitStatus(2, err)
				}
			} else {
				renderSnapshotDiff(cmd.OutOrStdout(), result)
			}
			if result.HasDrift() {
				return withExitStatus(1, nil)
			}
			return nil
		},
	}
	cmd.SetFlagErrorFunc(func(cmd *cobra.Command, err error) error {
		return withExitStatus(2, err)
	})
	cmd.Flags().StringVar(&projectDir, "project-dir", "", "Project root used to resolve project snapshot entries")
	cmd.Flags().StringVar(&format, "format", snapshotFormatText, "Output format: text or json")
	return cmd
}

func (a *App) snapshotRestoreCommand() *cobra.Command {
	var format, projectDir string
	var dryRun, yes, exact bool
	cmd := &cobra.Command{
		Use:   "restore <snapshot>",
		Short: "Safely restore instruction state from a snapshot",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := validateSnapshotFormat(format); err != nil {
				return err
			}
			service := snapshots.NewService()
			plan, err := service.PlanRestore(args[0], snapshots.ResolveOptions{ProjectDir: projectDir}, exact)
			if err != nil {
				return err
			}
			if format == snapshotFormatJSON {
				if err := writeSnapshotJSON(cmd.OutOrStdout(), plan); err != nil {
					return err
				}
			} else {
				renderRestorePlan(cmd.OutOrStdout(), plan, dryRun)
			}
			if dryRun || plan.ChangeCount() == 0 {
				return nil
			}
			if !yes {
				if !a.interactive {
					return errors.New("snapshot restore requires --yes for non-interactive input (or use --dry-run)")
				}
				confirmed, err := confirmSnapshotRestore(cmd, plan.ChangeCount())
				if err != nil {
					return err
				}
				if !confirmed {
					fmt.Fprintln(cmd.OutOrStdout(), "Restore cancelled.")
					return nil
				}
			}
			if err := service.ApplyRestore(plan); err != nil {
				return err
			}
			if format == snapshotFormatText {
				fmt.Fprintf(cmd.OutOrStdout(), "Restored %d targets from %s.\n", plan.ChangeCount(), plan.SnapshotID)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&projectDir, "project-dir", "", "Project root used to resolve project snapshot entries")
	cmd.Flags().StringVar(&format, "format", snapshotFormatText, "Output format: text or json")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Show the restore plan without writing files")
	cmd.Flags().BoolVar(&yes, "yes", false, "Apply the restore without interactive confirmation")
	cmd.Flags().BoolVar(&exact, "exact", false, "Remove live targets that were absent in the snapshot")
	return cmd
}

func validateSnapshotFormat(format string) error {
	if format != snapshotFormatText && format != snapshotFormatJSON {
		return fmt.Errorf("unsupported snapshot format %q (want text or json)", format)
	}
	return nil
}

func writeSnapshotJSON(writer io.Writer, value any) error {
	encoder := json.NewEncoder(writer)
	encoder.SetIndent("", "  ")
	return encoder.Encode(value)
}

func renderSnapshot(writer io.Writer, snapshot snapshots.Snapshot) {
	manifest := snapshot.Manifest
	fmt.Fprintf(writer, "Snapshot: %s\n", manifest.ID)
	if manifest.Name != "" {
		fmt.Fprintf(writer, "Name: %s\n", manifest.Name)
	}
	fmt.Fprintf(writer, "Created: %s\nScope: %s\nIntegrity: %s\nTargets: %d\n",
		manifest.CreatedAt.Format("2006-01-02T15:04:05Z07:00"), manifest.Selection.Scope, snapshot.Integrity, len(manifest.Entries))
	for _, entry := range manifest.Entries {
		fmt.Fprintf(writer, "- %s %s [%s] %s", entry.State, strings.Join(entry.Owners, ","), entry.Scope, entry.Locator)
		if entry.State == snapshots.StatePresent {
			fmt.Fprintf(writer, " sha256:%s", entry.Digest[:12])
		}
		fmt.Fprintln(writer)
	}
}

func renderSnapshotDiff(writer io.Writer, result snapshots.DriftResult) {
	fmt.Fprintf(writer, "Snapshot: %s\n", result.SnapshotID)
	for _, entry := range result.Entries {
		if entry.Status == snapshots.DriftUnchanged {
			continue
		}
		fmt.Fprintf(writer, "%s\t%s\t%s\n", driftCode(entry.Status), strings.Join(entry.Owners, ","), entry.Path)
		if entry.Error != "" {
			fmt.Fprintf(writer, "  %s\n", entry.Error)
		}
		if entry.TextDiff != "" {
			fmt.Fprint(writer, entry.TextDiff)
		}
	}
	fmt.Fprintf(writer, "Summary: %d unchanged, %d added, %d missing, %d changed, %d unreadable, %d unsupported\n",
		result.Summary.Unchanged, result.Summary.Added, result.Summary.Missing, result.Summary.Changed,
		result.Summary.Unreadable, result.Summary.Unsupported)
}

func driftCode(status snapshots.DriftStatus) string {
	switch status {
	case snapshots.DriftAdded:
		return "A"
	case snapshots.DriftMissing:
		return "D"
	case snapshots.DriftChanged:
		return "M"
	case snapshots.DriftUnreadable, snapshots.DriftUnsupported:
		return "!"
	default:
		return " "
	}
}

func renderRestorePlan(writer io.Writer, plan snapshots.RestorePlan, dryRun bool) {
	label := "Restore plan"
	if dryRun {
		label = "Restore dry run"
	}
	fmt.Fprintf(writer, "%s for %s:\n", label, plan.SnapshotID)
	for _, action := range plan.Actions {
		fmt.Fprintf(writer, "- %-14s %s", action.Type, action.Path)
		if action.ReplacesLink {
			fmt.Fprint(writer, " (replaces symbolic link)")
		}
		fmt.Fprintln(writer)
	}
	fmt.Fprintf(writer, "%d targets would change.\n", plan.ChangeCount())
}

func confirmSnapshotRestore(cmd *cobra.Command, count int) (bool, error) {
	fmt.Fprintf(cmd.ErrOrStderr(), "Restore %d targets? [y/N] ", count)
	line, err := bufio.NewReader(cmd.InOrStdin()).ReadString('\n')
	if err != nil && !errors.Is(err, io.EOF) {
		return false, err
	}
	answer := strings.ToLower(strings.TrimSpace(line))
	return answer == "y" || answer == "yes", nil
}

"""CLI tests for prompt management commands."""

import pytest

import code_assistant_manager.cli.prompts_commands as prompts_commands
from code_assistant_manager.prompts import Prompt, PromptManager


@pytest.fixture
def cli_manager(tmp_path, monkeypatch):
    """Provide a PromptManager backed by a temporary config directory."""
    config_dir = tmp_path / "config"
    manager = PromptManager(config_dir)
    monkeypatch.setattr(prompts_commands, "_get_prompt_manager", lambda: manager)
    return manager


def _prepare_user_files(tmp_path, monkeypatch, manager):
    """Create temporary user-level prompt files and configure manager handlers."""
    user_files = {}
    handler_overrides = {}

    for app in prompts_commands.VALID_APP_TYPES:
        file_path = tmp_path / f"user_{app}.md"
        file_path.write_text(f"user content {app}")
        user_files[app] = file_path
        handler_overrides[app] = {"user_path": file_path}

    # Update the manager's handlers with the new paths
    from code_assistant_manager.prompts import PROMPT_HANDLERS

    for name, cls in PROMPT_HANDLERS.items():
        overrides = handler_overrides.get(name, {})
        manager._handlers[name] = cls(
            user_path_override=overrides.get("user_path"),
            project_filename_override=overrides.get("project_filename"),
        )

    return user_files


def test_import_live_project_level(cli_manager, tmp_path, monkeypatch):
    """import-live should import prompts from project-level files."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    prompt_file = project_dir / "CLAUDE.md"
    prompt_file.write_text("CLI project prompt")

    outputs = []

    def capture(message=""):
        outputs.append(str(message))

    monkeypatch.setattr(prompts_commands.typer, "echo", capture)

    prompts_commands.import_live_prompt(
        app_type="claude",
        name="CLI_Test",
        level="project",
        project_dir=project_dir,
    )

    prompts = cli_manager.get_all()
    assert any(prompt.name == "CLI_Test" for prompt in prompts.values())
    assert any("From:" in msg for msg in outputs)


def test_show_live_project_level(cli_manager, tmp_path, monkeypatch):
    """show-live should display project-level prompt content."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    prompt_file = project_dir / "CLAUDE.md"
    prompt_file.write_text("Project show content")

    outputs = []

    def capture(message=""):
        outputs.append(str(message))

    monkeypatch.setattr(prompts_commands.typer, "echo", capture)

    prompts_commands.show_live_prompt(
        app_type="claude",
        level="project",
        project_dir=project_dir,
    )

    combined = "\n".join(outputs)
    assert "Project show content" in combined
    assert "Level:" in combined


def test_import_live_all_apps_levels(cli_manager, tmp_path, monkeypatch):
    """import-live supports app=all and level=all."""
    _prepare_user_files(tmp_path, monkeypatch, cli_manager)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    from code_assistant_manager import prompts as prompts_module

    for app, filename in prompts_module.PROJECT_PROMPT_FILE_NAMES.items():
        project_file = project_dir / filename
        project_file.write_text(f"project content {app}")

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.import_live_prompt(
        app_type="all",
        name="Batch",
        level="all",
        project_dir=project_dir,
    )

    prompts = cli_manager.get_all()
    # claude, codex, gemini: user + project = 6
    # copilot: only project (skipped because no copilot instructions file)
    # So total = 6 (not 8) when copilot file doesn't exist
    expected_count = len(prompts_commands.USER_LEVEL_APPS) * len(
        prompts_commands.VALID_LEVELS
    )
    assert len(prompts) == expected_count
    combined = "\n".join(outputs)
    for app in prompts_commands.USER_LEVEL_APPS:
        assert app in combined
    assert "project" in combined
    assert "user" in combined


def test_show_live_all_apps_levels(cli_manager, tmp_path, monkeypatch):
    """show-live prints every app/level combo when 'all' specified."""
    _prepare_user_files(tmp_path, monkeypatch, cli_manager)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    from code_assistant_manager import prompts as prompts_module

    for app, filename in prompts_module.PROJECT_PROMPT_FILE_NAMES.items():
        project_file = project_dir / filename
        project_file.write_text(f"project level content {app}")

    outputs = []

    def capture(message=""):
        outputs.append(str(message))

    monkeypatch.setattr(prompts_commands.typer, "echo", capture)

    prompts_commands.show_live_prompt(
        app_type="all",
        level="all",
        project_dir=project_dir,
    )

    combined = "\n".join(outputs)
    # Check user-level apps appear (copilot only shows at project level)
    for app in prompts_commands.USER_LEVEL_APPS:
        assert f"Live prompt for {app}" in combined
    assert combined.count("Level:") >= 2


def test_sync_prompt_project_scope(cli_manager, tmp_path, monkeypatch):
    """sync supports project scope for every app."""
    prompt = Prompt(id="cli", name="CLI", content="project-level content")
    cli_manager.create(prompt)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.sync_prompts(
        prompt_id="cli",
        app_type="claude",
        level="project",
        project_dir=project_dir,
        enable=False,
    )

    prompt_file = project_dir / "CLAUDE.md"
    assert prompt_file.exists()
    assert prompt_file.read_text() == "project-level content"

    stored = cli_manager.get("cli")
    assert stored.enabled is False
    assert any("CLAUDE.md" in msg for msg in outputs)


def test_sync_prompt_with_enable(cli_manager, tmp_path, monkeypatch):
    """sync --enable marks the prompt as active and syncs it."""
    from code_assistant_manager.prompts import PROMPT_HANDLERS

    # Setup user-level file path
    user_claude_file = tmp_path / "user_claude.md"

    # Update manager's handler with the new path
    handler_overrides = {"claude": {"user_path": user_claude_file}}
    for name, cls in PROMPT_HANDLERS.items():
        overrides = handler_overrides.get(name, {})
        cli_manager._handlers[name] = cls(
            user_path_override=overrides.get("user_path"),
            project_filename_override=overrides.get("project_filename"),
        )

    prompt = Prompt(id="test", name="Test", content="test content")
    cli_manager.create(prompt)

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.sync_prompts(
        prompt_id="test",
        app_type="claude",
        level="user",
        project_dir=None,
        enable=True,
    )

    assert user_claude_file.exists()
    assert user_claude_file.read_text() == "test content"

    stored = cli_manager.get("test")
    assert stored.enabled is True
    assert stored.app_type == "claude"
    assert any("enabled" in msg.lower() for msg in outputs)


def test_enable_prompt(cli_manager, tmp_path, monkeypatch):
    """enable command activates a prompt and syncs it."""
    from code_assistant_manager.prompts import PROMPT_HANDLERS

    # Setup user-level file path
    user_claude_file = tmp_path / "user_claude.md"

    # Update manager's handler with the new path
    for name, cls in PROMPT_HANDLERS.items():
        overrides = {"user_path": user_claude_file} if name == "claude" else {}
        cli_manager._handlers[name] = cls(
            user_path_override=overrides.get("user_path"),
        )

    prompt = Prompt(id="test-enable", name="Test Enable", content="enable content")
    cli_manager.create(prompt)

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.enable_prompt(
        prompt_id="test-enable",
        app_type="claude",
        level="user",
        project_dir=None,
    )

    assert user_claude_file.exists()
    assert user_claude_file.read_text() == "enable content"

    stored = cli_manager.get("test-enable")
    assert stored.enabled is True
    assert stored.app_type == "claude"
    assert any("enabled" in msg.lower() for msg in outputs)


def test_disable_prompt(cli_manager, tmp_path, monkeypatch):
    """disable command deactivates a prompt."""
    # Create and enable a prompt first
    prompt = Prompt(
        id="test-disable",
        name="Test Disable",
        content="disable content",
        enabled=True,
        app_type="claude",
    )
    cli_manager.create(prompt)

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.disable_prompt(prompt_id="test-disable")

    stored = cli_manager.get("test-disable")
    assert stored.enabled is False
    assert any("disabled" in msg.lower() for msg in outputs)


def test_disable_already_disabled_prompt(cli_manager, tmp_path, monkeypatch):
    """disable command shows warning for already disabled prompt."""
    prompt = Prompt(
        id="test-already-disabled",
        name="Already Disabled",
        content="content",
        enabled=False,
    )
    cli_manager.create(prompt)

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.disable_prompt(prompt_id="test-already-disabled")

    assert any("already disabled" in msg.lower() for msg in outputs)


def test_enable_prompt_invalid_app(cli_manager, tmp_path, monkeypatch):
    """enable command rejects invalid app types like copilot."""
    from click.exceptions import Exit

    prompt = Prompt(id="test-invalid-app", name="Test", content="content")
    cli_manager.create(prompt)

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    with pytest.raises(Exit):
        prompts_commands.enable_prompt(
            prompt_id="test-invalid-app",
            app_type="copilot",  # copilot doesn't support enable
            level="user",
            project_dir=None,
        )

    assert any("invalid" in msg.lower() for msg in outputs)

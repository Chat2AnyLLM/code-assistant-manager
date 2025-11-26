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


def _prepare_user_files(tmp_path, monkeypatch):
    """Patch user-level prompt paths to temporary files."""
    from code_assistant_manager import prompts as prompts_module

    user_files = {}
    for app in prompts_commands.VALID_APP_TYPES:
        file_path = tmp_path / f"user_{app}.md"
        file_path.write_text(f"user content {app}")
        user_files[app] = file_path

    monkeypatch.setattr(prompts_module, "USER_PROMPT_FILE_PATHS", user_files)
    monkeypatch.setattr(prompts_module, "PROMPT_FILE_PATHS", user_files)
    monkeypatch.setattr(prompts_commands, "PROMPT_FILE_PATHS", user_files)
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
    _prepare_user_files(tmp_path, monkeypatch)

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
    assert len(prompts) == len(prompts_commands.VALID_APP_TYPES) * len(
        prompts_commands.VALID_LEVELS
    )
    combined = "\n".join(outputs)
    for app in prompts_commands.VALID_APP_TYPES:
        assert app in combined
    assert "project" in combined
    assert "user" in combined


def test_show_live_all_apps_levels(cli_manager, tmp_path, monkeypatch):
    """show-live prints every app/level combo when 'all' specified."""
    _prepare_user_files(tmp_path, monkeypatch)

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
    for app in prompts_commands.VALID_APP_TYPES:
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
    from code_assistant_manager import prompts as prompts_module

    # Setup user-level file path
    user_claude_file = tmp_path / "user_claude.md"
    user_files = {"claude": user_claude_file}
    monkeypatch.setattr(prompts_module, "USER_PROMPT_FILE_PATHS", user_files)
    monkeypatch.setattr(prompts_module, "PROMPT_FILE_PATHS", user_files)

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

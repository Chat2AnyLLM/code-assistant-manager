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
    )

    prompt_file = project_dir / "CLAUDE.md"
    assert prompt_file.exists()
    assert prompt_file.read_text() == "project-level content"

    stored = cli_manager.get("cli")
    assert any("CLAUDE.md" in msg for msg in outputs)


def test_sync_default_prompt(cli_manager, tmp_path, monkeypatch):
    """sync without prompt_id syncs the default prompt."""
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
    cli_manager.set_default("test")

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.sync_prompts(
        prompt_id=None,
        app_type="claude",
        level="user",
        project_dir=None,
    )

    assert user_claude_file.exists()
    assert user_claude_file.read_text() == "test content"

    stored = cli_manager.get("test")
    assert stored.is_default is True
    assert any("synced" in msg.lower() for msg in outputs)


# Additional tests for uncovered functions


def test_list_prompts_empty(cli_manager, monkeypatch):
    """list_prompts shows message when no prompts exist."""
    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.list_prompts()

    combined = "\n".join(outputs)
    assert "No prompts found" in combined


def test_list_prompts_with_prompts(cli_manager, monkeypatch):
    """list_prompts shows all prompts with their status."""
    prompt1 = Prompt(id="p1", name="Prompt One", content="content 1")
    prompt2 = Prompt(
        id="p2", name="Prompt Two", content="content 2", description="A description"
    )
    cli_manager.create(prompt1)
    cli_manager.create(prompt2)
    cli_manager.set_default("p1")

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.list_prompts()

    combined = "\n".join(outputs)
    assert "Prompt One" in combined
    assert "Prompt Two" in combined
    assert "default" in combined
    assert "p1" in combined
    assert "p2" in combined
    assert "A description" in combined


def test_view_prompt_success(cli_manager, monkeypatch):
    """view_prompt displays prompt content."""
    prompt = Prompt(
        id="test",
        name="Test Prompt",
        content="This is the content",
        description="A test description",
    )
    cli_manager.create(prompt)

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.view_prompt("test")

    combined = "\n".join(outputs)
    assert "Test Prompt" in combined
    assert "This is the content" in combined
    assert "A test description" in combined


def test_view_prompt_not_found(cli_manager, monkeypatch):
    """view_prompt raises exit when prompt not found."""
    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    with pytest.raises(prompts_commands.typer.Exit):
        prompts_commands.view_prompt("nonexistent")

    combined = "\n".join(outputs)
    assert "not found" in combined


def test_create_prompt_from_file(cli_manager, tmp_path, monkeypatch):
    """create_prompt reads content from file."""
    content_file = tmp_path / "content.md"
    content_file.write_text("File content")

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.create_prompt(
        prompt_id="new-prompt",
        name="New Prompt",
        description="From file",
        file=content_file,
    )

    prompt = cli_manager.get("new-prompt")
    assert prompt is not None
    assert prompt.content == "File content"
    assert prompt.name == "New Prompt"
    assert prompt.description == "From file"


def test_create_prompt_empty_content(cli_manager, tmp_path, monkeypatch):
    """create_prompt fails with empty content."""
    content_file = tmp_path / "empty.md"
    content_file.write_text("")

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    with pytest.raises(prompts_commands.typer.Exit):
        prompts_commands.create_prompt(
            prompt_id="empty-prompt",
            name="Empty Prompt",
            description=None,
            file=content_file,
        )

    combined = "\n".join(outputs)
    assert "cannot be empty" in combined


def test_update_prompt_success(cli_manager, tmp_path, monkeypatch):
    """update_prompt updates existing prompt."""
    prompt = Prompt(id="upd", name="Original", content="original content")
    cli_manager.create(prompt)

    new_content_file = tmp_path / "new_content.md"
    new_content_file.write_text("updated content")

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.update_prompt(
        prompt_id="upd",
        name="Updated Name",
        description="Updated desc",
        file=new_content_file,
    )

    updated = cli_manager.get("upd")
    assert updated.name == "Updated Name"
    assert updated.description == "Updated desc"
    assert updated.content == "updated content"
    assert any("updated" in msg.lower() for msg in outputs)


def test_update_prompt_not_found(cli_manager, monkeypatch):
    """update_prompt fails when prompt not found."""
    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    with pytest.raises(prompts_commands.typer.Exit):
        prompts_commands.update_prompt(
            prompt_id="nonexistent",
            name="New Name",
            description=None,
            file=None,
        )

    combined = "\n".join(outputs)
    assert "not found" in combined


def test_delete_prompt_success(cli_manager, monkeypatch):
    """delete_prompt removes prompt with force flag."""
    prompt = Prompt(id="del", name="To Delete", content="content")
    cli_manager.create(prompt)

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.delete_prompt(prompt_id="del", force=True)

    assert cli_manager.get("del") is None
    assert any("deleted" in msg.lower() for msg in outputs)


def test_delete_prompt_not_found(cli_manager, monkeypatch):
    """delete_prompt fails when prompt not found."""
    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    with pytest.raises(prompts_commands.typer.Exit):
        prompts_commands.delete_prompt(prompt_id="nonexistent", force=True)

    combined = "\n".join(outputs)
    assert "not found" in combined


def test_set_default_prompt_success(cli_manager, monkeypatch):
    """set_default_prompt sets a prompt as default."""
    prompt = Prompt(id="def", name="Default", content="content")
    cli_manager.create(prompt)

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.set_default_prompt(prompt_id="def")

    updated = cli_manager.get("def")
    assert updated.is_default is True
    assert any("default" in msg.lower() for msg in outputs)


def test_set_default_prompt_not_found(cli_manager, monkeypatch):
    """set_default_prompt fails when prompt not found."""
    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    with pytest.raises(prompts_commands.typer.Exit):
        prompts_commands.set_default_prompt(prompt_id="nonexistent")

    combined = "\n".join(outputs)
    assert "not found" in combined


def test_clear_default_prompt(cli_manager, monkeypatch):
    """clear_default_prompt clears the default setting."""
    prompt = Prompt(id="def", name="Default", content="content")
    cli_manager.create(prompt)
    cli_manager.set_default("def")

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.clear_default_prompt()

    updated = cli_manager.get("def")
    assert updated.is_default is False
    assert any("cleared" in msg.lower() for msg in outputs)


def test_generate_prompt_id():
    """generate_prompt_id creates unique IDs with prefix."""
    id1 = prompts_commands.generate_prompt_id("test")
    id2 = prompts_commands.generate_prompt_id("test")

    assert id1.startswith("test-")
    assert id2.startswith("test-")
    assert id1 != id2  # Should be unique
    assert len(id1) == len("test-") + 8  # 8 char hex UUID


def test_parse_app_list_all():
    """_parse_app_list returns all apps when 'all' specified."""
    apps = prompts_commands._parse_app_list("all")
    assert apps == prompts_commands.VALID_APP_TYPES


def test_parse_app_list_comma_separated():
    """_parse_app_list parses comma-separated apps."""
    apps = prompts_commands._parse_app_list("claude,codex")
    assert apps == ["claude", "codex"]


def test_parse_app_list_invalid():
    """_parse_app_list raises error for invalid apps."""
    with pytest.raises(prompts_commands.typer.BadParameter) as exc_info:
        prompts_commands._parse_app_list("invalid,claude")

    assert "invalid" in str(exc_info.value).lower()


def test_unsync_prompt_project_level(cli_manager, tmp_path, monkeypatch):
    """unsync_prompt clears project-level prompt file content."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    prompt_file = project_dir / "CLAUDE.md"
    prompt_file.write_text("Content to unsync")

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.unsync_prompt(
        app_type="claude",
        level="project",
        force=True,
        project_dir=project_dir,
    )

    # unsync clears the file content, not deletes it
    assert prompt_file.exists()
    assert prompt_file.read_text() == ""
    combined = "\n".join(outputs)
    assert "cleared" in combined.lower()


def test_unsync_prompt_file_not_found(cli_manager, tmp_path, monkeypatch):
    """unsync_prompt handles missing file gracefully."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    outputs = []
    monkeypatch.setattr(
        prompts_commands.typer, "echo", lambda msg="": outputs.append(str(msg))
    )

    prompts_commands.unsync_prompt(
        app_type="claude",
        level="project",
        force=True,
        project_dir=project_dir,
    )

    combined = "\n".join(outputs)
    # Should indicate file doesn't exist
    assert "not exist" in combined.lower() or "does not exist" in combined.lower()

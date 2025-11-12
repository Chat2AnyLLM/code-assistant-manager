"""CLI tests for skill commands."""

from pathlib import Path

import pytest

import code_assistant_manager.cli.skills_commands as skills_commands


@pytest.fixture
def dummy_skill_manager(monkeypatch, tmp_path):
    """Stub SkillManager for CLI tests."""

    class DummyManager:
        def __init__(self):
            self.synced = []
            self.installs = []
            self.uninstalls = []
            self.skills = {}

        def sync_installed_status(self, app):
            self.synced.append(app)

        def get_all(self):
            return self.skills

        def install(self, key, app):
            self.installs.append((key, app))

        def uninstall(self, key, app):
            self.uninstalls.append((key, app))

    manager = DummyManager()
    monkeypatch.setattr(skills_commands, "_get_skill_manager", lambda: manager)
    return manager


def test_skill_list_all_apps(dummy_skill_manager):
    skills_commands.list_skills(app_type="all")
    assert dummy_skill_manager.synced == skills_commands.VALID_APP_TYPES


def test_skill_install_multiple_apps(dummy_skill_manager, tmp_path, monkeypatch):
    install_dirs = {app: tmp_path / app for app in skills_commands.VALID_APP_TYPES}
    for directory in install_dirs.values():
        directory.mkdir()
    monkeypatch.setattr(skills_commands, "SKILL_INSTALL_DIRS", install_dirs)

    skills_commands.install_skill("demo-skill", app_type="claude,codex")
    assert dummy_skill_manager.installs == [
        ("demo-skill", "claude"),
        ("demo-skill", "codex"),
    ]


def test_skill_installed_all_apps(monkeypatch, tmp_path, capsys):
    install_dirs = {}
    for app in skills_commands.VALID_APP_TYPES:
        app_dir = tmp_path / app
        app_dir.mkdir()
        (app_dir / "example").mkdir()
        install_dirs[app] = app_dir

    monkeypatch.setattr(skills_commands, "SKILL_INSTALL_DIRS", install_dirs)

    class Manager:
        def get_all(self):
            return {}

    monkeypatch.setattr(skills_commands, "_get_skill_manager", lambda: Manager())

    skills_commands.list_installed_skills(app_type="all")
    captured = capsys.readouterr().out
    for app in skills_commands.VALID_APP_TYPES:
        assert f"{app.capitalize()}" in captured

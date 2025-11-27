"""Skill management for Code Assistant Manager.

This module provides functionality to manage skills for AI coding assistants.
Skills are downloaded from GitHub repositories and installed to:
- Claude: ~/.claude/skills/
- Codex: ~/.codex/skills/
- Gemini: ~/.gemini/skills/
"""

import io
import json
import logging
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

logger = logging.getLogger(__name__)


def _load_builtin_skill_repos() -> List[Dict]:
    """Load built-in skill repos from the bundled skill_repos.json file."""
    # Look for skill_repos.json in the package directory
    package_dir = Path(__file__).parent
    repos_file = package_dir / "skill_repos.json"

    if repos_file.exists():
        try:
            with open(repos_file, "r", encoding="utf-8") as f:
                repos_data = json.load(f)
                # Convert from dict format to list format
                return [
                    {
                        "owner": repo.get("owner"),
                        "name": repo.get("name"),
                        "branch": repo.get("branch", "main"),
                        "enabled": repo.get("enabled", True),
                        "skillsPath": repo.get("skillsPath"),
                    }
                    for repo in repos_data.values()
                ]
        except Exception as e:
            logger.warning(f"Failed to load builtin skill repos: {e}")

    # Fallback defaults if file not found
    return [
        {
            "owner": "ComposioHQ",
            "name": "awesome-claude-skills",
            "branch": "main",
            "enabled": True,
            "skillsPath": None,
        },
        {
            "owner": "obra",
            "name": "superpowers",
            "branch": "main",
            "enabled": True,
            "skillsPath": "skills",
        },
    ]


# Default skill repositories loaded from bundled file
DEFAULT_SKILL_REPOS = _load_builtin_skill_repos()

# Skill install directories for each app type
SKILL_INSTALL_DIRS = {
    "claude": Path.home() / ".claude" / "skills",
    "codex": Path.home() / ".codex" / "skills",
    "gemini": Path.home() / ".gemini" / "skills",
    "droid": Path.home() / ".factory" / "skills",
}


class Skill:
    """Represents a skill configuration."""

    def __init__(
        self,
        key: str,
        name: str,
        description: str,
        directory: str,
        installed: bool = False,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        repo_branch: Optional[str] = None,
        skills_path: Optional[str] = None,
        readme_url: Optional[str] = None,
        source_directory: Optional[str] = None,
    ):
        self.key = key
        self.name = name
        self.description = description
        self.directory = directory
        self.installed = installed
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.repo_branch = repo_branch or "main"
        self.skills_path = skills_path
        self.readme_url = readme_url
        # source_directory stores full path in repo; directory is just the skill folder name for installation
        self.source_directory = source_directory

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "directory": self.directory,
            "installed": self.installed,
        }
        if self.repo_owner:
            data["repoOwner"] = self.repo_owner
        if self.repo_name:
            data["repoName"] = self.repo_name
        if self.repo_branch:
            data["repoBranch"] = self.repo_branch
        if self.skills_path:
            data["skillsPath"] = self.skills_path
        if self.readme_url:
            data["readmeUrl"] = self.readme_url
        if self.source_directory:
            data["sourceDirectory"] = self.source_directory
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "Skill":
        """Create from dictionary."""
        return cls(
            key=data["key"],
            name=data["name"],
            description=data["description"],
            directory=data["directory"],
            installed=data.get("installed", False),
            repo_owner=data.get("repoOwner"),
            repo_name=data.get("repoName"),
            repo_branch=data.get("repoBranch"),
            skills_path=data.get("skillsPath"),
            readme_url=data.get("readmeUrl"),
            source_directory=data.get("sourceDirectory"),
        )


class SkillRepo:
    """Represents a skill repository."""

    def __init__(
        self,
        owner: str,
        name: str,
        branch: str = "main",
        enabled: bool = True,
        skills_path: Optional[str] = None,
    ):
        self.owner = owner
        self.name = name
        self.branch = branch
        self.enabled = enabled
        self.skills_path = skills_path

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = {
            "owner": self.owner,
            "name": self.name,
            "branch": self.branch,
            "enabled": self.enabled,
        }
        if self.skills_path:
            data["skillsPath"] = self.skills_path
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "SkillRepo":
        """Create from dictionary."""
        return cls(
            owner=data["owner"],
            name=data["name"],
            branch=data.get("branch", "main"),
            enabled=data.get("enabled", True),
            skills_path=data.get("skillsPath"),
        )


class SkillManager:
    """Manages skills storage and retrieval."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize skill manager."""
        if config_dir is None:
            config_dir = Path.home() / ".config" / "code-assistant-manager"
        self.config_dir = Path(config_dir)
        self.skills_file = self.config_dir / "skills.json"
        self.repos_file = self.config_dir / "skill_repos.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_skills(self) -> Dict[str, Skill]:
        """Load skills from file."""
        if not self.skills_file.exists():
            return {}

        try:
            with open(self.skills_file, "r") as f:
                data = json.load(f)
            return {
                skill_key: Skill.from_dict(skill_data)
                for skill_key, skill_data in data.items()
            }
        except Exception as e:
            logger.warning(f"Failed to load skills: {e}")
            return {}

    def _save_skills(self, skills: Dict[str, Skill]) -> None:
        """Save skills to file."""
        try:
            data = {skill_key: skill.to_dict() for skill_key, skill in skills.items()}
            with open(self.skills_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(skills)} skills to {self.skills_file}")
        except Exception as e:
            logger.error(f"Failed to save skills: {e}")
            raise

    def _load_repos(self) -> Dict[str, SkillRepo]:
        """Load skill repos from file. Initializes with defaults if file doesn't exist."""
        if not self.repos_file.exists():
            # Initialize with default repos on first use
            self._init_default_repos_file()

        try:
            with open(self.repos_file, "r") as f:
                data = json.load(f)
            return {
                repo_id: SkillRepo.from_dict(repo_data)
                for repo_id, repo_data in data.items()
            }
        except Exception as e:
            logger.warning(f"Failed to load skill repos: {e}")
            return {}

    def _init_default_repos_file(self) -> None:
        """Initialize the repos file with default skill repos."""
        repos = {}
        for repo_data in DEFAULT_SKILL_REPOS:
            repo = SkillRepo(
                owner=repo_data["owner"],
                name=repo_data["name"],
                branch=repo_data.get("branch", "main"),
                enabled=repo_data.get("enabled", True),
                skills_path=repo_data.get("skillsPath"),
            )
            repo_id = f"{repo.owner}/{repo.name}"
            repos[repo_id] = repo

        self._save_repos(repos)
        logger.info(f"Initialized {len(repos)} default skill repos")

    def _save_repos(self, repos: Dict[str, SkillRepo]) -> None:
        """Save skill repos to file."""
        try:
            data = {repo_id: repo.to_dict() for repo_id, repo in repos.items()}
            with open(self.repos_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(repos)} skill repos to {self.repos_file}")
        except Exception as e:
            logger.error(f"Failed to save skill repos: {e}")
            raise

    def get_all(self) -> Dict[str, Skill]:
        """Get all skills."""
        return self._load_skills()

    def get(self, skill_key: str) -> Optional[Skill]:
        """Get a specific skill."""
        skills = self._load_skills()
        return skills.get(skill_key)

    def create(self, skill: Skill) -> None:
        """Create a new skill."""
        skills = self._load_skills()
        if skill.key in skills:
            raise ValueError(f"Skill with key '{skill.key}' already exists")
        skills[skill.key] = skill
        self._save_skills(skills)
        logger.info(f"Created skill: {skill.key}")

    def update(self, skill: Skill) -> None:
        """Update an existing skill."""
        skills = self._load_skills()
        if skill.key not in skills:
            raise ValueError(f"Skill with key '{skill.key}' not found")
        skills[skill.key] = skill
        self._save_skills(skills)
        logger.info(f"Updated skill: {skill.key}")

    def upsert(self, skill: Skill) -> None:
        """Create or update a skill."""
        skills = self._load_skills()
        skills[skill.key] = skill
        self._save_skills(skills)
        logger.info(f"Upserted skill: {skill.key}")

    def delete(self, skill_key: str) -> None:
        """Delete a skill."""
        skills = self._load_skills()
        if skill_key not in skills:
            raise ValueError(f"Skill with key '{skill_key}' not found")
        del skills[skill_key]
        self._save_skills(skills)
        logger.info(f"Deleted skill: {skill_key}")

    def install(self, skill_key: str, app_type: str = "claude") -> None:
        """
        Install a skill by downloading from GitHub and copying to the app's skills directory.

        Args:
            skill_key: The skill identifier
            app_type: The app type to install to (claude, codex, gemini)
        """
        skills = self._load_skills()
        if skill_key not in skills:
            raise ValueError(f"Skill with key '{skill_key}' not found")

        skill = skills[skill_key]

        # Get the install directory for the app type
        install_dir = SKILL_INSTALL_DIRS.get(app_type)
        if not install_dir:
            raise ValueError(f"Unknown app type: {app_type}")

        # Ensure install directory exists
        install_dir.mkdir(parents=True, exist_ok=True)

        # Download and install the skill
        if skill.repo_owner and skill.repo_name:
            self._download_and_install_skill(skill, install_dir)
        else:
            raise ValueError(f"Skill '{skill_key}' has no repository information")

        # Mark as installed
        skill.installed = True
        self._save_skills(skills)
        logger.info(f"Installed skill: {skill_key} to {install_dir}")

    def uninstall(self, skill_key: str, app_type: str = "claude") -> None:
        """
        Uninstall a skill by removing it from the app's skills directory.

        Args:
            skill_key: The skill identifier
            app_type: The app type to uninstall from (claude, codex, gemini)
        """
        skills = self._load_skills()
        if skill_key not in skills:
            raise ValueError(f"Skill with key '{skill_key}' not found")

        skill = skills[skill_key]

        # Get the install directory for the app type
        install_dir = SKILL_INSTALL_DIRS.get(app_type)
        if not install_dir:
            raise ValueError(f"Unknown app type: {app_type}")

        # Remove the skill directory
        skill_dir = install_dir / skill.directory
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
            logger.info(f"Removed skill directory: {skill_dir}")

        # Mark as uninstalled
        skill.installed = False
        self._save_skills(skills)
        logger.info(f"Uninstalled skill: {skill_key}")

    def _download_and_install_skill(self, skill: Skill, install_dir: Path) -> None:
        """
        Download a skill from GitHub and install it to the specified directory.

        Args:
            skill: The skill to download
            install_dir: The directory to install to
        """
        if not skill.repo_owner or not skill.repo_name:
            raise ValueError("Skill has no repository information")

        branch = skill.repo_branch or "main"

        # Try downloading the repo
        temp_dir, actual_branch = self._download_repo(
            skill.repo_owner, skill.repo_name, branch
        )

        try:
            # Determine the source path within the downloaded repo
            # Use source_directory if available (full path in repo), otherwise fall back to directory
            source_dir = skill.source_directory or skill.directory
            if skill.skills_path:
                source_path = temp_dir / skill.skills_path.strip("/") / source_dir
            else:
                source_path = temp_dir / source_dir

            if not source_path.exists():
                raise ValueError(
                    f"Skill directory not found in repository: {source_path}"
                )

            # Copy to install directory using just the skill folder name (directory field)
            dest_path = install_dir / skill.directory
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(source_path, dest_path)
            logger.info(f"Installed skill to: {dest_path}")
        finally:
            # Clean up temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def _download_repo(self, owner: str, name: str, branch: str) -> Tuple[Path, str]:
        """
        Download a GitHub repository as a zip file and extract it.

        Args:
            owner: Repository owner
            name: Repository name
            branch: Branch name

        Returns:
            Tuple of (Path to the extracted directory, actual branch name used)
        """
        # Try multiple branch names - always try main and master as fallbacks
        if branch == "main":
            branches = ["main", "master"]
        elif branch == "master":
            branches = ["master", "main"]
        else:
            branches = [branch, "main", "master"]

        for try_branch in branches:
            url = (
                f"https://github.com/{owner}/{name}/archive/refs/heads/{try_branch}.zip"
            )
            logger.debug(f"Trying to download: {url}")

            try:
                req = Request(url, headers={"User-Agent": "code-assistant-manager"})
                with urlopen(req, timeout=60) as response:
                    zip_data = response.read()

                # Create temp directory
                temp_dir = Path(tempfile.mkdtemp(prefix="cam-skill-"))

                # Extract the zip file
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                    # GitHub zips have a root directory like "repo-name-branch"
                    root_dir = None
                    for name_in_zip in zf.namelist():
                        parts = name_in_zip.split("/")
                        if len(parts) > 1 and not root_dir:
                            root_dir = parts[0]

                        # Extract with adjusted path
                        if root_dir and name_in_zip.startswith(root_dir + "/"):
                            rel_path = name_in_zip[len(root_dir) + 1 :]
                            if not rel_path:
                                continue

                            target_path = temp_dir / rel_path
                            if name_in_zip.endswith("/"):
                                target_path.mkdir(parents=True, exist_ok=True)
                            else:
                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                with (
                                    zf.open(name_in_zip) as src,
                                    open(target_path, "wb") as dst,
                                ):
                                    dst.write(src.read())

                logger.info(f"Downloaded repository {owner}/{name}@{try_branch}")
                return temp_dir, try_branch

            except HTTPError as e:
                if e.code == 404:
                    logger.debug(f"Branch {try_branch} not found, trying next")
                    continue
                raise
            except URLError as e:
                logger.error(f"Failed to download repository: {e}")
                raise

        raise ValueError(
            f"Could not download repository {owner}/{name} - no valid branch found"
        )

    def get_repos(self) -> List[SkillRepo]:
        """Get all skill repos."""
        repos = self._load_repos()
        return list(repos.values())

    def add_repo(self, repo: SkillRepo) -> None:
        """Add a skill repo."""
        repos = self._load_repos()
        repo_id = f"{repo.owner}/{repo.name}"
        repos[repo_id] = repo
        self._save_repos(repos)
        logger.info(f"Added skill repo: {repo_id}")

    def remove_repo(self, owner: str, name: str) -> None:
        """Remove a skill repo."""
        repos = self._load_repos()
        repo_id = f"{owner}/{name}"
        if repo_id not in repos:
            raise ValueError(f"Skill repo '{repo_id}' not found")
        del repos[repo_id]
        self._save_repos(repos)
        logger.info(f"Removed skill repo: {repo_id}")

    def import_from_file(self, file_path: Path) -> None:
        """Import skills from a JSON file."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            skills = self._load_skills()
            imported_count = 0

            if isinstance(data, dict):
                # Format: {"key": {...}, "key2": {...}}
                for skill_key, skill_data in data.items():
                    if isinstance(skill_data, dict):
                        skill = Skill.from_dict(skill_data)
                        skills[skill.key] = skill
                        imported_count += 1
            elif isinstance(data, list):
                # Format: [{...}, {...}]
                for skill_data in data:
                    if isinstance(skill_data, dict):
                        skill = Skill.from_dict(skill_data)
                        skills[skill.key] = skill
                        imported_count += 1

            self._save_skills(skills)
            logger.info(f"Imported {imported_count} skills from {file_path}")
        except Exception as e:
            logger.error(f"Failed to import skills: {e}")
            raise

    def export_to_file(self, file_path: Path) -> None:
        """Export skills to a JSON file."""
        try:
            skills = self._load_skills()
            data = {skill_key: skill.to_dict() for skill_key, skill in skills.items()}
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Exported {len(skills)} skills to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export skills: {e}")
            raise

    def init_default_repos(self) -> None:
        """Initialize default skill repositories if none exist."""
        repos = self._load_repos()
        if not repos:
            for repo_data in DEFAULT_SKILL_REPOS:
                repo = SkillRepo.from_dict(repo_data)
                repo_id = f"{repo.owner}/{repo.name}"
                repos[repo_id] = repo
            self._save_repos(repos)
            logger.info(f"Initialized {len(DEFAULT_SKILL_REPOS)} default skill repos")

    def fetch_skills_from_repos(self) -> List[Skill]:
        """
        Fetch all skills from configured repositories.

        Returns:
            List of discovered skills
        """
        repos = self._load_repos()
        if not repos:
            # Initialize default repos if none exist
            self.init_default_repos()
            repos = self._load_repos()

        all_skills = []
        existing_skills = self._load_skills()

        for repo_id, repo in repos.items():
            if not repo.enabled:
                logger.debug(f"Skipping disabled repo: {repo_id}")
                continue

            try:
                skills = self._fetch_skills_from_repo(repo)
                for skill in skills:
                    # Check if already installed locally
                    if skill.key in existing_skills:
                        skill.installed = existing_skills[skill.key].installed
                    all_skills.append(skill)
                logger.info(f"Found {len(skills)} skills in {repo_id}")
            except Exception as e:
                logger.warning(f"Failed to fetch skills from {repo_id}: {e}")

        # Merge with existing skills and save
        for skill in all_skills:
            existing_skills[skill.key] = skill
        self._save_skills(existing_skills)

        return all_skills

    def _fetch_skills_from_repo(self, repo: SkillRepo) -> List[Skill]:
        """
        Fetch skills from a single repository.

        Args:
            repo: The repository to fetch from

        Returns:
            List of skills found in the repository
        """
        temp_dir, actual_branch = self._download_repo(
            repo.owner, repo.name, repo.branch
        )
        skills = []

        try:
            # Determine the scan directory
            if repo.skills_path:
                scan_dir = temp_dir / repo.skills_path.strip("/")
            else:
                scan_dir = temp_dir

            if not scan_dir.exists():
                logger.warning(f"Skills path not found: {scan_dir}")
                return skills

            # Scan for SKILL.md files recursively
            for skill_md in scan_dir.rglob("SKILL.md"):
                skill_dir = skill_md.parent
                if not skill_dir.is_dir():
                    continue

                # Parse skill metadata from SKILL.md
                meta = self._parse_skill_metadata(skill_md)

                try:
                    # Calculate relative path from scan_dir (full path in repo relative to skills_path)
                    rel_path = skill_dir.relative_to(scan_dir)
                    source_directory = str(rel_path).replace("\\", "/")

                    # Skip if SKILL.md is at the root of scan_dir (directory == ".")
                    # to avoid conflicts when installing to the root of skills directory
                    if source_directory == ".":
                        continue

                    # The install directory is just the skill folder name (last part of path)
                    directory = skill_dir.name
                except ValueError:
                    continue

                # Build README URL using actual branch
                path_from_repo_root = skill_dir.relative_to(temp_dir)
                readme_path = str(path_from_repo_root).replace("\\", "/")

                skill = Skill(
                    key=f"{repo.owner}/{repo.name}:{source_directory}",
                    name=meta.get("name", directory),
                    description=meta.get("description", ""),
                    directory=directory,
                    installed=False,
                    repo_owner=repo.owner,
                    repo_name=repo.name,
                    repo_branch=actual_branch,
                    skills_path=repo.skills_path,
                    readme_url=f"https://github.com/{repo.owner}/{repo.name}/tree/{actual_branch}/{readme_path}",
                    source_directory=source_directory,
                )
                skills.append(skill)
                logger.debug(f"Found skill: {skill.key}")
        finally:
            # Clean up temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

        return skills

    def _parse_skill_metadata(self, skill_md_path: Path) -> Dict:
        """
        Parse skill metadata from SKILL.md file.

        Args:
            skill_md_path: Path to the SKILL.md file

        Returns:
            Dictionary with name and description
        """
        try:
            content = skill_md_path.read_text(encoding="utf-8")
            # Remove BOM if present
            content = content.lstrip("\ufeff")

            # Extract YAML front matter
            parts = content.split("---", 2)
            if len(parts) >= 3:
                front_matter = parts[1].strip()
                try:
                    meta = yaml.safe_load(front_matter)
                    if isinstance(meta, dict):
                        return {
                            "name": meta.get("name"),
                            "description": meta.get("description", ""),
                        }
                except yaml.YAMLError as e:
                    logger.debug(f"Failed to parse YAML front matter: {e}")
        except Exception as e:
            logger.debug(f"Failed to read SKILL.md: {e}")

        return {}

    def get_installed_skills(self, app_type: str = "claude") -> List[Skill]:
        """
        Get all installed skills for a specific app type by scanning the install directory.

        Args:
            app_type: The app type (claude, codex, gemini)

        Returns:
            List of installed skills
        """
        install_dir = SKILL_INSTALL_DIRS.get(app_type)
        if not install_dir or not install_dir.exists():
            return []

        installed_skills = []
        existing_skills = self._load_skills()

        # Scan recursively for SKILL.md
        for skill_md in install_dir.rglob("SKILL.md"):
            skill_dir = skill_md.parent
            if not skill_dir.is_dir():
                continue

            try:
                rel_path = skill_dir.relative_to(install_dir)
                directory = str(rel_path).replace("\\", "/")
            except ValueError:
                continue

            # Check if we have this skill in our database
            matching_skill = None
            for skill_key, skill in existing_skills.items():
                if skill.directory.lower() == directory.lower():
                    matching_skill = skill
                    break

            if matching_skill:
                matching_skill.installed = True
                installed_skills.append(matching_skill)
            else:
                # Local skill not in our database
                meta = self._parse_skill_metadata(skill_md)
                skill = Skill(
                    key=f"local:{directory}",
                    name=meta.get("name", directory.split("/")[-1]),
                    description=meta.get("description", ""),
                    directory=directory,
                    installed=True,
                )
                installed_skills.append(skill)

        return installed_skills

    def sync_installed_status(self, app_type: str = "claude") -> None:
        """
        Sync the installed status of all skills based on what's actually installed.

        Args:
            app_type: The app type (claude, codex, gemini)
        """
        install_dir = SKILL_INSTALL_DIRS.get(app_type)
        if not install_dir:
            return

        installed_dirs = set()
        if install_dir.exists():
            # Scan recursively for SKILL.md
            for skill_md in install_dir.rglob("SKILL.md"):
                try:
                    skill_dir = skill_md.parent
                    rel_path = skill_dir.relative_to(install_dir)
                    installed_dirs.add(str(rel_path).replace("\\", "/").lower())
                except ValueError:
                    continue

        skills = self._load_skills()
        for skill in skills.values():
            skill.installed = skill.directory.lower() in installed_dirs
        self._save_skills(skills)
        logger.debug(f"Synced installed status for {len(skills)} skills")

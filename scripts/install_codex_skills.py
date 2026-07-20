#!/usr/bin/env python3
"""Install Codex-compatible copies of the skills in this repository.

The source skills intentionally use Claude Code extensions such as ``model``,
``context``, and ``${CLAUDE_SKILL_DIR}``. Codex follows the portable Agent
Skills frontmatter contract, so this script creates derived copies instead of
symlinking the Claude-specific sources directly.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path.home() / ".agents" / "skills"
MARKER_NAME = ".codex-skill-sync.json"
PORTABLE_FRONTMATTER_KEYS = {
    "allowed-tools",
    "description",
    "license",
    "metadata",
    "name",
}
TOP_LEVEL_KEY = re.compile(r"^([A-Za-z0-9_-]+):(?:\s|$)")
IGNORED_NAMES = {
    ".DS_Store",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}


class InstallError(RuntimeError):
    """Raised when an installation cannot be completed safely."""


def discover_skills(repo_root: Path = REPO_ROOT) -> dict[str, Path]:
    """Return top-level skill directories keyed by their directory name."""

    return {
        child.name: child
        for child in sorted(repo_root.iterdir())
        if child.is_dir() and (child / "SKILL.md").is_file()
    }


def _split_frontmatter(text: str) -> tuple[list[str], list[str]]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise InstallError("SKILL.md must start with YAML frontmatter")

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], lines[index + 1 :]

    raise InstallError("SKILL.md frontmatter is missing its closing ---")


def portable_skill_text(text: str, installed_skill_dir: Path) -> str:
    """Strip Claude-only frontmatter and resolve Claude's skill-dir variable."""

    frontmatter, body = _split_frontmatter(text)
    kept: list[str] = []
    keep_section = True
    seen_keys: set[str] = set()

    for line in frontmatter:
        match = TOP_LEVEL_KEY.match(line)
        if match:
            key = match.group(1)
            seen_keys.add(key)
            keep_section = key in PORTABLE_FRONTMATTER_KEYS
        if keep_section:
            kept.append(line)

    missing = {"name", "description"} - seen_keys
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise InstallError(f"SKILL.md is missing required frontmatter: {missing_list}")

    rendered = "---\n" + "".join(kept) + "---\n" + "".join(body)
    return rendered.replace("${CLAUDE_SKILL_DIR}", str(installed_skill_dir))


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in IGNORED_NAMES or name.endswith((".pyc", ".pyo"))
    }


def _read_marker(destination: Path) -> dict[str, str] | None:
    marker = destination / MARKER_NAME
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _destination_is_managed(destination: Path, source: Path) -> bool:
    marker = _read_marker(destination)
    if marker is None:
        return False
    return (
        marker.get("source") == str(source.resolve())
        and marker.get("installer") == "claude-skills-to-codex"
    )


def sync_skill(source: Path, target_root: Path, *, dry_run: bool = False) -> str:
    """Create or refresh one managed portable copy and return its action."""

    destination = target_root / source.name
    action = "update" if destination.exists() else "install"

    if destination.exists() and not _destination_is_managed(destination, source):
        raise InstallError(
            f"refusing to replace unmanaged destination: {destination}\n"
            "Move it aside or remove it after reviewing its contents, then rerun."
        )

    if dry_run:
        return action

    target_root.mkdir(parents=True, exist_ok=True)
    temporary = target_root / f".{source.name}.{uuid.uuid4().hex}.tmp"
    backup = target_root / f".{source.name}.{uuid.uuid4().hex}.bak"

    try:
        shutil.copytree(source, temporary, ignore=_copy_ignore)
        skill_file = temporary / "SKILL.md"
        portable = portable_skill_text(
            skill_file.read_text(encoding="utf-8"), destination.resolve()
        )
        skill_file.write_text(portable, encoding="utf-8")
        marker = {
            "installer": "claude-skills-to-codex",
            "source": str(source.resolve()),
            "skill": source.name,
        }
        (temporary / MARKER_NAME).write_text(
            json.dumps(marker, indent=2) + "\n", encoding="utf-8"
        )

        if destination.exists():
            destination.rename(backup)
        temporary.rename(destination)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if destination.exists() and backup.exists():
            shutil.rmtree(destination)
        if backup.exists():
            backup.rename(destination)
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    return action


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Install portable Codex copies of this repository's Claude Code skills."
        )
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
        help="Codex user-skill directory (default: ~/.agents/skills)",
    )
    parser.add_argument(
        "--skill",
        action="append",
        dest="skills",
        metavar="NAME",
        help="Install only this skill; repeat to select more than one",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List source skills and exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    available = discover_skills()

    if args.list:
        for name in available:
            print(name)
        return 0

    selected = args.skills or list(available)
    unknown = sorted(set(selected) - set(available))
    if unknown:
        parser.error("unknown skill(s): " + ", ".join(unknown))

    target = args.target.expanduser().resolve()
    try:
        for name in dict.fromkeys(selected):
            action = sync_skill(available[name], target, dry_run=args.dry_run)
            prefix = "would " if args.dry_run else ""
            print(f"{prefix}{action}: {name} -> {target / name}")
    except InstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

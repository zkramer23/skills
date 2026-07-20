from __future__ import annotations

import json
from pathlib import Path

import pytest

from install_codex_skills import (
    MARKER_NAME,
    InstallError,
    portable_skill_text,
    sync_skill,
)


def make_source(root: Path, body: str = "Run ${CLAUDE_SKILL_DIR}/scripts/tool.py\n") -> Path:
    source = root / "demo-skill"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    (source / "SKILL.md").write_text(
        """---
name: demo-skill
description: >-
  Demonstrate portable installation.
argument-hint: "<input>"
model: sonnet
context: fork
metadata:
  owner: personal
---
"""
        + body,
        encoding="utf-8",
    )
    return source


def test_portable_skill_text_strips_claude_extensions() -> None:
    source = """---
name: demo
description: >-
  A multiline description.
argument-hint: "<file>"
model: opus
context: fork
metadata:
  owner: zach
---
Run "${CLAUDE_SKILL_DIR}/scripts/tool.py".
"""

    rendered = portable_skill_text(source, Path("/tmp/codex/demo"))

    assert "name: demo" in rendered
    assert "description: >-\n  A multiline description." in rendered
    assert "metadata:\n  owner: zach" in rendered
    assert "argument-hint:" not in rendered
    assert "model:" not in rendered
    assert "context:" not in rendered
    assert 'Run "/tmp/codex/demo/scripts/tool.py".' in rendered


def test_sync_skill_installs_and_updates_managed_copy(tmp_path: Path) -> None:
    source = make_source(tmp_path / "sources")
    target = tmp_path / "target"

    assert sync_skill(source, target) == "install"
    destination = target / source.name
    assert (destination / "scripts" / "tool.py").is_file()
    marker = json.loads((destination / MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["source"] == str(source.resolve())

    (source / "scripts" / "tool.py").write_text("print('updated')\n", encoding="utf-8")
    assert sync_skill(source, target) == "update"
    assert (destination / "scripts" / "tool.py").read_text(encoding="utf-8") == (
        "print('updated')\n"
    )


def test_sync_skill_refuses_unmanaged_destination(tmp_path: Path) -> None:
    source = make_source(tmp_path / "sources")
    destination = tmp_path / "target" / source.name
    destination.mkdir(parents=True)
    (destination / "SKILL.md").write_text("personal edit\n", encoding="utf-8")

    with pytest.raises(InstallError, match="unmanaged destination"):
        sync_skill(source, tmp_path / "target")

    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "personal edit\n"


def test_dry_run_does_not_create_target(tmp_path: Path) -> None:
    source = make_source(tmp_path / "sources")
    target = tmp_path / "target"

    assert sync_skill(source, target, dry_run=True) == "install"
    assert not target.exists()

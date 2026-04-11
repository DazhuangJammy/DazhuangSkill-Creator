#!/usr/bin/env python3
"""Regression test: strict validation should block TODO placeholders and packaging should use it."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable

    with tempfile.TemporaryDirectory(prefix="quick_validate_strict_mode_test_") as tmp:
        out = Path(tmp)
        skill_name = "strict-mode-sample"
        skill_dir = out / skill_name

        created = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                skill_name,
                "--path",
                str(out),
                "--memory-mode",
                "off",
                "--force-memory-off",
            ],
            cwd=root,
        )
        assert_true(created.returncode == 0, "scaffold creation should pass")
        assert_true((skill_dir / "SKILL.md").exists(), "SKILL.md should exist")

        normal = run(
            [
                python_cmd,
                str(root / "scripts" / "quick_validate.py"),
                str(skill_dir),
            ],
            cwd=root,
        )
        assert_true(normal.returncode == 0, "default validation should keep TODO placeholders allowed")

        strict = run(
            [
                python_cmd,
                str(root / "scripts" / "quick_validate.py"),
                str(skill_dir),
                "--strict",
            ],
            cwd=root,
        )
        strict_output = strict.stdout + strict.stderr
        assert_true(strict.returncode != 0, "strict validation should fail on TODO placeholders")
        assert_true("严格模式失败" in strict_output, "strict output should mention strict failure")

        packaged = run(
            [
                python_cmd,
                str(root / "scripts" / "package_skill.py"),
                str(skill_dir),
                str(out / "dist"),
            ],
            cwd=root,
        )
        package_output = packaged.stdout + packaged.stderr
        assert_true(packaged.returncode != 0, "packaging should fail when strict validation fails")
        assert_true(
            "严格模式失败" in package_output,
            "package output should include strict validation failure message",
        )

    print("PASS: quick validate strict mode regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

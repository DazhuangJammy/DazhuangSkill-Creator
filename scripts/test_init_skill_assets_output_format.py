#!/usr/bin/env python3
"""Regression test: selecting assets should always scaffold assets/output-format.md."""

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

    with tempfile.TemporaryDirectory(prefix="init_skill_assets_output_format_test_") as tmp:
        out = Path(tmp)
        skill_name = "assets-template-default"
        created = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                skill_name,
                "--path",
                str(out),
                "--resources",
                "assets",
                "--memory-mode",
                "off",
                "--force-memory-off",
            ],
            cwd=root,
        )
        assert_true(created.returncode == 0, "init with assets should pass")

        output_format = out / skill_name / "assets" / "output-format.md"
        assert_true(output_format.exists(), "assets/output-format.md should be created even without --examples")

        content = output_format.read_text(encoding="utf-8")
        assert_true("# 输出格式" in content, "output-format scaffold should include template heading")

    print("PASS: init skill assets output-format regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

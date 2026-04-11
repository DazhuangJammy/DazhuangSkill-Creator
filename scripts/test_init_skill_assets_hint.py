#!/usr/bin/env python3
"""Regression test: inline output-format on report-like intent should emit assets guidance."""

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

    with tempfile.TemporaryDirectory(prefix="init_skill_assets_hint_test_") as tmp:
        out = Path(tmp)
        created = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                "medical-review-inline",
                "--path",
                str(out),
                "--sections",
                "output-format",
                "--memory-mode",
                "off",
                "--force-memory-off",
                "--intent",
                "医疗合规风控评审报告，需要固定章节和打分表",
            ],
            cwd=root,
        )
        output = created.stdout + created.stderr
        assert_true(created.returncode == 0, "init should still pass with inline output-format")
        assert_true("[WARN]" in output, "report-like inline output-format should emit warning")
        assert_true(
            "assets/output-format.md" in output,
            "warning should suggest migrating to assets/output-format.md",
        )

    print("PASS: init skill assets hint regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

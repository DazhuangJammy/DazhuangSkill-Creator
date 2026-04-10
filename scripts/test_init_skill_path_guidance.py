#!/usr/bin/env python3
"""Regression test: missing output path should return actionable guidance."""

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

    with tempfile.TemporaryDirectory(prefix="init_skill_path_guidance_test_") as tmp:
        work = Path(tmp)
        config_path = work / "config.yaml"
        config_path.write_text(
            "init_skill:\n"
            '  output_path: ""\n',
            encoding="utf-8",
        )

        blocked = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                "plain-tool",
                "--config",
                str(config_path),
                "--memory-mode",
                "off",
                "--force-memory-off",
            ],
            cwd=root,
        )
        output = blocked.stdout + blocked.stderr

        assert_true(blocked.returncode != 0, "missing path should fail fast")
        assert_true("没找到输出目录" in output, "error should mention missing output path")
        assert_true("--path ./out" in output, "error should include copy-ready --path example")
        assert_true("init_skill.output_path" in output, "error should include config key guidance")
        assert_true(not (work / "plain-tool").exists(), "failure should not create skill dir")

    print("PASS: init skill missing path guidance regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

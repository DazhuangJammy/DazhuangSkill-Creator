#!/usr/bin/env python3
"""Regression test: auto memory modes should clearly disclose resource auto-completion."""

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

    with tempfile.TemporaryDirectory(prefix="init_skill_auto_resource_disclosure_test_") as tmp:
        out = Path(tmp)
        created = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                "security-review",
                "--path",
                str(out),
                "--resources",
                "references,assets",
                "--memory-mode",
                "auto",
            ],
            cwd=root,
        )
        output = created.stdout + created.stderr

        assert_true(created.returncode == 0, "auto high-signal init should pass")
        assert_true("资源补齐策略" in output, "output should explain auto resource completion policy")
        assert_true("已自动启用 scripts/" in output, "output should explicitly disclose auto-added scripts/")
        assert_true(
            (out / "security-review" / "scripts" / "memory_mode_guard.py").exists(),
            "auto-resolved memory mode should create memory guard under scripts/",
        )

    print("PASS: init skill auto resource disclosure regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

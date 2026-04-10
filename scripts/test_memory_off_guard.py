#!/usr/bin/env python3
"""Regression test: block accidental --memory-mode off on high-risk skills."""

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

    with tempfile.TemporaryDirectory(prefix="memory_off_guard_test_") as tmp:
        out = Path(tmp)

        no_force_name = "xhs-compliance-off"
        no_force_cmd = [
            python_cmd,
            str(root / "scripts" / "init_skill.py"),
            no_force_name,
            "--path",
            str(out),
            "--memory-mode",
            "off",
            "--resources",
            "references,assets",
            "--sections",
            "role,index",
        ]
        no_force = run(no_force_cmd, cwd=root)
        combined = no_force.stdout + no_force.stderr
        assert_true(no_force.returncode != 0, "off without force should fail")
        assert_true("--force-memory-off" in combined, "failure output should include force hint")
        assert_true(not (out / no_force_name).exists(), "failed run should not create skill dir")

        force_name = "xhs-compliance-off-force"
        force_cmd = [
            python_cmd,
            str(root / "scripts" / "init_skill.py"),
            force_name,
            "--path",
            str(out),
            "--memory-mode",
            "off",
            "--force-memory-off",
            "--resources",
            "references,assets",
            "--sections",
            "role,index",
        ]
        force = run(force_cmd, cwd=root)
        assert_true(force.returncode == 0, "off with force should pass")
        assert_true((out / force_name / "SKILL.md").exists(), "force run should create skill")
        assert_true(
            not (out / force_name / "scripts" / "memory_mode_guard.py").exists(),
            "forced off should stay off (no memory guard file)",
        )

        config_path = out / "memory_off_config.yaml"
        config_path.write_text(
            "init_skill:\n"
            "  memory_mode: \"off\"\n",
            encoding="utf-8",
        )
        config_name = "xhs-compliance-config-off"
        config_cmd = [
            python_cmd,
            str(root / "scripts" / "init_skill.py"),
            config_name,
            "--config",
            str(config_path),
            "--path",
            str(out),
            "--resources",
            "references,assets",
            "--sections",
            "role,index",
        ]
        config_run = run(config_cmd, cwd=root)
        config_output = config_run.stdout + config_run.stderr
        assert_true(config_run.returncode != 0, "config off without force should fail")
        assert_true("init_skill.memory_mode=off" in config_output, "should explain config source")
        assert_true("--force-memory-off" in config_output, "should include force hint for config path")
        assert_true(not (out / config_name).exists(), "config-blocked run should not create skill dir")

    print("PASS: memory off guard regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

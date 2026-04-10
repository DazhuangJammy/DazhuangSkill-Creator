#!/usr/bin/env python3
"""Regression test: require explicit intent signal for ambiguous auto->off."""

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

    with tempfile.TemporaryDirectory(prefix="memory_auto_intent_guard_test_") as tmp:
        out = Path(tmp)

        # 1) Auto mode with no intent and low-signal input should block.
        blocked_name = "plain-tool"
        blocked = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                blocked_name,
                "--path",
                str(out),
                "--memory-mode",
                "auto",
            ],
            cwd=root,
        )
        blocked_output = blocked.stdout + blocked.stderr
        assert_true(blocked.returncode != 0, "auto without intent should block when it falls to off")
        assert_true("--intent" in blocked_output, "blocked output should mention --intent guidance")
        assert_true(not (out / blocked_name).exists(), "blocked run should not create skill dir")

        # 2) Auto mode with explicit intent should proceed even if final mode is off.
        allowed_name = "plain-tool-with-intent"
        allowed = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                allowed_name,
                "--path",
                str(out),
                "--memory-mode",
                "auto",
                "--intent",
                "deterministic formatter for csv rename",
            ],
            cwd=root,
        )
        assert_true(allowed.returncode == 0, "auto with intent should pass")
        assert_true((out / allowed_name / "SKILL.md").exists(), "allowed run should create SKILL.md")
        assert_true(
            not (out / allowed_name / "scripts" / "memory_mode_guard.py").exists(),
            "deterministic intent should stay off by default",
        )

        # 3) High-signal auto classification can still pass without intent (warn only).
        high_signal_name = "security-review"
        high_signal = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                high_signal_name,
                "--path",
                str(out),
                "--memory-mode",
                "auto",
            ],
            cwd=root,
        )
        high_signal_output = high_signal.stdout + high_signal.stderr
        assert_true(high_signal.returncode == 0, "high-signal auto without intent should still pass")
        assert_true("[WARN]" in high_signal_output, "high-signal run should emit missing-intent warning")
        assert_true(
            (out / high_signal_name / "scripts" / "memory_mode_guard.py").exists(),
            "high-signal auto run should enable memory runtime",
        )

    print("PASS: memory auto intent guard regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

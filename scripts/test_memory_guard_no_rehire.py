#!/usr/bin/env python3
"""Tiny regression test for memory guard "no rehire" behavior.

Goal:
- A lesson promoted to hard rule (status=retired) must not be reactivated
  immediately by leftover counters.
- During cooldown window, even new risk events should not reactivate it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"  {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )


def load_state(state_path: Path) -> tuple[dict, dict]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    signatures = state.get("signatures", {})
    if not signatures:
        raise RuntimeError("state.signatures is empty")
    _, entry = next(iter(signatures.items()))
    return state, entry


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable
    tmp = Path(tempfile.mkdtemp(prefix="memory_no_rehire_test_"))

    try:
        # 1) Create a fresh lessons-mode skill from current generator.
        run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                "no-rehire-skill",
                "--path",
                str(tmp),
                "--memory-mode",
                "lessons",
            ],
            cwd=root,
        )
        skill_dir = tmp / "no-rehire-skill"
        guard = skill_dir / "scripts" / "memory_mode_guard.py"
        state_path = skill_dir / "references" / "memory-state.json"
        request = "release note memory no rehire regression"

        # 2) Trigger a lesson and then promote it into hard rule.
        for event in ["invoke", "failure", "retry", "failure"]:
            run(
                [
                    python_cmd,
                    str(guard),
                    "--skill-dir",
                    str(skill_dir),
                    "--event",
                    event,
                    "--request",
                    request,
                    "--quiet",
                ],
                cwd=root,
            )

        # Flush risk events out of stable window and accumulate success hits.
        for _ in range(21):
            run(
                [
                    python_cmd,
                    str(guard),
                    "--skill-dir",
                    str(skill_dir),
                    "--event",
                    "success",
                    "--request",
                    request,
                    "--quiet",
                ],
                cwd=root,
            )

        _, entry = load_state(state_path)
        assert_true(entry.get("lesson_status") == "retired", "lesson should be retired after promotion")
        assert_true(bool(entry.get("promoted_at")), "promoted_at should be set")
        risk_cursor = int(entry.get("risk_cursor", 0))
        assert_true(risk_cursor >= 2, "risk_cursor should snapshot risk baseline after retirement")

        # 3) Safe events should not reactivate.
        for event in ["invoke", "success", "success"]:
            run(
                [
                    python_cmd,
                    str(guard),
                    "--skill-dir",
                    str(skill_dir),
                    "--event",
                    event,
                    "--request",
                    request,
                    "--quiet",
                ],
                cwd=root,
            )
        _, entry = load_state(state_path)
        assert_true(entry.get("lesson_status") == "retired", "safe events must not reactivate retired lesson")

        # 4) Even with new risk >= threshold, cooldown should block immediate rehire.
        for event in ["failure", "retry"]:
            run(
                [
                    python_cmd,
                    str(guard),
                    "--skill-dir",
                    str(skill_dir),
                    "--event",
                    event,
                    "--request",
                    request,
                    "--quiet",
                ],
                cwd=root,
            )
        _, entry = load_state(state_path)
        assert_true(
            entry.get("lesson_status") == "retired",
            "cooldown should prevent immediate reactivation after retirement",
        )

        print("PASS: memory guard no-rehire regression test")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regression test: throttled update checks should not treat stale cache as latest."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable
    current_version = (root / "VERSION").read_text(encoding="utf-8").strip()

    with tempfile.TemporaryDirectory(prefix="check_update_throttled_cache_test_") as tmp:
        state_path = Path(tmp) / "update-state.json"
        state_payload = {
            "last_checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "last_seen_remote_version": "1.4.0",
        }
        state_path.write_text(json.dumps(state_payload, ensure_ascii=False), encoding="utf-8")

        checked = run(
            [
                python_cmd,
                str(root / "scripts" / "check_update.py"),
                "--json",
                "--state-file",
                str(state_path),
                "--interval-hours",
                "24",
            ],
            cwd=root,
        )
        output = checked.stdout + checked.stderr
        assert_true(checked.returncode == 0, "check_update should complete successfully")

        payload = json.loads(checked.stdout)
        assert_true(payload.get("status") == "throttled", "should stay in throttled mode")
        assert_true(
            payload.get("latest_version") == current_version,
            "stale cached remote version should not override latest_version",
        )
        assert_true(
            payload.get("cached_remote_version") == "1.4.0",
            "payload should still expose cached remote version explicitly",
        )
        assert_true("低于当前本地" in payload.get("message", ""), "message should explain stale-cache handling")
        assert_true(output.strip(), "json output should not be empty")

    print("PASS: check update throttled stale-cache regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

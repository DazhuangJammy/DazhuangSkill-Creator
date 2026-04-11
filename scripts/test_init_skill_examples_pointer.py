#!/usr/bin/env python3
"""Regression test: references/examples pointer should match file creation behavior."""

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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable

    with tempfile.TemporaryDirectory(prefix="init_skill_examples_pointer_test_") as tmp:
        out = Path(tmp)

        # 1) references enabled but no --examples -> no examples.md pointer in scaffold.
        no_examples_name = "no-examples-pointer"
        no_examples = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                no_examples_name,
                "--path",
                str(out),
                "--resources",
                "references",
                "--memory-mode",
                "off",
                "--force-memory-off",
            ],
            cwd=root,
        )
        assert_true(no_examples.returncode == 0, "init without --examples should pass")
        no_examples_skill = out / no_examples_name / "SKILL.md"
        no_examples_body = read_text(no_examples_skill)
        assert_true(
            "references/examples.md" not in no_examples_body,
            "scaffold should not reference references/examples.md when --examples is absent",
        )
        assert_true(
            not (out / no_examples_name / "references" / "examples.md").exists(),
            "references/examples.md should not exist when --examples is absent",
        )

        # 2) references + --examples -> file exists and scaffold points to it.
        with_examples_name = "with-examples-pointer"
        with_examples = run(
            [
                python_cmd,
                str(root / "scripts" / "init_skill.py"),
                with_examples_name,
                "--path",
                str(out),
                "--resources",
                "references",
                "--examples",
                "--memory-mode",
                "off",
                "--force-memory-off",
            ],
            cwd=root,
        )
        assert_true(with_examples.returncode == 0, "init with --examples should pass")
        with_examples_skill = out / with_examples_name / "SKILL.md"
        with_examples_body = read_text(with_examples_skill)
        assert_true(
            "references/examples.md" in with_examples_body,
            "scaffold should reference references/examples.md when --examples is enabled",
        )
        assert_true(
            (out / with_examples_name / "references" / "examples.md").exists(),
            "references/examples.md should exist when --examples is enabled",
        )

    print("PASS: init skill examples pointer regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

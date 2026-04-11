#!/usr/bin/env python3
"""Regression test: review generation should require eval-plan by default."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable

    with tempfile.TemporaryDirectory(prefix="generate_review_requires_plan_test_") as tmp:
        tmp_path = Path(tmp)
        workspace = tmp_path / "workspace" / "iteration-1"
        run_dir = workspace / "eval-0" / "with_skill" / "run-1"
        outputs_dir = run_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        (outputs_dir / "answer.txt").write_text("done", encoding="utf-8")
        write_json(
            run_dir / "eval_metadata.json",
            {
                "eval_id": 0,
                "prompt": "请拆解这个问题",
            },
        )

        benchmark_path = workspace / "benchmark.json"
        write_json(
            benchmark_path,
            {
                "metadata": {
                    "skill_name": "musk-skill",
                    "timestamp": "2026-04-11T09:00:00Z",
                    "evals_run": [0],
                    "runs_per_configuration": 1,
                },
                "runs": [],
                "run_summary": {},
                "notes": [],
            },
        )

        blocked_static = tmp_path / "blocked-review.html"
        blocked = run(
            [
                python_cmd,
                str(root / "eval-viewer" / "generate_review.py"),
                str(workspace),
                "--benchmark",
                str(benchmark_path),
                "--static",
                str(blocked_static),
            ],
            cwd=root,
        )
        blocked_output = blocked.stdout + blocked.stderr
        assert_true(blocked.returncode != 0, "generate_review should fail without eval-plan by default")
        assert_true("正式评估计划" in blocked_output, "missing-plan error should mention 正式评估计划")
        assert_true(not blocked_static.exists(), "blocked review should not write static output")
        assert_true(not (tmp_path / "report.html").exists(), "blocked review should not leave companion report behind")

        allowed_static = tmp_path / "allowed-review.html"
        allowed = run(
            [
                python_cmd,
                str(root / "eval-viewer" / "generate_review.py"),
                str(workspace),
                "--benchmark",
                str(benchmark_path),
                "--static",
                str(allowed_static),
                "--allow-missing-eval-plan",
            ],
            cwd=root,
        )
        allowed_output = allowed.stdout + allowed.stderr
        assert_true(allowed.returncode == 0, f"generate_review should allow legacy mode: {allowed_output}")
        assert_true(allowed_static.exists(), "legacy review should still write static output")
        assert_true((tmp_path / "report.html").exists(), "legacy review should still backfill companion report")

        html = allowed_static.read_text(encoding="utf-8")
        assert_true('"evaluation_plan"' not in html, "legacy review should not invent evaluation_plan payload")

    print("PASS: generate review requires eval-plan regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

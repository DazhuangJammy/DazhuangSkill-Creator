#!/usr/bin/env python3
"""Regression test: benchmark aggregation should enforce eval-to-dimension alignment."""

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


def write_grading(path: Path) -> None:
    write_json(
        path,
        {
            "summary": {"pass_rate": 1.0, "passed": 2, "failed": 0, "total": 2},
            "expectations": [],
            "execution_metrics": {"total_tool_calls": 3, "errors_encountered": 0},
            "timing": {"total_duration_seconds": 5.0},
            "user_notes_summary": {"uncertainties": [], "needs_review": [], "workarounds": []},
        },
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable

    with tempfile.TemporaryDirectory(prefix="aggregate_benchmark_dimension_alignment_test_") as tmp:
        tmp_path = Path(tmp)

        # Case 1: eval metadata does not declare any mapped dimensions.
        skill_dir_1 = tmp_path / "skill-missing-dimensions"
        benchmark_dir_1 = tmp_path / "workspace-missing" / "iteration-1"
        write_json(
            skill_dir_1 / "evals" / "eval-plan.json",
            {
                "target": {"skill_name": "missing-dimensions", "comparison_mode": "with-vs-without", "variants": ["with_skill", "without_skill"]},
                "confirmed_plan": {
                    "primary_direction": {"id": "delivery_effect", "label": "落地效果", "weight": 1.0},
                    "dimensions": [
                        {"id": "task_completion", "label": "任务完成度", "weight": 1.0},
                    ],
                },
            },
        )
        write_json(
            benchmark_dir_1 / "eval-0" / "eval_metadata.json",
            {"eval_id": 0, "eval_name": "漏标维度题"},
        )
        write_grading(benchmark_dir_1 / "eval-0" / "with_skill" / "run-1" / "grading.json")
        write_grading(benchmark_dir_1 / "eval-0" / "without_skill" / "run-1" / "grading.json")

        blocked_missing = run(
            [
                python_cmd,
                str(root / "scripts" / "aggregate_benchmark.py"),
                str(benchmark_dir_1),
                "--skill-path",
                str(skill_dir_1),
            ],
            cwd=root,
        )
        missing_output = blocked_missing.stdout + blocked_missing.stderr
        assert_true(blocked_missing.returncode != 0, "aggregation should fail when eval_metadata has no dimensions")
        assert_true("还没在 eval_metadata.json 里标明对应维度" in missing_output, "error should mention missing eval metadata dimensions")

        # Case 2: plan dimension coverage is incomplete.
        skill_dir_2 = tmp_path / "skill-incomplete-coverage"
        benchmark_dir_2 = tmp_path / "workspace-coverage" / "iteration-1"
        write_json(
            skill_dir_2 / "evals" / "eval-plan.json",
            {
                "target": {"skill_name": "incomplete-coverage", "comparison_mode": "with-vs-without", "variants": ["with_skill", "without_skill"]},
                "confirmed_plan": {
                    "primary_direction": {"id": "delivery_effect", "label": "落地效果", "weight": 1.0},
                    "dimensions": [
                        {"id": "task_completion", "label": "任务完成度", "weight": 0.5},
                        {"id": "correctness", "label": "正确性", "weight": 0.5},
                    ],
                },
            },
        )
        write_json(
            benchmark_dir_2 / "eval-0" / "eval_metadata.json",
            {
                "eval_id": 0,
                "eval_name": "只覆盖一半维度",
                "dimension_ids": ["task_completion"],
                "dimension_labels": ["任务完成度"],
            },
        )
        write_grading(benchmark_dir_2 / "eval-0" / "with_skill" / "run-1" / "grading.json")
        write_grading(benchmark_dir_2 / "eval-0" / "without_skill" / "run-1" / "grading.json")

        blocked_coverage = run(
            [
                python_cmd,
                str(root / "scripts" / "aggregate_benchmark.py"),
                str(benchmark_dir_2),
                "--skill-path",
                str(skill_dir_2),
            ],
            cwd=root,
        )
        coverage_output = blocked_coverage.stdout + blocked_coverage.stderr
        assert_true(blocked_coverage.returncode != 0, "aggregation should fail when plan dimensions are not fully covered")
        assert_true("这些维度还没被任何题覆盖" in coverage_output and "正确性" in coverage_output, "error should mention uncovered plan dimensions")

    print("PASS: aggregate benchmark dimension alignment regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

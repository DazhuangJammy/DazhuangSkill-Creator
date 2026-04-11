#!/usr/bin/env python3
"""Regression test: formal evaluation should always emit review.html and report.html."""

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

    with tempfile.TemporaryDirectory(prefix="generate_eval_artifacts_test_") as tmp:
        tmp_path = Path(tmp)
        workspace = tmp_path / "musk-workspace" / "iteration-1"
        eval_dir = workspace / "eval-0"
        write_json(
            eval_dir / "eval_metadata.json",
            {
                "eval_id": 0,
                "eval_name": "真实案例 A",
                "prompt": "请用第一性原理重写这个方案。",
                "dimension_ids": ["task_completion"],
                "dimension_labels": ["任务完成度"],
            },
        )

        for config, answer, pass_rate in (
            ("with_skill", "with skill answer", 1.0),
            ("without_skill", "without skill answer", 0.0),
        ):
            run_dir = eval_dir / config / "run-1"
            outputs_dir = run_dir / "outputs"
            outputs_dir.mkdir(parents=True, exist_ok=True)
            (outputs_dir / "answer.txt").write_text(answer, encoding="utf-8")
            write_json(
                run_dir / "grading.json",
                {
                    "expectations": [
                        {
                            "text": "给出可执行方案",
                            "passed": pass_rate >= 1.0,
                            "evidence": "with skill answer" if pass_rate >= 1.0 else "without skill answer",
                        }
                    ],
                    "summary": {
                        "passed": 1 if pass_rate >= 1.0 else 0,
                        "failed": 0 if pass_rate >= 1.0 else 1,
                        "total": 1,
                        "pass_rate": pass_rate,
                    },
                    "execution_metrics": {
                        "total_tool_calls": 4,
                        "errors_encountered": 0,
                        "output_chars": 2200,
                    },
                    "timing": {
                        "total_duration_seconds": 11.0 if config == "with_skill" else 14.0,
                    },
                    "user_notes_summary": {
                        "uncertainties": [],
                        "needs_review": [],
                        "workarounds": [],
                    },
                },
            )

        benchmark_path = workspace / "benchmark.json"
        write_json(
            benchmark_path,
            {
                "metadata": {
                    "skill_name": "musk-skill",
                    "timestamp": "2026-04-11T11:00:00Z",
                    "evals_run": [0],
                    "runs_per_configuration": 1,
                    "evaluation_plan": {
                        "comparison_mode": "with-vs-without",
                        "variants": ["with_skill", "without_skill"],
                        "primary_direction": {
                            "id": "delivery_effect",
                            "label": "落地效果",
                            "weight": 1.0,
                        },
                        "dimensions": [
                            {
                                "id": "task_completion",
                                "label": "任务完成度",
                                "weight": 1.0,
                            }
                        ],
                        "report_requirements": {
                            "must_include": ["总判断", "证据"],
                        },
                    },
                    "dimension_coverage": {
                        "total_dimensions": 1,
                        "covered_dimension_ids": ["task_completion"],
                        "covered_dimension_labels": ["任务完成度"],
                        "evals": [
                            {
                                "eval_id": 0,
                                "eval_name": "真实案例 A",
                                "dimension_ids": ["task_completion"],
                                "dimension_labels": ["任务完成度"],
                            }
                        ],
                    },
                },
                "runs": [
                    {
                        "eval_id": 0,
                        "eval_name": "真实案例 A",
                        "dimension_ids": ["task_completion"],
                        "dimension_labels": ["任务完成度"],
                        "configuration": "with_skill",
                        "run_number": 1,
                        "result": {
                            "pass_rate": 1.0,
                            "passed": 1,
                            "failed": 0,
                            "total": 1,
                            "time_seconds": 11.0,
                            "tokens": 1200,
                            "tool_calls": 4,
                            "errors": 0,
                        },
                        "expectations": [],
                        "notes": [],
                    },
                    {
                        "eval_id": 0,
                        "eval_name": "真实案例 A",
                        "dimension_ids": ["task_completion"],
                        "dimension_labels": ["任务完成度"],
                        "configuration": "without_skill",
                        "run_number": 1,
                        "result": {
                            "pass_rate": 0.0,
                            "passed": 0,
                            "failed": 1,
                            "total": 1,
                            "time_seconds": 14.0,
                            "tokens": 1500,
                            "tool_calls": 4,
                            "errors": 0,
                        },
                        "expectations": [],
                        "notes": [],
                    },
                ],
                "run_summary": {
                    "with_skill": {
                        "pass_rate": {"mean": 1.0, "stddev": 0.0, "min": 1.0, "max": 1.0},
                        "time_seconds": {"mean": 11.0, "stddev": 0.0, "min": 11.0, "max": 11.0},
                        "tokens": {"mean": 1200.0, "stddev": 0.0, "min": 1200.0, "max": 1200.0},
                    },
                    "without_skill": {
                        "pass_rate": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                        "time_seconds": {"mean": 14.0, "stddev": 0.0, "min": 14.0, "max": 14.0},
                        "tokens": {"mean": 1500.0, "stddev": 0.0, "min": 1500.0, "max": 1500.0},
                    },
                    "delta": {
                        "pass_rate": "+1.00",
                        "time_seconds": "-3.0",
                        "tokens": "-300",
                    },
                },
                "notes": [],
            },
        )

        generated = run(
            [
                python_cmd,
                str(root / "scripts" / "generate_eval_artifacts.py"),
                str(workspace),
                "--benchmark",
                str(benchmark_path),
            ],
            cwd=root,
        )
        output = generated.stdout + generated.stderr
        assert_true(generated.returncode == 0, f"generate_eval_artifacts should pass: {output}")

        review_path = workspace / "review.html"
        report_path = workspace / "report.html"
        assert_true(review_path.exists(), "review.html should be created")
        assert_true(report_path.exists(), "report.html should be created")

        review_html = review_path.read_text(encoding="utf-8")
        report_html = report_path.read_text(encoding="utf-8")
        assert_true('"evaluation_plan"' in review_html, "review should still embed evaluation_plan")
        assert_true("with skill answer" in report_html, "report should include per-case answers")
        assert_true("正式评估双 HTML 已生成" in output, "script should confirm dual artifacts")

    print("PASS: generate eval artifacts regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

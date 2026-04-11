#!/usr/bin/env python3
"""Regression test: review viewer should embed eval-plan summary for benchmark review."""

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

    with tempfile.TemporaryDirectory(prefix="generate_review_eval_plan_test_") as tmp:
        tmp_path = Path(tmp)
        workspace = tmp_path / "musk-workspace" / "iteration-1"
        run_dir = workspace / "eval-0" / "with_skill" / "run-1"
        outputs_dir = run_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        (outputs_dir / "answer.txt").write_text("done", encoding="utf-8")
        write_json(
            run_dir / "eval_metadata.json",
            {
                "eval_id": 0,
                "prompt": "用马斯克的方式拆解这个问题",
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
                    "evaluation_plan": {
                        "comparison_mode": "with-vs-without",
                        "primary_direction": {
                            "id": "delivery_effect",
                            "label": "落地效果",
                            "weight": 0.7,
                        },
                        "secondary_direction": {
                            "id": "thinking_imitation",
                            "label": "思维方式模仿",
                            "weight": 0.3,
                        },
                        "dimensions": [
                            {"id": "task_completion", "label": "任务完成度", "weight": 0.4}
                        ],
                        "out_of_scope": ["tone_similarity"],
                        "report_requirements": {
                            "must_include": ["总判断", "分维度判断", "证据"],
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
                "runs": [],
                "run_summary": {},
                "notes": [],
            },
        )

        static_path = tmp_path / "review.html"
        generated = run(
            [
                python_cmd,
                str(root / "eval-viewer" / "generate_review.py"),
                str(workspace),
                "--benchmark",
                str(benchmark_path),
                "--static",
                str(static_path),
            ],
            cwd=root,
        )
        output = generated.stdout + generated.stderr
        assert_true(generated.returncode == 0, f"generate_review should pass: {output}")
        assert_true(static_path.exists(), "static review file should be created")
        companion_report = tmp_path / "report.html"
        assert_true(companion_report.exists(), "direct review generation should auto-create companion report.html")

        html = static_path.read_text(encoding="utf-8")
        report_html = companion_report.read_text(encoding="utf-8")
        assert_true('"evaluation_plan"' in html, "embedded review data should contain evaluation_plan")
        assert_true("落地效果" in html, "embedded review data should carry primary direction label")
        assert_true("tone_similarity" in html, "embedded review data should carry out_of_scope items")
        assert_true('"report_requirements"' in html, "embedded review data should carry report requirements")
        assert_true('"dimension_coverage"' in html, "embedded review data should carry dimension coverage")
        assert_true("本次测评计划" in report_html, "companion report should include plan section")

    print("PASS: generate review eval-plan regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

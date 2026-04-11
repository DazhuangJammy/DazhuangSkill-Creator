#!/usr/bin/env python3
"""一次性生成正式评估所需的双 HTML 产物。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.utils import configure_utf8_stdio

configure_utf8_stdio()


def run_step(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        print(output.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    output = (result.stdout or "") + (result.stderr or "")
    if output.strip():
        print(output.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="生成正式评估的 review.html 和 report.html")
    parser.add_argument("workspace", type=Path, help="工作区目录路径")
    parser.add_argument("--skill-name", "-n", default=None, help="页面里显示的 skill 名称")
    parser.add_argument("--benchmark", type=Path, default=None, help="benchmark.json 路径（默认尝试使用 <workspace>/benchmark.json）")
    parser.add_argument("--eval-plan", type=Path, default=None, help="正式评估计划路径；如果 benchmark 已带摘要，可以不传")
    parser.add_argument("--previous-workspace", type=Path, default=None, help="上一轮工作区路径（只传给 review，用于做上下轮对照）")
    parser.add_argument("--allow-missing-eval-plan", action="store_true", help="允许在没有正式评估计划时继续生成（仅兼容旧数据，默认会拦住）")
    parser.add_argument("--output-dir", type=Path, default=None, help="统一输出目录（默认：<workspace>）")
    parser.add_argument("--review-output", type=Path, default=None, help="review.html 输出路径（默认：<output-dir>/review.html）")
    parser.add_argument("--report-output", type=Path, default=None, help="report.html 输出路径（默认：<output-dir>/report.html）")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"错误：{workspace} 不是目录", file=sys.stderr)
        sys.exit(1)

    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable
    benchmark_path = (args.benchmark or (workspace / "benchmark.json")).resolve()
    output_dir = (args.output_dir or workspace).resolve()
    review_output = (args.review_output or (output_dir / "review.html")).resolve()
    report_output = (args.report_output or (output_dir / "report.html")).resolve()

    review_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)

    review_cmd = [
        python_cmd,
        str(root / "eval-viewer" / "generate_review.py"),
        str(workspace),
        "--benchmark",
        str(benchmark_path),
        "--static",
        str(review_output),
        "--skip-companion-report",
    ]
    report_cmd = [
        python_cmd,
        str(root / "eval-viewer" / "generate_report.py"),
        str(workspace),
        "--benchmark",
        str(benchmark_path),
        "--output",
        str(report_output),
        "--skip-companion-review",
    ]

    if args.skill_name:
        review_cmd.extend(["--skill-name", args.skill_name])
        report_cmd.extend(["--skill-name", args.skill_name])
    if args.eval_plan:
        eval_plan_path = str(args.eval_plan.resolve())
        review_cmd.extend(["--eval-plan", eval_plan_path])
        report_cmd.extend(["--eval-plan", eval_plan_path])
    if args.previous_workspace:
        review_cmd.extend(["--previous-workspace", str(args.previous_workspace.resolve())])
    if args.allow_missing_eval_plan:
        review_cmd.append("--allow-missing-eval-plan")
        report_cmd.append("--allow-missing-eval-plan")

    run_step(review_cmd)
    run_step(report_cmd)

    missing = [str(path) for path in (review_output, report_output) if not path.exists()]
    if missing:
        print(
            "错误：评估双 HTML 产物没有生成完整：\n- " + "\n- ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)

    print("正式评估双 HTML 已生成：")
    print(f"- review.html: {review_output}")
    print(f"- report.html: {report_output}")


if __name__ == "__main__":
    main()

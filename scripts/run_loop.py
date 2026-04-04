#!/usr/bin/env python3
"""Run the eval + improve loop until all pass or max iterations reached.

Combines run_eval.py and improve_description.py in a loop, tracking history
and returning the best description found. Supports train/test split to prevent
overfitting.
"""

import argparse
import json
import random
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_report import generate_html
from scripts.improve_description import improve_description
from scripts.run_eval import find_project_root, run_eval
from scripts.utils import (
    coalesce,
    extract_eval_items,
    get_config_value,
    load_dazhuangskill_creator_config,
    load_structured_data,
    parse_skill_md,
)


def split_eval_set(eval_set: list[dict], holdout: float, seed: int = 42) -> tuple[list[dict], list[dict]]:
    """Split eval set into train and test sets, stratified by should_trigger."""
    random.seed(seed)

    # Separate by should_trigger
    trigger = [e for e in eval_set if e["should_trigger"]]
    no_trigger = [e for e in eval_set if not e["should_trigger"]]

    # Shuffle each group
    random.shuffle(trigger)
    random.shuffle(no_trigger)

    # Calculate split points
    n_trigger_test = max(1, int(len(trigger) * holdout))
    n_no_trigger_test = max(1, int(len(no_trigger) * holdout))

    # Split
    test_set = trigger[:n_trigger_test] + no_trigger[:n_no_trigger_test]
    train_set = trigger[n_trigger_test:] + no_trigger[n_no_trigger_test:]

    return train_set, test_set


def run_loop(
    eval_set: list[dict],
    skill_path: Path,
    description_override: str | None,
    num_workers: int,
    timeout: int,
    max_iterations: int,
    runs_per_query: int,
    trigger_threshold: float,
    holdout: float,
    model: str,
    verbose: bool,
    live_report_path: Path | None = None,
    log_dir: Path | None = None,
) -> dict:
    """Run the eval + improvement loop."""
    project_root = find_project_root()
    name, original_description, content = parse_skill_md(skill_path)
    current_description = description_override or original_description

    # Split into train/test if holdout > 0
    if holdout > 0:
        train_set, test_set = split_eval_set(eval_set, holdout)
        if verbose:
            print(f"切分完成：训练集 {len(train_set)} 条，测试集 {len(test_set)} 条（holdout={holdout}）", file=sys.stderr)
    else:
        train_set = eval_set
        test_set = []

    history = []
    exit_reason = "unknown"

    for iteration in range(1, max_iterations + 1):
        if verbose:
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"第 {iteration}/{max_iterations} 轮", file=sys.stderr)
            print(f"当前描述：{current_description}", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)

        # Evaluate train + test together in one batch for parallelism
        all_queries = train_set + test_set
        t0 = time.time()
        all_results = run_eval(
            eval_set=all_queries,
            skill_name=name,
            description=current_description,
            num_workers=num_workers,
            timeout=timeout,
            project_root=project_root,
            runs_per_query=runs_per_query,
            trigger_threshold=trigger_threshold,
            model=model,
        )
        eval_elapsed = time.time() - t0

        # Split results back into train/test by matching queries
        train_queries_set = {q["query"] for q in train_set}
        train_result_list = [r for r in all_results["results"] if r["query"] in train_queries_set]
        test_result_list = [r for r in all_results["results"] if r["query"] not in train_queries_set]

        train_passed = sum(1 for r in train_result_list if r["pass"])
        train_total = len(train_result_list)
        train_summary = {"passed": train_passed, "failed": train_total - train_passed, "total": train_total}
        train_results = {"results": train_result_list, "summary": train_summary}

        if test_set:
            test_passed = sum(1 for r in test_result_list if r["pass"])
            test_total = len(test_result_list)
            test_summary = {"passed": test_passed, "failed": test_total - test_passed, "total": test_total}
            test_results = {"results": test_result_list, "summary": test_summary}
        else:
            test_results = None
            test_summary = None

        history.append({
            "iteration": iteration,
            "description": current_description,
            "train_passed": train_summary["passed"],
            "train_failed": train_summary["failed"],
            "train_total": train_summary["total"],
            "train_results": train_results["results"],
            "test_passed": test_summary["passed"] if test_summary else None,
            "test_failed": test_summary["failed"] if test_summary else None,
            "test_total": test_summary["total"] if test_summary else None,
            "test_results": test_results["results"] if test_results else None,
            # For backward compat with report generator
            "passed": train_summary["passed"],
            "failed": train_summary["failed"],
            "total": train_summary["total"],
            "results": train_results["results"],
        })

        # Write live report if path provided
        if live_report_path:
            partial_output = {
                "original_description": original_description,
                "best_description": current_description,
                "best_score": "in progress",
                "iterations_run": len(history),
                "holdout": holdout,
                "train_size": len(train_set),
                "test_size": len(test_set),
                "history": history,
            }
            live_report_path.write_text(generate_html(partial_output, auto_refresh=True, skill_name=name))

        if verbose:
            def print_eval_stats(label, results, elapsed):
                pos = [r for r in results if r["should_trigger"]]
                neg = [r for r in results if not r["should_trigger"]]
                tp = sum(r["triggers"] for r in pos)
                pos_runs = sum(r["runs"] for r in pos)
                fn = pos_runs - tp
                fp = sum(r["triggers"] for r in neg)
                neg_runs = sum(r["runs"] for r in neg)
                tn = neg_runs - fp
                total = tp + tn + fp + fn
                precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
                accuracy = (tp + tn) / total if total > 0 else 0.0
                print(f"{label}：{tp+tn}/{total} 正确，precision={precision:.0%} recall={recall:.0%} accuracy={accuracy:.0%}（{elapsed:.1f}s）", file=sys.stderr)
                for r in results:
                    status = "通过" if r["pass"] else "失败"
                    rate_str = f"{r['triggers']}/{r['runs']}"
                    print(f"  [{status}] 触发={rate_str} 期望触发={r['should_trigger']}: {r['query'][:60]}", file=sys.stderr)

            print_eval_stats("训练集", train_results["results"], eval_elapsed)
            if test_summary:
                print_eval_stats("测试集", test_results["results"], 0)

        if train_summary["failed"] == 0:
            exit_reason = f"all_passed (iteration {iteration})"
            if verbose:
                print(f"\n第 {iteration} 轮时训练集已全部通过！", file=sys.stderr)
            break

        if iteration == max_iterations:
            exit_reason = f"max_iterations ({max_iterations})"
            if verbose:
                print(f"\n已达到最大迭代次数（{max_iterations}）。", file=sys.stderr)
            break

        # Improve the description based on train results
        if verbose:
            print(f"\n正在改进描述...", file=sys.stderr)

        t0 = time.time()
        # Strip test scores from history so improvement model can't see them
        blinded_history = [
            {k: v for k, v in h.items() if not k.startswith("test_")}
            for h in history
        ]
        new_description = improve_description(
            skill_name=name,
            skill_content=content,
            current_description=current_description,
            eval_results=train_results,
            history=blinded_history,
            model=model,
            log_dir=log_dir,
            iteration=iteration,
        )
        improve_elapsed = time.time() - t0

        if verbose:
            print(f"新方案（{improve_elapsed:.1f}s）：{new_description}", file=sys.stderr)

        current_description = new_description

    # Find the best iteration by TEST score (or train if no test set)
    if test_set:
        best = max(history, key=lambda h: h["test_passed"] or 0)
        best_score = f"{best['test_passed']}/{best['test_total']}"
    else:
        best = max(history, key=lambda h: h["train_passed"])
        best_score = f"{best['train_passed']}/{best['train_total']}"

    if verbose:
        print(f"\n结束原因：{exit_reason}", file=sys.stderr)
        print(f"最佳得分：{best_score}（第 {best['iteration']} 轮）", file=sys.stderr)

    return {
        "exit_reason": exit_reason,
        "original_description": original_description,
        "best_description": best["description"],
        "best_score": best_score,
        "best_train_score": f"{best['train_passed']}/{best['train_total']}",
        "best_test_score": f"{best['test_passed']}/{best['test_total']}" if test_set else None,
        "final_description": current_description,
        "iterations_run": len(history),
        "holdout": holdout,
        "train_size": len(train_set),
        "test_size": len(test_set),
        "history": history,
    }


def main():
    parser = argparse.ArgumentParser(description="运行评测 + 改进循环")
    parser.add_argument("--config", default=None, help="config.yaml 路径（默认读取 dazhuangskill-creator/config.yaml）")
    parser.add_argument("--eval-set", required=True, help="评测集 JSON/YAML 路径")
    parser.add_argument("--skill-path", required=True, help="skill 目录路径")
    parser.add_argument("--description", default=None, help="覆盖起始描述")
    parser.add_argument("--num-workers", type=int, default=None, help="并行 worker 数（CLI > config.yaml > 内置默认值）")
    parser.add_argument("--timeout", type=int, default=None, help="每个查询的超时时间（秒，CLI > config.yaml > 内置默认值）")
    parser.add_argument("--max-iterations", type=int, default=None, help="最大改进轮数（CLI > config.yaml > 内置默认值）")
    parser.add_argument("--runs-per-query", type=int, default=None, help="每个 query 的运行次数（CLI > config.yaml > 内置默认值）")
    parser.add_argument("--trigger-threshold", type=float, default=None, help="触发率阈值（CLI > config.yaml > 内置默认值）")
    parser.add_argument("--holdout", type=float, default=None, help="用于测试的留出集比例（CLI > config.yaml > 内置默认值）")
    parser.add_argument("--model", default=None, help="用于改进的模型（CLI > config.yaml）")
    parser.add_argument("--verbose", action="store_true", help="把进度打印到 stderr")
    parser.add_argument("--report", default=None, help="在这个路径生成 HTML 报告（CLI > config.yaml > 'auto'；用 'none' 关闭）")
    parser.add_argument("--results-dir", default=None, help="把所有输出（results.json、report.html、log.txt）保存到这里的时间戳子目录（CLI > config.yaml）")
    args = parser.parse_args()

    config = load_dazhuangskill_creator_config(args.config)
    eval_set = extract_eval_items(load_structured_data(args.eval_set))
    skill_path = Path(args.skill_path)
    num_workers = int(coalesce(args.num_workers, get_config_value(config, "evaluation.num_workers"), 10))
    timeout = int(coalesce(args.timeout, get_config_value(config, "evaluation.timeout"), 30))
    max_iterations = int(
        coalesce(args.max_iterations, get_config_value(config, "optimization.max_iterations"), 5)
    )
    runs_per_query = int(
        coalesce(args.runs_per_query, get_config_value(config, "evaluation.runs_per_query"), 3)
    )
    trigger_threshold = float(
        coalesce(args.trigger_threshold, get_config_value(config, "evaluation.trigger_threshold"), 0.5)
    )
    holdout = float(coalesce(args.holdout, get_config_value(config, "optimization.holdout"), 0.4))
    model = coalesce(args.model, get_config_value(config, "optimization.model"), get_config_value(config, "evaluation.model"))
    report_setting = coalesce(args.report, get_config_value(config, "optimization.report"), "auto")
    results_dir_setting = coalesce(args.results_dir, get_config_value(config, "optimization.results_dir"))

    if not model:
        print("错误：如果 config.yaml 里没有设置 optimization.model 或 evaluation.model，就必须显式提供 --model", file=sys.stderr)
        sys.exit(1)

    if not (skill_path / "SKILL.md").exists():
        print(f"错误：在 {skill_path} 未找到 SKILL.md", file=sys.stderr)
        sys.exit(1)

    name, _, _ = parse_skill_md(skill_path)

    # Set up live report path
    if report_setting != "none":
        if report_setting == "auto":
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            live_report_path = Path(tempfile.gettempdir()) / f"skill_description_report_{skill_path.name}_{timestamp}.html"
        else:
            live_report_path = Path(report_setting)
        # Open the report immediately so the user can watch
        live_report_path.write_text("<html><body><h1>Starting optimization loop...</h1><meta http-equiv='refresh' content='5'></body></html>")
        webbrowser.open(str(live_report_path))
    else:
        live_report_path = None

    # Determine output directory (create before run_loop so logs can be written)
    if results_dir_setting:
        timestamp = time.strftime("%Y-%m-%d_%H%M%S")
        results_dir = Path(results_dir_setting) / timestamp
        results_dir.mkdir(parents=True, exist_ok=True)
    else:
        results_dir = None

    log_dir = results_dir / "logs" if results_dir else None

    output = run_loop(
        eval_set=eval_set,
        skill_path=skill_path,
        description_override=args.description,
        num_workers=num_workers,
        timeout=timeout,
        max_iterations=max_iterations,
        runs_per_query=runs_per_query,
        trigger_threshold=trigger_threshold,
        holdout=holdout,
        model=model,
        verbose=args.verbose,
        live_report_path=live_report_path,
        log_dir=log_dir,
    )

    # Save JSON output
    json_output = json.dumps(output, indent=2)
    print(json_output)
    if results_dir:
        (results_dir / "results.json").write_text(json_output)

    # Write final HTML report (without auto-refresh)
    if live_report_path:
        live_report_path.write_text(generate_html(output, auto_refresh=False, skill_name=name))
        print(f"\nReport: {live_report_path}", file=sys.stderr)

    if results_dir and live_report_path:
        (results_dir / "report.html").write_text(generate_html(output, auto_refresh=False, skill_name=name))

    if results_dir:
        print(f"Results saved to: {results_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()

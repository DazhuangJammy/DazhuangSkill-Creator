#!/usr/bin/env python3
"""评估一个 skill 描述的触发效果。

检查某个 skill 的描述是否会让 Claude 在一组 query 上正确触发
（也就是判断要不要读取这个 skill），并以 JSON 输出结果。
"""

import argparse
import json
import os
import select
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.utils import (
    coalesce,
    extract_eval_items,
    get_config_value,
    load_dazhuangskill_creator_config,
    load_structured_data,
    parse_skill_md,
)


def find_project_root() -> Path:
    """Find the project root by walking up from cwd looking for .claude/.

    Mimics how Claude Code discovers its project root, so the command file
    we create ends up where claude -p will look for it.
    """
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    model: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered.

    Creates a command file in .claude/commands/ so it appears in Claude's
    available_skills list, then runs `claude -p` with the raw query.
    Uses --include-partial-messages to detect triggering early from
    stream events (content_block_start) rather than waiting for the
    full assistant message, which only arrives after tool execution.
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"
    project_commands_dir = Path(project_root) / ".claude" / "commands"
    command_file = project_commands_dir / f"{clean_name}.md"

    try:
        project_commands_dir.mkdir(parents=True, exist_ok=True)
        # Use YAML block scalar to avoid breaking on quotes in description
        indented_desc = "\n  ".join(skill_description.split("\n"))
        command_content = (
            f"---\n"
            f"description: |\n"
            f"  {indented_desc}\n"
            f"---\n\n"
            f"# {skill_name}\n\n"
            f"This skill handles: {skill_description}\n"
        )
        command_file.write_text(command_content)

        cmd = [
            "claude",
            "-p", query,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        # Remove CLAUDECODE env var to allow nesting claude -p inside a
        # Claude Code session. The guard is for interactive terminal conflicts;
        # programmatic subprocess usage is safe.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=project_root,
            env=env,
        )

        triggered = False
        start_time = time.time()
        buffer = ""
        # Track state for stream event detection
        pending_tool_name = None
        accumulated_json = ""

        try:
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    remaining = process.stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    break

                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if not ready:
                    continue

                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Early detection via stream events
                    if event.get("type") == "stream_event":
                        se = event.get("event", {})
                        se_type = se.get("type", "")

                        if se_type == "content_block_start":
                            cb = se.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                tool_name = cb.get("name", "")
                                if tool_name in ("Skill", "Read"):
                                    pending_tool_name = tool_name
                                    accumulated_json = ""
                                else:
                                    return False

                        elif se_type == "content_block_delta" and pending_tool_name:
                            delta = se.get("delta", {})
                            if delta.get("type") == "input_json_delta":
                                accumulated_json += delta.get("partial_json", "")
                                if clean_name in accumulated_json:
                                    return True

                        elif se_type in ("content_block_stop", "message_stop"):
                            if pending_tool_name:
                                return clean_name in accumulated_json
                            if se_type == "message_stop":
                                return False

                    # Fallback: full assistant message
                    elif event.get("type") == "assistant":
                        message = event.get("message", {})
                        for content_item in message.get("content", []):
                            if content_item.get("type") != "tool_use":
                                continue
                            tool_name = content_item.get("name", "")
                            tool_input = content_item.get("input", {})
                            if tool_name == "Skill" and clean_name in tool_input.get("skill", ""):
                                triggered = True
                            elif tool_name == "Read" and clean_name in tool_input.get("file_path", ""):
                                triggered = True
                            return triggered

                    elif event.get("type") == "result":
                        return triggered
        finally:
            # Clean up process on any exit path (return, exception, timeout)
            if process.poll() is None:
                process.kill()
                process.wait()

        return triggered
    finally:
        if command_file.exists():
            command_file.unlink()


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
) -> dict:
    """Run the full eval set and return results."""
    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    str(project_root),
                    model,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                query_triggers[query].append(future.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="评估一个 skill 描述的触发效果")
    parser.add_argument("--config", default=None, help="config.yaml 路径（默认读取 dazhuangskill-creator/config.yaml）")
    parser.add_argument("--eval-set", required=True, help="评测集 JSON/YAML 路径")
    parser.add_argument("--skill-path", required=True, help="skill 目录路径")
    parser.add_argument("--description", default=None, help="覆盖要测试的描述")
    parser.add_argument("--num-workers", type=int, default=None, help="并行 worker 数（CLI > config.yaml > 内置默认值）")
    parser.add_argument("--timeout", type=int, default=None, help="每个查询的超时时间（秒，CLI > config.yaml > 内置默认值）")
    parser.add_argument("--runs-per-query", type=int, default=None, help="每个 query 的运行次数（CLI > config.yaml > 内置默认值）")
    parser.add_argument("--trigger-threshold", type=float, default=None, help="触发率阈值（CLI > config.yaml > 内置默认值）")
    parser.add_argument("--model", default=None, help="用于 claude -p 的模型（CLI > config.yaml > 用户默认模型）")
    parser.add_argument("--verbose", action="store_true", help="把进度打印到 stderr")
    args = parser.parse_args()

    config = load_dazhuangskill_creator_config(args.config)
    eval_set = extract_eval_items(load_structured_data(args.eval_set))
    skill_path = Path(args.skill_path)
    num_workers = int(coalesce(args.num_workers, get_config_value(config, "evaluation.num_workers"), 10))
    timeout = int(coalesce(args.timeout, get_config_value(config, "evaluation.timeout"), 30))
    runs_per_query = int(
        coalesce(args.runs_per_query, get_config_value(config, "evaluation.runs_per_query"), 3)
    )
    trigger_threshold = float(
        coalesce(args.trigger_threshold, get_config_value(config, "evaluation.trigger_threshold"), 0.5)
    )
    model = coalesce(args.model, get_config_value(config, "evaluation.model"))

    if not (skill_path / "SKILL.md").exists():
        print(f"错误：在 {skill_path} 未找到 SKILL.md", file=sys.stderr)
        sys.exit(1)

    name, original_description, content = parse_skill_md(skill_path)
    description = args.description or original_description
    project_root = find_project_root()

    if args.verbose:
        print(f"正在评估：{description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=num_workers,
        timeout=timeout,
        project_root=project_root,
        runs_per_query=runs_per_query,
        trigger_threshold=trigger_threshold,
        model=model,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"结果：{summary['passed']}/{summary['total']} 通过", file=sys.stderr)
        for r in output["results"]:
            status = "通过" if r["pass"] else "失败"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] 触发={rate_str} 期望触发={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

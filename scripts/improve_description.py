#!/usr/bin/env python3
"""根据评测结果改进 skill 描述。

读取 run_eval.py 产出的评测结果，并通过子进程调用 `claude -p`
生成改进后的描述（认证方式与 run_eval.py 相同：直接复用当前会话的
Claude Code 登录态，不需要额外的 ANTHROPIC_API_KEY）。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.utils import (
    coalesce,
    get_config_value,
    load_dazhuangskill_creator_config,
    load_structured_data,
    parse_skill_md,
)


def _call_claude(prompt: str, model: str | None, timeout: int = 300) -> str:
    """Run `claude -p` with the prompt on stdin and return the text response.

    Prompt goes over stdin (not argv) because it embeds the full SKILL.md
    body and can easily exceed comfortable argv length.
    """
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])

    # Remove CLAUDECODE env var to allow nesting claude -p inside a
    # Claude Code session. The guard is for interactive terminal conflicts;
    # programmatic subprocess usage is safe. Same pattern as run_eval.py.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p exited {result.returncode}\nstderr: {result.stderr}"
        )
    return result.stdout


def improve_description(
    skill_name: str,
    skill_content: str,
    current_description: str,
    eval_results: dict,
    history: list[dict],
    model: str,
    test_results: dict | None = None,
    log_dir: Path | None = None,
    iteration: int | None = None,
) -> str:
    """Call Claude to improve the description based on eval results."""
    failed_triggers = [
        r for r in eval_results["results"]
        if r["should_trigger"] and not r["pass"]
    ]
    false_triggers = [
        r for r in eval_results["results"]
        if not r["should_trigger"] and not r["pass"]
    ]

    # Build scores summary
    train_score = f"{eval_results['summary']['passed']}/{eval_results['summary']['total']}"
    if test_results:
        test_score = f"{test_results['summary']['passed']}/{test_results['summary']['total']}"
        scores_summary = f"训练集：{train_score}，测试集：{test_score}"
    else:
        scores_summary = f"训练集：{train_score}"

    prompt = f"""你正在为一个名为 "{skill_name}" 的 Claude Code skill 优化描述。这里的 “skill” 有点像 prompt，但它采用渐进展开：Claude 在决定要不要使用这个 skill 时，先只会看到标题和描述；如果决定使用，才会继续读取 .md 文件里的详细说明，以及 skill 目录中可能链接到的辅助文件、脚本、额外文档或示例。

这个描述会出现在 Claude 的 “available_skills” 列表里。用户发来 query 后，Claude 只会根据 skill 标题和这段描述来决定是否调用它。你的目标是写出一段描述：该触发的时候触发，不该触发的时候不要触发。

当前描述如下：
<current_description>
"{current_description}"
</current_description>

当前得分（{scores_summary}）：
<scores_summary>
"""
    if failed_triggers:
        prompt += "漏触发（本应触发，但没有触发）：\n"
        for r in failed_triggers:
            prompt += f'  - "{r["query"]}"（触发了 {r["triggers"]}/{r["runs"]} 次）\n'
        prompt += "\n"

    if false_triggers:
        prompt += "误触发（不该触发，但触发了）：\n"
        for r in false_triggers:
            prompt += f'  - "{r["query"]}"（触发了 {r["triggers"]}/{r["runs"]} 次）\n'
        prompt += "\n"

    if history:
        prompt += "历史尝试（不要重复这些写法，尽量做结构上不同的尝试）：\n\n"
        for h in history:
            train_s = f"{h.get('train_passed', h.get('passed', 0))}/{h.get('train_total', h.get('total', 0))}"
            test_s = f"{h.get('test_passed', '?')}/{h.get('test_total', '?')}" if h.get('test_passed') is not None else None
            score_str = f"训练集={train_s}" + (f"，测试集={test_s}" if test_s else "")
            prompt += f'<attempt {score_str}>\n'
            prompt += f'描述："{h["description"]}"\n'
            if "results" in h:
                prompt += "训练集结果：\n"
                for r in h["results"]:
                    status = "通过" if r["pass"] else "失败"
                    prompt += f'  [{status}] "{r["query"][:80]}"（触发 {r["triggers"]}/{r["runs"]}）\n'
            if h.get("note"):
                prompt += f'备注：{h["note"]}\n'
            prompt += "</attempt>\n\n"

    prompt += f"""</scores_summary>

Skill 内容（帮助你理解这个 skill 到底做什么）：
<skill_content>
{skill_content}
</skill_content>

请基于这些失败案例，写一版更容易正确触发的新描述。这里的“基于失败案例”其实需要拿捏分寸，因为我们不想对眼前这些具体例子过拟合。所以我明确不希望你做的事，是写出一份越来越长的“这个 skill 应该/不应该在哪些具体 query 上触发”的清单。相反，你应该从这些失败中抽象出更大的用户意图类别，以及这个 skill 在什么情境下有用、什么情境下没必要触发。原因有两个：

1. 避免过拟合
2. 这段描述会被注入到所有 query 的上下文里，而且系统里可能有很多 skill，所以不能让任何一个描述占掉太多空间。

具体来说，这段描述最好控制在 100-200 字左右，即便要为此牺牲一点准确性也可以。系统的硬上限是 1024 个字符，超出就会被截断，所以请明显低于这个上限。

下面是一些实践中比较有效的写法：
- 尽量用祈使句，比如“遇到这类任务时使用这个 skill”，而不是“这个 skill 会做什么”
- 描述要聚焦在用户意图，也就是用户想达成什么，而不是实现细节
- 这段描述是在和其他 skill 竞争 Claude 的注意力，所以要足够鲜明，一眼能认出来
- 如果连续多轮失败很多，就要大胆换写法，试试不同句式和措辞

你可以大胆一些，在不同轮次里尝试不同风格。我们有多次试错机会，最后只会保留得分最高的那版。 

请只输出放在 <new_description> 标签里的新描述文本，不要附加任何其他内容。"""

    text = _call_claude(prompt, model)

    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    description = match.group(1).strip().strip('"') if match else text.strip().strip('"')

    transcript: dict = {
        "iteration": iteration,
        "prompt": prompt,
        "response": text,
        "parsed_description": description,
        "char_count": len(description),
        "over_limit": len(description) > 1024,
    }

    # Safety net: the prompt already states the 1024-char hard limit, but if
    # the model blew past it anyway, make one fresh single-turn call that
    # quotes the too-long version and asks for a shorter rewrite. (The old
    # SDK path did this as a true multi-turn; `claude -p` is one-shot, so we
    # inline the prior output into the new prompt instead.)
    if len(description) > 1024:
        shorten_prompt = (
            f"{prompt}\n\n"
            f"---\n\n"
            f"上一版生成了下面这段描述，它有 "
            f"{len(description)} 个字符，已经超过 1024 字符的硬限制：\n\n"
            f'"{description}"\n\n'
            f"请把它改写到 1024 字符以内，同时尽量保留最重要的触发词和意图覆盖。"
            f"只输出放在 <new_description> 标签里的新描述。"
        )
        shorten_text = _call_claude(shorten_prompt, model)
        match = re.search(r"<new_description>(.*?)</new_description>", shorten_text, re.DOTALL)
        shortened = match.group(1).strip().strip('"') if match else shorten_text.strip().strip('"')

        transcript["rewrite_prompt"] = shorten_prompt
        transcript["rewrite_response"] = shorten_text
        transcript["rewrite_description"] = shortened
        transcript["rewrite_char_count"] = len(shortened)
        description = shortened

    transcript["final_description"] = description

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"improve_iter_{iteration or 'unknown'}.json"
        log_file.write_text(json.dumps(transcript, indent=2))

    return description


def main():
    parser = argparse.ArgumentParser(description="根据评测结果改进 skill 描述")
    parser.add_argument("--config", default=None, help="config.yaml 路径（默认读取 dazhuangskill-creator/config.yaml）")
    parser.add_argument("--eval-results", required=True, help="评测结果 JSON/YAML 路径（来自 run_eval.py）")
    parser.add_argument("--skill-path", required=True, help="skill 目录路径")
    parser.add_argument("--history", default=None, help="历史记录 JSON/YAML 路径（之前的尝试）")
    parser.add_argument("--model", default=None, help="用于改进的模型（CLI > config.yaml）")
    parser.add_argument("--verbose", action="store_true", help="把思考过程打印到 stderr")
    args = parser.parse_args()

    config = load_dazhuangskill_creator_config(args.config)
    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        print(f"错误：在 {skill_path} 未找到 SKILL.md", file=sys.stderr)
        sys.exit(1)

    eval_results = load_structured_data(args.eval_results)
    history = []
    if args.history:
        history = load_structured_data(args.history)

    model = coalesce(args.model, get_config_value(config, "optimization.model"), get_config_value(config, "evaluation.model"))
    if not model:
        print("错误：如果 config.yaml 里没有设置 optimization.model 或 evaluation.model，就必须显式提供 --model", file=sys.stderr)
        sys.exit(1)

    name, _, content = parse_skill_md(skill_path)
    current_description = eval_results["description"]

    if args.verbose:
        print(f"当前描述：{current_description}", file=sys.stderr)
        print(f"当前得分：{eval_results['summary']['passed']}/{eval_results['summary']['total']}", file=sys.stderr)

    new_description = improve_description(
        skill_name=name,
        skill_content=content,
        current_description=current_description,
        eval_results=eval_results,
        history=history,
        model=model,
    )

    if args.verbose:
        print(f"改进结果：{new_description}", file=sys.stderr)

    # Output as JSON with both the new description and updated history
    output = {
        "description": new_description,
        "history": history + [{
            "description": current_description,
            "passed": eval_results["summary"]["passed"],
            "failed": eval_results["summary"]["failed"],
            "total": eval_results["summary"]["total"],
            "results": eval_results["results"],
        }],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

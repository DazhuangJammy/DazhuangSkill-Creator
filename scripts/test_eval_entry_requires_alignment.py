#!/usr/bin/env python3
"""Regression test: evaluation requests must stop at alignment before execution."""

from __future__ import annotations

from pathlib import Path


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    skill_md = (root / "SKILL.md").read_text(encoding="utf-8")
    eval_planning = (root / "references" / "eval-planning.md").read_text(encoding="utf-8")
    eval_loop = (root / "references" / "eval-loop.md").read_text(encoding="utf-8")
    proposal_template = (root / "assets" / "evaluation-proposal-template.md").read_text(encoding="utf-8")
    plan_template = (root / "assets" / "evaluation-plan-template.md").read_text(encoding="utf-8")

    assert_true(
        "第一次响应必须先停在“评估前置提案”" in skill_md,
        "SKILL.md should hard-require first evaluation response to stop at alignment",
    )
    assert_true(
        "用户明确拍板" in skill_md and "才允许进入正式评估计划和执行层" in skill_md,
        "SKILL.md should require explicit user confirmation before execution",
    )
    assert_true(
        "只有一套标准化正式流程" in skill_md and "不存在轻量版、降级版或聊天结论版" in skill_md,
        "SKILL.md should define evaluation as a single formal workflow",
    )
    assert_true(
        "不能改走结构判断/评审模式" in skill_md and "review.html" in skill_md and "report.html" in skill_md,
        "SKILL.md should require confirmed evaluations to continue until dual HTML",
    )
    assert_true(
        "没有出现评估 / 测评 / 评测意图词" in skill_md and "只是讨论结构或架构、且这次没有评估 / 测评 / 评测意图" in skill_md,
        "SKILL.md should keep structure-only review separate from evaluation requests",
    )
    assert_true(
        "## 入口硬规则" in eval_planning,
        "eval-planning should define entry hard rules",
    )
    assert_true(
        "第一次响应默认只能停在 `AI 初判 + 评估前置提案 + 等用户拍板`" in eval_planning,
        "eval-planning should force first response to stop at proposal",
    )
    assert_true(
        "如果用户没有明确回答“按哪一种来评”" in eval_planning,
        "eval-planning should block silent auto-confirmation",
    )
    assert_true(
        "前置对齐 -> 正式执行 -> `review.html` + `report.html`" in eval_planning,
        "eval-planning should define the single formal evaluation workflow",
    )
    assert_true(
        "不能把一段聊天结论当成完成" in eval_planning,
        "eval-planning should forbid ending confirmed evaluations with chat-only conclusions",
    )
    assert_true(
        "这份文档不是“第一次收到评估请求”时的入口文档" in eval_loop,
        "eval-loop should reject being the first entry point",
    )
    assert_true(
        "必须是用户已经明确确认过的版本" in eval_loop,
        "eval-loop should require a user-confirmed plan",
    )
    assert_true(
        "唯一允许的正式执行主线" in eval_loop,
        "eval-loop should define itself as the only formal execution path",
    )
    assert_true(
        "如果缺任意一个文件，就不算这次正式评估完成，也不能对用户声称“评估已经做完”" in eval_loop,
        "eval-loop should require both HTML artifacts before completion",
    )
    assert_true(
        "不要直接开始正式测评" in proposal_template,
        "proposal template should remind the model to stop before execution",
    )
    assert_true(
        "不是轻量版评估" in proposal_template and "`review.html` 和 `report.html`" in proposal_template,
        "proposal template should frame alignment as part of the formal workflow",
    )
    assert_true(
        "不能降级成聊天结论、Markdown 结论或普通 review" in plan_template,
        "plan template should require formal execution after confirmation",
    )

    print("PASS: evaluation entry alignment regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

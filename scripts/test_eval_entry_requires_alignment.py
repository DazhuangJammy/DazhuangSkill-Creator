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

    assert_true(
        "第一次响应必须先停在“评估前置提案”" in skill_md,
        "SKILL.md should hard-require first evaluation response to stop at alignment",
    )
    assert_true(
        "用户明确拍板" in skill_md and "才允许进入正式评估计划和执行层" in skill_md,
        "SKILL.md should require explicit user confirmation before execution",
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
        "这份文档不是“第一次收到评估请求”时的入口文档" in eval_loop,
        "eval-loop should reject being the first entry point",
    )
    assert_true(
        "必须是用户已经明确确认过的版本" in eval_loop,
        "eval-loop should require a user-confirmed plan",
    )
    assert_true(
        "不要直接开始正式测评" in proposal_template,
        "proposal template should remind the model to stop before execution",
    )

    print("PASS: evaluation entry alignment regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

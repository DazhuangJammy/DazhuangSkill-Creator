#!/usr/bin/env python3
"""
Skill 初始化器：用固定的单文件/多文件脚手架创建新 skill。

用法：
    init_skill.py <skill-name> --path <path> [--resources scripts,references,assets] [--sections role,examples,output-format,index] [--memory-mode off|lessons|adaptive|auto] [--force-memory-off] [--intent <text>] [--examples] [--config-file] [--openai-yaml] [--interface key=value]
    init_skill.py <skill-name> [--config ./config.yaml]

示例：
    init_skill.py my-new-skill --path skills/public --memory-mode auto --intent "低风险的确定性整理任务"
    init_skill.py my-new-skill --path skills/public --resources references --memory-mode auto --intent "需要持续复盘的高变异任务"
    init_skill.py my-judge-skill --path skills/public --sections role,output-format --memory-mode auto --intent "需要边界判断的评审任务"
    init_skill.py my-api-helper --path skills/private --resources scripts,references,assets --examples --memory-mode auto --intent "会反复迭代的 API 排障助手"
    init_skill.py my-review-skill --path skills/public --memory-mode lessons
    init_skill.py my-analysis-skill --path skills/public --memory-mode auto --intent "要处理高变异输入并持续迭代"
    init_skill.py my-legacy-skill --path skills/public --memory-mode off --force-memory-off
    init_skill.py custom-skill --path /custom/location --memory-mode off --force-memory-off
    init_skill.py my-skill --path skills/public --memory-mode auto --intent "需要迭代优化的业务助手" --openai-yaml --interface short_description="中文界面说明"
    init_skill.py my-skill --config ./config.yaml
"""

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_openai_yaml import write_openai_yaml
from scripts.utils import (
    coalesce,
    configure_utf8_stdio,
    get_config_value,
    load_dazhuangskill_creator_config,
    write_utf8_text,
)

configure_utf8_stdio()

MAX_SKILL_NAME_LENGTH = 64
ALLOWED_RESOURCES = {"scripts", "references", "assets"}
ALLOWED_SECTIONS = {"role", "examples", "output-format", "index"}
ALLOWED_MEMORY_MODES = {"off", "lessons", "adaptive", "auto"}
SECTION_ORDER = ["role", "rules", "workflow", "examples", "output-format", "index"]

DEFAULT_MEMORY_AUTO_SCORES = {
    "lessons_score": 6,
    "adaptive_score": 3,
}

MEMORY_HARD_RULES_START = "<!-- MEMORY_HARD_RULES_START -->"
MEMORY_HARD_RULES_END = "<!-- MEMORY_HARD_RULES_END -->"

DEFAULT_MEMORY_THRESHOLDS = {
    "min_calls": 20,
    "min_retry_events": 2,
    "min_repeat_requests": 2,
    "window_size": 10,
    "failure_signature_threshold": 2,
    "promote_success_hits": 5,
    "promote_stable_window": 20,
    "max_active_lessons": 12,
    "retire_after_days": 30,
    "reactivation_cooldown_days": 14,
}

MEMORY_SIGNAL_KEYWORDS = {
    "high_variability": (
        "analysis",
        "analyze",
        "synthesis",
        "strategy",
        "strategic",
        "planning",
        "plan",
        "review",
        "critique",
        "judge",
        "advisor",
        "coach",
        "diagnose",
        "research",
        "interview",
        "brief",
        "memo",
        "risk",
        "policy",
        "design",
        "产品",
        "策略",
        "评审",
        "诊断",
        "研究",
        "复盘",
        "纪要",
        "总结",
        "风险",
        "治理",
        "决策",
    ),
    "high_stakes": (
        "security",
        "compliance",
        "legal",
        "finance",
        "financial",
        "medical",
        "incident",
        "release",
        "migration",
        "production",
        "监管",
        "合规",
        "法务",
        "财务",
        "医疗",
        "上线",
        "事故",
        "风控",
    ),
    "deterministic": (
        "convert",
        "converter",
        "format",
        "formatter",
        "lint",
        "rename",
        "slug",
        "commit",
        "changelog",
        "one-line",
        "single line",
        "regex",
        "csv",
        "json",
        "yaml",
        "toml",
        "template-fill",
        "转换",
        "格式化",
        "重命名",
        "压缩",
        "提取字段",
        "单行",
    ),
}

EXAMPLE_SCRIPT = '''#!/usr/bin/env python3
"""
{skill_name} 的示例辅助脚本

当某个确定性步骤每次都要重复写一遍时，才应该把它正式收进 scripts/。
如果这个占位脚本没有真实价值，就删掉它。
"""


def main():
    print("请把 scripts/example_task.py 替换成真正有价值的辅助脚本，或者直接删除它。")


if __name__ == "__main__":
    main()
'''

EXAMPLE_REFERENCE_EXAMPLES = """# 例子

只有在你真的需要给模型补 canonical case、边界判断样本或 few-shot 参考时，才读取这份文件。
这里放的是给 skill / 模型看的内部参考材料，不是教用户怎么提问的示例。

## 例子 1： [场景名]

场景：

```text
[描述模型会遇到的任务场景、输入材料或冲突点；不要只写一句用户问句]
```

在这个例子里，模型应该学到：

- [遇到什么信号时，优先采用哪种判断框架]
- [应该如何取舍、如何组织答案]
- [哪些常见误判或跑偏方式必须避免]

推荐输出落点：

```md
[只保留关键结构、关键句型或关键判断，不要写成冗长成品]
```
"""

EXAMPLE_REFERENCE_MEMORY_LESSONS = """# 记忆提炼（memory-lessons）

只记录“会改变下次决策”的可复用经验，不记录流水账、情绪反馈或无证据结论。

## 使用约束

- 默认最多保留 12 条，超过后先清理过期或低命中条目。
- 每次调用最多读取 3 条最相关经验；如果不相关，就不要读取。
- 同类坑重复出现（建议 >=2 次）后，必须新增或更新一条 lesson。
- 同一条 lesson 命中稳定且长期有效后，应该回写到 `SKILL.md` 的硬规则，再把 lesson 状态改为 `retired`。
- 超过 30 天未命中的 lesson，优先清理或降级。

## 条目模板

```md
### L-001: [短标题]

- 触发信号： [什么输入信号会触发这条经验]
- 推荐动作： [命中信号时该怎么做]
- 禁止项： [最容易跑偏的行为]
- 证据 ID： [关联到哪次评测、复盘或工单]
- 到期日： YYYY-MM-DD
- 状态： active | pending-removal | retired
```
"""

MEMORY_GUARD_SCRIPT_TEMPLATE = """#!/usr/bin/env python3
\"\"\"Memory guard for generated skills.

Tracks runtime events, detects repeated failures, maintains lessons, and
promotes stable lessons into hard rules in SKILL.md.
\"\"\"

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEFAULT_THRESHOLDS = __DEFAULT_THRESHOLDS__
MEMORY_LESSONS_TEMPLATE = __MEMORY_LESSONS_TEMPLATE__
STATE_FILE_RELATIVE = Path("references") / "memory-state.json"
EVENTS_FILE_RELATIVE = Path("references") / "memory-events.jsonl"
LESSONS_FILE_RELATIVE = Path("references") / "memory-lessons.md"
RISK_EVENTS = {"retry", "failure", "reject"}
SUCCESS_EVENTS = {"success", "accept"}
VALID_EVENTS = {"invoke", "retry", "failure", "success", "reject", "accept"}
VALID_MODES = {"adaptive", "lessons"}
MEMORY_HARD_RULES_START = "<!-- MEMORY_HARD_RULES_START -->"
MEMORY_HARD_RULES_END = "<!-- MEMORY_HARD_RULES_END -->"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso_time(value: str) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def to_positive_int(value, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def normalize_request(text: str) -> str:
    return " ".join((text or "").lower().split())


def signature_for_request(text: str) -> str:
    normalized = normalize_request(text)
    if not normalized:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8",
        newline="\\n",
    )


def append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False)
    with path.open("a", encoding="utf-8", newline="\\n") as handle:
        handle.write(line + "\\n")


def ensure_lessons_file(skill_dir: Path) -> Path:
    lessons_path = skill_dir / LESSONS_FILE_RELATIVE
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    if not lessons_path.exists():
        lessons_path.write_text(
            MEMORY_LESSONS_TEMPLATE,
            encoding="utf-8",
            newline="\\n",
        )
    return lessons_path


def trim_mapping(mapping: dict, limit: int = 300) -> dict:
    if len(mapping) <= limit:
        return mapping
    ranked = sorted(
        mapping.items(),
        key=lambda item: item[1].get("updated_at", ""),
        reverse=True,
    )
    return dict(ranked[:limit])


def initialize_state(raw_state: dict) -> dict:
    state = raw_state if isinstance(raw_state, dict) else {}
    mode = str(state.get("mode", "adaptive")).strip().lower()
    if mode not in VALID_MODES:
        mode = "adaptive"

    raw_thresholds = state.get("thresholds", {})
    thresholds = {}
    for key, fallback in DEFAULT_THRESHOLDS.items():
        value = raw_thresholds.get(key, fallback) if isinstance(raw_thresholds, dict) else fallback
        thresholds[key] = to_positive_int(value, fallback)

    quality_events = state.get("recent_quality_events", [])
    if not isinstance(quality_events, list):
        quality_events = []
    quality_events = [str(item) for item in quality_events if str(item) in VALID_EVENTS]

    signatures = state.get("signatures", {})
    if not isinstance(signatures, dict):
        signatures = {}

    hard_rules = state.get("hard_rules", [])
    if not isinstance(hard_rules, list):
        hard_rules = []
    normalized_hard_rules = []
    for item in hard_rules:
        if not isinstance(item, dict):
            continue
        signature = str(item.get("signature", "")).strip()
        rule = str(item.get("rule", "")).strip()
        if not signature or not rule:
            continue
        normalized_hard_rules.append(
            {
                "signature": signature,
                "rule": rule,
                "source_lesson_id": str(item.get("source_lesson_id", "")).strip(),
                "created_at": str(item.get("created_at", "")).strip(),
            }
        )

    return {
        "mode": mode,
        "memory_enabled": bool(state.get("memory_enabled", mode == "lessons")),
        "enabled_at": str(state.get("enabled_at", "")).strip(),
        "thresholds": thresholds,
        "total_calls": to_positive_int(state.get("total_calls", 0), 0),
        "retry_events": to_positive_int(state.get("retry_events", 0), 0),
        "failure_events": to_positive_int(state.get("failure_events", 0), 0),
        "success_events": to_positive_int(state.get("success_events", 0), 0),
        "reject_events": to_positive_int(state.get("reject_events", 0), 0),
        "accept_events": to_positive_int(state.get("accept_events", 0), 0),
        "recent_quality_events": quality_events,
        "signatures": signatures,
        "hard_rules": normalized_hard_rules,
        "lesson_counter": to_positive_int(state.get("lesson_counter", 0), 0),
        "last_event": str(state.get("last_event", "")).strip(),
        "updated_at": str(state.get("updated_at", "")).strip(),
    }


def ensure_signature_record(state: dict, signature: str, request_text: str) -> dict:
    signatures = state["signatures"]
    entry = signatures.get(signature)
    if not isinstance(entry, dict):
        entry = {}

    request_sample = str(entry.get("request_sample", "")).strip() or (request_text or "").strip()
    lesson_status = str(entry.get("lesson_status", "none")).strip()
    if lesson_status not in {"none", "active", "pending-removal", "retired"}:
        lesson_status = "none"

    recent_events = entry.get("recent_events", [])
    if not isinstance(recent_events, list):
        recent_events = []
    recent_events = [str(item) for item in recent_events if str(item) in VALID_EVENTS]

    normalized = {
        "request_sample": request_sample,
        "invoke_count": to_positive_int(entry.get("invoke_count", 0), 0),
        "retry_count": to_positive_int(entry.get("retry_count", 0), 0),
        "failure_count": to_positive_int(entry.get("failure_count", 0), 0),
        "success_count": to_positive_int(entry.get("success_count", 0), 0),
        "reject_count": to_positive_int(entry.get("reject_count", 0), 0),
        "accept_count": to_positive_int(entry.get("accept_count", 0), 0),
        "lesson_status": lesson_status,
        "lesson_id": str(entry.get("lesson_id", "")).strip(),
        "lesson_hits": to_positive_int(entry.get("lesson_hits", 0), 0),
        "lesson_created_at": str(entry.get("lesson_created_at", "")).strip(),
        "promoted_at": str(entry.get("promoted_at", "")).strip(),
        "retired_at": str(entry.get("retired_at", "")).strip(),
        "risk_cursor": to_positive_int(entry.get("risk_cursor", 0), 0),
        "reactivation_allowed_at": str(entry.get("reactivation_allowed_at", "")).strip(),
        "last_event_at": str(entry.get("last_event_at", "")).strip(),
        "updated_at": str(entry.get("updated_at", "")).strip(),
        "recent_events": recent_events,
    }
    signatures[signature] = normalized
    return normalized


def risk_total(entry: dict) -> int:
    return (
        to_positive_int(entry.get("retry_count", 0), 0)
        + to_positive_int(entry.get("failure_count", 0), 0)
        + to_positive_int(entry.get("reject_count", 0), 0)
    )


def set_reactivation_guard(entry: dict, cooldown_days: int) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    entry["risk_cursor"] = risk_total(entry)
    if cooldown_days > 0:
        entry["reactivation_allowed_at"] = (now + timedelta(days=cooldown_days)).isoformat()
    else:
        entry["reactivation_allowed_at"] = ""


def update_signature_entry(entry: dict, event: str, thresholds: dict) -> None:
    now = utc_now()
    if event == "invoke":
        entry["invoke_count"] += 1
    elif event == "retry":
        entry["retry_count"] += 1
        entry["lesson_hits"] = 0
    elif event == "failure":
        entry["failure_count"] += 1
        entry["lesson_hits"] = 0
    elif event == "reject":
        entry["reject_count"] += 1
        entry["lesson_hits"] = 0
    elif event == "success":
        entry["success_count"] += 1
        if entry["lesson_status"] == "active":
            entry["lesson_hits"] += 1
    elif event == "accept":
        entry["accept_count"] += 1
        if entry["lesson_status"] == "active":
            entry["lesson_hits"] += 1

    entry["recent_events"].append(event)
    stable_window = thresholds.get("promote_stable_window", 20)
    entry["recent_events"] = entry["recent_events"][-max(stable_window, 1):]
    entry["last_event_at"] = now
    entry["updated_at"] = now


def update_global_counters(state: dict, event: str) -> None:
    if event == "invoke":
        state["total_calls"] += 1
    elif event == "retry":
        state["retry_events"] += 1
        state["recent_quality_events"].append("retry")
    elif event == "failure":
        state["failure_events"] += 1
        state["recent_quality_events"].append("failure")
    elif event == "success":
        state["success_events"] += 1
        state["recent_quality_events"].append("success")
    elif event == "reject":
        state["reject_events"] += 1
        state["recent_quality_events"].append("reject")
    elif event == "accept":
        state["accept_events"] += 1
        state["recent_quality_events"].append("accept")
    window_size = state["thresholds"].get("window_size", 10)
    state["recent_quality_events"] = state["recent_quality_events"][-max(window_size, 1):]
    state["last_event"] = event
    state["updated_at"] = utc_now()


def maybe_enable_memory(state: dict, skill_dir: Path) -> tuple[bool, str]:
    if state["memory_enabled"]:
        return False, ""
    if state["mode"] == "lessons":
        state["memory_enabled"] = True
        state["enabled_at"] = utc_now()
        lessons_path = ensure_lessons_file(skill_dir)
        return True, str(lessons_path)

    thresholds = state["thresholds"]
    recent_risk_events = sum(1 for item in state["recent_quality_events"] if item in RISK_EVENTS)
    max_repeat_count = 0
    for entry in state["signatures"].values():
        if not isinstance(entry, dict):
            continue
        repeat = (
            to_positive_int(entry.get("invoke_count", 0), 0)
            + to_positive_int(entry.get("retry_count", 0), 0)
            + to_positive_int(entry.get("failure_count", 0), 0)
            + to_positive_int(entry.get("success_count", 0), 0)
            + to_positive_int(entry.get("reject_count", 0), 0)
            + to_positive_int(entry.get("accept_count", 0), 0)
        )
        if repeat > max_repeat_count:
            max_repeat_count = repeat

    should_enable = (
        state["total_calls"] >= thresholds["min_calls"]
        and (
            recent_risk_events >= thresholds["min_retry_events"]
            or max_repeat_count >= thresholds["min_repeat_requests"]
        )
    )
    if not should_enable:
        return False, ""

    state["memory_enabled"] = True
    state["enabled_at"] = utc_now()
    lessons_path = ensure_lessons_file(skill_dir)
    return True, str(lessons_path)


def next_lesson_id(state: dict) -> str:
    state["lesson_counter"] += 1
    return f"L-{state['lesson_counter']:03d}"


def sync_lessons(state: dict) -> None:
    if not state["memory_enabled"]:
        return
    thresholds = state["thresholds"]
    failure_threshold = thresholds.get("failure_signature_threshold", 2)
    cooldown_days = thresholds.get("reactivation_cooldown_days", 14)
    max_active = thresholds.get("max_active_lessons", 12)
    now = datetime.now(timezone.utc)
    active_entries = [
        entry
        for entry in state["signatures"].values()
        if isinstance(entry, dict) and entry.get("lesson_status") == "active"
    ]
    active_count = len(active_entries)

    for entry in state["signatures"].values():
        if not isinstance(entry, dict):
            continue
        total_risk = risk_total(entry)
        risk_cursor = to_positive_int(entry.get("risk_cursor", 0), 0)
        if risk_cursor > total_risk:
            risk_cursor = total_risk
        incremental_risk = total_risk - risk_cursor
        status = str(entry.get("lesson_status", "none"))
        if status in {"retired", "pending-removal"}:
            allowed_at = parse_iso_time(str(entry.get("reactivation_allowed_at", "")).strip())
            if allowed_at and now < allowed_at:
                continue
        if incremental_risk >= failure_threshold and status in {"none", "retired", "pending-removal"}:
            if active_count >= max_active and status == "none":
                continue
            if not entry.get("lesson_id"):
                entry["lesson_id"] = next_lesson_id(state)
            entry["lesson_status"] = "active"
            entry["lesson_created_at"] = entry.get("lesson_created_at") or utc_now()
            entry["retired_at"] = ""
            entry["promoted_at"] = ""
            entry["lesson_hits"] = 0
            entry["risk_cursor"] = total_risk
            entry["reactivation_allowed_at"] = ""
            active_count += 1


def promote_hard_rules(state: dict) -> None:
    thresholds = state["thresholds"]
    promote_hits = thresholds.get("promote_success_hits", 5)
    cooldown_days = thresholds.get("reactivation_cooldown_days", 14)
    for signature, entry in state["signatures"].items():
        if not isinstance(entry, dict):
            continue
        if entry.get("lesson_status") != "active":
            continue
        recent_events = [str(item) for item in entry.get("recent_events", [])]
        recent_risk = sum(1 for item in recent_events if item in RISK_EVENTS)
        lesson_hits = to_positive_int(entry.get("lesson_hits", 0), 0)
        if lesson_hits < promote_hits or recent_risk > 0:
            continue

        request_sample = (entry.get("request_sample") or "").strip() or signature
        existing = next(
            (item for item in state["hard_rules"] if item.get("signature") == signature),
            None,
        )
        rule_text = (
            f"当请求接近“{request_sample}”时，先执行一次关键约束自检，"
            "并避开该签名历史失败路径；输出前完成最终一致性检查。"
        )
        if existing:
            existing["rule"] = rule_text
            existing["source_lesson_id"] = entry.get("lesson_id", "")
            existing["created_at"] = existing.get("created_at") or utc_now()
        else:
            state["hard_rules"].append(
                {
                    "signature": signature,
                    "rule": rule_text,
                    "source_lesson_id": entry.get("lesson_id", ""),
                    "created_at": utc_now(),
                }
            )
        entry["lesson_status"] = "retired"
        entry["promoted_at"] = utc_now()
        entry["retired_at"] = entry["promoted_at"]
        entry["lesson_hits"] = 0
        set_reactivation_guard(entry, cooldown_days)


def retire_inactive_lessons(state: dict) -> None:
    retire_after_days = state["thresholds"].get("retire_after_days", 30)
    cooldown_days = state["thresholds"].get("reactivation_cooldown_days", 14)
    if retire_after_days <= 0:
        return
    now = datetime.now(timezone.utc)
    for entry in state["signatures"].values():
        if not isinstance(entry, dict):
            continue
        status = entry.get("lesson_status")
        if status not in {"active", "pending-removal"}:
            continue
        last_event_at = parse_iso_time(str(entry.get("last_event_at", "")).strip())
        if last_event_at is None:
            continue
        if now - last_event_at < timedelta(days=retire_after_days):
            continue
        if status == "active":
            entry["lesson_status"] = "pending-removal"
            entry["updated_at"] = utc_now()
        elif status == "pending-removal":
            entry["lesson_status"] = "retired"
            entry["retired_at"] = utc_now()
            entry["updated_at"] = entry["retired_at"]
            set_reactivation_guard(entry, cooldown_days)


def render_lessons_markdown(state: dict) -> str:
    ordered = sorted(
        (
            (signature, entry)
            for signature, entry in state["signatures"].items()
            if isinstance(entry, dict) and entry.get("lesson_status") in {"active", "pending-removal", "retired"}
        ),
        key=lambda item: item[1].get("updated_at", ""),
        reverse=True,
    )
    active = [(sig, entry) for sig, entry in ordered if entry.get("lesson_status") == "active"]
    pending = [(sig, entry) for sig, entry in ordered if entry.get("lesson_status") == "pending-removal"]
    retired = [(sig, entry) for sig, entry in ordered if entry.get("lesson_status") == "retired"]

    lines = [
        "# 记忆提炼（memory-lessons）",
        "",
        "只记录“会改变下次决策”的可复用经验，不记录流水账、情绪反馈或无证据结论。",
        "",
        "## 使用约束",
        "",
        "- 默认最多保留 12 条，超过后先清理过期或低命中条目。",
        "- 每次调用最多读取 3 条最相关经验；如果不相关，就不要读取。",
        "- 同类坑重复出现（建议 >=2 次）后，必须新增或更新一条 lesson。",
        "- 同一条 lesson 命中稳定且长期有效后，应该回写到 `SKILL.md` 的硬规则，再把 lesson 状态改为 `retired`。",
        "- 超过 30 天未命中的 lesson，优先清理或降级。",
        "",
    ]

    def append_entries(title: str, entries: list[tuple[str, dict]]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not entries:
            lines.append("- 无")
            lines.append("")
            return
        for signature, entry in entries:
            lesson_id = entry.get("lesson_id") or "L-000"
            sample = (entry.get("request_sample") or signature).strip()
            lines.extend(
                [
                    f"### {lesson_id}: {sample[:80]}",
                    "",
                    f"- 触发信号：签名 `{signature}` 的请求在窗口内重复出现风险事件",
                    "- 推荐动作：先核对关键约束，再按历史稳定路径输出；输出前做一次自检。",
                    "- 禁止项：重复使用已知失败路径，或跳过关键约束检查。",
                    f"- 证据 ID：{signature}",
                    f"- 到期日：{entry.get('retired_at') or '待评估'}",
                    f"- 状态：{entry.get('lesson_status')}",
                    (
                        "- 统计："
                        f" invoke={entry.get('invoke_count', 0)},"
                        f" retry={entry.get('retry_count', 0)},"
                        f" failure={entry.get('failure_count', 0)},"
                        f" success={entry.get('success_count', 0)},"
                        f" lesson_hits={entry.get('lesson_hits', 0)}"
                    ),
                    "",
                ]
            )

    append_entries("Active Lessons", active)
    append_entries("Pending Removal", pending)
    append_entries("Retired Lessons", retired)
    return "\\n".join(lines).rstrip() + "\\n"


def sync_hard_rules_to_skill(skill_dir: Path, hard_rules: list[dict]) -> None:
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.exists():
        return
    try:
        content = skill_path.read_text(encoding="utf-8-sig")
    except OSError:
        return

    block_lines = [MEMORY_HARD_RULES_START]
    if hard_rules:
        for index, rule in enumerate(hard_rules, start=1):
            text = str(rule.get("rule", "")).strip()
            if not text:
                continue
            block_lines.append(f"- [Memory Hard Rule {index}] {text}")
    else:
        block_lines.append("- [Memory Hard Rule] [AUTO] 暂无已晋升规则。")
    block_lines.append(MEMORY_HARD_RULES_END)
    block = "\\n".join(block_lines)

    if MEMORY_HARD_RULES_START in content and MEMORY_HARD_RULES_END in content:
        before, rest = content.split(MEMORY_HARD_RULES_START, 1)
        _, after = rest.split(MEMORY_HARD_RULES_END, 1)
        updated = before + block + after
    else:
        anchor = "\\n# 工作流程\\n"
        insert = block + "\\n\\n"
        if anchor in content:
            updated = content.replace(anchor, "\\n" + insert + "# 工作流程\\n", 1)
        else:
            updated = content.rstrip() + "\\n\\n" + insert
    skill_path.write_text(updated, encoding="utf-8", newline="\\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory mode guard.")
    parser.add_argument("--skill-dir", default=".", help="Skill 根目录")
    parser.add_argument(
        "--event",
        choices=sorted(VALID_EVENTS),
        default="invoke",
        help="本次事件类型",
    )
    parser.add_argument("--request", default="", help="当前请求摘要（可选）")
    parser.add_argument("--mode", choices=sorted(VALID_MODES), default=None, help="覆盖模式（adaptive 或 lessons）")
    parser.add_argument("--min-calls", type=int, default=None)
    parser.add_argument("--min-retry-events", type=int, default=None)
    parser.add_argument("--min-repeat-requests", type=int, default=None)
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--failure-signature-threshold", type=int, default=None)
    parser.add_argument("--promote-success-hits", type=int, default=None)
    parser.add_argument("--promote-stable-window", type=int, default=None)
    parser.add_argument("--max-active-lessons", type=int, default=None)
    parser.add_argument("--retire-after-days", type=int, default=None)
    parser.add_argument("--reactivation-cooldown-days", type=int, default=None)
    parser.add_argument("--quiet", action="store_true", help="只输出关键消息")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skill_dir = Path(args.skill_dir).resolve()
    state_path = skill_dir / STATE_FILE_RELATIVE
    events_path = skill_dir / EVENTS_FILE_RELATIVE
    lessons_path = skill_dir / LESSONS_FILE_RELATIVE

    state = initialize_state(read_json(state_path))
    if args.mode:
        state["mode"] = args.mode
        if args.mode == "lessons":
            state["memory_enabled"] = True
            state["enabled_at"] = state.get("enabled_at") or utc_now()

    overrides = {
        "min_calls": args.min_calls,
        "min_retry_events": args.min_retry_events,
        "min_repeat_requests": args.min_repeat_requests,
        "window_size": args.window_size,
        "failure_signature_threshold": args.failure_signature_threshold,
        "promote_success_hits": args.promote_success_hits,
        "promote_stable_window": args.promote_stable_window,
        "max_active_lessons": args.max_active_lessons,
        "retire_after_days": args.retire_after_days,
        "reactivation_cooldown_days": args.reactivation_cooldown_days,
    }
    for key, value in overrides.items():
        if value is None:
            continue
        state["thresholds"][key] = to_positive_int(value, state["thresholds"][key])

    request_text = (args.request or "").strip()
    signature = signature_for_request(request_text)
    update_global_counters(state, args.event)
    if signature:
        entry = ensure_signature_record(state, signature, request_text)
        update_signature_entry(entry, args.event, state["thresholds"])
    state["signatures"] = trim_mapping(state["signatures"])

    event_payload = {
        "timestamp": utc_now(),
        "event": args.event,
        "request": request_text,
        "signature": signature,
        "memory_enabled": state["memory_enabled"],
    }
    append_event(events_path, event_payload)

    enabled_now, enabled_path = maybe_enable_memory(state, skill_dir)
    sync_lessons(state)
    promote_hard_rules(state)
    retire_inactive_lessons(state)

    if state["memory_enabled"]:
        ensure_lessons_file(skill_dir)
        lessons_markdown = render_lessons_markdown(state)
        lessons_path.write_text(lessons_markdown, encoding="utf-8", newline="\\n")
        sync_hard_rules_to_skill(skill_dir, state["hard_rules"])

    write_json(state_path, state)

    recent_risk_events = sum(1 for item in state["recent_quality_events"] if item in RISK_EVENTS)
    active_lessons = sum(
        1
        for entry in state["signatures"].values()
        if isinstance(entry, dict) and entry.get("lesson_status") == "active"
    )

    if not args.quiet:
        print(
            "[memory-mode] "
            f"mode={state['mode']} "
            f"enabled={state['memory_enabled']} "
            f"event={args.event} "
            f"calls={state['total_calls']} "
            f"recent_risk={recent_risk_events} "
            f"active_lessons={active_lessons}"
        )
    if enabled_now:
        print(
            "[memory-mode] auto-enabled lessons: "
            f"{enabled_path} "
            "(triggered by thresholds)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

EXAMPLE_ASSET_OUTPUT_FORMAT = """# 输出格式

只有当最终输出需要稳定结构时，才读取这份文件。
这里放的是给 skill / 模型直接遵循的模板、骨架或字段约束，不是给用户看的说明文字。
如果这个 skill 的输出天然开放，就不要保留这份文件。

## 默认行为

- [描述默认输出行为]

## 推荐结构

```md
[把这里替换成输出骨架]
```

## 扩写边界

- [只有在什么条件下才允许多写]

## 禁止项

- [哪些解释、备选项或 body 不应该出现]
"""

EXAMPLE_CONFIG = """# 人工可编辑的 skill 参数
# 经常要调的值放这里，不要另外发明一份手写 JSON。
# 机器写入的运行产物、缓存、API payload 再继续用 JSON。

defaults:
  # 在这里补具体参数。
"""


def normalize_skill_name(skill_name):
    """Normalize a skill name to lowercase hyphen-case."""
    normalized = skill_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized


def parse_resources(raw_resources):
    if not raw_resources:
        return []
    resources = [item.strip() for item in raw_resources.split(",") if item.strip()]
    invalid = sorted({item for item in resources if item not in ALLOWED_RESOURCES})
    if invalid:
        allowed = ", ".join(sorted(ALLOWED_RESOURCES))
        print(f"[ERROR] 未知资源类型：{', '.join(invalid)}")
        print(f"   可选值：{allowed}")
        sys.exit(1)
    deduped = []
    seen = set()
    for resource in resources:
        if resource not in seen:
            deduped.append(resource)
            seen.add(resource)
    return deduped


def parse_sections(raw_sections):
    if not raw_sections:
        return []
    sections = [item.strip() for item in raw_sections.split(",") if item.strip()]
    invalid = sorted({item for item in sections if item not in ALLOWED_SECTIONS})
    if invalid:
        allowed = ", ".join(sorted(ALLOWED_SECTIONS))
        print(f"[ERROR] 未知 section：{', '.join(invalid)}")
        print(f"   可选值：{allowed}")
        sys.exit(1)
    deduped = []
    seen = set()
    for section in SECTION_ORDER:
        if section in sections and section not in seen:
            deduped.append(section)
            seen.add(section)
    return deduped


def parse_memory_mode(raw_mode):
    if raw_mode is None:
        return "auto"
    if isinstance(raw_mode, bool):
        return "lessons" if raw_mode else "off"
    mode = str(raw_mode).strip().lower()
    aliases = {
        "on": "lessons",
        "enabled": "lessons",
        "required": "lessons",
    }
    mode = aliases.get(mode, mode)
    if mode not in ALLOWED_MEMORY_MODES:
        allowed = ", ".join(sorted(ALLOWED_MEMORY_MODES))
        print(f"[ERROR] 未知 memory_mode：{mode}")
        print(f"   可选值：{allowed}")
        sys.exit(1)
    return mode


def parse_positive_int(raw_value, field_name):
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        print(f"[ERROR] {field_name} 必须是正整数，当前值：{raw_value}")
        sys.exit(1)
    if parsed <= 0:
        print(f"[ERROR] {field_name} 必须是正整数，当前值：{raw_value}")
        sys.exit(1)
    return parsed


def parse_memory_auto_scores(raw_scores):
    scores = dict(DEFAULT_MEMORY_AUTO_SCORES)
    if raw_scores is None:
        return scores
    if not isinstance(raw_scores, dict):
        print("[ERROR] config.yaml 里的 init_skill.memory_auto 必须是 YAML 映射。")
        sys.exit(1)
    for key in scores:
        if key in raw_scores:
            scores[key] = parse_positive_int(raw_scores[key], f"init_skill.memory_auto.{key}")
    if scores["lessons_score"] <= scores["adaptive_score"]:
        print("[ERROR] init_skill.memory_auto.lessons_score 必须大于 adaptive_score。")
        sys.exit(1)
    return scores


def parse_memory_thresholds(raw_thresholds):
    thresholds = dict(DEFAULT_MEMORY_THRESHOLDS)
    if raw_thresholds is None:
        return thresholds
    if not isinstance(raw_thresholds, dict):
        print("[ERROR] config.yaml 里的 init_skill.memory_thresholds 必须是 YAML 映射。")
        sys.exit(1)
    for key in thresholds:
        if key in raw_thresholds:
            thresholds[key] = parse_positive_int(
                raw_thresholds[key],
                f"init_skill.memory_thresholds.{key}",
            )
    return thresholds


def classify_memory_mode(skill_name, intent, resources, sections, auto_scores):
    signal_text = " ".join(
        [skill_name or "", intent or "", " ".join(resources or []), " ".join(sections or [])]
    ).lower()

    score = 0
    reasons = []

    for keyword in MEMORY_SIGNAL_KEYWORDS["high_stakes"]:
        if keyword in signal_text:
            score += 4
            reasons.append(f"+4 high-stakes keyword: {keyword}")
    for keyword in MEMORY_SIGNAL_KEYWORDS["high_variability"]:
        if keyword in signal_text:
            score += 2
            reasons.append(f"+2 high-variability keyword: {keyword}")
    for keyword in MEMORY_SIGNAL_KEYWORDS["deterministic"]:
        if keyword in signal_text:
            score -= 3
            reasons.append(f"-3 deterministic keyword: {keyword}")

    if "references" in resources:
        score += 1
        reasons.append("+1 resource signal: references/")
    if "role" in sections:
        score += 1
        reasons.append("+1 structure signal: role section")
    if "examples" in sections:
        score += 1
        reasons.append("+1 structure signal: examples section")

    if score >= auto_scores["lessons_score"]:
        resolved_mode = "lessons"
    elif score >= auto_scores["adaptive_score"]:
        resolved_mode = "adaptive"
    else:
        resolved_mode = "off"

    preview = reasons[:5]
    if len(reasons) > 5:
        preview.append(f"... and {len(reasons) - 5} more signals")
    return resolved_mode, score, preview


def resolve_memory_mode(requested_mode, skill_name, intent, resources, sections, auto_scores):
    if requested_mode != "auto":
        return requested_mode, None
    resolved_mode, score, reasons = classify_memory_mode(
        skill_name,
        intent,
        resources,
        sections,
        auto_scores,
    )
    auto_summary = {
        "score": score,
        "reasons": reasons,
        "resolved_mode": resolved_mode,
    }
    return resolved_mode, auto_summary


def build_auto_memory_summary(skill_name, intent, resources, sections, auto_scores):
    resolved_mode, score, reasons = classify_memory_mode(
        skill_name,
        intent,
        resources,
        sections,
        auto_scores,
    )
    return {
        "score": score,
        "reasons": reasons,
        "resolved_mode": resolved_mode,
    }


def enforce_auto_memory_intent_guard(requested_memory_mode, memory_intent, auto_reference_summary):
    """Guard against silent auto->off when no intent signal is provided."""
    if requested_memory_mode != "auto":
        return

    if str(memory_intent or "").strip():
        return

    suggested_mode = auto_reference_summary["resolved_mode"]
    if suggested_mode != "off":
        print(
            "[WARN] 你当前使用了 memory_mode=auto，但没有提供 --intent。"
            " 这次会继续执行，不过建议补一句 intent 提高判型稳定性。"
        )
        return

    print("[ERROR] 你当前使用了 memory_mode=auto，但没有提供 --intent，且 auto 判型暂时落到 off。")
    print("        为了确保“是否启用记忆层”经过显式判断，这次初始化已暂停。")
    print("        请二选一：")
    print("        1) 追加 --intent \"...\"，让 auto 判型拿到业务语义；")
    print("        2) 明确指定 --memory-mode off/adaptive/lessons。")
    print("        如果你确认要强制关闭，请使用 --memory-mode off --force-memory-off。")
    sys.exit(1)


def enforce_memory_off_guard(
    requested_memory_mode,
    auto_reference_summary,
    force_memory_off,
    memory_mode_from_cli,
):
    if requested_memory_mode != "off":
        return

    suggested_mode = auto_reference_summary["resolved_mode"]
    if suggested_mode == "off":
        return

    suggestion_line = (
        f"auto 判型建议是 `{suggested_mode}`（score={auto_reference_summary['score']}），"
        "因为检测到了高风险或高变异信号。"
    )

    if force_memory_off:
        print("[WARN] 你使用了 --force-memory-off，已按要求继续关闭记忆层。")
        print(f"       但 {suggestion_line}")
        return

    if memory_mode_from_cli:
        print("[ERROR] 你手动传了 `--memory-mode off`，但当前 skill 不建议关闭记忆层。")
    else:
        print("[ERROR] config.yaml 里 `init_skill.memory_mode=off`，但当前 skill 不建议关闭记忆层。")
    print(f"        {suggestion_line}")
    print("        如果你确认要强制关闭，请追加 `--force-memory-off`。")
    if memory_mode_from_cli:
        print("        否则请改用 `--memory-mode auto` 或直接指定 `adaptive/lessons`。")
    else:
        print("        否则请把 config.yaml 的 `init_skill.memory_mode` 改回 `auto`。")
    sys.exit(1)


def validate_structure_choices(resources, sections, memory_mode):
    if "references" in resources and "examples" in sections:
        print("[ERROR] 启用 references/ 时，不要再把 `# 例子` 内联到主 SKILL.md。")
        print("   二选一：要么用单文件 `# 例子`，要么把例子下沉到 references/examples.md。")
        sys.exit(1)
    if "assets" in resources and "output-format" in sections:
        print("[ERROR] 启用 assets/ 时，不要再把 `# 输出格式` 内联到主 SKILL.md。")
        print("   二选一：要么用单文件 `# 输出格式`，要么把输出格式下沉到 assets/output-format.md。")
        sys.exit(1)
    if memory_mode == "lessons" and ("references" not in resources or "scripts" not in resources):
        print("[ERROR] memory_mode=lessons 需要 references/ 和 scripts/。")
        print("   请在 --resources 里包含 references,scripts，或把 memory_mode 设为 off。")
        sys.exit(1)
    if memory_mode == "adaptive" and ("references" not in resources or "scripts" not in resources):
        print("[ERROR] memory_mode=adaptive 需要 references/ 和 scripts/。")
        print("   请在 --resources 里包含 references,scripts，或把 memory_mode 改成 off/lessons。")
        sys.exit(1)


def needs_skill_base_rule(resources, create_config, create_openai_yaml):
    return bool(resources or create_config or create_openai_yaml)


def render_memory_guard_script(default_thresholds):
    script = MEMORY_GUARD_SCRIPT_TEMPLATE
    script = script.replace(
        "__DEFAULT_THRESHOLDS__",
        json.dumps(default_thresholds, ensure_ascii=False, indent=4),
    )
    script = script.replace(
        "__MEMORY_LESSONS_TEMPLATE__",
        repr(EXAMPLE_REFERENCE_MEMORY_LESSONS),
    )
    return script


def render_skill_template(skill_name, sections, resources, create_config, create_openai_yaml, memory_mode):
    require_skill_base = needs_skill_base_rule(resources, create_config, create_openai_yaml)
    has_memory_runtime = memory_mode in {"lessons", "adaptive"}
    blocks = [
        "---",
        f"name: {skill_name}",
        "description: [TODO: 说明这个 skill 帮用户解决什么问题、什么时候应该触发、什么情况下不要触发。]",
        "---",
        "",
    ]

    if "role" in sections:
        blocks.extend(
            [
                "# 角色",
                "",
                "- [TODO: 先判断这是“扮演角色”还是“借用视角”，只选一个主方向。]",
                "- [TODO: 定义这个 skill 的判断视角、身份边界或表达姿态。]",
                "- [TODO: 如果借用某个人物或方法论，默认写成“借用其判断框架，不模仿口吻”。]",
                "",
            ]
        )

    blocks.extend(
        [
            "# 规则",
            "",
            "- 这里只保留对当前 skill 真正承重的规则；能交给 creator、validator 或 bundled resources 保证的通用结构说明，不要原封不动塞进最终版。",
            "- [TODO: 只补充真正耐久、真正承重的规则。]",
            "- [TODO: 新建时必须先判断记忆层是否需要开启；就算最后结论是 off，也要写明理由。]",
        ]
    )

    if require_skill_base:
        blocks.insert(
            len(blocks) - 1,
            "- 把当前 `SKILL.md` 所在目录视为 `<skill-base>`。所有 bundled resources 都从这里解析，不要依赖调用方当前工作目录。",
        )
    if "scripts" in resources:
        blocks.insert(
            len(blocks) - 1,
            "- 当工作流要运行 bundled script 时，优先写成显式命令，例如 `<python-cmd> \"<skill-base>/scripts/...\"`；其中 `<python-cmd>` 在 macOS/Linux 通常是 `python3`，Windows 通常优先 `py -3`，其次 `python`。",
        )
    if create_config:
        blocks.insert(
            len(blocks) - 1,
            "- 这个 skill 已启用 `<skill-base>/config.yaml`；只有当流程真的依赖可调参数时才读取它。",
        )

    if "references" in resources:
        blocks.append("- 已启用 `references/` 时，只在需要低频边界、内部参考例子或 few-shot 材料时读取 `<skill-base>/references/examples.md`。")
    if memory_mode == "lessons":
        blocks.append(
            "- 已启用记忆层（`memory_mode=lessons`）时，默认从第 1 次调用开始记录事件；每次先读 `<skill-base>/references/memory-lessons.md` 的相关 active 经验（最多 3 条），同类坑重复出现后更新 lesson。"
        )
    if memory_mode == "adaptive":
        blocks.append(
            "- 已启用自适应记忆层（`memory_mode=adaptive`）时，通过 `<python-cmd> \"<skill-base>/scripts/memory_mode_guard.py\"` 追踪调用摩擦；当 `references/memory-state.json` 里的 `memory_enabled=true` 时，后续调用必须先读 `memory-lessons`。"
        )
    if has_memory_runtime:
        blocks.extend(
            [
                "- 记忆硬规则由 guard 自动回写到 `# 规则` 区块中的 `MEMORY_HARD_RULES` 标记内；不要手工改写该标记块。",
                "- `memory-state.json` 是运行计数器，`memory-events.jsonl` 是事件轨迹，`memory-lessons.md` 是给模型读取的提炼层。",
                "- 以下硬规则块由 memory guard 自动维护：",
                MEMORY_HARD_RULES_START,
                "- [Memory Hard Rule] [AUTO] 暂无已晋升规则。",
                MEMORY_HARD_RULES_END,
            ]
        )
    if "assets" in resources:
        blocks.append("- 已启用 `assets/` 时，只在需要稳定交付模板、固定骨架或字段约束时读取 `<skill-base>/assets/output-format.md`。")

    blocks.extend(
        [
            "- [TODO: 删除泛泛建议，只保留任务专属约束。]",
            "",
            "# 工作流程",
            "",
            "## Step 1：先判断任务",
            "",
            "- [TODO: 提取任务类型、输入、约束、缺失信息。]",
            "- 先判断这个 skill 需不需要 `角色`、`例子`、`输出格式`、`索引`；不需要就不要加。",
            "- 这一步必须完成“记忆层判断”：先判断这次是 `off`、`adaptive` 还是 `lessons`，并记录判断理由（高风险 / 高变异 / 低风险确定性）。",
        ]
    )

    if require_skill_base:
        blocks.append("- 如果这个 skill 带有本地资源，统一沿 `<skill-base>` 解析，不要依赖当前工作目录。")
    if create_config:
        blocks.append("- 只有当流程真的依赖可调参数时，才读取 `<skill-base>/config.yaml`。")
    if "references" in resources:
        blocks.append("- 如果需要下沉的例子，读取 `<skill-base>/references/examples.md`；这里的例子是给模型看的内部参考，不是用户问句示例。")
    if memory_mode == "lessons":
        blocks.append(
            "- 先运行 `<python-cmd> \"<skill-base>/scripts/memory_mode_guard.py\" --skill-dir \"<skill-base>\" --mode lessons --event invoke` 记录调用；再读取 `references/memory-lessons.md` 的 active 条目（最多 3 条相关经验）。"
        )
    if memory_mode == "adaptive":
        blocks.append(
            "- 先运行 `<python-cmd> \"<skill-base>/scripts/memory_mode_guard.py\" --skill-dir \"<skill-base>\" --event invoke` 记录调用；若 `references/memory-state.json` 里 `memory_enabled=true`，本次必须先读取 `references/memory-lessons.md`（最多 3 条相关 active 经验）。"
        )
    if "assets" in resources:
        blocks.append("- 如果需要下沉的输出格式，读取 `<skill-base>/assets/output-format.md`；这里放的是模型应直接遵循的模板或骨架。")
    if "scripts" in resources:
        blocks.append("- 如果需要确定性或重复性执行，运行 `<python-cmd> \"<skill-base>/scripts/...\"`。")

    blocks.extend(
        [
            "",
            "## Step 2：先定结构，再决定怎么做",
            "",
            "- [TODO: 判断这次请求的主路径、主结构、主策略。]",
            "- [TODO: 明确指出哪些内容留在主 `SKILL.md`，哪些内容应该下沉到 `references/`、`assets/`、`scripts/`。]",
            "- [TODO: 如果 `例子` 或 `输出格式` 已经变长、变多，改下沉，不要把主文件写胖。]",
            "- [TODO: 把 creator 的通用架构说明压到最小，只留下这个 skill 真正会用到的结构规则。]",
            "",
            "## Step 3：产出结果",
            "",
            "- [TODO: 生成最终交付物。]",
            "- [TODO: 如果本步骤调用脚本，把完整命令写出来，不要假设当前 cwd。]",
            "- [TODO: 如果默认输出应该很短，只有在满足明确条件时才允许加 body、解释或备选项。]",
            "",
            "## Step 4：最后检查",
            "",
            "- [TODO: 检查结果是否满足规则、任务约束和主策略。]",
            "- [TODO: 检查 `SKILL.md` 有没有长出未允许的顶级 section。]",
            "- [TODO: 如果 `例子` 或 `输出格式` 已经过长，改下沉到 `references/` 或 `assets/`。]",
            "- [TODO: 再问一次：有没有哪一块内容拿掉也不会垮？如果有，删掉。]",
            "",
        ]
    )

    if has_memory_runtime:
        insert_at = blocks.index("- [TODO: 检查 `SKILL.md` 有没有长出未允许的顶级 section。]")
        blocks.insert(
            insert_at,
            "- [TODO: 如果用户明确反馈“重来 / 不对 / 继续改”，运行 `<python-cmd> \"<skill-base>/scripts/memory_mode_guard.py\" --skill-dir \"<skill-base>\" --event retry` 记录摩擦信号。]",
        )
        blocks.insert(
            insert_at + 1,
            "- [TODO: 如果本轮结果被判定失败，运行 `<python-cmd> \"<skill-base>/scripts/memory_mode_guard.py\" --skill-dir \"<skill-base>\" --event failure`；若顺利交付可用 `--event success`。]",
        )


    if "examples" in sections:
        blocks.extend(
            [
                "# 例子",
                "",
                "- [TODO: 只放高代价边界或最关键的 canonical example；这是给模型看的内部参考，不是给用户看的提问示例。]",
                "",
            ]
        )

    if "output-format" in sections:
        blocks.extend(
            [
                "# 输出格式",
                "",
                "- [TODO: 写清模型应遵循的默认输出结构、允许扩写的条件和禁止项；这里是模板，不是面向用户的解释。]",
                "",
            ]
        )

    if "index" in sections:
        blocks.extend(
            [
                "# 索引",
                "",
                "- [TODO: 只有当单文件已经复杂到容易漂移时才保留这个 section。]",
                "- [TODO: 这个索引只负责恢复方向，不替代工作流程。]",
                "",
            ]
        )
        if memory_mode == "lessons":
            blocks.extend(
                [
                    "- 记忆状态：`<skill-base>/references/memory-state.json`（`memory_enabled` 默认应为 `true`）。",
                    "- 记忆事件：`<skill-base>/references/memory-events.jsonl`。",
                    "- 记忆入口：`<skill-base>/references/memory-lessons.md`（优先读取 active 且相关条目，最多 3 条）。",
                    "- 记忆计数脚本：`<python-cmd> \"<skill-base>/scripts/memory_mode_guard.py\" --mode lessons ...`。",
                    "",
                ]
            )
        if memory_mode == "adaptive":
            blocks.extend(
                [
                    "- 记忆状态：`<skill-base>/references/memory-state.json`（`memory_enabled=true` 时必须读 memory-lessons）。",
                    "- 记忆事件：`<skill-base>/references/memory-events.jsonl`。",
                    "- 记忆入口：`<skill-base>/references/memory-lessons.md`。",
                    "- 记忆计数脚本：`<python-cmd> \"<skill-base>/scripts/memory_mode_guard.py\" ...`。",
                    "",
                ]
            )

    return "\n".join(blocks)


def create_resource_dirs(skill_dir, skill_name, resources, include_examples):
    for resource in resources:
        resource_dir = skill_dir / resource
        resource_dir.mkdir(exist_ok=True)
        if resource == "scripts":
            if include_examples:
                example_script = resource_dir / "example_task.py"
                write_utf8_text(example_script, EXAMPLE_SCRIPT.format(skill_name=skill_name))
                example_script.chmod(0o755)
                print("[OK] 已创建 scripts/example_task.py")
            else:
                print("[OK] 已创建 scripts/")
        elif resource == "references":
            if include_examples:
                examples_file = resource_dir / "examples.md"
                write_utf8_text(examples_file, EXAMPLE_REFERENCE_EXAMPLES)
                print("[OK] 已创建 references/examples.md")
            else:
                print("[OK] 已创建 references/")
        elif resource == "assets":
            if include_examples:
                output_format_file = resource_dir / "output-format.md"
                write_utf8_text(output_format_file, EXAMPLE_ASSET_OUTPUT_FORMAT)
                print("[OK] 已创建 assets/output-format.md")
            else:
                print("[OK] 已创建 assets/")


def create_memory_lessons_file(skill_dir):
    references_dir = skill_dir / "references"
    references_dir.mkdir(exist_ok=True)
    memory_path = references_dir / "memory-lessons.md"
    write_utf8_text(memory_path, EXAMPLE_REFERENCE_MEMORY_LESSONS)
    print("[OK] 已创建 references/memory-lessons.md")


def create_memory_runtime_bundle(skill_dir, memory_thresholds, memory_mode):
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    guard_path = scripts_dir / "memory_mode_guard.py"
    guard_script = render_memory_guard_script(memory_thresholds)
    write_utf8_text(guard_path, guard_script)
    guard_path.chmod(0o755)
    print("[OK] 已创建 scripts/memory_mode_guard.py")

    references_dir = skill_dir / "references"
    references_dir.mkdir(exist_ok=True)
    state_path = references_dir / "memory-state.json"
    events_path = references_dir / "memory-events.jsonl"

    memory_enabled = memory_mode == "lessons"
    initial_state = {
        "mode": memory_mode if memory_mode in {"adaptive", "lessons"} else "adaptive",
        "memory_enabled": memory_enabled,
        "enabled_at": "",
        "thresholds": memory_thresholds,
        "total_calls": 0,
        "retry_events": 0,
        "failure_events": 0,
        "success_events": 0,
        "reject_events": 0,
        "accept_events": 0,
        "recent_quality_events": [],
        "signatures": {},
        "hard_rules": [],
        "lesson_counter": 0,
        "last_event": "",
        "updated_at": "",
    }
    if memory_enabled:
        initial_state["enabled_at"] = ""
    write_utf8_text(state_path, json.dumps(initial_state, ensure_ascii=False, indent=2) + "\n")
    print("[OK] 已创建 references/memory-state.json")
    if not events_path.exists():
        write_utf8_text(events_path, "")
    print("[OK] 已创建 references/memory-events.jsonl")
    if memory_enabled:
        create_memory_lessons_file(skill_dir)


def create_config_file(skill_dir):
    config_path = skill_dir / "config.yaml"
    write_utf8_text(config_path, EXAMPLE_CONFIG)
    print("[OK] 已创建 config.yaml")


def init_skill(
    skill_name,
    path,
    resources,
    sections,
    include_examples,
    interface_overrides,
    interface_defaults,
    create_config,
    create_openai_yaml,
    memory_mode,
    memory_thresholds,
):
    """Initialize a new skill directory with a fixed scaffold."""
    skill_dir = Path(path).resolve() / skill_name

    if skill_dir.exists():
        print(f"[ERROR] Skill 目录已存在：{skill_dir}")
        return None

    try:
        skill_dir.mkdir(parents=True, exist_ok=False)
        print(f"[OK] 已创建 skill 目录：{skill_dir}")
    except Exception as exc:
        print(f"[ERROR] 创建目录失败：{exc}")
        return None

    skill_content = render_skill_template(
        skill_name,
        sections,
        resources,
        create_config,
        create_openai_yaml,
        memory_mode,
    )

    skill_md_path = skill_dir / "SKILL.md"
    try:
        write_utf8_text(skill_md_path, skill_content)
        print("[OK] 已创建 SKILL.md")
    except Exception as exc:
        print(f"[ERROR] 创建 SKILL.md 失败：{exc}")
        return None

    try:
        if create_config:
            create_config_file(skill_dir)
        if create_openai_yaml:
            result = write_openai_yaml(
                skill_dir,
                skill_name,
                interface_overrides,
                interface_defaults,
            )
            if not result:
                return None
    except Exception as exc:
        print(f"[ERROR] 创建可选文件失败：{exc}")
        return None

    if resources:
        try:
            create_resource_dirs(skill_dir, skill_name, resources, include_examples)
        except Exception as exc:
            print(f"[ERROR] 创建资源目录失败：{exc}")
            return None
    if memory_mode in {"lessons", "adaptive"}:
        try:
            create_memory_runtime_bundle(skill_dir, memory_thresholds, memory_mode)
        except Exception as exc:
            print(f"[ERROR] 创建 memory runtime bundle 失败：{exc}")
            return None

    print(f"\n[OK] Skill '{skill_name}' 已在 {skill_dir} 初始化完成")
    print("\n下一步建议：")
    print("1. 先替换 SKILL.md 里的 TODO，并确认顶级 section 只来自固定白名单。")
    if create_config:
        print("2. 经常要调的参数放进 config.yaml，不要额外发明一份手写 JSON。")
    else:
        print("2. 只有当人会频繁调参数时，才补 config.yaml。")
    if resources:
        if include_examples:
            print("3. 把 scripts/、references/、assets/ 里的示例文件替换成真实内容，没价值的就删掉。")
        else:
            print("3. 只往 scripts/、references/、assets/ 里补真正需要的文件。")
    else:
        print("3. 只有当 skill 真的需要时，才创建资源目录。")
    if memory_mode == "lessons":
        print("4. `scripts/memory_mode_guard.py` 已启用：每次调用先记事件，再读取 `memory-lessons`（最多 3 条相关 active 经验）。")
        print("   同类失败重复后自动更新 lessons；稳定命中后自动回写 `SKILL.md` 的 MEMORY_HARD_RULES。")
    elif memory_mode == "adaptive":
        print("4. 先保持 memory 关闭；按 `scripts/memory_mode_guard.py` 自动追踪，达到阈值后自动开启 memory-lessons。")
        print("   你可以在 `references/memory-state.json` / `references/memory-events.jsonl` 查看计数与轨迹。")
    else:
        print("4. 如果后续出现重复错误且代价高，再考虑启用 memory_mode=adaptive 或 lessons。")
    print("5. 如果 `# 例子` 或 `# 输出格式` 已经变长、变多，就把它们下沉到 references/ 或 assets/。")
    print("6. bundled file 指针保持精确，默认写成 <skill-base>/...，不要把本次运行的绝对路径写进最终交付物。")
    if create_openai_yaml:
        print("7. 如果界面元数据需要变化，重新生成 agents/openai.yaml。")
    else:
        print("7. 只有目标环境真的需要时，才补 agents/openai.yaml。")
    print("8. 如果默认输出应该极简，最后再专门删一遍不必要的 body、解释和备选项。")
    print("9. 结构写完后，跑 validator 检查 skill 是否成立。")

    return skill_dir


def main():
    parser = argparse.ArgumentParser(
        description="创建一个新的 skill 目录，并生成固定的 SKILL.md 脚手架。",
    )
    parser.add_argument("skill_name", help="Skill 名称（会规范化为 kebab-case）")
    parser.add_argument("--config", default=None, help="config.yaml 路径（默认使用 dazhuangskill-creator/config.yaml）")
    parser.add_argument("--path", required=False, help="skill 输出目录（CLI > config.yaml）")
    parser.add_argument(
        "--resources",
        default=None,
        help="逗号分隔：scripts,references,assets（CLI > config.yaml）",
    )
    parser.add_argument(
        "--sections",
        default=None,
        help="逗号分隔：role,examples,output-format,index（CLI > config.yaml）",
    )
    parser.add_argument(
        "--memory-mode",
        choices=sorted(ALLOWED_MEMORY_MODES),
        default=None,
        help=(
            "记忆层模式：off | lessons | adaptive | auto（默认）。"
            "lessons=直接启用记忆，adaptive=运行期自动检测后启用，auto=创建前自动判型。"
        ),
    )
    parser.add_argument(
        "--force-memory-off",
        action="store_true",
        default=False,
        help="仅在 --memory-mode off 时生效：确认强制关闭记忆层，即使 auto 判型建议开启。",
    )
    parser.add_argument(
        "--intent",
        default=None,
        help=(
            "skill 目标说明（用于 memory_mode=auto 判型；CLI > config.yaml）。"
            "建议在 auto 模式下始终提供。"
        ),
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        default=None,
        help="在所选资源目录里创建示例文件（CLI > config.yaml）",
    )
    parser.add_argument(
        "--config-file",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="是否创建 config.yaml（CLI > config.yaml；默认关闭）",
    )
    parser.add_argument(
        "--openai-yaml",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="是否创建 agents/openai.yaml（CLI > config.yaml；默认关闭）",
    )
    parser.add_argument(
        "--interface",
        action="append",
        default=[],
        help="界面字段覆盖，格式 key=value，可重复传入；只有生成 agents/openai.yaml 时才需要",
    )
    args = parser.parse_args()

    config = load_dazhuangskill_creator_config(args.config)
    raw_skill_name = args.skill_name
    skill_name = normalize_skill_name(raw_skill_name)
    if not skill_name:
        print("[ERROR] Skill 名称里至少要有一个字母或数字。")
        sys.exit(1)
    if len(skill_name) > MAX_SKILL_NAME_LENGTH:
        print(
            f"[ERROR] Skill 名称 '{skill_name}' 过长（{len(skill_name)} 个字符）。最大允许 {MAX_SKILL_NAME_LENGTH} 个字符。"
        )
        sys.exit(1)
    if skill_name != raw_skill_name:
        print(f"提示：已把 skill 名从 '{raw_skill_name}' 规范化为 '{skill_name}'。")

    if args.resources is not None:
        resources = parse_resources(args.resources)
    else:
        configured_resources = get_config_value(config, "init_skill.resources", [])
        if not isinstance(configured_resources, list):
            print("[ERROR] config.yaml 里的 init_skill.resources 必须是 YAML 列表。")
            sys.exit(1)
        resources = parse_resources(",".join(str(item) for item in configured_resources))

    if args.sections is not None:
        sections = parse_sections(args.sections)
    else:
        configured_sections = get_config_value(config, "init_skill.sections", [])
        if not isinstance(configured_sections, list):
            print("[ERROR] config.yaml 里的 init_skill.sections 必须是 YAML 列表。")
            sys.exit(1)
        sections = parse_sections(",".join(str(item) for item in configured_sections))

    requested_memory_mode = parse_memory_mode(
        coalesce(args.memory_mode, get_config_value(config, "init_skill.memory_mode", "auto"))
    )
    memory_intent = coalesce(args.intent, get_config_value(config, "init_skill.memory_intent", ""))
    auto_scores = parse_memory_auto_scores(get_config_value(config, "init_skill.memory_auto", {}))
    memory_thresholds = parse_memory_thresholds(get_config_value(config, "init_skill.memory_thresholds", {}))
    memory_mode, _ = resolve_memory_mode(
        requested_memory_mode,
        skill_name,
        memory_intent,
        resources,
        sections,
        auto_scores,
    )
    auto_reference_summary = build_auto_memory_summary(
        skill_name,
        memory_intent,
        resources,
        sections,
        auto_scores,
    )
    enforce_auto_memory_intent_guard(
        requested_memory_mode,
        memory_intent,
        auto_reference_summary,
    )
    enforce_memory_off_guard(
        requested_memory_mode,
        auto_reference_summary,
        args.force_memory_off,
        args.memory_mode == "off",
    )

    if memory_mode in {"lessons", "adaptive"}:
        missing = []
        if "references" not in resources:
            resources = [*resources, "references"]
            missing.append("references/")
        if "scripts" not in resources:
            resources = [*resources, "scripts"]
            missing.append("scripts/")
        if missing:
            print(f"提示：memory_mode={memory_mode} 已自动启用 {', '.join(missing)}。")

    validate_structure_choices(resources, sections, memory_mode)

    include_examples = (
        args.examples
        if args.examples is not None
        else bool(get_config_value(config, "init_skill.include_examples", False))
    )
    if include_examples and not resources:
        print("[ERROR] 使用 --examples 时，必须同时提供 --resources。")
        sys.exit(1)

    path = coalesce(args.path, get_config_value(config, "init_skill.output_path"))
    if not path:
        print("[ERROR] 必须提供 --path，除非 config.yaml 已设置 init_skill.output_path。")
        sys.exit(1)

    interface_defaults = get_config_value(config, "openai_yaml.interface_defaults", {})
    create_config = (
        args.config_file
        if args.config_file is not None
        else bool(get_config_value(config, "init_skill.create_config", False))
    )
    create_openai_yaml = (
        args.openai_yaml
        if args.openai_yaml is not None
        else bool(get_config_value(config, "init_skill.create_openai_yaml", False))
    )
    if args.interface and not create_openai_yaml:
        print("[ERROR] 只有在启用 --openai-yaml 时，才应该传 --interface 覆盖。")
        sys.exit(1)

    print(f"准备初始化 skill：{skill_name}")
    print(f"   位置：{path}")
    if resources:
        print(f"   资源目录：{', '.join(resources)}")
        if include_examples:
            print("   示例文件：开启")
    else:
        print("   资源目录：无（按需再建）")
    print(f"   内联 section：{', '.join(sections) if sections else '无（只保留规则 + 工作流程）'}")
    if requested_memory_mode == "auto":
        print(f"   记忆层：auto -> {memory_mode}")
    else:
        print(f"   记忆层：{memory_mode}")
    print(
        "   记忆判型（必做）："
        f"{auto_reference_summary['resolved_mode']} (score={auto_reference_summary['score']})"
    )
    if auto_reference_summary["reasons"]:
        for reason in auto_reference_summary["reasons"]:
            print(f"   auto signal：{reason}")
    else:
        print("   auto signal：无明显高风险或高变异信号")
    if requested_memory_mode != "auto":
        print("   记忆判型用途：仅作参考，最终以你显式指定的 --memory-mode 为准。")
    if memory_mode == "adaptive":
        print(
            "   adaptive 阈值："
            f"min_calls={memory_thresholds['min_calls']}, "
            f"min_retry_events={memory_thresholds['min_retry_events']}, "
            f"min_repeat_requests={memory_thresholds['min_repeat_requests']}, "
            f"window_size={memory_thresholds['window_size']}"
        )
    print(f"   创建 config.yaml：{'是' if create_config else '否'}")
    print(f"   创建 agents/openai.yaml：{'是' if create_openai_yaml else '否'}")
    print()

    result = init_skill(
        skill_name,
        path,
        resources,
        sections,
        include_examples,
        args.interface,
        interface_defaults,
        create_config,
        create_openai_yaml,
        memory_mode,
        memory_thresholds,
    )

    if result:
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()

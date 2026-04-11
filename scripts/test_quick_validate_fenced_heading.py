#!/usr/bin/env python3
"""Regression test: quick_validate should ignore level-1 headings inside fenced code blocks."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_cmd = sys.executable

    skill_body = """---
name: fenced-heading-check
description: validate fenced heading parsing
---
# 规则

- 保持结构稳定。

# 工作流程

- 先输出结论，再补结构化明细。

# 输出格式

```md
# 医疗合规风控评审
## 结论
- [结果]
```
"""

    with tempfile.TemporaryDirectory(prefix="quick_validate_fenced_heading_test_") as tmp:
        skill_dir = Path(tmp) / "fenced-heading-check"
        skill_dir.mkdir(parents=True, exist_ok=False)
        (skill_dir / "SKILL.md").write_text(skill_body, encoding="utf-8")

        validated = run(
            [
                python_cmd,
                str(root / "scripts" / "quick_validate.py"),
                str(skill_dir),
            ],
            cwd=root,
        )

        output = validated.stdout + validated.stderr
        assert_true(validated.returncode == 0, "fenced heading should not be treated as top-level section")
        assert_true("Skill 结构有效" in output, "validator should report valid structure")

    print("PASS: quick validate fenced heading regression test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

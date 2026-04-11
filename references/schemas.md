# JSON Schema 说明

这份文档定义了 dazhuangskill-creator 使用的 JSON 结构。

当产物是机器写入、机器消费，或者需要严格交换格式时，使用这些 JSON 文件。
如果是人会频繁手改的参数，优先放到 `config.yaml`，不要重新发明一份手写 JSON。

- 这份文档是“查表型 reference”，不是 workflow 文档。
- 它不重写 `current_path` 或 `current_step`；只有在当前步骤需要严格 JSON 格式时，再局部查阅对应 section。

## 快速定位

- 如果你现在要写评估前置计划：看 `eval-plan.json`
- 如果你现在要写评测集合：看 `evals.json`
- 如果你现在要看 benchmark 聚合产物：看 `benchmark.json`
- 如果你现在要看版本演进：看 `history.json`
- 如果你现在要写 grader 输出：看 `grading.json`
- 如果你现在要看 executor 执行指标：看 `metrics.json`
- 如果你现在要保存单次 run 时间：看 `timing.json`

## 使用规则

- 只读取当前需要的 schema，不要把整份文档一次性塞进上下文。
- 如果上下文已经很长，先回当前 workflow 文档确认自己在哪一步，再来这里读对应 JSON 结构。
- 如果需求是“人类经常手改的配置”，优先回 `config.yaml`，不要硬造 JSON。

---

## eval-plan.json

定义正式评估计划。通常放在目标 skill 的 `evals/eval-plan.json`。

这个文件对应 `<skill-base>/references/eval-planning.md` 里的“正式评估计划”。

```json
{
  "target": {
    "skill_name": "musk-skill",
    "comparison_mode": "with-vs-without",
    "variants": ["with_skill", "without_skill"]
  },
  "initial_judgement": {
    "skill_type": "mixed",
    "recommended_primary_direction": "delivery_effect",
    "recommended_secondary_direction": "thinking_imitation",
    "reasoning": "这个 skill 主要给 agent 增强决策和执行方式，不是单纯模仿口吻。"
  },
  "confirmed_plan": {
    "primary_direction": {
      "id": "delivery_effect",
      "label": "落地效果",
      "weight": 0.7
    },
    "secondary_direction": {
      "id": "thinking_imitation",
      "label": "思维方式模仿",
      "weight": 0.3
    },
    "dimensions": [
      {
        "id": "task_completion",
        "label": "任务完成度",
        "weight": 0.3,
        "notes": "看任务是不是被真正做完"
      },
      {
        "id": "solution_effectiveness",
        "label": "方案有效性",
        "weight": 0.25,
        "notes": "看方案能不能真的落地"
      },
      {
        "id": "cost_efficiency",
        "label": "成本效率",
        "weight": 0.15,
        "notes": "看 token / 时间 / 工具成本"
      },
      {
        "id": "first_principles",
        "label": "第一性原理程度",
        "weight": 0.3,
        "notes": "看是否明显体现目标人物的思考方式"
      }
    ],
    "out_of_scope": ["tone_similarity"],
    "case_plan": {
      "sample_types": ["真实业务决策题", "资源受限题", "开放式问题拆解题"],
      "sample_count": 3,
      "blind_review": true
    },
    "report_requirements": {
      "must_include": ["总判断", "分维度判断", "证据", "适用场景", "不适用场景"]
    }
  }
}
```

**字段说明：**

- `target.skill_name`：被评估的 skill 名
- `target.comparison_mode`：`single-skill`、`with-vs-without`、`old-vs-new`、`peer-vs-peer`
- `target.variants`：这次要跑哪些对象
- `initial_judgement`：AI 在前置对齐阶段的初判
- `confirmed_plan.primary_direction`：这次主方向
- `confirmed_plan.secondary_direction`：可选，次方向
- `confirmed_plan.dimensions[]`：这次真正参与判断的维度
- `confirmed_plan.out_of_scope`：明确不纳入主判的内容
- `confirmed_plan.case_plan`：样本类型、数量、是否盲评
- `confirmed_plan.report_requirements`：最后结论必须包含什么

---

## evals.json

定义某个 skill 的评测集合。通常放在目标 skill 的 `evals/evals.json`。

这个文件对应 `<skill-base>/references/eval-loop.md` 里的具体测题集合。默认应该从已经确认过的 `eval-plan.json` 倒推出来，而不是临时想到什么就测什么。

如果你已经有正式评估计划，建议在每个 eval 对应的 `eval_metadata.json` 里补上 `dimension_ids` 或 `dimension_labels`。聚合 benchmark 时，会用这些字段硬校验“这道题到底在测哪条维度”。

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "用户的示例请求",
      "expected_output": "成功结果的文字说明",
      "files": ["evals/files/sample1.pdf"],
      "expectations": [
        "输出里包含 X",
        "skill 使用了脚本 Y"
      ]
    }
  ]
}
```

**字段说明：**

- `skill_name`：应与 skill frontmatter 里的 `name` 一致
- `evals[].id`：唯一整数 ID
- `evals[].prompt`：要执行的任务
- `evals[].expected_output`：人类可读的成功标准
- `evals[].files`：可选，相对 skill 根目录的输入文件列表
- `evals[].expectations`：可验证断言列表

---

## history.json

在 Improve 模式下记录版本演进。通常放在 workspace 根目录。

```json
{
  "started_at": "2026-01-15T10:30:00Z",
  "skill_name": "pdf",
  "current_best": "v2",
  "iterations": [
    {
      "version": "v0",
      "parent": null,
      "expectation_pass_rate": 0.65,
      "grading_result": "baseline",
      "is_current_best": false
    },
    {
      "version": "v1",
      "parent": "v0",
      "expectation_pass_rate": 0.75,
      "grading_result": "won",
      "is_current_best": false
    },
    {
      "version": "v2",
      "parent": "v1",
      "expectation_pass_rate": 0.85,
      "grading_result": "won",
      "is_current_best": true
    }
  ]
}
```

**字段说明：**

- `started_at`：开始时间，ISO 时间戳
- `skill_name`：正在优化的 skill 名
- `current_best`：当前最佳版本 ID
- `iterations[].version`：版本号，如 `v0`、`v1`
- `iterations[].parent`：父版本
- `iterations[].expectation_pass_rate`：断言通过率
- `iterations[].grading_result`：`baseline`、`won`、`lost`、`tie`
- `iterations[].is_current_best`：是否是当前最佳版本

---

## benchmark.json

benchmark 聚合脚本的输出。通常位于 `<workspace>/benchmark.json`。

这个文件由 `<skill-base>/scripts/aggregate_benchmark.py` 生成。如果你已经有 `evals/eval-plan.json`，建议一并传给聚合脚本，让 benchmark 结果带上“这次到底按什么标准评”的摘要。
默认情况下，如果聚合脚本找不到正式评估计划，就会直接拦住；只有在兼容旧 benchmark 时，才建议显式加 `--allow-missing-eval-plan`。
正式评估结束时，通常会继续基于同一份 `benchmark.json` 和同一个 workspace 生成两份 HTML：`review.html` 和 `report.html`。

```json
{
  "metadata": {
    "skill_name": "musk-skill",
    "skill_path": "skills/musk-skill",
    "executor_model": "<model-name>",
    "analyzer_model": "<model-name>",
    "timestamp": "2026-04-11T09:00:00Z",
    "evals_run": [0, 1, 2],
    "runs_per_configuration": 3,
    "evaluation_plan_path": "evals/eval-plan.json",
    "evaluation_plan": {
      "comparison_mode": "with-vs-without",
      "variants": ["with_skill", "without_skill"],
      "primary_direction": {
        "id": "delivery_effect",
        "label": "落地效果",
        "weight": 0.7
      },
      "secondary_direction": {
        "id": "thinking_imitation",
        "label": "思维方式模仿",
        "weight": 0.3
      },
      "dimensions": [
        {
          "id": "task_completion",
          "label": "任务完成度",
          "weight": 0.3,
          "notes": "看任务是不是被真正做完"
        }
      ],
      "out_of_scope": ["tone_similarity"],
      "case_plan": {
        "sample_types": ["真实业务决策题"],
        "sample_count": 3,
        "blind_review": true
      },
      "report_requirements": {
        "must_include": ["总判断", "分维度判断", "证据", "适用场景", "不适用场景"]
      }
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
          "dimension_labels": ["任务完成度"]
        }
      ]
    }
  },
  "runs": [
    {
      "eval_id": 0,
      "eval_name": "真实案例 A",
      "dimension_labels": ["任务完成度", "方案有效性"],
      "configuration": "with_skill",
      "run_number": 1,
      "result": {
        "pass_rate": 1.0,
        "passed": 4,
        "failed": 0,
        "total": 4,
        "time_seconds": 18.2,
        "tokens": 4200,
        "tool_calls": 9,
        "errors": 0
      },
      "expectations": [],
      "notes": []
    }
  ],
  "run_summary": {
    "with_skill": {
      "pass_rate": {"mean": 0.92, "stddev": 0.08, "min": 0.83, "max": 1.0},
      "time_seconds": {"mean": 18.4, "stddev": 1.1, "min": 17.2, "max": 19.8},
      "tokens": {"mean": 4300, "stddev": 120.0, "min": 4180, "max": 4420}
    },
    "without_skill": {
      "pass_rate": {"mean": 0.61, "stddev": 0.14, "min": 0.5, "max": 0.83},
      "time_seconds": {"mean": 21.3, "stddev": 0.9, "min": 20.2, "max": 22.1},
      "tokens": {"mean": 5000, "stddev": 180.0, "min": 4780, "max": 5190}
    },
    "delta": {
      "pass_rate": "+0.31",
      "time_seconds": "-2.9",
      "tokens": "-700"
    }
  },
  "notes": []
}
```

**字段说明：**

- `metadata.evaluation_plan_path`：这次 benchmark 对应的正式评估计划路径
- `metadata.evaluation_plan`：从正式评估计划里提炼出的摘要
- `metadata.dimension_coverage`：正式评估计划里的维度，是否真的被题目覆盖到了
- `runs[].eval_name`：可选，来自 `eval_metadata.json` 的人类可读名称
- `runs[].dimension_labels`：可选，这题主要在测哪些维度
- `run_summary`：不同配置的聚合统计；只有严格两方对比时，才会额外带 `delta`
- `notes`：给 analyzer 或人工复盘补充的说明

---

## grading.json

grader agent 的输出。通常位于 `<run-dir>/grading.json`。

```json
{
  "expectations": [
    {
      "text": "输出里包含姓名 'John Smith'",
      "passed": true,
      "evidence": "在 transcript 第 3 步找到：'Extracted names: John Smith, Sarah Johnson'"
    },
    {
      "text": "表格 B10 单元格有 SUM 公式",
      "passed": false,
      "evidence": "根本没有生成电子表格，输出是一个文本文件。"
    }
  ],
  "summary": {
    "passed": 2,
    "failed": 1,
    "total": 3,
    "pass_rate": 0.67
  },
  "execution_metrics": {
    "tool_calls": {
      "Read": 5,
      "Write": 2,
      "Bash": 8
    },
    "total_tool_calls": 15,
    "total_steps": 6,
    "errors_encountered": 0,
    "output_chars": 12450,
    "transcript_chars": 3200
  },
  "timing": {
    "executor_duration_seconds": 165.0,
    "grader_duration_seconds": 26.0,
    "total_duration_seconds": 191.0
  },
  "claims": [
    {
      "claim": "这个表单有 12 个可填写字段",
      "type": "factual",
      "verified": true,
      "evidence": "在 field_info.json 里数到了 12 个字段"
    }
  ],
  "user_notes_summary": {
    "uncertainties": ["用了 2023 年的数据，可能偏旧"],
    "needs_review": [],
    "workarounds": ["对不可填写字段退回到文字覆盖"]
  },
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "输出里包含姓名 'John Smith'",
        "reason": "如果一个幻觉文档只是顺手提到了这个名字，也会通过这条断言"
      },
      {
        "reason": "正式评估计划把“稳定性”列为主维度，但这组 expectations 还没有直接覆盖它"
      }
    ],
    "overall": "这些断言更像是在检查“有无”，而不是检查“对不对”。"
  }
}
```

**字段说明：**

- `expectations[]`：逐条断言的判定与证据
- `summary`：聚合通过/失败统计
- `execution_metrics`：执行过程里的工具使用和产出体量
- `timing`：来自 `timing.json` 的时间信息
- `claims`：从输出中抽出的隐含声明及验证结果
- `user_notes_summary`：执行者自己标记的不确定点和权宜之计
- `eval_feedback`：grader 对 eval 本身的改进建议，可选；这里也可以指出“正式评估计划的主维度没有被当前 eval 覆盖”

---

## metrics.json

executor agent 的输出。通常位于 `<run-dir>/outputs/metrics.json`。

```json
{
  "tool_calls": {
    "Read": 5,
    "Write": 2,
    "Bash": 8,
    "Edit": 1,
    "Glob": 2,
    "Grep": 0
  },
  "total_tool_calls": 18,
  "total_steps": 6,
  "files_created": ["filled_form.pdf", "field_values.json"],
  "errors_encountered": 0,
  "output_chars": 12450,
  "transcript_chars": 3200
}
```

**字段说明：**

- `tool_calls`：每种工具的调用次数
- `total_tool_calls`：所有工具调用总数
- `total_steps`：主要执行步骤数
- `files_created`：创建出的文件列表
- `errors_encountered`：执行中遇到的错误数
- `output_chars`：输出文件的总字符数
- `transcript_chars`：transcript 的字符数

---

## timing.json

单次 run 的 wall-clock 时间数据。通常位于 `<run-dir>/timing.json`。

**如何保存：** 当子任务完成时，任务通知里会给出 `total_tokens` 和 `duration_ms`。要立刻保存，因为之后通常无法再恢复。

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3,
  "executor_start": "2026-01-15T10:30:00Z",
  "executor_end": "2026-01-15T10:32:45Z",
  "executor_duration_seconds": 165.0,
  "grader_start": "2026-01-15T10:32:46Z",
  "grader_end": "2026-01-15T10:33:12Z",
  "grader_duration_seconds": 26.0
}
```

---

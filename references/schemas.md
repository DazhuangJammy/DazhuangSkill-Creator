# JSON Schema 说明

这份文档定义了 dazhuangskill-creator 使用的 JSON 结构。

当产物是机器写入、机器消费，或者需要严格交换格式时，使用这些 JSON 文件。
如果是人会频繁手改的参数，优先放到 `config.yaml`，不要重新发明一份手写 JSON。

- 这份文档是“查表型 reference”，不是 workflow 文档。
- 它不重写 `current_path` 或 `current_step`；只有在当前步骤需要严格 JSON 格式时，再局部查阅对应 section。

## 快速定位

- 如果你现在要写评测集合：看 `evals.json`
- 如果你现在要看版本演进：看 `history.json`
- 如果你现在要写 grader 输出：看 `grading.json`
- 如果你现在要看 executor 执行指标：看 `metrics.json`
- 如果你现在要保存单次 run 时间：看 `timing.json`

## 使用规则

- 只读取当前需要的 schema，不要把整份文档一次性塞进上下文。
- 如果上下文已经很长，先回当前 workflow 文档确认自己在哪一步，再来这里读对应 JSON 结构。
- 如果需求是“人类经常手改的配置”，优先回 `config.yaml`，不要硬造 JSON。

---

## evals.json

定义某个 skill 的评测集合。通常放在目标 skill 的 `evals/evals.json`。

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
- `eval_feedback`：grader 对 eval 本身的改进建议，可选

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

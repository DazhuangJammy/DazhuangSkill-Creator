# Post-hoc Analyzer Agent

分析 blind comparison 结果，理解赢家为什么赢，并给失败一方提出改进建议。

## 角色

当 blind comparator 选出赢家之后，Post-hoc Analyzer 会“揭盲”，去读 skill 本体和执行 transcript。目标不是复述输赢，而是提炼出可执行的结论：赢家到底赢在哪，输家应该怎么改。

## 输入

提示里会给你这些参数：

- **winner**：`"A"` 或 `"B"`
- **winner_skill_path**：赢家对应的 skill 路径
- **winner_transcript_path**：赢家的执行 transcript 路径
- **loser_skill_path**：输家的 skill 路径
- **loser_transcript_path**：输家的执行 transcript 路径
- **comparison_result_path**：blind comparator 输出的 JSON 路径
- **output_path**：分析结果保存路径

## 流程

### Step 1：先读 comparison 结果

1. 读取 `comparison_result_path`
2. 记录赢家是哪边、判决理由、关键得分
3. 理解 comparator 看重了什么

### Step 2：读两个 skill

1. 读赢家的 `SKILL.md` 以及关键引用文件
2. 读输家的 `SKILL.md` 以及关键引用文件
3. 对比结构差异：
   - 指令是否更清楚
   - 脚本/工具的使用方式是否更稳
   - 示例覆盖是否更完整
   - 边界情况是否处理得更好

### Step 3：读两个 transcript

1. 读赢家 transcript
2. 读输家 transcript
3. 比执行模式：
   - 哪一边更贴着 skill 指令走
   - 哪些工具用法不同
   - 输家在什么地方偏离了更优路径
   - 有没有一边出现错误或失败恢复

### Step 4：分析指令遵循度

对每个 transcript 都判断：
- agent 有没有按 skill 的显式指令执行
- 有没有真的用上 skill 自带的工具/脚本
- 有没有错过 skill 已经提供的能力
- 有没有额外做了 skill 里根本没要求、还浪费时间的步骤

给指令遵循度打 1-10 分，并记录具体问题。

### Step 5：找出赢家的优势

判断赢家赢在什么地方：
- 指令更清楚，导致执行更稳？
- 自带脚本/工具更实用？
- 示例更能覆盖边界场景？
- 失败处理更好？

要具体，必要时引用 skill 或 transcript 里的内容。

### Step 6：找出输家的弱点

判断输家输在什么地方：
- 指令模糊，导致执行分叉太多？
- 缺脚本/工具，被迫临场 improvisation？
- 边界情况覆盖不足？
- 错误处理太弱，导致早早失败？

### Step 7：产出改进建议

基于分析，给输家 skill 提出可执行建议：
- 要改哪些指令
- 要加或改哪些工具/脚本
- 要不要补示例
- 哪些边界情况需要补进去

按影响排序，优先那些“很可能会改变输赢结果”的建议。

### Step 8：写分析结果

把结构化分析保存到 `{output_path}`。

## 输出格式

写成下面这种 JSON：

```json
{
  "comparison_summary": {
    "winner": "A",
    "winner_skill": "path/to/winner/skill",
    "loser_skill": "path/to/loser/skill",
    "comparator_reasoning": "比较器为什么选它赢的简述"
  },
  "winner_strengths": [
    "对多页文档给了清晰的分步处理方式",
    "包含一个能抓格式错误的校验脚本",
    "OCR 失败时有明确 fallback"
  ],
  "loser_weaknesses": [
    "'合适地处理文档' 这种说法太模糊，导致行为不稳定",
    "没有校验脚本，agent 只能临场应付",
    "没有 OCR 失败 fallback，困难样本直接放弃"
  ],
  "instruction_following": {
    "winner": {
      "score": 9,
      "issues": [
        "轻微问题：跳过了可选日志步骤"
      ]
    },
    "loser": {
      "score": 6,
      "issues": [
        "没有使用 skill 提供的格式模板",
        "偏离了第 3 步要求，另起了一套做法",
        "漏掉了“总是先验证输出”的指令"
      ]
    }
  },
  "improvement_suggestions": [
    {
      "priority": "high",
      "category": "instructions",
      "suggestion": "把“合适地处理文档”改成明确步骤：1）抽文本；2）识别结构；3）按模板格式化",
      "expected_impact": "能减少模糊性，避免执行路径漂移"
    },
    {
      "priority": "high",
      "category": "tools",
      "suggestion": "补一个类似赢家方案的 validate_output.py",
      "expected_impact": "能在最终交付前抓出格式错误"
    },
    {
      "priority": "medium",
      "category": "error_handling",
      "suggestion": "加入 OCR 失败 fallback：1）换分辨率；2）做图像预处理；3）必要时手动抽取",
      "expected_impact": "能减少困难样本上的过早失败"
    }
  ],
  "transcript_insights": {
    "winner_execution_pattern": "读 skill -> 按 5 步流程执行 -> 用校验脚本 -> 修 2 个问题 -> 产出结果",
    "loser_execution_pattern": "读 skill -> 路径不清 -> 换了 3 种方法 -> 没校验 -> 最终输出有缺陷"
  }
}
```

## 指南

- **具体**：不要只说“指令不够清楚”，要指出到底哪里不清楚
- **可执行**：建议必须能落地，不能只是空泛评价
- **聚焦 skill 改进**：重点是改 skill，不是责怪 agent
- **按影响排序**：哪些改动最可能改变结果，就排前面
- **关注因果**：确认问题真的导致了差结果，而不是偶然共现
- **保持客观**：分析发生了什么，不要抒情
- **考虑泛化**：优先那些不只对这一个 eval 有帮助的改法

## 建议分类

| 分类 | 含义 |
|------|------|
| `instructions` | 修改 skill 正文指令 |
| `tools` | 补或改脚本、模板、工具 |
| `examples` | 增加输入/输出示例 |
| `error_handling` | 改进失败处理 |
| `structure` | 调整 skill 内容组织 |
| `references` | 补外部说明文档 |

## 优先级

- **high**：很可能改变这次对比的输赢
- **medium**：会改善质量，但不一定改变输赢
- **low**：锦上添花，边际收益较小

---

# Benchmark 结果分析

在 benchmark 场景下，analyzer 的任务不是直接提改 skill，而是从大量 run 里找出 pattern 和异常。

## 角色

阅读全部 benchmark run 结果，输出自由格式分析笔记，帮助用户理解 skill 的表现。重点放在那些汇总统计不容易直接看出来的现象上。

## 输入

提示里会给你这些参数：

- **benchmark_data_path**：正在生成中的 benchmark.json 路径
- **skill_path**：被测 skill 路径
- **output_path**：笔记输出路径（JSON 字符串数组）

## 流程

### Step 1：读 benchmark 数据

1. 读取 benchmark.json
2. 记录测试配置，例如 `with_skill`、`without_skill`
3. 理解现有 run_summary 已经聚合出的统计

### Step 2：按 assertion 观察 pattern

对每条 expectation，看它跨 run 的表现：
- 是否两边永远都过？如果是，可能没区分度
- 是否两边永远都不过？如果是，可能写坏了或任务超出能力范围
- 是否 with-skill 永远过、without-skill 永远不过？如果是，skill 明显有价值
- 是否 with-skill 永远不过、without-skill 反而过？如果是，skill 可能在伤害结果
- 是否波动很大？如果是，可能断言太脆或结果太随机

### Step 3：做跨 eval 观察

- 某些 eval 是否系统性更难？
- 某些配置是否在时间/token 上代价巨大但收益有限？
- 某些 run 是否存在异常值？
- 某些 assertions 是否只在某一类 prompt 上有效？

### Step 4：写分析笔记

输出自由格式笔记，帮助用户理解：
- 哪些地方 skill 确实在创造价值
- 哪些地方 benchmark 设计还不够锋利
- 哪些 run 或 assertion 需要额外关注

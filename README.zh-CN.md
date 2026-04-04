# Dazhuang Skill Creator

中文 | [English](README.md)

![Dazhuang Skill Creator 基准测试总览](assets/benchmark-overview.png)

> 官方原版 = Claude Code 官方 `skill-creator`  
> `My Skill Creator Copy` = 我迭代出来的第二个版本  
> `Dazhuang Skill Creator` = 当前仓库中的最终版

Dazhuang Skill Creator 基于 Claude Code 官方 `skill-creator`，但并不只是改几句提示词。我把自己对提示词架构、Skill 架构，以及 CLI 工具运行机制的理解重新整合进去，对整体工作流、结构分层、bundled resources 和可维护性做了一次完整重构。

在测评环节，我采用 Codex 的 Headless 模式进行测试：不需要打开图形界面，也不需要进入 CLI 页面，直接在终端执行。每个 benchmark item 都至少进行了 3 轮独立对话测试。完整的评测标准、原始结果与报告已经归档在 `测评报告/` 文件夹中。

如果这个项目对你有帮助，欢迎点一个 star。联系 / 合作请加微信：`yinyinGyL`。

## 我测评了什么

### 1）5 大类型能力对比

- A 类｜内容型：提示词、模板、平台风格能不能组织成可复用 skill
- B 类｜结构化输出型：能不能严格遵守 JSON schema，输出稳不稳
- C 类｜工具调研型：会不会看源文件、附来源，而不是瞎总结
- D 类｜脚本型：产出的脚本能不能真的跑起来，失败会不会收住
- E 类｜混合编排型：prompt、reference、asset、script 能不能协同配合

### 2）5 大能力原型对比

- 极简压缩输出
- 严格结构化输出
- 安全判断
- 模板化归纳
- 脏输入归一化

## 测评方法

- 全部 benchmark 均使用 Codex Headless 模式，在终端中执行
- 每个 case 至少做 3 轮独立对话测试
- 在 3 版本能力原型对比中，比较对象分别是：
  - Claude Code 官方 `skill-creator`
  - `My Skill Creator Copy`（我的第二版迭代）
  - `Dazhuang Skill Creator`（最终版）
- 已归档的 benchmark 包含：
  - `45 次 creation runs + 15 次 baselines` 的 3 版本对比
  - `30 次 creation runs + 15 次 baselines` 的官方原版 vs 最终版对比
- benchmark 过程中保留了源目录完整性检查，结果为 `manifest diff = 0`

## 测评维度

综合评分最终汇总到 5 个顶层维度：

- 过程效率（Process efficiency）
- 精准度（Precision）
- 产物质量（Product quality）
- 实际使用效果（Actual-use effect）
- 稳定性（Stability）

## 测评结果

### 总体结论

- `Dazhuang Skill Creator` 在本仓库归档的两套 benchmark 中都拿到了第一
- 在 3 版本能力原型对比中，最终版总分 `99.43`，排名第一
- 在 5 大类型对比的正面对比中，最终版总分 `99.44`，官方原版为 `96.20`
- 结果属于明确领先，但按照报告自己的判定规则，还不算“碾压”

### 3 版本能力原型对比结果

| 版本 | 总分 | 实际使用效果 | 过程效率 | 精准度 | 产物质量 | 稳定性 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dazhuang Skill Creator | 99.43 | 98.64 | 100.00 | 99.53 | 100.00 | 100.00 |
| My Skill Creator Copy | 87.84 | 94.60 | 84.25 | 97.55 | 94.39 | 0.00 |
| Claude Code 官方 `skill-creator` | 87.22 | 98.06 | 77.18 | 100.00 | 90.72 | 0.00 |

关键信息：

- 最终版相比第二名领先 `11.59` 分
- 在这一组 benchmark 里，最终版下游语义准确率达到 `100.0`
- 最终版平均 skill 体积也是三者里最小的：`4,290` bytes，对比 `7,063` 和 `6,613`

### 5 大类型对比：最终版 vs 官方原版

| 类型 | 官方原版 | 最终版 | 结论 |
| --- | ---: | ---: | --- |
| A 类｜内容型 | 100.00 | 100.00 | 持平 |
| B 类｜结构化输出型 | 100.00 | 100.00 | 持平 |
| C 类｜工具调研型 | 98.89 | 100.00 | 最终版领先 |
| D 类｜脚本型 | 100.00 | 100.00 | 持平 |
| E 类｜混合编排型 | 83.72 | 83.82 | 最终版微弱领先 |

这组正面对比里的补充结果：

- 综合总分：`99.44` vs `96.20`
- 实际使用效果：`100.00` vs `98.08`
- 过程效率：`97.74` vs `89.37`
- 下游语义准确率：`96.76` vs `96.52`
- Runtime validation：两边都是 `100.0`

## 为什么这个版本更易维护

相比官方原版，这个项目更强调可维护的结构分层：

- 主 `SKILL.md` 只放耐久规则和默认工作流
- 长解释下沉到 `references/`
- 可复用模板下沉到 `assets/`
- 确定性或重复性动作放进 `scripts/`
- 高频可调项集中放在 `config.yaml`

这样做的好处是，后续继续迭代时更容易改、更容易查，也更适合多人协作。原版 skill 一旦生成，后续提示词往往会越来越难维护；而这个版本从一开始就是按“可演进”来设计的。

## 项目结构

- `SKILL.md` - 最终版 Dazhuang Skill Creator skill 定义
- `agents/` - 用于评测与对比的 agent 提示词
- `references/` - 架构说明、评测流程、打包说明、schema 等参考资料
- `assets/` - 可复用资源和报告模板
- `scripts/` - 初始化、校验、评测、优化、生成报告、打包等脚本
- `config.yaml` - 初始化、评测、优化、打包等流程的默认配置
- `测评报告/` - 已归档的 benchmark 报告与截图

## 快速开始

### 新建一个 skill 脚手架

```bash
python3 scripts/init_skill.py my-skill --path ./out
```

### 校验 skill 结构

```bash
python3 scripts/quick_validate.py ./out/my-skill
```

### 评估触发效果

```bash
python3 scripts/run_eval.py \
  --eval-set ./path/to/eval-set.json \
  --skill-path ./out/my-skill
```

### 跑描述优化循环

```bash
python3 scripts/run_loop.py \
  --eval-set ./path/to/eval-set.json \
  --skill-path ./out/my-skill
```

### 打包 skill

```bash
python3 scripts/package_skill.py ./out/my-skill ./dist
```

## 测评报告位置

可直接查看以下归档目录：

- `测评报告/5 个能力原型对比/`
- `测评报告/5 个类型性能对比/`
- `测评报告/iShot_2026-04-04_12.17.26.png`

## License

Apache 2.0，见 `LICENSE` 与 `LICENSE.txt`。

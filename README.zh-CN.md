# Dazhuang Skill Creator

中文 | [English](README.md) | [更新日志](CHANGELOG.md)

![Dazhuang Skill Creator 基准测试总览](assets/benchmark-overview.png)

> 官方原版 = Claude Code 官方 `skill-creator`  
> `My Skill Creator Copy` = 我迭代出来的第二个版本  
> `Dazhuang Skill Creator` = 当前仓库中的最终版

Dazhuang Skill Creator 基于 Claude Code 官方 `skill-creator`，但并不只是改几句提示词。我把自己对提示词架构、Skill 架构，以及 CLI 工具运行机制的理解重新整合进去，对整体工作流、结构分层、bundled resources 和可维护性做了一次完整重构。

> `v1.5.0` 更新（2026-04-11）：这是一次大版本更新。新增记忆模式（`off` / `adaptive` / `lessons` / `auto`），补齐 lesson 晋升硬规则链路，`quick_validate.py` 增加记忆结构强校验，并补上“经验退休后不立刻复活”的回归测试。

在测评环节，我采用 Codex 的 Headless 模式进行测试：不需要打开图形界面，也不需要进入 CLI 页面，直接在终端执行。每个 benchmark item 都至少进行了 3 轮独立对话测试。完整的评测标准、原始结果与报告已经归档在 `测评报告/` 文件夹中。

如果这个项目对你有帮助，欢迎点一个 star。联系 / 合作方式：

- 微信：`yinyinGyL`
- 邮箱：`372749817@qq.com`

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

- 主 `SKILL.md` 以耐久规则和工作流程为主
- 单文件 skill 用固定 section 白名单收口：`角色`、`规则`、`工作流程`、`例子`、`输出格式`、`索引`
- `例子` 是给模型看的内部参考，不是用户提问示例；`输出格式` 是给模型直接遵循的模板
- 长解释下沉到 `references/`
- 可复用模板下沉到 `assets/`
- 确定性或重复性动作放进 `scripts/`
- 高频可调项集中放在 `config.yaml`

这样做的好处是，后续继续迭代时更容易改、更容易查，也更适合多人协作。原版 skill 一旦生成，后续提示词往往会越来越难维护；而这个版本从一开始就是按“可演进”来设计的。

## 改已有 skill 的默认策略

这个仓库现在不把“优化别人 skill”默认理解成只改几句 `description`，也不把“重构旧 skill”当成另一套方法论。

- 新建 skill 和重构 skill 共用同一套蓝图；差别只是从零搭，还是拿旧 skill 当素材重组
- 先诊断问题主要在触发、结构，还是两者都有
- 如果旧 skill 太胖、太散、多路径易跑偏，就默认先做结构重构，让它重新对齐 Dazhuang 这套架构
- 只有在 skill 本体结构已经站住后，才进入 trigger eval / description optimization
- 目标是对齐同一套蓝图，不是机械强套一份固定模板；简单 skill 仍然可以保持单文件

## 项目结构

- `SKILL.md` - 最终版 Dazhuang Skill Creator skill 定义
- `VERSION` - 当前 creator 版本号，供运行时更新检查使用
- `agents/` - 用于评测与对比的 agent 提示词
- `references/` - 架构说明、评测流程、打包说明、内部例子、schema 等参考资料
- `assets/` - 模型直接遵循的模板、可复用资源和报告模板
- `scripts/` - 初始化、校验、更新检查、评测、优化、生成报告、打包等脚本
- `config.yaml` - 初始化、更新检查、评测、优化、打包等流程的默认配置
- `测评报告/` - 已归档的 benchmark 报告与截图

## 快速开始

### 安装到 Claude Code / Codex / Open Claude 的 skill 目录

推荐安装方式是 `git clone`，因为运行时更新检查和自动更新都依赖 git 工作区。

```bash
cd <your-skill-dir>
git clone https://github.com/DazhuangJammy/DazhuangSkill-Creator.git
```

如果你是把 GitHub 链接丢给 AI 帮你安装，也请明确要求它：

- 用 `git clone https://github.com/DazhuangJammy/DazhuangSkill-Creator.git`
- 不要只下载 zip
- 不要只复制文件夹内容
- 不要删掉 `.git`

给 Claude / Codex / 其他安装型 AI 的标准提示词：

```text
请把这个 skill 安装到我的 skill 目录里，并且必须使用 git clone：

仓库地址：
https://github.com/DazhuangJammy/DazhuangSkill-Creator.git

要求：
1. 用 git clone 安装，不要下载 zip
2. 不要只复制文件夹内容
3. 保留 .git 目录
4. 安装完成后确认当前目录是一个正常的 git 工作区
5. 如果已经存在同名目录，优先先告诉我，再决定是 pull 还是重装
```

### 新建一个 skill 脚手架

如果你在 Windows 上运行，把 `python3` 替换成 `py -3`（优先）或 `python`。

```bash
python3 scripts/init_skill.py my-skill --path ./out
```

如果单文件 skill 需要额外模块，可以显式声明：

```bash
python3 scripts/init_skill.py my-judge-skill --path ./out --sections role,output-format
```

记忆层模式说明：

- `off`：不启用记忆层
- `lessons`：从创建当天启用完整记忆管线（`memory-state` + `memory-events` + `memory-lessons`）
- `adaptive`：先不启用，运行中检测到重复摩擦后自动开启
- `auto`（默认）：创建前自动判型，在 `off` / `adaptive` / `lessons` 里自动选择

`config.yaml` 里的这些 `memory_*` 字段只控制“新创建 skill 的默认策略”，不代表当前 creator 自己开启了记忆功能。

如果你要强制从第一天启用记忆层，可以用 lessons：

```bash
python3 scripts/init_skill.py my-review-skill --path ./out --memory-mode lessons
```

如果你要创建前自动判型，建议补一段 intent：

```bash
python3 scripts/init_skill.py my-analysis-skill --path ./out --memory-mode auto --intent "高变异分析任务，且会持续迭代"
```

如果你要运行中自动开启记忆层，使用 adaptive：

```bash
python3 scripts/init_skill.py my-analysis-skill --path ./out --memory-mode adaptive
```

`lessons` 和 `adaptive` 都会创建 `scripts/memory_mode_guard.py`、`references/memory-state.json`、`references/memory-events.jsonl`。

- `lessons`：从第一天就开始记忆；同类失败签名重复后写入/更新 lessons。
- `adaptive`：先关闭记忆；达到阈值后自动开启 lessons。
- 两种模式都会在 lesson 稳定命中后，把规则晋升到生成的 `SKILL.md` 里的 `MEMORY_HARD_RULES` 区块。

### 校验 skill 结构

```bash
python3 scripts/quick_validate.py ./out/my-skill
```

`quick_validate.py` 现在会对 memory skill 做强校验：`MEMORY_HARD_RULES` 标记块、Step 1 / Step 4 的 guard 命令，以及必需的记忆运行文件是否齐全。

### 手动检查 creator 更新

```bash
python3 scripts/check_update.py --force
```

### 重构一个现有 skill

- 本质上还是按新建 skill 的那套蓝图来写，只是先从旧 skill 里抽取可保留的内容
- 先判断这次需要多大力度：`轻优化`、`结构重构`、`完整改造`
- 如果问题是结构臃肿、路径漂移、长上下文容易丢主线，先重排 `SKILL.md` 与 `references/` / `assets/` / `scripts/`
- 只有当结构已经站住时，再进入下面的触发评估与描述优化

### 评估触发效果

```bash
python3 scripts/run_eval.py --eval-set ./path/to/eval-set.json --skill-path ./out/my-skill
```

### 跑描述优化循环

仅在 skill 本体结构已经站住时使用：

```bash
python3 scripts/run_loop.py --eval-set ./path/to/eval-set.json --skill-path ./out/my-skill
```

### 打包 skill

```bash
python3 scripts/package_skill.py ./out/my-skill ./dist
```

## 运行时更新检查

这个 repo 现在自带一条轻量的自更新链路，默认挂在这个 skill 的 Step 1：

- 推荐安装地址：`https://github.com/DazhuangJammy/DazhuangSkill-Creator.git`
- 推荐安装方式：`git clone` 到目标 skill 目录
- 每次真正启用这个 skill 时，会先运行 `scripts/check_update.py`
- 默认每 `24` 小时最多联网检查一次
- 发现新版本时，默认只提醒一次；之后等到更高版本再提醒
- 默认配置已经开启 `update_check.auto_update: true`；只要当前安装是干净的 git clone 工作区，脚本就会尝试执行 `git pull --ff-only`
- 如果当前 skill 是手动复制安装，或者目录里有本地改动，则不会强制覆盖，只做提醒
- 就算自动更新成功，新版本也会从“下一次调用这个 skill”开始完整生效；当前这次调用仍沿已加载版本继续

最小配置如下：

```yaml
update_check:
  enabled: true
  interval_hours: 24
  auto_update: true
```

如果你想保守一点，也可以显式关闭自动更新：

```yaml
update_check:
  enabled: true
  auto_update: false
  interval_hours: 24
```

## 测评报告位置

可直接查看以下归档目录：

- `测评报告/5 个能力原型对比/`
- `测评报告/5 个类型性能对比/`
- `测评报告/iShot_2026-04-04_12.17.26.png`

## License

Apache 2.0，见 `LICENSE` 与 `LICENSE.txt`。

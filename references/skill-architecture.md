# Skill 架构指南

当你要从零起草 skill，或把一个现有 skill 从“说明书堆叠”重整为“可用结构”并按当前这套蓝图重新落盘时，读这份文档。

默认把 `<skill-base>` 理解为当前 skill 的 `SKILL.md` 所在目录。

- 进入这份文档时，沿用主 `SKILL.md` 已经判定好的 `current_path`，通常是：`新建` 或 `修改`。
- 执行过程中始终显式维护：`current_step` 和 `next_action`。
- 如果刚看完大段旧文档、工具输出、或 bundled resources，先复述：
  - 当前路径：`新建` 或 `修改`
  - 当前步骤：`Step N`
  - 下一动作：一句话
- 如果任务已经漂移成“评估输出质量”“优化触发描述”或“打包交付”，不要继续沿用这份文档；回主 `SKILL.md` 的 Step 1 重新判路。

## 快速主线

- `Step 1`：先判断这个 skill 的目标、触发场景、产出物、边界，以及本轮需要多大力度
- `Step 2`：把内容分层到 `SKILL.md` / `references/` / `assets/` / `scripts/` / `config.yaml`
- `Step 3`：起草最小可用 body，只保留耐久规则、工作流程、精确文件指针
- `Step 4`：判断要不要给目标 skill 加一个紧凑 `# 索引`
- `Step 5`：做最终结构检查，确认它更轻、更稳、更不容易漂移

如果只是想快速恢复方向，先看这 5 条主线；需要细节时再往下读。

## 目标

一个好 skill 的主 body 读起来应该像一条顺畅的默认路径，而不是一本全集说明书。默认路径之外的内容，尽量下沉到 bundled resources。

起草前先回答五个问题：

1. 这个 skill 要让 Claude 做什么？
2. 它应该在什么情况下触发？
3. 它要产出什么结果或文件？
4. 哪些是耐久规则，哪些只是示例、模板、细节说明？
5. 它需不需要一个紧凑 `# 索引` 来帮助恢复方向？

如果一段内容既不会改变默认下一步决策，也不会避免高频错误，也不属于大多数调用都会用到的部分，它大概率不该留在主 body。

同样，**不是所有辅助文件都值得默认创建**。如果一个 skill 用单个 `SKILL.md` 就能稳定完成任务，就不要顺手加 `references/`、`assets/`、`config.yaml`、`agents/openai.yaml` 或评测资产。

## 修改现有 skill：仍然走同一套蓝图

如果用户说的是“优化这个现有 skill”，不要把它理解成另一套方法论。新建 skill 和重构 skill 共用同一套蓝图；区别只在于你是从空白开始，还是从旧 skill 里抽取材料再重组。

先判断这次需要多大力度：

- `轻优化`：结构基本站得住，只补 `description`、局部规则、边界、示例，或小的 workflow 断点
- `结构重构`：skill 太胖、太散、多路径易漂移，需要按当前这套架构原则重排主 body 与 bundled resources
- `完整改造`：先做结构重构，再做 output eval、trigger optimization、blind comparison 之类更重的验证

如果后面要进 output eval，不要直接从写 eval prompts 开始。先回主 `SKILL.md` 的 Step 1，再走 `<skill-base>/references/eval-planning.md`，把“到底评什么、哪些不看、怎么比较”先锁成正式评估计划；之后才进 `<skill-base>/references/eval-loop.md`。

满足下面任一条时，默认至少升到 `结构重构`：

- 主 body 混了长解释、长示例、低频模块说明
- 有多条路径，但没有恢复方向的入口
- `references/`、`assets/`、`scripts/` 指针不少，却没有精确分流
- 一进长对话、viewer、批量运行或大段工具输出就容易丢主线
- 你已经无法用几处局部修补解释它的问题

只有当 skill 本体结构已经站住时，才值得进入 `description` 优化。

重构现有 skill 的目标，是让它重新对齐这套蓝图，而不是尽量保留旧写法。简单 skill 如果单文件就够稳，保持单文件也完全可以；复杂 skill 才继续拆到 `references/`、`assets/`、`scripts/`。

你可以把旧 skill 看成“素材和脏输入”：

- 承重的规则留下
- 真正的工作流程留下并重写得更清楚
- 长解释、长示例、低频模块下沉
- 不承重的累赘直接删掉

最后仍然回到同一个目标形状：主 `SKILL.md` 扛规则和工作流程，必要时再补一个紧凑 `# 索引`。

## Skill 目录的基本结构

```text
skill-name/
├── SKILL.md
├── config.yaml                  # 可选，人会改的配置
├── references/                 # 长解释、示例、schema
├── assets/                     # 直接使用的模板或文件
└── scripts/                    # 确定性或重复性执行
```

## 各层分别放什么

### 主 `SKILL.md` body

这里只放：
- 耐久规则
- 工作流程
- 复杂 skill 可选的紧凑 `# 索引`
- 在工作流里嵌入的精确文件指针

这里不要放：
- 长示例
- 长输出规格
- 巨大的导航目录
- 环境专用手册
- 只在某个低频模块里才成立的执行细节

### `references/`

这里放：
- 长解释
- 给模型看的内部例子 / canonical case
- 可复用的短经验提炼（例如 `references/memory-lessons.md`，只在命中重复错误或高代价边界时读取）
- 运行期记忆状态（例如 `references/memory-state.json`）与事件轨迹（例如 `references/memory-events.jsonl`）
- 记忆计数脚本（例如 `scripts/memory_mode_guard.py`；当 `memory_enabled=true` 时把读 memory-lessons 视为默认前置步骤，并把稳定 lesson 晋升到 `SKILL.md` 的硬规则块）
- schema
- 环境差异说明
- 触发优化、benchmark、blind comparison 这类低频模块说明

如果任务是“原始输入很乱，但最终输出结构很稳”的类型，一份短而专的 `reference` 往往比继续加厚主 body 更有效。比如提炼访谈纪要、研究 brief、结构化摘要时，可以把抽取顺序、歧义处理、证据标准单独放进 `references/`。如果最终交付物的标题、章节顺序、heading level 本来就固定，再配一个写死结构的 `assets/` 模板，不要只在主 body 里口头描述章节名。

这里要特别分清：

- `references/examples.md` 或主 body 里的 `# 例子`，是给模型看的内部参考材料
- 它们的作用是示范“遇到这类情况该怎么判断、怎么取舍、怎么落到输出”
- 它们不是“用户可以这样提问”的入口示例
- 用户入口示例如果需要存在，应该落在 `description`、触发优化材料，或交付环境自己的元数据里

对单文件 skill 而言，`# 例子` 和 `# 输出格式` 可以存在，但它们不是默认常驻件。一旦出现下面这些信号，就该下沉：

- 例子已经不止一两个关键边界
- 输出格式已经变成长模板、长 schema、长排版说明
- 这些内容不是每次调用都会用到
- 主 `SKILL.md` 已经开始像一本说明书，而不是一条默认路径

下沉时默认对应关系是：

- `# 例子` -> `references/examples.md`
- `# 输出格式` -> `assets/output-format.md`

### `assets/`

这里放：
- 模型应直接遵循的模板、骨架、字段约束
- HTML review 壳子
- Claude 应该直接复制、填写、交付的文件

如果你在做输出评估，也可以把固定提案骨架和固定计划骨架放这里。像这次 creator 自带的：

- `assets/evaluation-proposal-template.md`
- `assets/evaluation-plan-template.md`
- `assets/evaluation-alignment-script.md`

就是给模型直接复制使用的评估模板，而不是长解释。

### `scripts/`

这里放：
- 确定性转换
- 重复性执行步骤
- validator
- 打包辅助脚本
- report 生成器

### `config.yaml`

这里放：
- 人会频繁调的参数
- 不该散落在脚本和 JSON 里的默认值

JSON 保留给机器写入的产物、缓存、benchmark 输出或严格交换格式。

如果当前 skill 没有明显需要“人类频繁调”的参数，就不要为了形式完整而创建 `config.yaml`。

### `agents/openai.yaml`

这里只有在**目标交付环境明确需要 OpenAI 界面元数据**时才创建。

如果用户只是要一个本地可用、可打包、可复用的 skill，而没有要求 OpenAI 商店/界面适配，就不要默认生成它。

如果需要字段说明、最小示例或覆盖优先级，读 `<skill-base>/references/openai-yaml.md`。

## Frontmatter 怎么写

### `name`

- 尽量稳定，保持 kebab-case
- 修改已有 skill 时，除非用户明确要求，否则不要改名

### `description`

这就是 skill 的第一层触发面。

写法要围绕“用户意图”，而不是内部实现细节。至少要覆盖：
- 这个 skill 帮什么忙
- 什么情况下应该用它
- 哪些相近场景里 Claude 容易漏触发，它应该补上

不要把它写成又臭又长的关键词清单。它应该直接、清晰、有辨识度，并且明显低于硬长度上限。

如果用户需要严谨地调优触发行为，读 `<skill-base>/references/description-optimization.md`。

如果旧 skill 的结构还没站住，不要指望只靠 `description` 把问题救回来；先把它拉回这套蓝图。

## 单文件 hard format

如果目标 skill 单文件就够稳，默认把 `SKILL.md` 收进下面这套固定 section 白名单：

- `# 角色`
- `# 规则`
- `# 工作流程`
- `# 例子`
- `# 输出格式`
- `# 索引`

其中只有下面两项是必选：

- `# 规则`
- `# 工作流程`

其余四项都是按需启用：

- `# 角色`：只有当判断视角、身份边界或表达姿态会明显影响结果时才加
- `# 例子`：只有当高代价边界靠文字规则钉不住时才加，而且应当很短；它是给模型看的内部参考，不是用户问句示例
- `# 输出格式`：只有当输出结构需要稳定时才加；它是给模型直接遵循的模板，不是面向用户的解释
- `# 索引`：只有当单文件已经复杂到容易漂移时才加

不要让单文件 skill 自由长出其他顶级 section。要么用这套闭集，要么判断是不是该改成多文件。

这里还要分清两层：

- creator / validator 负责的架构规则：section 白名单、下沉阈值、命名约束、打包前校验
- 目标 skill 自己要背的规则：真正会影响执行结果的最小结构规则

前一层不要整段原封不动抄进每个目标 skill。否则 skill 虽然不跑偏，但会平白变胖。

但有一条例外要钉死：只要目标 skill 根目录下出现 bundled resources（例如 `references/`、`assets/`、`scripts/`、`agents/`、`evals/`、`config.yaml`），主 `SKILL.md` 就必须明确把当前 `SKILL.md` 所在目录定义为 `<skill-base>`。这是运行语义，不只是 creator 的偏好。

如果要加 `# 角色`，再往下判断它更像哪一种：

- 扮演角色：例如编辑、教练、审稿人、谈判者
- 借用视角：例如乔布斯式判断、巴菲特式取舍、第一性原理视角

两种都可以存在，但要明确主方向，不要把“人格扮演”和“方法论视角”混写成一团。

## 推荐的主 body 形状

默认使用下面这个形状：

```markdown
# 角色
- [可选]

# 规则
- 只放耐久规则
- 保持短

# 工作流程
## Step 1：判断任务
- 搞清楚请求、约束、缺失信息

## Step 2：先定结构，再写内容
- 判断哪些该留在 body，哪些该下沉

## Step 3：起草或重写 skill
- 需要 bundled resources 时，给出精确文件指针

## Step 4：选择验证路径
- 走最轻但仍可信的验证方式

## Step 5：继续迭代，或者停下
- 只在新增结构还能带来收益时继续

# 例子
- [可选]

# 输出格式
- [可选]

# 索引
- [可选]
```

如果这个 skill 足够复杂，可以在 workflow 后面再加一个紧凑 `# 索引`，但它是可选组件，不是默认必选项。

## 可移植路径策略

默认用 `<skill-base>` 作为 bundled resources 的锚点。

- 推荐：`<skill-base>/references/...`
- 推荐：`<python-cmd> "<skill-base>/scripts/..."`
- 不推荐：把本次运行时的绝对路径直接写进最终交付物

只有当用户明确要求“只在当前机器临时用”或者某个环境文档本来就是一次性本地说明时，才考虑绝对路径。

## 极简输出 skill 的写法

有一类 skill 的核心价值就是**把输出收得非常短**，例如：

- Conventional Commit
- 一条 shell 命令
- 一个标题
- 一段短摘要

这类 skill 最常见的失败不是“不会做”，而是**顺手多说了两句**。

因此建议把约束写成三层：

1. 在 `规则` 里明确写：默认只输出什么
2. 在 `工作流程` 里明确写：什么时候才允许扩写
3. 在最后检查里再明确删一遍：把不必要的 body、解释、备选项去掉

如果默认产物是单行，就不要只写“尽量简洁”；要直接写成“默认只输出单行结果，除非满足 X 条件才允许 body”。

对 Conventional Commit 这类场景，`X` 最好是闭集，而不是模糊判断。更稳的写法通常是：

- 只有明确的 breaking change 才允许 body
- 或者只有迁移/弃用说明会误导读者时才允许 body
- 或者用户明确要求附加上下文时才允许 body
- 对公开接口变更要单独钉住：旧 CLI flag / option / env var / config key / API field 只要被拒绝、移除、重命名，或被新名字替代，通常都应该视为 breaking interface change，而不是普通 `fix`

不要把“还有一个支持细节”“顺手补一句测试更新”“多写一行会更完整”当作允许扩写的理由；这类说法最容易把单行 skill 重新写胖。

如果这个边界在测试里已经反复误判，可以保留 1 个极短 canonical example 来封口，例如：

```text
Input: "replace --legacy-token with --api-token in the deploy CLI; the old flag is now rejected"

Output:
feat(deploy)!: replace --legacy-token with --api-token

BREAKING CHANGE: update scripts and automation to use --api-token
```

这里的关键不是 body 本身，而是让模型别把“旧 flag 被拒绝 + 新 flag 替代”误读成普通修复。

反过来，如果任务是结构化合成而不是极简输出，也不要把所有 heuristics 都硬塞回主 body。主 body 负责默认路径；提取细则可以交给一份短 reference。如果输出格式是固定 markdown brief，最好把精确模板单独放进 `assets/`，例如直接写死 `## Summary`、`## Pain Points` 等 heading，而不是让模型自己决定标题层级。

## 什么时候该加 `# 索引`

只有当 skill 已经复杂到容易让模型在长上下文里漂移时，才加 `# 索引`。默认至少满足下面两条再加：

- 有 2 条以上路径分流
- 有 3 个以上 `references/`、`agents/`、`scripts/` 指针
- 会出现长工具输出、多轮迭代或批量运行
- 有 Claude.ai / Codex / Cowork 之类的环境分支
- 主 body 已经不是很短的单路径说明

如果 skill 很短、单路径、资源很少，就不要为了形式统一硬加索引。

## `# 索引` 应该怎么写

好的索引只做“恢复方向”这一件事，不要把它写成第二份 workflow。

索引里通常只放：
- 先复述 `current_path`、`current_step`、`next_action`
- 按当前路径直达精确文件
- 一句边界说明：索引只用于恢复上下文，不替代 workflow

默认形状可以像这样：

```markdown
# 索引

- 如果上下文变长、刚看完大段工具输出、或需要重新找回方向，先复述：
  - `current_path`
  - `current_step`
  - `next_action`
- 然后按当前路径直达对应材料：
  - 路径 A：`<skill-base>/references/...`
  - 路径 B：`<skill-base>/scripts/...`
- 这个索引只用来快速恢复上下文，不替代 workflow。
```

## 写作原则

- 尽量使用祈使句。
- 如果解释“为什么”能帮助 Claude 泛化，就解释原因，不要只堆 MUST。
- 对长 body 保持怀疑。能下沉就下沉。
- 不要笼统地说“去 references 看看”，而要精确指到文件。
- 命令一旦重要，就把路径写死：`<python-cmd> "<skill-base>/scripts/..."`
- 让 workflow 负责分流，不要把所有模块以同样权重平铺在主 body 里。
- 如果加 `# 索引`，让它做恢复，不要让它和 workflow 抢主导权。

## 常用脚手架命令

### 新建 skill 骨架

当空白结构比手写更省时间时，执行：

```bash
<python-cmd> "<skill-base>/scripts/init_skill.py" <skill-name> --path <output-dir> --memory-mode auto --intent "<task semantics>"
```

注意：`--path` 和 `config.yaml -> init_skill.output_path` 至少要有一个；两边都没有会直接报错。

常见选项：
- `--resources scripts,references,assets`
- `--memory-mode off|lessons|adaptive|auto`
- `--intent "<text>"`（在 `memory-mode=auto` 下提供判型语义）
- `--examples`（只有加这个，才会创建 `references/examples.md`）
- `--config-file`
- `--openai-yaml`
- `--interface key=value`（只有在已经决定要生成 `agents/openai.yaml` 时才需要）

额外提醒：
- 如果最终模式是 `lessons` 或 `adaptive`，脚手架会自动补齐 `references/` 和 `scripts/`。
- 只要启用了 `--resources assets`，脚手架会默认创建 `assets/output-format.md`。
- 如果任务是固定章节/评审报告/表格模板输出，优先走 assets 路径，不要先塞进内联 `# 输出格式`。

记忆层判断是必做步骤，不要跳过：
- 无论最后是 `off`、`adaptive` 还是 `lessons`，都要先判断“要不要记忆层”。
- 推荐默认写法：`--memory-mode auto --intent "<任务语义>"`。
- 如果你手动指定 `--memory-mode off`，要补一句理由（例如低风险、低变异、可确定性执行）。

### 生成 OpenAI 界面元数据

当 skill 需要 `agents/openai.yaml` 时，执行：

```bash
<python-cmd> "<skill-base>/scripts/generate_openai_yaml.py" <skill-dir>
```

如果你不确定字段该怎么填，先读 `<skill-base>/references/openai-yaml.md`。

## 最终结构检查

在你认为结构已经定型前，检查：
- 这次改已有 skill 时，是否已经明确本轮需要多大力度，才能把它拉回当前这套蓝图
- 单文件 skill 的顶级 section 是否只来自固定白名单
- `# 规则` 和 `# 工作流程` 是否都存在
- 如果有 `# 索引`，它是否足够短，而且只是恢复入口，不是第二份说明书
- `# 例子` 和 `# 输出格式` 如果已经变长，是否已经下沉
- 每个 bundled file 指针是否都足够精确
- 每条脚本命令是否都写明执行路径
- 如果是 memory skill，Step 4 里是否保留了 `memory_mode_guard.py --event retry` 和 `--event failure`
- 如果准备交付，是否已经跑过 `quick_validate.py <skill-dir> --strict`，并清掉 TODO/TBD 占位词
- 新结构是否真的比之前更轻，而且没有丢关键能力
- 最终交付物里有没有混入不必要的 `config.yaml`、`agents/openai.yaml`、`evals/` 或 workspace 资产
- 如果默认输出应该极简，最终样例有没有偷偷长出多余 body、解释或多方案
- 汇报时是否已经交代：主 body 留了什么、下沉了什么、删了什么，以及为什么这次需要这样的干预力度

## 索引

- 如果上下文变长、刚读完 bundled resources、或需要重新找回方向，先复述：
  - `current_path`
  - `current_step`
  - `next_action`
- 然后按当前路径直达对应材料：
  - 快速恢复主线：回到这份文档的 `快速主线`
  - 判断要不要加 `# 索引`：看这份文档的 `什么时候该加 # 索引`
  - 需要 body 骨架：看这份文档的 `推荐的主 body 形状`
  - 需要脚手架命令：看这份文档的 `常用脚手架命令`
  - 如果任务已漂移成评测 / 优化 / 打包：回主 `SKILL.md` 的 Step 1，再跳到对应 reference
- 这个索引只用来快速恢复上下文，不替代上面的主线和各节内容。

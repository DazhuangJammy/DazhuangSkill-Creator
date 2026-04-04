# 评测循环

当用户需要的不只是“结构更顺眼”，而是想知道 skill 产出是否真的更好时，走这条路径。

默认把 `<skill-base>` 理解为当前 skill 的 `SKILL.md` 所在目录。

- 一旦进入这份文档，先固定：`current_path` = `评估`。
- 执行过程中始终显式维护：`current_step` 和 `next_action`。
- 每次进入新步骤，或准备进入批量运行、grader、benchmark、viewer 这类重型操作前，先复述：
  - 当前路径：`评估`
  - 当前步骤：`Step N`
  - 下一动作：一句话
- 如果任务已经从“评估输出质量”漂移成“优化触发描述”或“打包交付”，不要继续沿用这份文档；先回主 `SKILL.md` 的 Step 1 重新判路。

## 什么时候该用完整评测循环

当至少满足下面一条时，使用完整评测循环：
- 用户明确问“这个 skill 到底有没有变好”
- 这个 skill 会显著影响输出质量，应该在真实 prompt 上验证
- 用户想要可复用的迭代闭环，而不是一次性的 vibe check

如果只是讨论结构，不要默认进入这条重路径。

## Step 1：写真实 eval prompts

- 进入这一步时，更新：
  - `current_step` = `Step 1`
  - `next_action` = 先写少量真实 eval prompts，覆盖主要失败模式
- 先写 2-3 个用户真的会说的 prompt。
- 尽量覆盖不同失败模式。
- 只有当你明确进入完整评测循环时，才保存到目标 skill 的 `evals/evals.json`。
- 一开始先有 prompt 和期望结果就够了；只有当断言客观可验证，而且值得这笔成本时，才补 assertions。

如果你需要机器格式，读 `<skill-base>/references/schemas.md`。

## Step 2：组织 workspace

- 进入这一步时，更新：
  - `current_step` = `Step 2`
  - `next_action` = 搭好最小 workspace 结构，边跑边建目录
结果建议放到一个同级 workspace：

```text
<target-skill>-workspace/
└── iteration-1/
    └── eval-0/
        ├── with_skill/
        └── without_skill/   # 如果是在改旧 skill，也可以是 old_skill/
```

规则：
- 边跑边建目录，不要一次性全建完。
- 如果某个 eval 的测试目标很明确，目录名可以更有语义。
- 每个 eval 目录都写一个 `eval_metadata.json`。

## Step 3：with-skill 和 baseline 同轮跑

- 进入这一步时，更新：
  - `current_step` = `Step 3`
  - `next_action` = 成对启动 with-skill 和 baseline，同轮比较
- 进入批量运行前，先再做一次状态播报，确认你是为了比较而运行，而不是因为惯性把任务拉进重路径。
每个 eval 都要成对执行：
- 跑一轮 with-skill
- 同一轮再跑一轮 baseline

baseline 的选择：
- 新建 skill：用 `without_skill`
- 修改现有 skill：先 snapshot 旧 skill，用 `old_skill`

这样你比的是“同一题下的新旧差异”，而不是单独看新方案自我感觉良好。

## Step 4：只有断言值得存在时才加

- 进入这一步时，更新：
  - `current_step` = `Step 4`
  - `next_action` = 只补那些客观、值得、真能区分好坏的 assertions
在执行跑起来之后：
- 补那些客观可验证的 assertions
- 对写作风格、审美、设计感这类强主观内容，不要硬塞断言
- 向用户解释每条断言到底在检查什么

好断言应该有区分度：skill 真的做对了才会过，表面凑合、糊弄过去不该过。

## Step 5：及时保存 timing 数据

- 进入这一步时，更新：
  - `current_step` = `Step 5`
  - `next_action` = 一有完成通知就立刻写 timing.json
每个子任务一结束，就立刻把 `total_tokens` 和 `duration_ms` 写进该 run 的 `timing.json`。这个信息很容易错过，晚了就没了。

## Step 6：给每轮 run 打分

- 进入这一步时，更新：
  - `current_step` = `Step 6`
  - `next_action` = 用 grader 或脚本化检查给每轮结果打分
这里用 `<skill-base>/agents/grader.md`。

grader 应该：
- 读 transcript 和 outputs
- 给每条 expectation 判定并附证据
- 顺手指出那些会制造虚假信心的弱断言
- 把结果保存成 `grading.json`

能脚本化检查的地方，优先脚本化，而不是肉眼猜。

## Step 7：聚合 benchmark

- 进入这一步时，更新：
  - `current_step` = `Step 7`
  - `next_action` = 聚合通过率、耗时、Token 等对比数据
在 `<skill-base>` 下执行：

```bash
cd "<skill-base>" && python3 -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
```

它会输出通过率、耗时、Token 数等聚合数据。

如果你需要 schema 细节，读 `<skill-base>/references/schemas.md`。

## Step 8：生成 review viewer

- 进入这一步时，更新：
  - `current_step` = `Step 8`
  - `next_action` = 生成 review viewer，把结果尽快交给人看
- 在启动 viewer 前，先确认是否需要 headless / static 模式，不要凭默认环境假设继续。
用自带 viewer，不要自己重新写一套 HTML。

典型命令：

```bash
cd "<skill-base>" && python3 eval-viewer/generate_review.py <workspace>/iteration-N --skill-name "<name>" --benchmark <workspace>/iteration-N/benchmark.json
```

如果是第 2 轮以后，还要带上 `--previous-workspace <workspace>/iteration-(N-1)`。

如果环境是 headless，就生成静态 HTML，而不是依赖本地浏览器 server。

## Step 9：让人类看输出

- 进入这一步时，更新：
  - `current_step` = `Step 9`
  - `next_action` = 引导用户看输出、formal grades 和反馈区
因为有些判断天然带主观性，所以 review 这一步很重要。

让用户重点看：
- prompt
- 输出文件
- 上一轮输出（如果有）
- formal grades（如果有）
- feedback 区域

用户 review 完之后，读 `feedback.json`，优先改那些用户明确指出有问题的 eval。

## Step 10：只改真正该存在的东西

- 进入这一步时，更新：
  - `current_step` = `Step 10`
  - `next_action` = 根据反馈抽象共性，修改真正该存在的结构
根据 review 去改 skill 时：
- 从反馈里抽象共性，不要只对一个 prompt 过拟合
- transcript 里如果出现明显浪费工时的行为，就把诱发这些行为的说明删掉或重写
- 如果多个 eval 都在重复造同一种 helper script，就应该把它正式收进 `scripts/`
- 继续保持 body 精简；一旦膨胀，就把细节移回 references/assets
- 如果某个 skill 的默认产物本来就该很短，下一轮要专门检查“是否出现了不必要的 body/解释/多方案”，并把这类失败纳入 eval

## Step 11：继续，或者停下

- 进入这一步时，更新：
  - `current_step` = `Step 11`
  - `next_action` = 判断是否继续下一轮评测，还是及时停下
只有在循环还带来清晰收益时，才继续迭代。

满足下面任一条，就可以停：
- 用户已经满意
- feedback 只剩轻微问题或空白
- 新增复杂度已经不再换来明显提升

- 如果还要继续下一轮，并且当前路径仍然是 `评估`，回到这份文档的 Step 1。
- 如果用户下一步要做的是触发优化、环境适配或打包交付，回主 `SKILL.md` 的 Step 1 重新判路。

## 相关文件

- schema：`<skill-base>/references/schemas.md`
- grader 指南：`<skill-base>/agents/grader.md`
- 如果要做 blind 对比：
  - `<skill-base>/agents/comparator.md`
  - `<skill-base>/agents/analyzer.md`

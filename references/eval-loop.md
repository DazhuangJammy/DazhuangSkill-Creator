# 评测循环

当用户需要的不只是“感觉更顺眼”，而是想知道 skill 产出是否真的更好时，走这条路径。

默认把 `<skill-base>` 理解为当前 skill 的 `SKILL.md` 所在目录。

这份文档就是前置对齐之后唯一允许的正式执行主线。只要用户已经确认评估标准，就不要把任务降回结构讨论、普通 review、聊天结论或其他轻路径。

- 一旦进入这份文档，先固定：`current_path` = `评估`。
- 执行过程中始终显式维护：`current_step` 和 `next_action`。
- 每次进入新步骤，或准备进入批量运行、grader、benchmark、viewer 这类重型操作前，先复述：
  - 当前路径：`评估`
  - 当前步骤：`Step N`
  - 下一动作：一句话
- 如果任务已经从“评估输出质量”漂移成“优化触发描述”或“打包交付”，不要继续沿用这份文档；先回主 `SKILL.md` 的 Step 1 重新判路。
- 如果还没有正式评估计划，或者“到底算哪种好”还没和人对齐，就先回 `<skill-base>/references/eval-planning.md`。
- 这份文档不是“第一次收到评估请求”时的入口文档。只要用户还没明确确认测评方案，就不要继续读下面步骤，直接回 `<skill-base>/references/eval-planning.md`。
- 一旦已经进入这条主线，除非条件阻塞并明确说明卡点，否则默认一直执行到 Step 10，把 `review.html` 和 `report.html` 都落地。

## 什么时候该用完整评测循环

当至少满足下面一条时，使用完整评测循环：

- 用户明确问“这个 skill 到底有没有变好”
- 用户想比较“有这个 skill”和“没有这个 skill”到底差在哪里
- 用户想比较两个或三个同类 skill 谁更好
- 这个 skill 会显著影响输出质量，应该在真实 prompt 上验证
- 用户想要可复用的迭代闭环，而不是一次性的 vibe check

如果只是讨论结构，或者正式评估计划都还没定，就不要默认进入这条重路径。

## Step 1：先读正式评估计划

- 进入这一步时，更新：
  - `current_step` = `Step 1`
  - `next_action` = 先锁定这次已经确认过的目标、维度、比较方式和不看项
- 先读已经确认过的 `正式评估计划`。
- 至少锁定下面这些信息：
  - 评估对象是谁
  - 比较模式是什么：单 skill / with-vs-without / 多 skill 对比
  - 主方向、次方向和权重
  - 重点维度和明确不看项
  - 样本类型、样本数量、是否盲评
- 如果是纯客观任务，前置计划可以很短；但不能完全没有。
- 这里说的“正式评估计划”，必须是用户已经明确确认过的版本；不能是 AI 自己刚写完、还没给用户拍板的草案。
- 如果需要机器格式，可把计划落到 `evals/eval-plan.json`；字段见 `<skill-base>/references/schemas.md`。
- 从这一步开始，不要再把任务改回“先给个简短判断”或“先做个普通 review”。

## Step 2：按计划写真实 eval prompts

- 进入这一步时，更新：
  - `current_step` = `Step 2`
  - `next_action` = 按已确认的维度写少量真实 eval prompts，覆盖主要失败模式
- 先写 2-3 个用户真的会说的 prompt。
- prompt 必须从正式评估计划倒推出来，不要临时想到什么就测什么。
- 尽量覆盖不同失败模式。
- 如果是比较多个对象，所有被比较对象都必须跑同一组 prompt。
- 只有当你明确进入完整评测循环时，才保存到目标 skill 的 `evals/evals.json`。
- 一开始先有 prompt 和期望结果就够了；只有当断言客观可验证，而且值得这笔成本时，才补 assertions。

如果你需要机器格式，读 `<skill-base>/references/schemas.md`。

## Step 3：组织 workspace 和比较拓扑

- 进入这一步时，更新：
  - `current_step` = `Step 3`
  - `next_action` = 搭好最小 workspace 结构，并明确这轮到底怎么比

结果建议放到一个同级 workspace：

```text
<target-skill>-workspace/
└── iteration-1/
    └── eval-0/
        ├── with_skill/
        ├── without_skill/
        ├── old_skill/
        ├── skill_a/
        ├── skill_b/
        └── skill_c/
```

规则：

- 边跑边建目录，不要一次性全建完。
- 只保留当前比较模式需要的目录，不要所有名字都预建。
- 每个 eval 目录都写一个 `eval_metadata.json`。
- 在 `eval_metadata.json` 里写清楚这题对应的是哪条已确认维度，避免后面看结果时忘了这题本来在测什么。
- 只要已经有正式评估计划，`eval_metadata.json` 里的 `dimension_ids` / `dimension_labels` 就不是可有可无；后面的 benchmark 聚合会拿它做硬校验。

比较拓扑默认只选一种：

- `单 skill 体检`：看它本身站不站得住
- `with-vs-without`：看有没有实际增益
- `old-vs-new`：看改动是不是带来了提升
- `peer-vs-peer`：看同类 skill 谁更好

如果这次要比三个 skill：

- 默认用同一组题做固定轮次对比
- 可以做 round-robin 或固定主擂台
- 不要一轮轮改 rubric，也不要一边跑一边换评价标准

## Step 4：同题同轮跑所有被比较对象

- 进入这一步时，更新：
  - `current_step` = `Step 4`
  - `next_action` = 在同样条件下跑所有被比较对象，避免比较失真
- 进入批量运行前，先再做一次状态播报，确认你是在执行已对齐的计划，而不是因为惯性把任务拉进重路径。
- 同一题下，所有被比较对象都要尽量控制变量：
  - 同模型
  - 同环境
  - 同预算
  - 同时间约束
  - 同 prompt
- baseline 的选择：
  - 新建 skill：用 `without_skill`
  - 修改现有 skill：先 snapshot 旧 skill，用 `old_skill`
  - 同类 skill 对比：直接用 `skill_a / skill_b / skill_c`

这样你比的是“同一题下的真实差异”，而不是各自跑在不同条件下的幻觉优劣。

## Step 5：只给客观部分写 assertions

- 进入这一步时，更新：
  - `current_step` = `Step 5`
  - `next_action` = 只补那些客观、值得、真能区分好坏的 assertions
- 对写作风格、人格相似、思维味道这类强主观内容，不要硬塞断言。
- assertions 只覆盖那些真的能客观验证的部分，例如：
  - 有没有完成任务
  - 关键字段对不对
  - 是否用了某个必要脚本
  - 时间 / 成本 / token 是否超预算
- 向用户解释每条断言到底在检查什么。
- 如果正式评估计划里的主维度根本没有被 assertions 覆盖到，要明确记下来，后面交给 blind comparison 或人类 review。

好断言应该有区分度：skill 真的做对了才会过，表面凑合、糊弄过去不该过。

## Step 6：及时保存 timing 数据

- 进入这一步时，更新：
  - `current_step` = `Step 6`
  - `next_action` = 一有完成通知就立刻写 timing.json
- 每个子任务一结束，就立刻把 `total_tokens` 和 `duration_ms` 写进该 run 的 `timing.json`。这个信息很容易错过，晚了就没了。

## Step 7：给每轮 run 做基础 grading

- 进入这一步时，更新：
  - `current_step` = `Step 7`
  - `next_action` = 用 grader 或脚本化检查给每轮结果打基础分
- 这里用 `<skill-base>/agents/grader.md`。
- 如果有正式评估计划，调用 grader 时把计划路径或关键维度一起传进去。

grader 应该：

- 读 transcript 和 outputs
- 给每条 expectation 判定并附证据
- 顺手指出那些会制造虚假信心的弱断言
- 如果正式评估计划里的关键维度还没被当前 eval 覆盖，要在反馈里点出来
- 把结果保存成 `grading.json`

能脚本化检查的地方，优先脚本化，而不是肉眼猜。

## Step 8：需要选赢家时做 blind comparison

- 进入这一步时，更新：
  - `current_step` = `Step 8`
  - `next_action` = 用盲评比较输出，尤其是强主观维度和同类 skill 横向比较
- 这里用 `<skill-base>/agents/comparator.md`。
- 只要这次比较里存在强主观维度，或者要比较同类 skill 谁更强，默认优先 blind comparison。
- 如果有正式评估计划，调用 comparator 时把它一起传进去，不要让 comparator 临场重发明评分标准。
- 如果是三个 skill：
  - 可以按已确认计划做成对盲评
  - 也可以固定一套 round-robin 对比
  - 不要中途改维度或改权重

## Step 9：聚合 benchmark

- 进入这一步时，更新：
  - `current_step` = `Step 9`
  - `next_action` = 聚合通过率、耗时、Token 等对比数据
- 在 `<skill-base>` 下执行：

```bash
<python-cmd> "<skill-base>/scripts/aggregate_benchmark.py" <workspace>/iteration-N --skill-name <name> --skill-path <path-to-skill> --eval-plan <path-to-skill>/evals/eval-plan.json
```

- 它会输出通过率、耗时、Token 数等聚合数据。
- 默认会硬拦截：如果还没找到 `evals/eval-plan.json`，脚本会直接失败；只有在兼容旧 benchmark 时，才允许显式加 `--allow-missing-eval-plan`。
- 默认还会硬校验：如果某道题没标维度、标了计划里没有的维度，或者正式评估计划里的主维度还没被任何题覆盖，脚本也会直接失败。
- 如果这次是 `peer-vs-peer` 或三方对比，聚合结果和 markdown 汇总会把所有配置都展示出来，不再只看前两个。
- 如果你需要 schema 细节，读 `<skill-base>/references/schemas.md`。

## Step 10：硬性生成双 HTML 产物

- 进入这一步时，更新：
  - `current_step` = `Step 10`
  - `next_action` = 生成 review.html 和 report.html，两份都落地后才算这次正式评估完成
- 正式评估的硬标准不是“口头讲完了”，而是这次结果最终一定有两份 HTML：
  - `review.html`：基础版证据工作台，这条线不要改味
  - `report.html`：给用户看的完整报告，要把计划、案例、提示词、回答、评分和结论串起来
- 默认不要手工拼装两份 HTML；直接用统一脚本一次性生成。

典型命令：

```bash
<python-cmd> "<skill-base>/scripts/generate_eval_artifacts.py" <workspace>/iteration-N --skill-name "<name>" --benchmark <workspace>/iteration-N/benchmark.json --eval-plan <path-to-skill>/evals/eval-plan.json
```

- 如果是第 2 轮以后，还要带上 `--previous-workspace <workspace>/iteration-(N-1)`。
- 统一脚本会同时调用：
  - `generate_review.py` 生成 `review.html`
  - `generate_report.py` 生成 `report.html`
- 就算有人直接单独跑 `generate_review.py --static ...` 或 `generate_report.py --output ...`，脚本也会默认自动补齐另一份 companion HTML；如果补不齐，会直接报错并回滚刚写出的单份文件。
- 默认会硬拦截：如果 benchmark 或命令里都拿不到正式评估计划，双产物生成会直接失败；只有在兼容旧结果时，才允许显式加 `--allow-missing-eval-plan`。
- 如果缺任意一个文件，就不算这次正式评估完成，也不能对用户声称“评估已经做完”。
- `review.html` 会继续把这次的主方向、次方向、不看项、结论必须包含什么、维度覆盖和题目映射带出来。
- `report.html` 还要进一步把下面这些内容铺给用户看：
  - 本次正式评估计划
  - 测评维度和不看项
  - 案例数量
  - 每个案例的提示词
  - 每个对象在每个案例里的回答
  - 每轮评分细项、证据和补充说明
  - 综合评分与最终结论

## Step 11：让人按已对齐标准读 review + report

- 进入这一步时，更新：
  - `current_step` = `Step 11`
  - `next_action` = 引导用户先看 report 抓主线，再回 review 查底层证据
- 因为有些判断天然带主观性，所以这一步不能只看一句“谁更好”，要同时看完整版报告和底层证据台。
- 让用户重点看：
  - `report.html` 里的正式评估计划、案例提示词、各对象回答、综合评分和最终结论
  - `review.html` 里的 prompt、输出文件、上一轮输出（如果有）、formal grades、blind comparison 理由和 feedback 区域
- 如果用户看完之后改变了评判标准，不要直接继续下一轮；先回 `<skill-base>/references/eval-planning.md` 重新对齐。

## Step 12：只改真正该存在的东西

- 进入这一步时，更新：
  - `current_step` = `Step 12`
  - `next_action` = 根据反馈抽象共性，修改真正该存在的结构
- 根据 review 去改 skill 时：
  - 从反馈里抽象共性，不要只对一个 prompt 过拟合
  - transcript 里如果出现明显浪费工时的行为，就把诱发这些行为的说明删掉或重写
  - 如果多个 eval 都在重复造同一种 helper script，就应该把它正式收进 `scripts/`
  - 继续保持 body 精简；一旦膨胀，就把细节移回 references/assets
  - 如果某个 skill 的默认产物本来就该很短，下一轮要专门检查“是否出现了不必要的 body/解释/多方案”，并把这类失败纳入 eval

## Step 13：继续，或者停下

- 进入这一步时，更新：
  - `current_step` = `Step 13`
  - `next_action` = 判断是否继续下一轮评测，还是及时停下
- 只有在循环还带来清晰收益时，才继续迭代。
- 只有双 HTML 已经落地之后，才谈得上“这一轮评估先停在这里”。

满足下面任一条，就可以停：

- 用户已经满意
- feedback 只剩轻微问题或空白
- 新增复杂度已经不再换来明显提升

- 如果还要继续下一轮，并且当前路径仍然是 `评估`，回到这份文档的 Step 1。
- 如果用户下一步要改的是评估标准本身，回 `<skill-base>/references/eval-planning.md`。
- 如果用户下一步要做的是触发优化、环境适配或打包交付，回主 `SKILL.md` 的 Step 1 重新判路。

## 相关文件

- 前置对齐：`<skill-base>/references/eval-planning.md`
- schema：`<skill-base>/references/schemas.md`
- grader 指南：`<skill-base>/agents/grader.md`
- 如果要做 blind 对比：
  - `<skill-base>/agents/comparator.md`
  - `<skill-base>/agents/analyzer.md`

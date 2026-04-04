# 运行环境说明：Cowork

当这个 skill 运行在 Cowork 或其他 headless 多代理环境时，读这份文档。

默认把 `<skill-base>` 理解为当前 skill 的 `SKILL.md` 所在目录。

- 进入这份文档时，沿用主 `SKILL.md` 已经判定好的 `current_path`；这份文档只负责环境适配，不重写主路径。
- 执行过程中始终显式维护：`current_step` 和 `next_action`。
- 每次进入新步骤，或准备依赖多代理、静态 review artifact、反馈回传这类能力前，先复述：
  - 当前路径：沿用主流程
  - 当前步骤：`Step N`
  - 下一动作：一句话
- 如果任务已经不只是环境适配，而是回到了“评估 / 优化 / 打包”的主路径判断，回主 `SKILL.md` 的 Step 1 再决定走哪条 reference。

## Step 1：先确认 Cowork 里哪些高阶能力可用

- 进入这一步时，更新：
  - `current_step` = `Step 1`
  - `next_action` = 先确认多代理、headless review、文件回传是否可用
- 主流程仍然成立。
- 并行子代理、baseline runs、grading、packaging 通常都可用。
- 先确认有没有浏览器显示能力；很多后续选择都取决于这个。

## Step 2：保留多代理评测，但接受必要降级

- 进入这一步时，更新：
  - `current_step` = `Step 2`
  - `next_action` = 尽量保留并行评测，但避免因为超时把主循环拖崩
- 如果子代理超时非常严重，可以退化成串行跑，而不是把整个评测循环弄崩。
- 只要环境扛得住，with-skill / baseline / grading 这些链路都尽量保留。
- 如果要跑完整评测主线，回 `<skill-base>/references/eval-loop.md`。

## Step 3：把 review 结果优先做成静态工件

- 进入这一步时，更新：
  - `current_step` = `Step 3`
  - `next_action` = 生成用户可打开的静态 review artifact
- 如果环境没有浏览器显示能力，review 结果应优先生成静态工件。
- 保留 review artifact 这一步，不要自己临时写一套 boutique HTML 替代。
- 反馈可能不是实时提交，而是下载文件再回传。

## Step 4：把 trigger 优化放到后面

- 进入这一步时，更新：
  - `current_step` = `Step 4`
  - `next_action` = 判断 trigger 优化是不是已经值得做
- 触发优化是重路径，等 skill 本体已经成型再做。
- 如果当前还在修结构、修输出质量、修 review 流程，不要过早进入 description 优化。
- 如果真的要进这条路径，回 `<skill-base>/references/description-optimization.md`。

## Step 5：保留打包交付路径

- 进入这一步时，更新：
  - `current_step` = `Step 5`
  - `next_action` = 在 Cowork 里完成交付所需的最后动作
- packaging 通常可用。
- 如果要进入完整交付路径，回 `<skill-base>/references/package-and-present.md`。

## Step 6：完成环境适配后，回主线继续

- 进入这一步时，更新：
  - `current_step` = `Step 6`
  - `next_action` = 说明 Cowork 下保留了什么、降级了什么，然后回主线继续
- 汇报时要说明：
  - 哪些主流程能力照常可用
  - 哪些地方因为 headless / timeout 做了降级
  - review artifact 和 feedback 是怎么流转的
  - 为什么这套选择比硬套默认环境更稳

## 索引

- 如果上下文变长、刚看完一大段多代理日志、或需要重新找回方向，先复述：
  - `current_path`
  - `current_step`
  - `next_action`
- 然后按当前路径直达对应材料：
  - Cowork 适配主线：留在这份文档，继续当前 Step
  - 普通输出评测：回主 `SKILL.md` 的 Step 1，再看 `<skill-base>/references/eval-loop.md`
  - 触发描述优化：回主 `SKILL.md` 的 Step 1，再看 `<skill-base>/references/description-optimization.md`
  - 打包交付：回主 `SKILL.md` 的 Step 1，再看 `<skill-base>/references/package-and-present.md`
- 这个索引只用来快速恢复上下文，不替代上面的 Step 1 到 Step 6。

# OpenAI YAML 速查

当目标 skill 真的需要 `agents/openai.yaml` 时，读这份短参考。

默认把 `<skill-base>` 理解为当前 skill 的 `SKILL.md` 所在目录。

## 什么时候才需要

- 只有目标交付环境明确需要 OpenAI 界面元数据时，才创建。
- 如果只是本地使用、普通打包、或当前任务根本不涉及界面展示，就不要顺手加。

## 当前生成器支持什么

当前 `<python-cmd> "<skill-base>/scripts/generate_openai_yaml.py" <skill-dir>` 只会生成 `interface:` 段，支持这些字段：

- `display_name`
- `short_description`
- `default_prompt`
- `brand_color`
- `icon_small`
- `icon_large`

不在这份列表里的字段，不要假设当前脚本会帮你写。

## 默认值优先级

字段来源按这个优先级覆盖：

1. CLI 传入的 `--interface key=value`
2. `<skill-base>/config.yaml` 里的 `openai_yaml.interface_defaults`
3. 脚本自动生成的默认值

其中：

- `display_name`：会根据 skill 名自动格式化
- `short_description`：会自动生成，但必须满足 25-64 字符
- 其他可选字段：没有值就不写进最终文件

## 推荐约束

- 所有字符串都加引号
- 路径写成相对 skill 目录的路径，例如 `./assets/logo.svg`
- `short_description` 保持短、可扫描，不要写成长说明书
- `default_prompt` 如果要写，优先用一句短示例，并显式提到 `$skill-name`
- 图标和品牌色只有在用户明确提供或确实需要时才加

## 最小示例

```yaml
interface:
  display_name: "Skill Creator"
  short_description: "Create or update a skill"
  default_prompt: "Use $skill-creator to create a new reusable skill."
```

## 典型命令

只用自动默认值：

```bash
<python-cmd> "<skill-base>/scripts/generate_openai_yaml.py" <skill-dir>
```

覆盖部分字段：

```bash
<python-cmd> "<skill-base>/scripts/generate_openai_yaml.py" <skill-dir> --interface display_name="Skill Creator" --interface short_description="Create or update a skill"
```

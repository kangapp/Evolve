# Evolve

面向 Codex 和 Claude Code 的项目工作流插件。让 AI 理解项目、规划并完成开发任务，在换会话后继续已有工作。

Evolve 将方案、代码修改、检查、项目知识和工作进度保存在项目中。你可以从一次小修复开始，也可以拆分复杂需求、调查 SQL 和数据口径，或只检查已有修改。

## 安装

需要 Python 3.11+、Git，以及 Codex 或 Claude Code。运行时使用 Python 标准库，无需安装 Python 依赖。

先获取源码并构建完整插件。以下两个目录应尚不存在，也可以换成自己的稳定路径：

```bash
mkdir -p "$HOME/.local/share"
git clone https://github.com/kangapp/Evolve.git "$HOME/.local/share/evolve-source"
python3 "$HOME/.local/share/evolve-source/scripts/build_package.py" --out "$HOME/.local/share/evolve"
```

<details>
<summary><strong>Codex</strong></summary>

```bash
codex plugin marketplace add "$HOME/.local/share/evolve"
codex plugin add evolve@evolve-local
```

安装会默认在用户级启用插件。若仅在当前项目使用，将用户配置 `~/.codex/config.toml` 中已有的插件配置改为：

```toml
[plugins."evolve@evolve-local"]
enabled = false
```

再在目标项目的 `.codex/config.toml` 中添加或合并：

```toml
[plugins."evolve@evolve-local"]
enabled = true
```

在 Codex 中打开并信任目标项目，开始新会话。保留配置中的其他内容。

</details>

<details>
<summary><strong>Claude Code</strong></summary>

在目标项目目录运行：

```bash
claude plugin marketplace add "$HOME/.local/share/evolve" --scope project
claude plugin install evolve@evolve-local --scope project
```

按提示重启会话，插件仅在该项目启用。

</details>

保留完整安装目录。八个 Skill 共用 `shared/` 和 `runtime/`，请整体安装。更新、禁用和卸载见[安装指南](docs/installation.md)。

## 开始第一个任务

不确定从哪里开始时，直接说：“使用 Evolve，我想给这个项目增加 X，先判断应该怎样开始。”`evolve-workflow` 会结合项目是否接入、已有工作和执行条件给出引导。只问用法时保持只读；空项目先明确目标与最小验收行为，已有项目按实际缺口调查。

在目标项目向 AI 发送：

```text
使用 Evolve 接入这个项目，说明主要模块、检查入口和当前约束，暂不修改业务文件。
```

AI 会查看项目，并建立配置和工作记录。已有源码、测试和说明文件会保留；项目知识的正式建立或修改会先展示内容供你确认。

然后提出一个明确的修改：

```text
使用 Evolve 修复总计计算错误，先展示简短方案，按我确认的范围实施，
保留已有测试，完成检查、审查和验收后封存。
```

Evolve 会保存方案、修改范围、实际检查结果和完成状态。复杂需求会先形成完整方案及有依赖的任务清单，再按确认的范围推进。

进入和切换流程会显示 `[Evolve · Skill · 阶段]`。收尾说明本阶段状态、整体剩余事项、接手 Skill 和一条可直接发送的指令。完整授权内连续推进；只规划、只验收或暂停请求在相应阶段结束。

## 日常工作流程

**理解项目 → 形成方案 → 实施 → 检查与审查 → 保存成果 → 继续下一项工作**

你可以请求完整流程，也可以只做其中一步：

| 你的目标 | 可以这样说 |
|---|---|
| 了解项目 | “使用 Evolve 梳理这个项目，说明入口、模块职责和主要约束。” |
| 规划功能 | “先为这个需求形成方案和任务清单，等我确认后实施。” |
| 排查异常 | “只调查这次金额异常，保存结论和下一步方案，暂不修复。” |
| 检查修改 | “只验收这次修改是否满足要求，暂不修改源码或测试。” |
| 开发 SQL | “修复这份 SQL，按指定日期和业务口径对账，保留独立预期。” |
| 整理知识 | “提出术语文档的具体修改，展示差异，确认后应用。” |
| 暂停工作 | “保存当前部分结果和剩余事项，检查和验收下次继续。” |
| 换会话继续 | “使用 Evolve 继续上次的报告任务，先核对当前代码变化。” |

换会话后，Evolve 从项目记录恢复方案、进度和下一步，并核对当前文件。多个工作项并存时，可以指定标题；详细示例见[使用指南](docs/usage.md)。

## 能力与 Skill

通常从 `evolve-workflow` 开始，AI 会按目标选择负责的 Skill。宿主可能显示带命名空间的名称，如 `evolve:evolve-workflow`；按实际入口使用，也可以直接用自然语言请求。

| Skill | 职责 |
|---|---|
| [evolve-workflow](skills/evolve-workflow/SKILL.md) | 定位工作、查看状态、选择下一步和跨会话续接 |
| [evolve-init](skills/evolve-init/SKILL.md) | 接入项目，配置检查与初次知识基线 |
| [evolve-propose](skills/evolve-propose/SKILL.md) | 调查问题、形成方案、拆分任务和修订需求 |
| [evolve-apply](skills/evolve-apply/SKILL.md) | 按已接受方案实施，运行检查并保存部分进度 |
| [evolve-verify](skills/evolve-verify/SKILL.md) | 检查完成条件，进行规格与规范审查，记录当前验收结果 |
| [evolve-archive](skills/evolve-archive/SKILL.md) | 封存成果，审阅和应用具体批准的项目知识 |
| [evolve-learn](skills/evolve-learn/SKILL.md) | 保存、检索和核对项目内经验，提出规则改进 |
| [evolve-maintain](skills/evolve-maintain/SKILL.md) | 诊断、导出、取消、备份、恢复与升级档案 |

## 工作资料和边界

目标项目的 `evolve/` 保存配置和工作历史，`.evolve-local/` 保存本机日志、保护备份和导出内容。插件安装目录与这些资料分开。源码或正式文档的修改按具体授权执行；只调查或只验收的请求保持相应边界。

SQL 开发可以使用普通任务流程。数据写入目前限可固定的同步 Python／SQLite 机制，执行前需要具体目标、范围和候选批准。恢复工作档案保留当前业务文件和外部数据，不承担业务数据回滚。环境前提和升级路径见[兼容说明](docs/compatibility.md)。

## 文档

- [安装与更新](docs/installation.md)
- [使用指南](docs/usage.md)与[复杂任务及数据工作](docs/workflows.md)
- [排错与恢复](docs/troubleshooting.md)
- [开发指南](docs/development.md)、[架构](docs/architecture.md)与[工程目录](docs/project-layout.md)

## 许可

当前权利与分发条件见 [LICENSE](LICENSE)，来源声明见 [NOTICE](NOTICE.md)。

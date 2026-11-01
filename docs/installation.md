# 安装与更新

Evolve 支持 Codex 和 Claude Code，需要 Python 3.11+ 与 Git。运行时只使用 Python 标准库。

## 构建完整插件

选择两个尚不存在的目录，分别保存源码和实际安装包：

```bash
mkdir -p "$HOME/.local/share"
git clone https://github.com/kangapp/Evolve.git "$HOME/.local/share/evolve-source"
python3 "$HOME/.local/share/evolve-source/scripts/build_package.py" --out "$HOME/.local/share/evolve"
```

可以替换为自己的路径。构建目标已存在时会停止并保留原目录；更新请使用新目录。

安装包包含八个 Skill、共享协议、Python 内核、模板、宿主清单和离线指南。保留整个安装目录：宿主可以从本地市场根直接加载资源，其缓存路径不一定是实际加载根。只读诊断中的 `package_root` 给出实际资源位置。

## Codex

```bash
codex plugin marketplace add "$HOME/.local/share/evolve"
codex plugin add evolve@evolve-local
codex plugin list
```

安装会在用户级启用插件。要限定在目标项目，将用户配置 `~/.codex/config.toml` 中该插件已有的 `enabled` 改为 `false`：

```toml
[plugins."evolve@evolve-local"]
enabled = false
```

在目标项目的 `.codex/config.toml` 中添加或合并：

```toml
[plugins."evolve@evolve-local"]
enabled = true
```

保留其他配置，避免重复添加同名表。在 Codex 中打开并信任目标项目，开始新会话。应能发现 `evolve:evolve-workflow` 等八个 Skill。

## Claude Code

在目标项目目录运行：

```bash
claude plugin marketplace add "$HOME/.local/share/evolve" --scope project
claude plugin install evolve@evolve-local --scope project
claude plugin list --json
```

按提示重启会话。入口带插件命名空间，例如 `/evolve:evolve-workflow`；也可以在对话中直接请求使用 Evolve。

## 第一次接入项目

先说“使用 Evolve 查看当前项目状态，暂不修改文件”。项目尚未接入时，状态为 `not_connected`。随后说：

```text
使用 Evolve 接入项目，识别主要模块和检查入口，保留已有文件。
```

接入建立 `evolve/` 和 `.evolve-local/` 等工作资料并保存检查配置。配置检查时不会执行这些命令；初次正式知识会先展示具体正文供你确认。后续工作见[使用指南](usage.md)。

也可以直接检查安装包能否运行：

```bash
python3 "$HOME/.local/share/evolve/runtime/evolve.py" --project /absolute/path/my-project status
```

将目标项目路径替换为自己的路径。未接入时，这条命令保持项目文件不变。

## 更新

更新分别核对插件安装、会话激活、档案兼容和后续执行条件。可以直接请求：“使用 Evolve 更新插件，保留旧包、项目历史和原启用范围；更新后说明实际加载情况与继续入口。”AI 沿[更新流程](../shared/plugin-update.md)准备和执行。普通接入保持原档案，不隐式迁移。

先结束或核实正在执行的工作，保留旧完整包和项目资料。使用旧包处理未完成的文件日志或数据操作，再更新源码：

```bash
git -C "$HOME/.local/share/evolve-source" pull --ff-only
python3 "$HOME/.local/share/evolve-source/scripts/build_package.py" --out "$HOME/.local/share/evolve-next"
```

`evolve-next` 应尚不存在。将旧安装目录保存在另一个位置，再将新完整目录放到原稳定路径；保持每个安装目录的版本一致。

切换前可用新包做只读检查：

```bash
python3 "$HOME/.local/share/evolve-next/runtime/evolve.py" --project /absolute/path/my-project maintain --method doctor --candidate-package "$HOME/.local/share/evolve-next"
```

该步骤核对候选资源和档案兼容，返回 update_check；安装、会话激活与档案迁移均分别标明尚未执行。可读旧协议或损坏档案的诊断保持只读。

Codex 通过重新安装刷新插件：

```bash
codex plugin remove evolve@evolve-local
codex plugin add evolve@evolve-local
```

重新安装后核对用户级 `enabled=false` 和项目级 `enabled=true`。

Claude Code 在目标项目更新：

```bash
claude plugin marketplace update evolve-local
claude plugin update evolve@evolve-local --scope project
```

重启会话，核对八个 Skill、诊断中的版本、摘要和实际资源根。新会话从实际 Skill 路径读取清单，后续 CLI 传 --session-package-digest；旧会话与新包摘要不匹配时停止写入并提示换会话。未核实加载时报告尚未激活。插件更新与档案升级分别处理，支持路径见[兼容说明](compatibility.md)。

接手时可发送：“使用 Evolve 核对更新后的实际版本、项目档案与执行条件，再恢复‘原工作标题’。”若安装或迁移失败，保留回执与旧包，按已发生的步骤处理；迁移后的回退需核对兼容关系与新历史。

## 禁用与卸载

Codex 临时禁用时，将项目插件配置设为 `enabled=false`，用户级保持 `false`。卸载运行：

```bash
codex plugin remove evolve@evolve-local
```

Claude Code 从目标项目按需选择：

```bash
claude plugin disable evolve@evolve-local --scope project
claude plugin enable evolve@evolve-local --scope project
claude plugin uninstall evolve@evolve-local --scope project
```

保留目标项目的 `evolve/`、`.evolve-local/`、业务文件和映射文档，重装后可读取原项目历史。禁用或卸载不会终止已经启动的业务进程；先核实进行中的操作。

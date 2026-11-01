# 安装与项目启用

本指南对应完整包0.1.0。Python需要3.11+；无需安装Python依赖。当前实际宿主为Codex CLI 0.154.0、Claude Code 2.1.117，其他版本以本机帮助及实际能力为准。

## 获取并保留完整目录

从源码工程根执行：

```bash
python3 scripts/build_package.py --out /absolute/path/evolve-installed
```

替换为自己的绝对路径，目标目录须不存在。拿到完整运行包时，将整个目录放到稳定安装位置；不要只复制Skill。根目录包含两个宿主清单、八Skill、shared、runtime、模板和本版本指南，清单为evolve-package.json。

下文使用 `/absolute/path/evolve-installed` 作为稳定安装根。它属于本地安装内容，注册后需要保留。原始下载副本可以移走。Claude本地目录市场会原位加载相对路径插件；`plugin list` 中的独立缓存不代表实际Skill从缓存运行。用宿主显示的Skill Base directory和doctor的package_root核对，不删除真实加载根。

## Codex

```bash
codex plugin marketplace add /absolute/path/evolve-installed
codex plugin add evolve@evolve-local
codex plugin list
```

本机 `plugin add` 会将用户配置中的插件设为enabled=true。安装后先将用户配置（默认 `~/.codex/config.toml`）中该插件的enabled改为false，再仅在目标项目的 `.codex/config.toml` 中设置：

```toml
[plugins."evolve@evolve-local"]
enabled = true
```

目标项目还需被宿主信任。不要覆盖其他配置。实际发现名称为 `evolve:evolve-workflow` 等八个Skill；按宿主显示名称使用，不依赖全局命令。自动化安装验收只使用临时隔离配置；它没有替你修改个人设置。

## Claude Code

从目标项目运行：

```bash
claude plugin marketplace add /absolute/path/evolve-installed --scope project
claude plugin install evolve@evolve-local --scope project
claude plugin list --json
```

启用限定在当前项目。入口按插件命名空间展示，例如 `/evolve:evolve-workflow`。临时调试可用 `claude --plugin-dir /absolute/path/evolve-installed`，但临时加载不代替完整市场安装验证。

## 确认安装和首次接入

在目标项目向AI表达“使用Evolve只读查看当前状态”。也可以直接运行：

```bash
python3 /absolute/path/evolve-installed/runtime/evolve.py --project /absolute/path/my-project status
```

安装成功但项目尚未接入时应显示 `data.project.state=not_connected`（history 对应 `data.history.project.state`），不能因此自动建库。请AI按实际指令执行init，展示将建立的配置及检查入口；这只创建 `evolve/` 和 `.evolve-local/` 等记录设施，不批准项目知识或修改业务代码。已有项目应保留原身份和历史；身份冲突、缺资源或不兼容时先[排错](troubleshooting.md)。

## 更新、禁用和卸载

更新前让原执行安全结束，保留旧完整包和项目资料。未决文件日志、数据操作或检查先用原包核对。将完整新版放到稳定安装根，不逐文件混换；新会话用doctor核对真实根、版本和摘要。安装更新不迁移档案、不重放旧请求或扩大授权，支持路径见[兼容说明](compatibility.md)。

Codex当前没有plugin update子命令，使用本机支持的重新安装路径：

```bash
codex plugin remove evolve@evolve-local
codex plugin add evolve@evolve-local
codex plugin list
```

重新add后，再按上文关闭用户级enabled，只在所需项目启用。临时禁用将项目enabled设为false，用户级维持false。卸载用remove；不删除目标项目的Evolve资料。

Claude从目标项目更新：

```bash
claude plugin marketplace update evolve-local
claude plugin update evolve@evolve-local --scope project
```

按宿主提示重启。禁用、重新启用和卸载：

```bash
claude plugin disable evolve@evolve-local --scope project
claude plugin enable evolve@evolve-local --scope project
claude plugin uninstall evolve@evolve-local --scope project
```

重装按首次install步骤；保留项目 `evolve/`、`.evolve-local/`、映射文档和业务文件，status应显示原身份／历史。禁用或卸载不证明旧进程或外部操作已停止；删除项目资料需要另一个明确请求。

<!-- source-only -->
实际安装、发现、目录移动、生命周期和模型执行的范围分别记录在[实施与验收](implementation.md)；宿主发现不冒充业务或模型通过。
<!-- /source-only -->

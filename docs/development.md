# 开发指南

Evolve 运行时使用 Python 3.11+ 标准库。先读[架构](architecture.md)了解模块职责，实际路径见[工程目录](project-layout.md)。

## 本地检查

在源码根运行：

```bash
python3 -B scripts/build_package.py --check
python3 -B scripts/project_inventory.py --check
python3 -B scripts/check_docs.py
python3 -B -m unittest discover -s tests -v
```

文档检查覆盖本地链接、锚点与 JSON／TOML 示例。行为回归使用临时文件、SQLite 和真实子进程，覆盖检查、冲突、中断、恢复及旧写入器兼容；不会调用模型或修改个人宿主配置。旧完整包夹具在 `tests/fixtures/`，其用途和摘要见该目录的说明。

修改时先保留能复现问题的用例，做局部修复，再运行受影响检查。共享执行、保护或恢复逻辑变更后运行全量回归。

## 更新资源清单

README、Skill、shared、runtime 和离线指南属于运行资源。资源变化后依次运行：

```bash
python3 -B scripts/build_package.py
python3 -B scripts/project_inventory.py --write
python3 -B scripts/build_package.py
python3 -B scripts/project_inventory.py --write
python3 -B scripts/build_package.py --check
python3 -B scripts/project_inventory.py --check
python3 -B scripts/check_docs.py
```

首次生成包文件集合后更新目录，再刷新目录对应的资源摘要。`engineering-file-manifest.json`描述维护工程，`evolve-package.json`描述运行资源，两者用途不同。

## 构建独立运行包

```bash
python3 -B scripts/build_package.py --out /absolute/path/new-evolve-package
```

目标目录应不存在，构建不会覆盖旧包。运行包包含八个 Skill、单份 shared／runtime、模板、宿主清单和离线指南，源码 tests、开发脚本和目标项目资料保留在源码工程。标记为 source-only 的开发导航只在源码显示。

包清单固定资源摘要，Python 文件构建前检查语法。完整包可以离线定位资源，从不同工作目录运行，并整体移动；使用者按[安装指南](installation.md)注册到宿主。

## 安装与流程检查

以下工具各自创建临时项目和隔离配置，`--out` 指定尚不存在的目录：

```bash
python3 -B scripts/verify_hosts.py --out /absolute/path/host-lab --workflow --continuation
python3 -B scripts/verify_lifecycle.py --out /absolute/path/lifecycle-lab
python3 -B scripts/external_smoke.py --package /absolute/path/new-evolve-package --out /absolute/path/data-lab
```

它们分别检查宿主安装／发现及公开 CLI 流程、生命周期和受控 SQLite 数据操作，不调用模型。流程中的审查输入是明确的受控测试观察。

模型测试工具另有 `--preflight-only`，用于先核对固定模型、文件、动作与副作用范围；真实派发按具体授权执行，遇到权限、额度或传输失败立即停对应批次。输出保存在指定临时目录，避免进入源码仓库。

`scripts/model_project_knowledge_acceptance.py` 覆盖六个新会话的知识初始化、必要文档交付、主题迁入与受限事实维护。与其他模型工具一样，先预检并绑定准确范围及已有用户授权；实际 Mermaid 渲染由环境变量 `EVOLVE_ACCEPTANCE_MMDC` 指定宿主 `mmdc`，使用已安装 Chrome，不是插件运行依赖。控制器保留原 CLI 回执、渲染结果、模型轨迹和独立断言，自动检查后仍需审阅正文及实际图文。

## 维护约定

动作归属由 `runtime/evolve_core/package.py`维护，领域模块实现对应协议。检查和长命令在短事务之外执行；未知数据效果与本地提交状态分别保存。协议或 schema 变化需要保留旧包拒绝和显式升级回归，安装／接入不代替迁移。

插件版本、两个宿主清单与 CHANGELOG 同步更新。代码审查应说明行为、范围、实际检查和剩余限制。许可见 [LICENSE](../LICENSE)。

<!-- source-only -->
工程规范见 [AGENTS](../AGENTS.md)。
<!-- /source-only -->

`scripts/model_workflow_acceptance.py` 的 work 旅程覆盖六个新会话：指南咨询、只规划、正常暂停、续接封存、只读诊断和受控修复。update 旅程通过隔离宿主原生命令安装真实 0.2.0 包、建立旧知识，再更新至当前包，以两个新会话核对和完成修改。用 --journey work／update 及 --preflight-only 读取准确范围；真实派发绑定该范围摘要和已有用户授权。完整自动检查后审阅实际可见标记、完成范围、接手指令及原始执行轨迹。

# Evolve 工程约定

回复使用中文。Evolve 是面向 Codex 与 Claude Code 的项目工作流插件；从 [README](README.md)了解当前能力，从[开发指南](docs/development.md)查看构建和检查方式。

## 修改原则

- 先读实际代码和相关文档，说明假设与可验证目标；未明确要求修改时先调查和给方案。
- 简单工作使用简短方案，复杂工作先说明范围、完成条件和有依赖的任务；已有授权在原范围内继续。
- 只修改需求涉及的部分，保留用户及其他工具的改动；实质范围或关键选择变化时核对原授权。
- 正式项目知识先展示具体候选及差异，按具体决定应用。候选经验用于调查，不能代替正式规则、验收条件或修改授权。
- 测试、安装和故障演练使用临时项目及隔离宿主配置。实际权限、额度或传输失败停止对应执行并保留结果；观察工具超时先检查原进程。
- 提交、推送、公开发布、部署及真实环境数据写入按用户明确请求执行。凭证留在环境或宿主凭证设施中。

## 代码与文档

- 八个 Skill 共用 `shared/` 与 `runtime/`。动作归属由 `runtime/evolve_core/package.py` 维护，Skill 按负责分支加载共享协议。
- 用户文档说明当前行为、操作步骤和必要限制。开发资料说明维护方式；原始执行日志与临时项目放在仓库外。
- 代码变更运行相关行为回归；共享执行或恢复语义变更运行全量测试。文档／打包变更检查引用、资源清单及受影响的安装路径。
- 资源变更后更新包清单和工程目录，再运行 `scripts/build_package.py --check`、`scripts/project_inventory.py --check` 和 `scripts/check_docs.py`。
- 插件版本、宿主清单及 CHANGELOG 保持一致；schema／protocol 变化单独核对兼容。普通安装和接入不隐式迁移档案。
- 保留真实失败与历史事实，按实际观察报告结果。只读查询、实施、检查、验收和封存分别处理。

## 按任务阅读

- 安装与项目启用：[installation](docs/installation.md)。
- 用户工作流：[usage](docs/usage.md)及[复杂任务与数据工作](docs/workflows.md)。
- 模块职责、存储和执行保护：[architecture](docs/architecture.md)。
- AI 工具请求及逐动作字段：[共享协议](shared/protocol.md)；分支细节由相应 Skill 指向。
- 版本与升级：[compatibility](docs/compatibility.md)；具体维护步骤见[recovery](shared/recovery.md)。
- 错误和中断：[troubleshooting](docs/troubleshooting.md)。

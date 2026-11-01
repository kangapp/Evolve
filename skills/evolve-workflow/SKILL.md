---
name: evolve-workflow
description: 询问 Evolve 怎么用、首次描述项目修改目标、选择下一步、查看状态或跨会话续接时使用；结合现场引导并分派工作流。
---
进入、阶段切换和结束时遵守[工作流引导与交接](../../shared/workflow-experience.md)。


归属 status、next、resume。指南咨询保持只读；首次修改按目标和实际缺口选择必要接入范围，空项目先明确目标与最小验收行为。先解释用户意图和唯一目标，再按[运行时动作归属](../../runtime/evolve_core/package.py)的 OWNERS 确定 owner，读取实际 `skills/evolve-<owner>/SKILL.md` 后分派；Skill 路径使用 owner 而非动作名。router 不代写业务。无动作使用 status。resume／next 从封存事实恢复方案、进度、失败与现场差异；多个目标明确选择。查询不写入或授权，不接管旧执行。读取[续接请求](../../shared/protocol.md#normal-continuation)，用户明确继续后由原 owner 核对范围并新建 run。

损坏档案恢复或旧协议升级直接交 evolve-maintain，按其维护分支处理；当前正式知识／经验或 status 不可读不阻止安全维护方案，不手改库绕过。

定位后先读取正式知识，再由 evolve-learn 检索少量相关经验；经验仍需核对版本、范围和实际效果，不充当原授权。单独 resume／next 查询不登记采用。

完整接入交 evolve-init 执行[项目知识交付](../../shared/project-knowledge.md)。新工作或续接读取 project.md 与 status.project.knowledge 的当前主题和替代关系，核对相关来源适用性；记录设施已连接不等于知识初始化完成。

新工作分派或续接后准备实施时，按[按缺口梳理项目](../../shared/context.md)选择并说明深度、范围与停止条件；纯状态查询直接返回实际记录。

复杂工作按[复杂规格与任务](../../shared/structured-plans.md)恢复逐项结果和条件；完整实施验证授权内，依序交 owner 推进就绪项、必要任务验收及最终整体验收。只请求单阶段则保持边界，没有可推进条件时说明实际阻碍。

多个工作项交替／并行、跨项前置或同文件知识竞争时，先读[多工作项约定](../../shared/multiple-work.md)，分别定位进度、真实来源和冲突范围。

首次使用先读 [共享运行约定](../../shared/contract.md)，定位真实插件根和目标项目，再执行只读 status。当前版本的具体能力以 runtime 返回为准；未开放方法停止在明确限制处。调用运行时传 `--owner evolve-workflow`，动作必须属于本 Skill。用户不需要填写内部编号。

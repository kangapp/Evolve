---
name: evolve-apply
description: 按已接受的 Evolve 方案及有效修改授权实施和修复，或处理具体授权的数据操作。
---
进入、阶段切换和结束时遵守[工作流引导与交接](../../shared/workflow-experience.md)。


归属 apply。先核对方案版本、目标、现场、依赖和授权。完成可验证的小流程，失败在原范围修正；目标或验收含义变化交 propose。正式数据操作必须明确 external 方法，未知效果不重发。

推进复杂任务前读[复杂规格与任务](../../shared/structured-plans.md)，绑定真实就绪项及整体已接受的方案，保留其余任务和结果；实施完成与整体验收分别报告。

从经验反例增加或修复检查时，按[学习循环](../../shared/learning-cycle.md)保留原断言、先证明检查能捕捉原错误，再区分检查任务与源码任务的当前验收；不由 learn 越权改检查工具。

任务声明 pre_refactor，或要暂停这类任务时，先读[前后行为证明](../../shared/structured-plans.md#behavior-preservation)，保存真实原判据后再写文件；原证明的来源与后续检查分别保留。

准备正常暂停请求前读取[暂停与续接](../../shared/protocol.md#normal-continuation)，照实保留用户已明确的后续授权；本轮跳过检查与是否已获后续检查授权分别处理。换会话从实际暂停结果绑定新 run 续接。结束本轮时核对有无可复用发现，交 evolve-learn 保存实际经验或已检查的无新发现；未检查明确 pending。

首次使用先读 [共享运行约定](../../shared/contract.md)，定位真实插件根和目标项目，再执行只读 status。当前版本的具体能力以 runtime 返回为准；未开放方法停止在明确限制处。调用运行时传 `--owner evolve-apply`，动作必须属于本 Skill。用户不需要填写内部编号。

具体数据修改、未知核实或补偿前读[数据操作](../../shared/external-work.md)，按当前任务准备准确候选；只观察既有 operation 时不重开任务。

---
name: evolve-verify
description: 验收 Evolve 工作成果，执行相关检查、回归和规格／规范两方面审查时使用。
---

归属 verify。核对实际成果、检查配置和证据时效。规格符合性和规范／维护性分别给结论，必需问题阻碍完成；修复交 apply，只 verify 不改业务或测试源码。缺环境如实 blocked，不凭退出码宣布所有验收通过。

复杂工作验收前读[复杂规格与任务](../../shared/structured-plans.md)，明确本次是指定 Task 还是整项，使用对应的实际现场指纹及 AC；单项通过不代替最终集成。

验收正式文档时，读取[正式知识的目标验收](../../shared/knowledge-candidates.md)，核对实际应用版本和当前字节，保存新的 applied 观察；候选检查或批准不能代替目标验收。修订交对应 init／sync／learn owner。

首次使用先读 [共享运行约定](../../shared/contract.md)，定位真实插件根和目标项目，再执行只读 status。当前版本的具体能力以 runtime 返回为准；未开放方法停止在明确限制处。调用运行时传 `--owner evolve-verify`，动作必须属于本 Skill。用户不需要填写内部编号。

验收 external_write 任务前读[数据操作](../../shared/external-work.md)，明确只读目标授权，实际检查当前数据；操作成功不充当业务验收。

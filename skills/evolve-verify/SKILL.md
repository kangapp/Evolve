---
name: evolve-verify
description: 验收 Evolve 工作成果，执行相关检查、回归和规格／规范两方面审查时使用。
---
进入、阶段切换和结束时遵守[工作流引导与交接](../../shared/workflow-experience.md)。


归属 verify。核对实际成果、检查配置和证据时效。规格符合性和规范／维护性分别给结论，必需问题阻碍完成；修复交 apply，只 verify 不改业务或测试源码。缺环境如实 blocked，不凭退出码宣布所有验收通过。

从 next／resume 的 execution.review_subject 取得当前指纹、AC 和审查要求，按[公开准备与工作文档](../../shared/protocol.md#公开准备与工作文档)提供实际 mode、自审或独立来源及逐 AC 的 check_ids。按已接受要求完成独立审查，缺少实际来源保留受阻；同一执行者的不同角色提示仍为自审。未运行的浏览器、HTTP、数据范围明确说明。

核对检查复用或用户要求重新运行时，读取[检查结果复用](../../shared/protocol.md#检查结果复用)，如实区分本次执行和原回执引用；当前语义审查仍实际完成，明确要求重跑的检查填写 fresh_checks。

复杂工作验收前读[复杂规格与任务](../../shared/structured-plans.md)，明确本次是指定 Task 还是整项，使用对应的实际现场指纹及 AC；单项通过不代替最终集成。

验收正式文档时，读取[正式知识的目标验收](../../shared/knowledge-candidates.md)，核对实际应用版本和当前字节，保存新的 applied 观察；候选检查或批准不能代替目标验收。修订交对应 init／sync／learn owner。

分类知识验收同时读[文档检查](../../shared/knowledge-documents.md#增量维护和检查)，观察 structure／sources／consistency／usefulness 及实际业务判据；有图时保存真实渲染与图文核对，源结构通过不冒充渲染通过。实现与规格冲突时保留冲突，不修改要求换取通过。

首次使用先读 [共享运行约定](../../shared/contract.md)，定位真实插件根和目标项目，再执行只读 status。当前版本的具体能力以 runtime 返回为准；未开放方法停止在明确限制处。调用运行时传 `--owner evolve-verify`，动作必须属于本 Skill。用户不需要填写内部编号。

验收 external_write 任务前读[数据操作](../../shared/external-work.md)，明确只读目标授权，实际检查当前数据；操作成功不充当业务验收。

---
name: evolve-propose
description: 为 Evolve 工作形成短方案或复杂 spec、修订方案，或开展不修改业务的独立调查。
---
进入、阶段切换和结束时遵守[工作流引导与交接](../../shared/workflow-experience.md)。


归属 propose、update、analyze。复用当前资料，区分事实、假设和未知。复杂方案给目标、边界、行为、验收和真实任务依赖；调查保存可重复症状判据、来源与限制，不凭分析请求开始修复。

形成方案或调查前，按[按缺口梳理项目](../../shared/context.md)说明选择的深度、理由、范围、未知与停止条件；已有可信背景可复用，复杂度不决定梳理深度。

已登记项目知识的方案，按[知识影响](../../shared/project-knowledge.md#方案中的知识影响)声明 knowledge_impact，区分必需更新、附带建议与保持不变；核对关联来源之外的业务含义影响。旧主题的修订迁入 evolve/ 并登记替代范围，必要文档纳入实际交付及 owner Task。

保存复杂 spec／任务清单或修订既有方案时，先读[复杂规格与任务](../../shared/structured-plans.md)，整体呈现后保存完整文档；必要预重构保留前后判据及只读输入。修订先读该文档的[REV 分支](../../shared/structured-plans.md#revision)，呈现具体变化，再按实际确认登记接受。

正式文档是必需成果时，读取[正式知识交付](../../shared/knowledge-candidates.md)，在方案／Task 声明负责的 init（初次）／sync（规格修订）／learn（规则）动作及实际文档 AC；正式文件经具体批准后由 owner 应用，不安排普通 apply 抢写。

即时解释：读取现场及必要的原检查，用对话说明实际事实、假设、建议和限制即完成此分支，无需构造请求材料。用户明确需要结构化校验结果时，才读取[调查请求](../../shared/protocol.md#analysis-request)的 answer_only 分支，通过标准输入提交；宿主拒绝该输入形式时，以已取得的只读观察直接答复结束。

明确留档调查时，读取[调查请求](../../shared/protocol.md#analysis-request)的 record 字段与证据要求；未接入则先最小 init，仅建立记录设施，调查不创建 Change。工作内排查仅沿仍有效的 parent 执行，已结束后另建独立调查。

调查数据日期／口径、SQL 或对象关系时，先读[数据工作](../../shared/data-work.md)，保存实际对象、日期与来源范围；局部关系保留推断和未知边界。

方案需要另一工作项的前置时，先读[跨项条件](../../shared/multiple-work.md#定位与前置)，在具体复杂 Task 绑定实际目标、版本、条件及依据；不把相关关系当依赖。

首次使用先读 [共享运行约定](../../shared/contract.md)，定位真实插件根和目标项目，再执行只读 status。当前版本的具体能力以 runtime 返回为准；未开放方法停止在明确限制处。调用运行时传 `--owner evolve-propose`，动作必须属于本 Skill。用户不需要填写内部编号。

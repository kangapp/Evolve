# 有来源的正式规则交付

经验要形成正式规则、规则来源变化或出现反例时读取本约定。当前版本的learn.promote 复用[正式知识候选](knowledge-candidates.md)及文件协议；仅处理当前项目 Markdown 规则。检查脚本、CI、hook 或业务代码改进仍交普通 Change／apply／verify，完整顺序见[学习循环](learning-cycle.md)。

## 具体候选与实际来源

先读取实际经验及原工作证据，区分事实、原因假设、适用条件、反例与局限。learn search 返回的 candidate／active 不是正式批准，也不授予修改权限。规则要求 observed 原因及实际留存观察；没有证据的引用、未复核反例、needs_review 或 retired 来源先补齐调查／复审，保留正式正文。

learn.promote.input.stage=propose，给完整候选 path／expected_digest／content／presentation／topic／reason／acceptance，可给 edits、dependencies 和 delivery；目标须已经由 init 登记。另给：

- rule_scope：非空的具体适用范围数组，不从经验标签自动扩大范围。
- rule_sources：非空且不重复的实际来源数组。每项给 experience_ref、最新 state_ref、counterexamples（逐条反馈的 feedback_ref，实际无反例才给空数组）及 basis（说明支持、反对证据和局限对本规则的影响）。引用来自本次实际 search，不重造 run 摘要。

该方法只保存候选，不改经验内容、状态或正式文件。内容／判据／来源状态／范围变化形成后继候选，旧批准不转移。相同被拒正文也不能通过换 owner 绕过；重新考虑沿明确 reconsideration 留依据。

## 决定、应用与任务

用 sync.check 保存具体正文观察，用 sync.review 记录逐项用户决定。必需规则在方案／Task 声明 responsible_action=learn，delivery 绑定实际 Task／AC；附带规则仍可延期。

具体批准且来源仍适用后，learn.promote.input.stage=apply，给准确 proposal 四项引用和 approved_event_id。必需成果另给当前 Change／Task／accepted_plan_digest；授权含 project_records、knowledge 及具体 paths。Learn 是实际文件写入方；同文件其他 owner 的已批准独立差异按[批准链约定](knowledge-patches.md)推进，实际组成正文仍需具名检查。

实际应用在同一事务保存 application、artifact 和 rule_bindings，绑定准确经验／提案、适用范围和实际规则版本。verify 重新检查目标；候选检查或旧批准不充当应用后验收。规则是必需成果时，未实际应用／未验收或当前来源受阻均不能封存。

来源经实际复审后，即使规则正文不变，也可为新的准确依据／范围形成具体候选并经检查、批准后重新关联实际版本；使用新的 delta，保留旧应用，不重放旧批准。正文和实际依据均未变时报告 KNOWLEDGE_NO_CHANGE。

## 反例、查询与恢复

新状态或反例使原来源绑定失效时，待应用候选停止；已应用规则的 status.rule_state 及 knowledge_refs.rule_bindings 标 needs_review，保留原批准、文件和历史验收。新的实际目标验收记录 blocked；原经验仍按原事实保存，不因为已关联规则变成自动授权。后续纠正正文需要新的具体候选，不能自动覆盖正式文件。

查询不写库或补检查。supported_basis 只表示来源绑定当前适用，规则语义仍需实际内容观察；effect_state 只证明声明范围的字节保留。对后续方案和实际检查的影响按[学习循环](learning-cycle.md)复核，各阶段结果按本次实际观察保存。

中断由 maintain recover 核对原实际 journal／批准／来源；尚未写入时门禁仍适用，已经写入的字节只补确定事实。rule_bindings 与实际应用一起提交，恢复不重复分配。未收尾文件日志会阻止其他记录写入，先恢复原操作。版本与升级路径见[兼容说明](../docs/compatibility.md)，不自动迁移。

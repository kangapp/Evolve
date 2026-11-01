# 正式知识候选与审阅

当前版本提供 init.baseline.propose／apply 的结构化初次文档路径，复用 sync.check／review 的具体内容观察与逐项决定；sync.propose／apply 负责后续修订，verify 负责实际目标验收。候选通过、批准、实际应用及应用后验收分别保存。Learn 规则候选／应用由 learn.promote 的明确阶段负责，经验来源、反例或依据变化时先读[规则交付](knowledge-rules.md)。三者共用文件协议及[同文件批准差异](knowledge-patches.md)；外部正式版本或旧待审内容被替代时，读取[采纳与后继约定](knowledge-adoption.md)，保留现场与历史决定。

## 保存具体候选

先展示完整新正文及相对原正式版本的差异，再调用 sync.propose，input 给：

- path：已由 init 登记的正式 Markdown 路径；expected_digest：当前已批准基线的实际摘要。
- content：实际呈现的新正文；presentation={source,text}，text 必须逐字等于 content。
- topic、reason：本次主题及改变的实际依据。
- acceptance：非空数组，各项 {key,text} 给独立、具体的内容检查判据。

首次建立正式文件按下节使用 init.baseline.propose／apply。实际文件偏离已批准版本时，先核对外部编辑和正式含义；普通候选路径报告 KNOWLEDGE_EXTERNAL，保留现场；需要采纳外部全文时按[具体采纳约定](knowledge-adoption.md)另给原正式版本和实际外部观察，不自动登记权威。

同主题／目标的相同候选归并上下文；正文或判据变化生成后继版本，旧全文、检查和决定保留，旧批准不转移。被拒绝的同主题或相同正文需要 reconsideration={proposal_id,proposal_version,source,text,reason}，记录实际新的重新审阅意图；不能仅换标题新建同一被拒内容。工具核对具体身份和正文，语义是否等价仍由实际审阅说明。

返回 proposal_id、proposal_version、candidate_digest、expected_digest。后续统一将这四项作为 proposal 引用，保持实际呈现版本，不在重试时改成当前值。

若正文同步对应实际业务实现，input.implementation_basis={verification_id,purpose} 引用实际通过且已安全收尾的实现验收。与业务 Change 关联的 followup 必须给此依据；应用前重核当前任务定义、实际业务输出、上下文、检查配置及更新的相关失败。纯文档交付用内容判据，不要求尚未落盘的目标先验收通过。

## 初次正式文档

初次候选仍给完整 content、presentation、topic、reason 和非空 acceptance，方法为 init.baseline.propose。path 必须尚未登记为正式知识；新文件的 expected_digest=null 表示实际不存在，已有未登记文件用实际摘要，即使正文不变也可登记。不存在与空文件分别绑定，不能互换。可按差异约定声明 edits。必需交付同时给下述 delivery，Task 的 responsible_action=init。

内容检查及用户决定由 sync.check／review 统一留档，这两个方法只写记录；实际应用仍调用 init.baseline.apply，给准确 proposal 四项引用、approved_event_id，以及必需交付的当前 Change／Task／方案绑定。返回真实 delta／application／artifact，后续应用验收与 sync 相同。

未带内容判据／交付等结构化字段的旧式初次候选仍用原 proposal_id 与具体 approval 路径。结构化候选必须引用已记录决定，旧式内联批准不能降级绕过。两条路径写前均核对正式映射尚未建立；即使其他初次应用没有改变字节，旧候选也不能再作为初次基线覆盖已建立的权威。

## 内容检查与逐项决定

实际检查新正文与每项 acceptance 后，用 sync.check 保存 proposal 和 observations。每项给 criterion_key、status=passed／failed／blocked、observer、basis；覆盖所有判据。这里只登记实际内容观察，不代运行命令或判断文档语义。subject_kind=candidate，证据不充当应用后的实际目标验收。更新的失败／受阻检查覆盖旧通过对后续批准的适用性。

用户已明确接受、拒绝或延期具体候选后，sync.review.input.decisions 逐项给 {proposal,decision,source,text,reason}，decision=approved／rejected／deferred。一次审阅可以对不同候选给不同决定；每项均保留实际用户依据。approved 需要最新匹配版本的内容检查通过且来源安全收尾，目标基线仍匹配。延期可在完成必要检查后按实际决定批准；被替代或拒绝版本保持原决定，重新考虑沿后继候选继续。

status 全局给 knowledge_proposals 导航；按候选编号、UUID 或唯一主题定位可读 base／candidate 全文、判据、原正式版本、旧决定、最新候选检查及实际基线是否匹配。多个版本同主题时按当前候选编号定位。查询不改文件、状态、检查或批准，source_pending 为 true 时先处理原执行收尾。

请求经标准 JSON 协议发送并保存返回绑定。候选、检查或审阅的元数据已提交后进程异常退出，maintain recover 只核实原提交，不重新分配候选、执行检查或应用文件；随后从安全结束的原记录继续。

## 必需文档与附带候选

正式文档为本次成果时，在简单方案或对应复杂 Task 声明 responsible_action=init（初次）、sync（规格修订）或 learn（规则），scope 全部为正式 Markdown 路径；完成条件和 AC 描述实际文档结果，普通 apply 不能登记这些产物。候选 input.delivery 给 role=required、change_id、revision_id、task_id、definition_digest 及实际对应的 acceptance_ids。多个文档可属于同一 Task，只有全部产物形成且覆盖对应 AC 才能完成实施部分。

附带知识用 delivery={role:followup,change_id}，或不与 Change 关联。拒绝／延期不阻碍与其无关的已完成成果；不能将必需文档改称 followup 来满足原 Task。已封存 Change 可继续应用已具体批准的 followup，原 Task／封存截点保持。

## 实际应用与目标验收

对应 owner 的 init.baseline.apply、sync.apply 或 learn.promote（stage=apply），input 给 proposal 四项引用及 approved_event_id；authorization 须含 project_records、knowledge 及目标 paths。必需文档另给 change_id、task_id（复杂工作也可 task_key）和实际接受的 accepted_plan_digest；新 CLI 冻结当前 REV／Task 定义及版本，重试保留返回的完整绑定。第一版方案可据此具体接受，语义 REV 先经 update 精确接受。

应用核对最新候选检查、具体批准、原正式版本和实际目标字节，沿共享文件 journal 写入。同文件前项已应用、需要部分应用或声明具体依赖时，先读[差异与组成约定](knowledge-patches.md)，核对真实链并检查实际组合正文；不以整篇覆盖代替独立差异。返回稳定 delta_id、application_id、真实 artifact 版本；Task 只得到实施产物，overall_verification=not_run。重复请求返回原回执；同 delta 已应用后新请求只报告原事实及 current_matches，不重写文件或恢复过时含义。新修订形成后继 delta，REV 不重放旧应用。

存在 Change 时，用 verify.run 检查实际文件、逐项 AC 和文档规范；复杂 Task 验收与整项验收保持分开。必需文档未应用、来源尚未安全收尾、目标改变或缺应用后适用通过记录时，不能封存。候选检查不能充当此步骤。

不涉及 Change 或需要单独复验实际文档时，用 verify.knowledge，input={application_id,observations}；observations 与候选判据键对应，但依据必须来自本次实际目标阅读。工具重新读取并留存实际字节及 artifact 关联，生成 subject_kind=applied 的新 VER。目标字节改变且缺少已批准的独立差异保留链时 blocked，保留旧 passed 及外部内容；有真实保留链仍需检查本次实际内容，不能沿用旧候选结论。该局部 VER 不替代整个 Change 验收，不运行代码测试或修改目标。

应用中断用 maintain recover：核对原批准、原 journal 和已写事实；未写项只按原有效授权继续，已提交项不重复分配应用或完成 Task。第三种字节保留冲突，恢复不重跑内容检查。alpha.12 使用 protocol v10／schema v4，旧档案保留完整兼容包，不自动迁移或手改版本号。

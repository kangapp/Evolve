# 复杂规格与任务

当前版本提供完整spec／任务清单保存、条件观察、任务实施、预重构前后证明、任务及整体验收与封存。update.revise可用于明确修订，宿主实际验收范围见[兼容说明](../docs/compatibility.md)。只保存提案不代表用户接受或授予修改权限。

需要保存复杂提案时，使用 propose.create，input.complexity=complex。先向用户实际呈现整个文档，再保存 presentation.source 和 presentation.document；document 必须逐项等于以下全部字段组成的对象，不能仅呈现摘要：

- title、plan、completion：目标标题、方案摘要与用户可验证的完成结果。
- scope：明确的业务文件数组；required_checks：已由 init 登记的最终检查 ID 数组。
- acceptance：非空对象数组，每项给稳定局部 key 和行为 text。
- spec：problem 文本；goals、non_goals、behavior、constraints、tradeoffs、test_decisions 字符串数组；open_questions 对象数组，未知问题不存在也显式给空数组。
- tasks：非空任务数组，每项给 local_key、title、completion、validation（独立验证方法）、exclusions（不覆盖范围数组）、scope、acceptance（上层条件 key 数组）、required_checks、context_paths、test_decision_refs、dependencies。

从独立调查转修复时，具体 Task 的 analysis_basis 及单 Task 根级简写按[调查转修复协议](protocol.md)绑定，完整呈现不能省略引用。原症状的 Task 验收及整项完成门槛沿同一协议核对。

每项 Task 对应可验证的用户结果及实际检查方式，所有文件及必需条件都有任务负责。test_decision_refs 引用本次实际呈现的测试决定，例如 spec.test_decisions/0；保存引用及对应内容摘要。context_paths 是实际存在的相关上下文文件；只记录其字节摘要，相关变化使该任务待核查，无关知识追加不阻塞全部任务。返回的 TASK 局部编号带 change_id，语义 local_key 用于本方案内依赖解析；编号不由用户填写。

scope 已描述本项改写的文件，context_paths 放补充上下文。若上下文同时是已声明上游（含传递上游）的产物，则沿实际依赖结果核对其字节，不冻结为下游的旧外部输入；上游未满足所需完成／验收条件或产物被外部改动时仍受阻。其余外部上下文按原摘要核对，格式修订不能借此接纳漂移。

dependencies 每项给 upstream_task（同 Change 的局部任务键）、condition_kind 和 basis（实际需要的产品／行为／检查条件）。目前接受 task_completed、verification_passed、artifact_available 三种条件定义；artifact_available 另给 condition_ref，必须是上游范围内的产物路径。依赖无环，共享输出文件需有真实的顺序条件。正式文档任务可声明 responsible_action=init（初次正式文档）、sync（规格修订）或 learn（规则），按[正式知识交付](knowledge-candidates.md)形成实际产物和验收；默认仍为 apply。跨Change协调及显式knowledge_applied条件按[多工作项约定](multiple-work.md)绑定实际目标、版本与依据，不用task_completed替代独立验收或知识应用。

未答问题每项给 id、question、blocking 布尔值及 task_keys 数组；blocking=true 必须列明受影响任务，仅这些任务直接受阻。依赖这些任务的后继仍按实际条件等待。

必要预重构在任务中声明 pre_refactor=true，并给 preservation_checks（必需任务检查的非空子集）、preservation_inputs（context_paths 的非空子集）；原判据输入不得与实际输出重叠，文件别名也须满足。提案通过形状检查不证明重构保持行为，执行步骤见[前后行为证明](#behavior-preservation)。

广泛迁移在 spec 给 broad_migration=true、integration_boundary 文本及非空最终 required_checks；单项 implemented 只表达实施结果，最终集成前不声称整项交付。

status 指定工作项后返回 plan.document、当前任务定义及每项 readiness。ready 只表示已声明条件在本次观察下满足；不代表授权、实施完成或验证通过。工具返回 plan_digest 绑定整个实际呈现的文档，不能用摘要相同来复用不同定义的批准。

完整文档已实际接受且具备修改授权后，apply.implement 一次绑定一个真实 Task；input.task_key 可用局部键或 TASK 编号，新请求由 CLI 转成 task_id，并冻结当前 REV、定义和 expected_versions={change, tasks}，tasks 为全部当前 Task 的身份／版本映射。未选任务时依呈现顺序选首个就绪项，不由该顺序虚构依赖。同一已接受方案内，完整实施请求继续推进其他就绪任务；显式只 apply 的请求遇到必需验收条件时停止在该阶段边界。文件仅限所选任务及实际授权范围，相关外部编辑需观察，不覆盖猜测。

每项实施执行其 required_checks，done 只表示该任务的实施结果。task_completed 要求上游实际完成；verification_passed 另需该上游最近的任务验收通过且已安全收尾；artifact_available 核对已登记上游结果及当前产物。依赖绑定实际上游结果及上下文，发生相关变化时只重开真正后继，保留旧结果与来源；无关经验或知识记录不因事件数量增加而使结果失效。

verify.run 给 input.task_key 时验收该任务，不给 task_id／task_key 时验收整个 Change。resume 的 task_contexts 给各任务现场指纹及保存结果；workspace_observation 给整项指纹；reviews 必须绑定所选择范围的实际指纹。任务审查只处理本项及其声明输入的发现，整项审查仍核对全部必需发现。验收请求始终只运行检查和保存观察，不改业务或测试源码。

全部任务已完成并仍适用后，运行整项 required_checks、逐 AC 和双维审查，再用整项通过的 verification_id 封存。任务通过不能替代整项 VER，整项通过后新增必需失败也会阻碍封存。集成失败可在原授权及相同 REV 下，将实际失败的 reopen_verification_id 交 apply 修复相关任务；变更目标或验收含义仍需 REV，不删 AC 或放宽检查。

正常暂停沿现有 pause／continuation 请求；仅暂停所选 Task，不记 done。resume／next 恢复各项实际进度、授权、依赖和最近任务／整项验收，查询本身不授权或重跑。原部分结果不能用于另一任务；重试保存返回的 task_id、REV、定义和版本映射，不能改为当前版本后重发。

当前版本在apply进入正常文件暂停的同定义Task时，若未显式给 continuation，可从该 Task 及已证明的 REV 继承链自动绑定唯一安全结束的实际暂停来源，并在结果和 source_runs 保留引用；原授权子集、撤销及未决效果照常核对。显式引用须对应当前暂停，不能用更早的原行为准备替代文件暂停。未结束或来源不一致先停止核实，独立前证明及故障恢复不冒充新的正常暂停。

<a id="revision"></a>

修订既有方案使用 update.revise，给整个当前 Change 的绑定、reason 和 proposal；proposal 采用上述完整文档及 presentation。简单方案使用短方案的原 presentation.text。CLI 新请求准备全项版本；重试保留原绑定，即使后续已经产生新 REV。

工具先返回 candidate、candidate_digest 和逐任务比较。移出文件／AC／核心约束、改写已有 AC 或撤去原调查判据时，outcome=scope_confirmation_required，旧 REV 继续有效。向用户展示完整候选、被移出的工作／AC 及原因；已有明确接受覆盖该具体候选时，approval={candidate_digest,source,text} 登记实际依据。目标字节、上下文或检查依据改变后须重新核对候选，不能复用过期摘要。修订仅改变记录，范围移出不删除业务文件。

其他语义修订可先保存未接受的新 REV；实施和验收前仍需明确接受。按同一完整 proposal 和已实际接受的 candidate_digest 调用 update，接受现有 REV，不重复分配 Task。已有授权不因新标题、措辞或排列变化重复询问；含义保持且原方案已接受时可沿用接受依据。未接受的语义修订经过格式调整仍需接受。

Task 沿 local_key 比较，保持 TASK 编号但新建 UUID，旧 Task／结果／VER 不覆盖，退役编号不回收。完成条件、AC、上下文、检查约定和真正上游变化重开相关任务；未改变定义且当前成果仍适用时复用结果。核心 spec 变化默认影响全部任务；如实际核查仅影响部分，可给 input.impact={affected_tasks:[local_key],basis}，自身定义与依赖变化仍单独核查。全项含义变化需新整体验收。

复用保留实际旧 run／VER／原行为证明，不创建假通过记录。status／resume 展示原 revision_id 及未确认的当前适用性；仍需核对当前文件、依赖和最新必需失败。旧阻碍审查发现保留，实际复查以原 finding 引用登记处置。部分实施跨 REV 续接仅限已证明同定义的 Task，并保持原授权子集。原判据变更时先审查影响，不能用修改后的代码补造旧基线。

修订提交后若进程异常退出，maintain recover 只核实原已提交元数据，保留新 REV 及旧来源，不重放修订、文件或检查。

<a id="behavior-preservation"></a>

必要预重构默认先运行原 preservation_checks，保存实际原现场、原代码／判据字节快照及命令证据；原检查失败、受阻、零测试或检查改变现场时，不提交候选文件。快照是只读事实，不改变正式文档的批准版本。通过后才写文件并运行原必需检查，原判据输入及相关上下文保持。证明只覆盖已声明检查与输入，不扩大为未测行为保证。

若需要先准备原证明，再在文件段暂停，单独使用 apply.input.preservation_only=true、files=[]，不带 pause，且仍须当前任务的有效授权。该步骤只准备原证明，返回 outcome=partial、checks=before_only，Task 保持 in_progress。后续正常 pause 请求复用原证明且不运行检查；没有原证明时，无检查暂停会在改文件前受阻。普通完整 apply 可以一次执行前检查、文件段和后检查。

结果 preservation.before 引用实际原 run／event，after_evidence_ids 引用实际后检查；before_passed／pending_after 都不是完成，只有实际配对通过且其余任务条件成立才能 done。证明来自已有事实，不能代替当前修改授权。新会话、后检查失败修复和实际恢复都保留同一原证明；不得在已改代码上重新运行检查并称为原始基线。判据／依赖变化先核对影响，需要修订时保留旧证据，不静默换条件。

恢复只核实原文件日志与证据，不重跑检查；已完成的真实配对保留，尚缺后检查仍待实际执行。实际写前及封存前会重核证明、只读输入和来源收尾。

同一正式文档有多个必需 Task 时，按[同文件批准差异](knowledge-patches.md)声明独立范围、顺序及真实验收依赖。实际组合不改写原 Task 结果；上游通过引用真实 application 及仍保留的含义，整项继续核对每项成果和最新失败。

项目协议隔离忽略当前文档、依赖及组合约束的旧写入器；使用兼容完整包和支持的显式升级路径，保留项目身份。

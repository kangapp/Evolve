# 确定性工具请求协议

本协议供宿主中的 AI 适配请求，不要求用户填写内部 ID 或 JSON。先读取实际 Skill 文件定位完整安装根，再运行 status；完整请求可按原授权连续切换 owner，显式阶段请求保持边界。

## 调用

```text
python3 <实际插件根>/runtime/evolve.py --project <目标项目根> <动作> [目标标题或ID] --owner evolve-<负责者> --method <方法> --request <JSON文件或->
```

路径含空格时按 argv 参数传递或正确引用。`--request -` 从标准输入读取 JSON，适合宿主准备请求；纯查询不接受写请求。十四动作的 owner 由运行时固定校验，实际可用方法见 status，未开放方法返回 UNAVAILABLE。

status的能力目录使用动作.方法标识，例如resume.show。CLI分别传动作resume和`--method show`，不把resume.show整体作为--method参数。动作／方法的对应关系见下表。

输入暂存及宿主拒绝标准输入时的回退按[共享运行约定](contract.md)执行；纯查询直接调用，不生成请求文件。

## 请求与授权

每个写请求包含 `authorization` 和 `input` 两个对象。authorization 保存实际用户来源 `source`、原话 `text`、本次允许的 `effect_kinds`；业务或知识文件修改另有具体 `paths` 数组。effect_kinds 使用 project_records（工作事实）、business_files（业务文件）、checks（已约定检查）、knowledge（具体正式内容应用）；不留档调查使用 read_only。授权来源由宿主忠实提供，字段不是身份认证；历史经验或配置不能充当用户授权。

新请求可不填内部编号，工具在只读准备时生成 request_id，定位 project_id／workspace_epoch，并为实施、验收及封存冻结当前 Change／REV／Task 版本。目标标题唯一时可解析，多个候选须明确。先用 status 指定目标读取 plan 原文及 Task definition；未指定目标时只列导航，不一次展开全部任务正文。knowledge_refs 的批准版本与实际字节分开，pending_knowledge 不是正式规则；latest_verification.recorded_status 不等于当前通过，applicability 未核实时为 unconfirmed。返回的 request_context 和 input_bindings 保存这些绑定；重试必须将它们合并回原请求及 input，并保留原输入，不能重新读当前版本替代旧绑定。已提供 request_id 的请求缺少原身份或 epoch 会拒绝，避免旧请求越过恢复截点。

`ok` 只表示接口操作；业务结论看 data.outcome、status、task_checks 和真实证据。checks_not_passed、blocked、needs_recovery 不能报告完成。副作用状态不明时先核对 pending_runs（包括 operations 与 pending_checks）和 maintain recover；不要生成新 ID 重试猜结果。检查主进程退出不等于子进程组已经停止；launch_unknown、foreign_host 或 process_group_present 均保留占用，不补记通过。

apply.implement始终需要project_records、business_files及原准确paths；即使正常续接的files=[]、本轮只做后检查，也须忠实携带仍有效的原修改授权，不能把checks授权当作业务授权。非暂停且存在必需检查时另需checks。若原授权没有该范围则停止，不从字段要求反推用户授权。

## 已实现的请求内容

当前完整包使用protocol v16／schema v4；外部数据Task绑定具体目标与执行约束。有限同步Python／SQLite方法按[数据操作](external-work.md)使用，实际开放能力以清单为准。维护屏障、执行／受管文件保护和定向升级见[完整档案维护](recovery.md)。复杂 Task 的调查／症状绑定不可由旧写入器忽略。跨项条件／混合现场与安全取消见[多工作项](multiple-work.md)，数据范围和独立导出字段见[数据工作](data-work.md)。

| 动作／方法 | input 内容及边界 |
|---|---|
| init／connect | 可选 name、checks。checks 是 id、argv 数组、项目相对 cwd、timeout；只配置不执行。初次接入只建记录设施；重复接入沿用身份。已有配置变化先返回 config_candidate；实际呈现 candidate 后，新请求保存相同 name／checks、expected_config_digest 及 presentation（原文 text 与 source）应用；检查按 ID 合并，不运行命令，不模板覆盖未知内容 |
| propose／create | 简单方案：title、plan、completion、scope 文件数组、acceptance 条件数组、required_checks ID 数组、presentation（实际呈现的 text 与 source）。复杂方案使用 complexity=complex，格式及当前边界见[复杂规格提案](structured-plans.md)。只存已呈现方案，不默认接受或修改业务 |
| update／revise | 绑定整个当前 Change／REV／定义及全部 Task 版本；reason、proposal 给完整呈现的新方案。approval 精确绑定候选；范围移出及结果继承见[REV 请求](structured-plans.md#revision)。仅修改项目记录，不写业务文件 |
| analyze／investigate | question、scope 项目内文件或目录范围、sources、business_effect=read_only、record_intent=answer_only／record、analysis。独立留档不创建 Change／Task，具体格式见下文 |
| apply／implement | 绑定 change_id、revision_id、definition_digest、accepted_plan_digest；files 数组逐项给 path、expected_digest（原文件不存在为 null）、content。简单任务冻结 change／task 版本；复杂任务另绑定 task_id（新请求可用 task_key 解析），expected_versions 冻结 change／tasks 身份版本映射，见[复杂任务](structured-plans.md)。新请求可自动补齐当前绑定；重试和文件字节前置仍保留原值 |
| verify／run | 当前绑定及reviews数组；每项给axis=spec或standards，分别提供实际observer、summary、fingerprint_digest和findings。reviews不是以轴名称为键的对象。spec 逐个 AC 给 acceptance_results（ac_id、status、basis）；复杂工作给 task_key 验收该项，不给任务目标则验收整项。只验收不修复或写测试；仅当必需命令非空时需要 checks 效果授权。已 archived 的工作项可追加当前现场复验，保留 Change／Task 和原封存截点；cancelled 仍受阻 |
| archive／close | 当前绑定与最新整项 verification_id。全部当前任务、最新必需检查、审查及完成截点现场全部成立后封存；任务 VER 不能替代整项验收，更新的必需失败会阻碍封存；不隐式批准或同步知识 |
| sync／propose、check、review | 外部正式全文的 adoption 及旧提案后继见[采纳约定](knowledge-adoption.md)。保存完整正式候选、实际内容观察及逐项用户决定；四项 proposal 引用绑定 UUID／版本／候选及基线摘要，见[知识候选协议](knowledge-candidates.md)。这三个方法只改记录 |
| sync／apply | 准确 proposal 引用及 approved_event_id；必需文档绑定当前 Change／Task 和具体接受的方案。只应用已批准且依据仍适用的正式内容，保存 delta／application／artifact，不隐含应用后验收，见[正式应用](knowledge-candidates.md) |
| verify／knowledge | application_id 及对每个内容判据的本次实际 observations；重新读取实际文件、保留字节并生成 applied VER，不改目标、不替代整项验收 |
| init／baseline.propose | path（Markdown）、expected_digest、content、presentation；结构化初次交付另给 topic／reason／acceptance 及可选 delivery／edits，见[初次正式文档](knowledge-candidates.md#初次正式文档)。只存具体候选，目标仍不改 |
| init／baseline.apply | 结构化候选给准确 proposal 和已记录 approved_event_id，必需交付绑定 Change／Task／方案；旧式候选仍给 proposal_id 与 approval（proposal_version、candidate_digest、expected_digest、source、text）。需 knowledge 效果和具体 paths；批准、实际版本、目标验收分别留档 |
| maintain／backup | input={}；固定 SQLite 截点与注册 authority，未批准字节单列保护；返回完整目录与准确 manifest_digest，不含业务源码／数据 |
| maintain／restore、upgrade | stage=plan 展示准确维护集合；restore 另给 bundle／manifest_digest。stage=apply 绑定 plan_id／plan_digest 及预存唯一完整请求；中断只恢复原 journal.request。upgrade 只支持健康 14／15→16，详细保护／排空／冲突与外部未知见[维护协议](recovery.md) |
| maintain／recover | 明确 operation_id 或 run_id；唯一可判定中断可自动定位。保留现场和候选，只按原有效授权核实本地步骤，不运行旧业务命令或补造通过 |
| maintain／export | source 绑定已完成分析的 run_id／result_digest，output 指定私有 exports 下新文件，format=markdown／json；只从保存事实渲染，视图失败保留底稿，见[导出](data-work.md#从保存事实导出) |
| apply／external.execute、reconcile、record、compensate | 具体候选／授权、provider 核实、来源声明和独立补偿见[数据操作](external-work.md)；观察既有 operation 不要求重开工作项 |
| maintain／cancel | external_operation_id 分支按[数据操作](external-work.md)撤销未来派发并保留未知；原 Change 分支为唯一工作项目标及实际 reason，冻结当前版本；只为安全结束的本地工作登记取消，保留已发生效果和完成结果，见[安全取消](multiple-work.md#安全取消) |

已有源文件发生外部变化时，apply 需用 observations 明确登记路径与当前摘要；工具不猜修改者或意图。同 REV 的 done 任务再次实施还要引用实际失败的 reopen_verification_id。更改需求／验收含义使用 update.revise，先呈现具体候选并按实际用户接受登记。

任务声明 pre_refactor 时，按[前后行为证明](structured-plans.md#behavior-preservation)准备和执行。preservation_only=true 仅用于 files=[] 的原证明准备，不与无检查 pause 混用；partial／before_only 不是实施完成。

## 验收和审查

review 的 fingerprint_digest 必须对应实际检查过的当前 workspace。规格和规范分别说明依据；每个必需 AC 有实际结果及来源。findings 必须给局部 id、path、basis、impact 和 blocking；不能只用“已读”清除必需发现。复查时 resolutions 引用原 verification_id、finding_id 并给本次实际依据，旧发现与失败保持不变。实际自审填写真实观察者，不称独立审查。

配置的 argv 检查在数据库事务和短锁之外运行；每次派发及文件写入前重新核对身份、epoch、包和资源归属。检查退出零不替代 AC 或审查。源码、未跟踪输入、必要检查变化会重核证据；保留业务文件，不能删断言换通过。任务级检查与整体验收分别记录，apply 返回 implemented 也不等于 archive 条件已成立。

<a id="analysis-request"></a>

## 调查请求

即时问答直接只读回答；需要结构化校验时用 record_intent=answer_only 与 read_only 效果，通过标准输入传请求，不先 init，不创建库、run、备份或暂存目录。宿主拒绝这种输入形式时仍可给出实际只读观察的对话回答，并说明未生成结构化结果。明确留档用 record 与 project_records 效果；未接入时先最小 init，仅建记录设施。两者均声明 business_effect=read_only。运行时保存或返回宿主实际调查的材料，不替宿主执行命令，不把提供者的陈述认证为机器自测。

sources 是有唯一 id 的数组。每个来源给 kind、observer、observed_at、limitations。时间为带时区的实际观察时间；不知日期用 null，并在限制中说明。file 来源另给 path 与 expected_digest，运行时核对并保存实际原字节。observation 来源给 object、version（不知用 null 并说明限制）、method、content 原始观察输出；不能只填“通过”。reference 来源给同样的 object／version／method，以及 location 和未取得原文的限制，不放 content，也不承诺外部内容可恢复。源文件必须在声明 scope 内。

analysis 包含 observations、hypotheses 两个数组，以及 answer_status=answered／partial／inconclusive、conclusion、coverage、limitations、remaining_questions、next_steps。后四项为字符串数组。观察逐条给 local_key=F1、statement、sources 来源 ID 数组；假设给 local_key=H1、statement、status=unconfirmed／supported／refuted、observations 观察局部键数组、basis。supported 也不等于证明所有环境的根因；completed 只表示这一轮结束。partial／inconclusive 保留限制与待答问题。

排错调查另存 analysis.symptom：criterion 绑定 method、environment、input、expected、expected_source（独立预期的来源 ID）、side_effects；原方法是已登记检查时另存完整 check 定义（id／argv／cwd／timeout），不要换成宽松命令。symptom 保存 status=reproduced／not_reproduced／blocked／historical、attempts、failures、sources 和 limitations。当前复现与未复现须有带日期、留存输出的 observation 和实际次数；历史／受阻可将未知次数写 null，不猜次数。偶发问题另给 intermittent=true、trigger、window 及采样限制，一次未复现不代表消除。缺权限只记限制，不加生产探针或持久化测试；隔离复现实验先核对实际副作用。

独立留档结果返回 run_id；用 status 指定该 RUN 可读原分析、result_digest、criterion_digest、当前头和后续纠正。续查的 previous 为所见头的 run_id／result_digest；旧头不再派生第二个后继，幂等重试仍返回原结果。纠正在新 F／H 的 corrects 数组中引用原 run_id、result_digest、local_key，旧结论不改写。未知结果先核对 pending_runs；maintain 仅封存实际中断，不补造分析成功。

工作内排查可给 parent（run_id、input_digest、execution_instance），从实际 pending_runs 读取，保持父阶段范围。父阶段须仍是同一实际活动执行且未撤销授权；已结束时另开独立调查。parent 不代表修改授权，analyze 仍不写业务。未留档的 answer_only 不派生 previous／parent 或持久纠正。

转修复时另外呈现方案并使用当前修改授权；analysis_basis 引用调查 run_id、result_digest、adoption_basis，说明当前适用依据。有症状判据时同时给原 criterion_digest，方案冻结原 symptom 与 check 定义。简单方案使用 propose.input.analysis_basis；复杂方案在对应 tasks 项中声明，单 Task 也可用根级 analysis_basis 明确绑定唯一 Task，两处同时声明必须一致。多 Task 根引用歧义时拒绝，不猜修复归属。完整呈现包含引用；每个修复 Task 的 required_checks 必须保留原完整检查。Task 验收给本节的当前 symptom_result；整项完成另核对其安全结束、当前局部依据匹配的原症状 Task 验收，不用普通绿灯或正文引用替代。调查许可不能充当 business_files 权限。

这类修复的 verify.input 另给 symptom_result：原 criterion_digest、当前 fingerprint_digest、status=passed／failed／blocked、observer、observed_at、basis、evidence 原始复验输出、attempts、failures、limitations。观察发生于当前任务结果之后，原检查仍由 verify 真实执行；原判据不可通过改摘要或换检查静默降低。缺 red 或偶发样本不足时保留限制，记录只是该观察范围的结果，不自动推断因果问题消除。双维审查、逐 AC、失败后同 REV 修正与封存门禁继续适用；只有命令绿灯没有原判据复验不能完成。

## 恢复限制

当前 recover 覆盖已有本地实施／初次知识／增量配置文件 journal、初始化截点、未派发文件操作的中断登记，以及 verify／archive 的记录收尾；完整档案restore另按[完整档案维护](recovery.md)执行；数据结果unknown另按[数据操作](external-work.md)核实，不由recover重发或推断完成。记录收尾保留已提交的验收／封存事实，原 run 仍为 interrupted，由 finalized_by 关联维护结果；未提交的验收保持 blocked，不重跑检查。检查执行仍在运行或启动结果尚无确证时拒绝回收占用。启动身份未知时，可在同一 recover 请求中提供 check_observations：逐个绑定 status 中的 execution_id、command_digest、host，给出 outcome=not_started／stopped、带时区的 observed_at、实际 source 和 basis。必须对应派发之后的确证，不能是猜测或仅凭主进程退出；运行时仍能观察到进程组时拒绝接管。确证由维护 run 单独留档，不推断检查通过。第三种文件内容保留冲突，已提交后的外部回退不会按旧候选覆盖。恢复不新增测试通过记录；原来确已保存的任务完成及证据也不会被抹去。验收结果明确实际环境和观察范围，不推断未运行环境的结果。


<a id="normal-continuation"></a>

## 正常暂停与只读续接

resume／next 与 status 一样是纯查询，不接受写请求；目标可用唯一标题或 ID，不给目标时只在唯一未完成工作项或未答分析主题时定位。返回 context 包含原方案／定义、已保存结果、实际失败与证据引用、原授权及撤销、待审知识、项目级 pending_runs 和本次现场差异。authorization_granted=false；外部数据没有重新读取时为 not_observed。差异只是观察，不自动登记或覆盖。多个候选返回 selection=required，不能按最近记录选择。

需要正常暂停时，apply.input.pause 给 completed、remaining、next_steps 三个字符串数组和实际 reason；remaining／next_steps 非空。工具只完成本次原授权文件段，按当前指纹保存进度，跳过检查，Task 保持 in_progress，释放已安全结束的本地占用，run completed／outcome=partial。completed 文本是宿主提供的进度说明，不代替文件与检查证据。完成文件段有异常时仍按真实中断恢复，不能伪装正常暂停。

暂停请求的 authorization 照实保存用户已明确的完整范围和后续授权：若原指令已允许后续检查，effect_kinds 保留 checks，text 保留该真实来源，pause 仍让本轮检查不执行；不能因本轮只写文件就删掉已授予的后续效果。原指令没有授予的效果仍不添加。续接效果超出暂停 run 实际保存的授权时，保留拒绝并核对原指令／记录缺口；独立新授权只依据用户实际的新明确指令准备，结果与原授权复用分开报告。

用户明确继续后，按 resume 展示的新版本与当前现场准备 apply 请求；input.continuation 引用安全结束的旧 apply run_id／result_digest。新请求保留实际授权来源和本次继续意图，工具核对原项目／epoch、Change／定义及授权未撤销；跨 REV 还须具有明确的同定义任务继承关系，复用时不扩张效果或路径；绑定新旧来源，新建 run，不需要假报异常或先 recover。新增授权应按真实新的明确指令另行准备，不能借旧上下文扩权。经验生产与消费另走下述 learn 请求，读到旧背景不等于完成学习闭环。

当前版本对正常文件暂停可从实际Task结果自动解析continuation；只在同任务／已证明的同定义 REV 来源唯一且安全结束时绑定，仍核对原授权子集。结果 continuation.resolved_from_task_result=true 标明自动解析，不等于自动授权；更早的 before_only 结果不能替代当前文件暂停。

项目协议不匹配时使用匹配的完整包处理未完成运行，再按[兼容说明](../docs/compatibility.md)执行支持的显式升级。保留原请求与身份，不能手改协议号或重放旧操作。


<a id="project-learning"></a>

## 项目学习请求

`learn "检索词" --method search --owner evolve-learn` 是纯查询，不接受写请求，不留 run 或命中计数；最多返回五条，随结果保留全部正式知识引用和待审知识，不受普通经验排名影响。结果有 experience_ref、state_ref、来源版本、适用条件、限制和 search_ref。candidate 只是待核实线索，active 表示限定范围内有支持；needs_review／retired 的 recommendation_allowed=false。no_match 才是真实无命中；not_connected、来源／记录错误及存在未完整留档的 incomplete 分开。当前直接扫描权威 run，不使用或修补物化索引。

以下写方法均只需 project_records 效果，不写业务文件、正式知识、Skill 或检查工具。保留实际来源及批准范围，工具不将宿主评估认证为所有环境的因果证明。

- **record**：input.experience 给 topic、problem、advice、applicability、version_context、observer 文本，scope／exclusions／tags／limitations 字符串数组；scope 和 limitations 非空。cause 给 statement、confidence=hypothesis／observed，区分假设与已有观察支持。input.sources 是非空实际工作引用数组，每条给 run_id、result_digest、可选 evidence_ids；核对原 run 和原始证据摘要，不能只引用另一经验来充当独立支持。内容保存为不可变候选，经验版本即原记录 run_id／result_digest。完全相同内容及同一来源的新 ID 会报 LEARNING_DUPLICATE，应读原经验及其状态；精确原请求重试仍幂等。实际新观察与修改后的内容另行留证，不以引用次数自动升级。
- **retro**：有发现时同 record；若另给 source，须也是 finding 的实际来源。检查后没有新发现时 input.experience 可空，给 source、实际 checked_basis 和 observer，单独记录 no_new_learning，不创建经验。未检查仍是 pending，不填成无发现。来源 run 保持不可变，学习结果由独立 learn run 关联。
- **review，kind=decision**：先保存搜索返回的 experience_ref／search_ref，再给当前 change_id／revision_id／definition_digest，observed_files 为本次实际核对的范围内文件摘要，decision=adopted／rejected／not_used、applicability_basis 和非空 limitations。工具重新检索并核对目录版本及实际文件，记录“命中”和“采用”两个事实；经验不改变 Task 的 AC 或权限。needs_review／retired 先复审，不能直接采用为建议。
- **review，kind=feedback**：给先前 decision_ref、该决定之后同一 Task 定义的 result_source（实际 apply／verify run 引用），outcome=helped／not_helped／unknown／counterexample、basis 和非空 limitations。采用效果是有来源的观察者评估，不从整单 passed 自动推断；未采用不能记采用有效或无效。每个决定一次结果，重复请求幂等，另一个新请求不能覆盖旧反馈。反例保留并使当前经验 needs_review。
- **review，kind=state**：给 experience_ref、最新 expected_state_ref、state=candidate／active／needs_review／retired、basis、实际支持 sources、逐条已复核的 reviewed_counterexamples run ID。状态沿明确前驱引用追加，不按时间猜最新；有新反例时必须逐条核对，旧绿灯不能消除较新的反例，active 需要反例之后的新实际支持，以证据 observed_at 核对，不能用重新入档的时间冒充新观察。业务假设不能因引用和绿灯自动变 active。内容版本保持，状态有独立 state_ref；任何状态都不是正式规则批准。
- **disable**：同状态审阅输入，状态固定 retired，保留原内容、来源、采用和反例。正式规则的 promote 见下项；检查工具修改仍归普通 Change 与 apply。

- **promote**：stage=propose 保存具体规则候选及 rule_scope／rule_sources；sync.check／review 记录实际内容检查与逐项决定；stage=apply 按准确 proposal、批准和当前交付绑定由 learn 实际写入。规则来源、反例、应用后验收和恢复见[规则交付](knowledge-rules.md)。

结果丢失先核对实际 run；已提交经验不能改写，未提交结果保留为草稿／未完整记录。maintain 只收尾真正中断的元数据，不补造经验或采用效果；完整旧 run 保留来源和结果。可选经验来源损坏时，resume 展示 unavailable 并保留原工作方案和正式知识，不能以检索故障迫使重建项目。

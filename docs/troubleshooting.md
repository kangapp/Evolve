# 诊断与排错

## 从具体问题开始

| 现象 | 先做什么 |
|---|---|
| 找不到 Skill | 核对完整安装根、当前项目是否启用及宿主是否重启，按[安装指南](installation.md)检查 |
| 显示未接入 | `not_connected` 是新项目状态，明确请求接入后才建立记录 |
| 任务受阻 | 读实际失败和依赖；只验收请求保持源码不变，需要修复时另给明确意图 |
| 上次正常暂停 | 说“继续指定任务”，恢复原进度即可 |
| 进程异常退出 | 保留现场，先诊断原执行，再按原操作核实恢复 |
| 数据操作超时 | 核实原操作的实际效果，保持原身份，避免重复派发 |

## 只读诊断

```bash
python3 "$HOME/.local/share/evolve/runtime/evolve.py" --project /absolute/path/my-project maintain --method doctor
```

替换安装与项目路径，保留返回的错误码、版本和内容摘要。诊断不会代替项目接入或数据恢复。

## 按错误码定位

| 错误 | 含义与下一步 |
|---|---|
| PYTHON_VERSION | 使用 Python 3.11+；插件不会自动安装系统依赖 |
| PACKAGE_INCOMPLETE | 资源缺失／被改或摘要不一致；重新构建／安装完整同版本包 |
| PACKAGE_VERSION | 内核、清单或能力表混用；停止写入，使用完整一致版本 |
| PROJECT_COLLISION | 存在同名 evolve 或 .evolve-local 资料；先核对身份，不覆盖 |
| PROJECT_INCOMPLETE | 配置／库仅有其一；保留现场，不能按新项目重建 |
| PROJECT_CHANGED | 观察期间历史变化；重做只读核查，不使用混合截点 |
| PROJECT_INVALID／PROJECT_IDENTITY | 配置、库或身份异常；只读诊断不修复 |
| SCHEMA_VERSION／CONFIG_VERSION | 当前包不支持该版本；保留数据，不自动迁移或降级 |
| UNKNOWN_ACTION／UNKNOWN_METHOD／OWNER | 动作、方法或负责 Skill 不匹配；按真实能力重试 |
| DUPLICATE_INSTALLATION | 发现同名散装 Skill；核对来源并选择单一渠道，工具不删除已有文件 |
| UNAVAILABLE | 当前版本尚未提供该方法；不是业务通过或资料已保存 |
| CONTINUATION／RUN_RESULT_INVALID | 续接来源未安全结束、结果已变或绑定不符；保留旧结果，重新定位原工作与当前版本；不能用新 ID 绕过来源检查 |
| ANALYSIS_SOURCE_CHANGED／ANALYSIS_SCOPE | 调查实际来源已变或不在声明范围；重新读取并核对实际范围，保留原观察，不将新字节冒充旧来源 |
| ANALYSIS_HEAD／ANALYSIS_RUNNING | 旧调查头已有后继，或前一轮尚未安全结束；读取当前头及实际执行，不按日期猜新主题或覆盖进度 |
| ANALYSIS_INCOMPLETE | 观察已提供但分析没有完整保存；先看 pending_runs、原输入和已存证据，不能补记成功；实际中断由 maintain 收尾 |
| ANALYSIS_PARENT | 原父阶段不再是所见的活动执行、范围不同或授权失效；核实现场后独立调查，不沿过期阶段越界 |
| SYMPTOM_CHANGED／SYMPTOM_REVERIFY_REQUIRED | 修复或验收缺少原症状判据，或替换了原预期／检查；恢复原判据复验，改变验收含义需重新确认 |
| SYMPTOM_LIMITATIONS | 缺 red 或偶发样本不足；记录观察局限，不补造根因、失败次数或问题已消除的结论 |
| REQUEST_REQUIRED／AUTHORIZATION | 写方法需要实际授权来源及输入；用户由 AI 准备请求，不从历史经验推断授权 |
| VERSION／WORKSPACE_EPOCH／DEFINITION | 请求依据已变化；重新核对现场和原请求，不用当前版本替换旧请求绑定 |
| FILE_CONFLICT／WORKSPACE_CHANGED | 原字节或受检现场已变化；保留外部内容，明确登记观察并重新判断证据 |
| FILE_TARGET_CHANGED | 目录别名指向的实际文件与原操作绑定不同；保留 journal 和两处文件，核实原目标。恢复前须恢复可核对的原指向，不能将相同字节视为同一文件 |
| CHECK_CONFIG | 必需检查命令与已批准依据不同；核实配置与方案，不沿用旧通过记录 |
| BASELINE_EXISTS | 正式映射已建立；初次候选即使仍匹配原字节也不能覆盖已建立的权威，后续修订交 sync |
| KNOWLEDGE_PATCH／KNOWLEDGE_CONFLICT | 原字节范围、UTF-8 边界、完整正文或语义目标不一致；保留双方，不做近似搜索覆盖 |
| KNOWLEDGE_BATCH／KNOWLEDGE_COMPOSITION／KNOWLEDGE_DEPENDENCY／KNOWLEDGE_CHAIN | 缺明确提案分组、实际组合内容观察、已应用依赖或已知来源链；读取具体候选和真实链，检查当前正文，不重复批准未变前项或绕过门禁 |
| KNOWLEDGE_DELIVERY／KNOWLEDGE_BASIS | 必需文档关联或实际实现依据不适用；核对真实 Task／AC、当前实现及更新的必需失败，不用候选检查代替实现证据 |
| RULE_SOURCE／RULE_SOURCE_CHANGED／RULE_REVIEW_REQUIRED | 规则缺实际支持、最新状态绑定或完整反例复核；先读准确经验及原证据，保留正式正文和旧批准，新依据重新形成具体候选 |
| KNOWLEDGE_VERIFICATION | 必需正式文档尚缺应用后的适用通过记录；由 verify 检查实际目标，局部内容验收不替代整个 Change 验收 |
| KNOWLEDGE_VERSION／KNOWLEDGE_CHECK | 候选绑定过时，或缺最新实际内容检查；读取具体版本并保存实际观察，candidate 不代替应用后验收 |
| KNOWLEDGE_ADOPTION | 当前外部全文、原正式版本或观察依据不匹配；保留现场和原权威，重新呈现具体采纳候选，不能重写文件凑摘要 |
| KNOWLEDGE_REJECTED／KNOWLEDGE_EXTERNAL | 保留原拒绝或外部正式文件变化，登记实际重新审阅意图／提出采用方案；不能换标题绕过或静默覆盖 |
| REVISION_APPROVAL／PLAN_ACCEPTANCE | 当前修订尚未接受或接受摘要对应旧候选；展示实际差异及最新依据，登记已有具体接受，不重造用户授权 |
| REVISION_PENDING | 修订已提交但来源未安全收尾；确认原执行停止后进行元数据恢复，不重新修订或重跑检查 |
| STALE_REVIEW／STALE_VERIFICATION | 审查或验收对应旧现场；按当前内容复验，不能只改摘要使旧结果适用 |
| CONFIG_PRESENTATION／KNOWLEDGE_APPROVAL | 缺具体候选或批准绑定；展示实际内容并按有效授权应用 |
| CONFIG_UNSUPPORTED | 当前配置表达式不能无损编辑；保留原文件，不能用模板覆盖未知段落 |
| CREDENTIAL_CONTENT | 输入包含当前环境中已知凭证；使用环境引用，凭证不进入记录或文件候选 |
| NEEDS_RECOVERY／JOURNAL_INVALID | 本地文件与记录需要核实，或 journal 与原授权不符；先只读诊断再选择原操作恢复 |
| WRITER_ACTIVE／CLAIM | 原执行仍可能运行或相关资源已被占用；核对原执行，不凭时间或新请求编号接管 |
| CHECK_OBSERVATION | 核实信息缺失、过时或与原执行／命令不符；按实际观察补齐，不修改执行身份换成别的命令 |
| CHECK_RUNNING／CHECK_EXECUTION_UNKNOWN | 检查进程组仍存在或启动身份未知；查看 pending_runs 中的 pending_checks，保留占用与现场，不重跑猜结果 |

status 返回的 pending_runs 包含运行、操作及待核实检查身份。maintain recover 需要明确的原 operation_id 或 run_id；唯一可判定的中断可自动定位。该操作收尾已授权的本地文件或记录事实，不执行原检查命令、不补造测试通过。已保存的任务完成、验收及封存事实保持，第三种文件内容保留为冲突。

缺少进程身份的检查不会自动解除。取得具体执行、命令、主机、时间及范围的确证后，由 AI 按[请求协议](../shared/protocol.md)将 check_observations 随原操作的 recover 请求登记；仅凭“主进程退出”不足以证明停止，也不能推断测试通过。系统仍观察到进程组时保持受阻，不通过手改数据库、删除占用或清库重建跳过。

## 本地中断的最小恢复

先用 status／doctor 查看 pending_runs、具体 operation、文件日志和待核实检查。正常暂停并安全结束的 run 不需要 recover；实际进程仍运行时先等待或核实停止，不能只凭锁文件过旧接管。若要更新／卸载包，先在完整旧版本中把能确定的本地事实收尾。

可以向 AI 表达：“核对这个中断执行及当前文件，保留外部修改，只恢复原已授权本地操作，不重新运行检查。”AI 按真实来源准备 `maintain --method recover` 的请求，明确选择原 operation_id 或 run_id。恢复使用原日志的原值／候选与当前文件逐项比较：原值可按原授权继续，已是候选则补登记；第三种内容保持冲突和占用，先展示差异及实际限制，不覆盖用户内容来取得通过。缺日志的原执行只能保存已观察事实，文件恰好正确也不能凭空记 Task done。

恢复结果中的 `checks=not_run` 表示没有重新运行检查；Task 可以保留 in_progress，原执行标 interrupted，并由独立维护 run 引用。下一次实施从已保存结果与有效授权继续，必须另行执行实际检查和验收。原先已经提交的完成／验收／封存事实保持；现场变化后旧 passed 不代表当前现场通过。

恢复保护位于返回的 protection 路径，保留当时库、日志及实际文件观察。其 `consistent_restore_package=false` 明确表示中断现场保护，不是可直接整体还原的一致包。首次写前日保护包含一致库截点和登记资料，实际外部字节在附录单列；未结束日志会阻止新保护，不因当天已有备份而跳过核查。业务数据库和外部服务数据未自动备份；完整 backup／restore 和定向 upgrade 的准确步骤见[完整档案维护](../shared/recovery.md)；不能手动替换 history.db 冒充完整恢复。

安装根被替换或包混用后，保留旧完整包与项目资料，停止相关写入；不要修改清单、协议号或数据库来绕过兼容检查。可读／可写范围不支持时仅诊断并保留资料。兼容新包使用新的 run，旧执行的原版本／摘要和事实不改写。

## 档案损坏、倒退与换库中断

先保留完整包、原目录与准确备份摘要。由 evolve-maintain 依[完整档案维护](../shared/recovery.md)先生成集合差异方案，再按完整唯一请求执行。数据库损坏不重跑 init；maintenance 状态按独立 control/restores 的 journal.request 继续。RESTORE_CHANGED 保留第三方值，JOURNAL_INVALID 停止使用被改日志；不得删屏障或改摘要强行继续。

DATABASE_OPEN／WRITER_ACTIVE／CHECK_RUNNING 要先明确结束原执行和连接；未知检查有具体停止证据才继续。lsof 观察不可用时不支持该次离线换库。PROTECTION_UNKNOWN 保留控制材料与库，先核查健康历史，不能从旧包或缺失索引推断无额外文档／外部效果。保护集合超限或空间不足先解决实际容量；不删唯一证据或静默缩小集合。

恢复成功会换 epoch，保留被隔离的额外受管文档及原始损坏 DB／sidecar，未知用户文件仍在原位。业务文件、数据库和外部效果保持当前现场；原验收的 passed 是历史事实，当前适用性须重新核对。分叉分别保留，不自动合并。具体恢复步骤见维护协议。

## 数据操作未知或补偿受阻

`external_unknown`、丢回执或提交后超时：保留原 operation 和保护索引，使用 external.reconcile 实际只读核实，不改 ID、删占用或再发。`CHECK_RUNNING` 表示数据 sender／检查进程组仍存在；`CHECK_EXECUTION_UNKNOWN` 需要对应原执行身份的真实停止依据，不能只等一段时间。原本地锁持有者已确证退出时，核实入口可接管其旧短锁，仍独立检查 sender。

`EXTERNAL_PROTECTION_UNKNOWN`／`EXTERNAL_SOURCE_UNKNOWN`：保留当前索引、胶囊和备份字节，检查准确来源；协议 16 丢失 sender 索引时拒绝换库。旧 14／15 升级后标为 unverified 的保护不会自动变成可派发。完整恢复合并当前及选中快照的未知来源，不恢复业务数据。

`EXTERNAL_MATERIAL_CHANGED`／`EXTERNAL_TARGET_CHANGED`／`EXTERNAL_PRECONDITION`：批准后的入口、helper、SQL、别名、目标身份或前置发生变化，停止使用旧候选，重新调查并呈现具体候选。动态或脱离进程组的机制当前不支持。`EXTERNAL_COMPENSATION_UNKNOWN` 表示原终止／完整范围尚未确证，先核实；补偿必须是自己的新任务、候选和批准。

人工成功声明经 external.record 留作来源，与实际核实分开。实际查询失败不清 unknown，也不抹去上次已确认事实。Task 检查尚未完成时显式 stage=checks，仅继续检查；最终 verify 仍需真实目标只读授权。接口字段与边界见[数据操作](../shared/external-work.md)。

## 已连接但检查保护缺失

先使用 evolve-maintain 的 doctor 查看 readiness。缺少控制资料与运行中断分别处理：未决原操作沿 recover 核实；已有运行安全结束且当前保护与完整历史足以支持时，准备 maintain.repair 方案，核对准确集合后应用。存在未知发送、未决检查或资料身份冲突时保留受阻，不能把缺索引视为没有执行。

SESSION_PACKAGE_MISMATCH 表示当前会话保留的包摘要与执行包不同。启动新会话，从宿主实际 Skill 路径重新核对版本后恢复原工作。每个错误的 workflow.next_steps 给出接手建议；建议不改变授权。

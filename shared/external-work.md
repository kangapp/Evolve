# 具体数据操作

本页维护宿主请求字段与具体调用。

<!-- source-only -->
设计权威的效果／恢复语义归[运行时协议](../docs/runtime.md#external-effects)。
<!-- /source-only -->

0.1.0 开放受控本地 SQLite 机制的四个 apply.external 方法，内核已按当前Codex范围通过受控数据验收。它不提供云数据库连接器，不证明正式环境可用；当前受控范围不执行真实生产数据。

## 先准备，后按准确候选执行

数据修改与文件实施共用 Change／REV／Task／Verification。propose 的简单方案或复杂任务须声明 execution_kind=external_write、external_target 和非空 required_checks；scope 列有限执行机制及独立检查文件。普通 apply.implement 拒绝代替数据操作。公开 execute／compensate 需要当前任务、定义和具体方案绑定，CLI 为新的请求准备这些字段；既有请求保持原绑定。

授权 effect_kinds 包含 project_records／external_read，真正派发另需 external_write／checks。authorization.external_targets 列准确的 kind、path、environment、objects、scope、provider_identity，必须与 target 的 identity.expected 对应。普通检查许可不包含数据写入许可。真实用户已给统一授权时照实保留来源；不得伪造需要重新确认，也不把验收夹具授权扩展为生产许可。

执行 `apply --method external.execute` 的 input.stage=prepare。字段如下：

| 字段 | 实际内容 |
|---|---|
| target | kind=sqlite、项目内 path、environment=isolated／test／production、明确 objects／scope；identity 含只读 SQL、可选 parameters 和非秘密稳定 expected |
| execution | files 全部有限文本依赖；argv 第一项为其中的 .py 入口，恰有一个 `{target}` 和一个 `{operation_id}` 参数；cwd 为冻结材料内目录；timeout 为 1—3600 秒 |
| execution.closure | 实际 observer／basis；complete=true、no_detached_or_delayed_work=true；非空 limitations。声明不能代替实际读取入口、helper、间接 SQL 和配置 |
| idempotency | supported 布尔及实际检查到的 basis；无能力明确说明 |
| preconditions | 1—16 项只读 SQL／parameters／expected_rows／description |
| reconciliation | receipt 只读查询，参数恰含一次 `{operation_id}`；按顺序返回 operation_id、outcome、known_effects_json、finished；complete_scope=true、实际 coverage_basis、effects 查询及 expected_rows／description |
| limitations | 实际核实能力、目标和有限机制的非空限制 |

运行时读取真实目标身份／schema／物理文件身份与各项数据前置，保存入口、所有声明依赖、解释器及候选正文。宿主实际检查机制是否在自己的事务内核对目标／前置及 provider 幂等键。动态读取、延迟或脱离进程组工作无法明确固定时拒绝，不能声称运行时自动证明任意 Python 的闭包。只留非秘密材料；不传个人配置或模型凭证给数据进程。

准备返回 candidate、candidate_digest、ready、run_id、result_digest；没有数据派发。先呈现实际候选与范围，再以适用授权执行 stage=apply，携带 candidate_ref={run_id,result_digest}、approval={candidate_digest,target_digest,source,text}，target_digest 取候选的 target_snapshot.digest。内容、间接文件、schema、目标物理身份或前置变化均使旧候选失效。每个候选只能派发一次；同一完整请求只返回既有回执，不新建操作重发。

实际执行固定候选字节，以固定 Python 的 -S／-B 参数运行，只继承明确非秘密环境项。派发前先保存 run／operation／资源、来源胶囊和独立 sender intent；PID 收据与数据效果分别保存。命令退出零或 stdout 自报成功不表示效果成功，必须实际读取 provider 记录和完整数据范围。

## 未知、核实和取消

超时、丢回执、进程消失或查询失败先保留 unknown。不能改 ID、删索引或恢复旧库后再发。调用 `apply --method external.reconcile`，input.operation_id 指向原操作，附准确只读目标授权；无需当前 Change 存在，不重开已封存／取消任务。核实只观察原 provider 记录和数据，不能补发原命令。后来的观察失败保留最近已确认事实，并明确新的未知观察。

仍有本地发送者／检查进程时停止接管。仅有 launch_unknown 或 foreign_host 时可提供 sender_observations／check_observations；每条按原 execution_id／command_digest／host 给准确 outcome=not_started／stopped、source／basis／observed_at，时间在实际执行窗口。有 PID 不得说 not_started，实际进程组存在始终阻止。不能凭等待时间或成功标签推断停止。

人工或外部来源用 `apply --method external.record`，input 含 operation_id 和 observation={source,basis,observed_at,scope,reported_outcome,known_effects,unknown_scope,limitations}；最后三项是列表，时间须含时区，scope 与原操作一致。声明单独保存，仍实际只读核实；没有可靠完整核实就保留保护。

`maintain --method cancel` 的 input={external_operation_id,reason} 只撤销原请求的后续派发，不终止／回滚已准入的 provider 工作，不释放未知效果及占用。随后仍能核实和记录过去事实。取消整个 Change 的旧入口不替代外部取消或核实。

确认原操作已经结束且完整范围已知后才释放外部保护。Task 检查若未完成，显式 `external.execute` stage=checks 携 operation_id 和当前具体任务方案绑定，只运行原任务检查，不执行数据命令；补偿任务同理用 external.compensate stage=checks。只读检查续接可沿已经证明同定义的任务版本关系；写候选不能重绑或跨恢复 epoch 重放。

## 补偿与最终验收

补偿使用 `apply --method external.compensate` 的新任务和新候选。stage=prepare 在上述材料中增加 compensates_operation_id。原操作必须确认终止、完整效果已知且当前实际范围仍对应；未知原效果不接受补偿。补偿只支持原确切目标／对象／范围内的明确修正，不能顺带扩目标；新 Change／Task、候选、批准及 provider 操作独立保留。stage=apply 必须批准补偿自身准确 candidate／target，不复用原写入批准猜测补偿内容。

数据操作确证成功和 Task 检查通过仅表示任务实施完成；之后另以 verify 运行实际检查及逐 AC／规格和规范审查，并明确 external_read 和对应目标授权。archive 再核对应 VER、数据目标依据和未决保护。status／导航只读已有元数据及文件指纹，不暗中查询业务数据。封存后数据变更可导致当前 verify 失败，原通过和封存历史保留。

档案恢复不回滚数据。当前保护索引、健康现库登记及选中快照的未知操作合并保留；胶囊来自准确不可变 blob，现存第三种字节拒绝覆盖。协议 16 缺失外部保护索引时停止恢复；旧 14／15 缺失索引明确 unverified，不能进行新数据派发。恢复和 maintain.recover 不发送数据或自动补偿。检查的本地元数据提交中断可按准确事件与 Task 结果观察恢复；原数据操作中断由 external.reconcile 核实，不能用本地文件恢复代替。

## 当前机制的限制

仅验证当前环境内有限同步 Python／SQLite 机制。未提供远程 provider、连接平台、任意动态代码闭包、后台／延迟接收者的核实，也未验证真实生产目标。业务项目移动造成原目标绝对位置变化时，旧候选拒绝写入，核实保留 unknown 和原身份限制；不自动重绑来源。受管工具锁不约束外部编辑器或目标数据库的其他写入者。正式 provider 扩展需要它自己的目标身份、幂等、终止及完整范围核实证据。

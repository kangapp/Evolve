# 完整档案维护

当前包提供 protocol 16／schema 4 的 maintain.backup、maintain.restore 和定向 maintain.upgrade，实际方法由完整包清单校验。维护的知识正文来自已批准版本，恢复准确旧版本不构成新知识批准；业务文件、真实数据和外部效果不随档案回退。

## 完整备份

`maintain --method backup` 只需 project_records 效果，input={}。在新运行登记后，用 SQLite 一致快照固定截点，并从快照里的不可变 blob 收集已注册配置／正式文档；方案、证据和实际留存附件位于该库。尚未保存正文的外部来源仍只有引用。业务源码、业务数据库、个人配置、旧备份及插件安装不入集合。当前未批准手改在 observed 附录保护，与 authority 分开。

返回 path、manifest_digest 和 checkpoint。保留整个目录及准确摘要；不只复制 history.db。manifest 的 pending_runs 是截点当时已开始的登记，不表示备份完成后它仍在执行。包在清单完整、SQLite／引用／blob／路径／文件摘要验证通过后才标 complete。备份不运行检查或重放业务。

当前固定上限：每份文档／观察副本 32 MiB，集合 256 MiB，另保留至少 8 MiB 空间。超限、空间不足、采集时字节变化、缺 blob 或未完成 file journal 会停止并保留不完整现场，不截断唯一证据。当日首次写入前保护复用同一完整集合；恢复后新 epoch 使用新同日保护点，旧点保留。当天已有副本仍核查新未决日志。手动 backup 是明确额外备份，不替代每日策略。

## 先方案，再恢复

数据库损坏或旧协议时，普通 status／经验读取可能失败；直接由 evolve-maintain 读取本页并调用对应维护方法，不手改库、guard 或索引绕过。status 发现活动屏障会返回 maintenance 和原请求位置线索。方案和执行都只需 project_records；其范围限已呈现的档案恢复集合。

1. 用 maintain.restore，input 给 stage=plan、bundle（现存完整目录）和 manifest_digest（原回执准确值）。只接受同项目、当前协议的完整包；校验当前 guard 与保护索引，列出准确当前字节、恢复目标、额外受管隔离清单和新旧 epoch。包内目标占用未登记用户文件时拒绝覆盖。
2. 实际呈现返回 plan 和 plan_digest。用户的具体恢复请求已覆盖该准确方案时直接继续；已有统一维护授权也可按实际范围执行，不重复索要许可。另有新决定才核对。保留“恢复不还原业务源码／数据、不重跑命令”边界。
3. 准备 input={stage:apply, plan_id, plan_digest}，使用方案回执的 project_id／expected_workspace_epoch；**调用前生成并保存唯一 request_id**，把完整请求写在本项目 .evolve-local/control/requests。调用 maintain.restore。不得在结果未知时生成新 ID。
4. 屏障先阻止新受管写入，核实旧执行实例、检查进程组及打开的 SQLite 连接已停止。当前环境通过 lsof 核查；观察不可用则拒绝换库，不用超时或 PID 年龄猜停止，也不杀用户进程。正式换库前保存当前原始 DB、sidecar、配置、正式文档和控制日志；损坏库也逐字保存。
5. 按已固定步骤替换配置／正式文档、隔离额外受管文档和旧 sidecar／file journal，再安装新库、epoch、guard 与保护索引。包外未登记用户文件留原处。每步只接纳原字节或本候选；第三种值保留并停止。核查整套安装成功才解除屏障。

恢复日志独立位于 .evolve-local/control/restores/<plan_id>，protection 是逐字现场保护，journal.json 保存原完整 apply 请求、固定步骤及进展。它们不随被恢复的库回退。维护屏障固定步骤／新库摘要和完成回执；日志被改不能扩大目标。中断后按 journal.request 重试原请求，不能从当前新 epoch 重新绑定。进程已经死亡时可清理其原短 writer lock；活跃或无法确定的实例仍拒绝。

check_observations 只用于特定 launch_unknown／foreign_host 的停止事实，字段沿[检查停止协议](protocol.md)：execution_id、command_digest、host、outcome=not_started／stopped、真实 source／basis／observed_at；有 PID 不得说 not_started，真实进程组存在始终阻止。恢复中途已安装新检查索引时，继续核对被保护的原索引及其字节，不把新空集合当原证据失效，也不补记检查通过。

## 已知外部效果与局限

control/external 的 running／unknown 引用和资源独立保护，恢复后仍 unknown／requires_reconciliation；旧库缺记录不释放它们。协议 16 的外部保护索引缺失时拒绝恢复；旧 14／15 的缺失保留 external_coverage=unverified，不能派发新数据操作。当前健康库的未知登记、当前独立保护与选中快照的未决来源合并；准确胶囊附件受保护且不覆盖冲突值。真实 sender 的进程组或未知 launch 均纳入排空，停止观察位于 input.sender_observations，格式同检查停止协议。维护仅保护来源，不核实业务效果，恢复后按[数据操作](external-work.md)另行只读核实。数据派发的机制及环境要求见[兼容说明](../docs/compatibility.md)。

受管文件保护索引只识别已登记路径和活跃本地执行，不批准内容。guard／索引不一致时拒绝从损坏库猜测集合；保留现场，用可验证的健康历史核查。旧项目缺少这些保护材料时不支持直接损坏库恢复。没有活跃进程和外部保护的可核事实，就不能放宽为在线恢复。外部编辑器不受工具锁保证，重新核对字节可阻止相关覆盖。

分叉双方分别保存完整包和现场，不自动合并库或选分支；恢复明确选择一个准确包并更换 epoch，之后重新核对业务现场。Git／档案恢复不回退业务数据，不构成重新执行外部操作的许可。恢复保留历史测试事实，但不说明当前工作目录仍满足它；恢复后由原 owner 只验收或按实际新指令修复。

## 14／15→16 定向升级

保留与旧项目 protocol 14 或 15 匹配的完整包。普通 init、安装和读取不迁移旧档案。健康 protocol 14／15 档案先由兼容包处理未完运行／file journal／检查；关闭所有旧执行和连接。

调用 maintain.upgrade，input={stage:plan}，呈现准确原字节、协议与新 epoch；再用同样的 plan_id／plan_digest 和预存完整唯一请求执行 stage=apply。先保护旧原始库／sidecar／资料，再从一致副本更新 protocol、package_version、epoch 与新检查点并安装保护索引。原历史与正式正文保留；不支持任意未来迁移、不清库或改业务文件。旧写入器的新请求与旧 epoch 重试均被拒绝。升级中断沿同一日志恢复。

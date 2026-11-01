# IMP-013：具体数据操作、未知核实与补偿

前置：[IMP-012 当前 Codex 门槛](../imp012/stage-gate-codex-alpha23.json)已通过。沿[实际统一授权](../continuation-authorization-20261101.json)实施、临时受控验收及同范围必要复验，不重复逐切片询问。不执行用户真实生产数据，不改个人配置／凭证，不启动嵌套代理，不发布／部署。

## 理解与取舍

本轮要证明真实受控目标发生数据修改及其核实协议，不能用模拟返回或只登记 operation 代替实际派发。采用现有项目 argv 入口、明确有限的执行材料清单以及单个本地 SQLite 目标核实方式；不建设通用云数据库／连接器平台。正式连接方式没有接入时明确 unsupported，不把受控通过称真实正式环境已通过。

SQLite 目标位于当前受控项目，业务数据不进入档案恢复集合。目标身份包含解析后的实际路径／文件身份、项目机制提供的稳定目标标识和 schema／相关前置；名称或配置别名不是身份。执行入口、间接 SQL、辅助脚本、非秘密配置／参数、cwd 和解释器均绑定候选摘要，冻结到私有材料目录执行。凭证只允许引用，不入候选／日志；本轮受控目标不使用凭证。宿主须实际审阅有限读取闭包及解析目标，无法固定或枚举的动态依赖拒绝派发，而不是声称自动证明任意程序安全。

公开动作仍归 apply.external.execute／reconcile／record／compensate；prepare 只保存并呈现具体候选，批准准确候选和目标后 apply。派发登记、外部保护索引与维护屏障共用原短 writer 临界区；真正命令在事务外。既有 operations／events／blob 能保存候选和追加观察，优先复用，不另造第二套业务历史。必要的新执行约束用 protocol 16 隔离旧写入器；schema 是否增加，以实际存储缺口决定，不为预期扩展建表。

维护升级只提供本轮实际支持并验证的定向版本路径。alpha.23／protocol 15 的完整受检包保留，不能把普通 init 改为自动迁移。恢复时保留当前未决保护引用、固定核实依据和资源；缺失／冲突标为需核实，不能从旧库没有记录推断安全。

## 有依赖的实施任务

1. **固定候选与目标**：设计小的候选准备接口，绑定准确 argv／解释器／cwd／所有声明的间接材料／参数、实际目标身份、数据对象／范围／前置、核实办法、幂等支持及限制、可选关联原操作。只保留真实非秘密输入，保存并呈现具体候选；未批准不执行。验证入口／间接 SQL／helper／别名配置／目标 schema 或文件替换使旧批准失效；无法完整固定拒绝。
2. **登记与真实派发**：准确批准后，先保存 run／operation／稳定 idempotency_key／执行实例／资源和独立未决保护，再准入并实际启动本项目机制。记录调用信号和 provider 引用，输出有界且脱敏。明确进程退出零不是效果成功。验证保护写失败不派发、双边登记故障保留未知、同请求不重复执行、相关资源受阻而其他目标可继续。
3. **未知、取消和核实**：超时／进程消失／回执丢失先 unknown，不生成新 ID 重发；reconcile 只追加与原操作／目标／范围对应的实际只读观察。SQLite 的 provider 记录与当前数据对账必须分开，已知部分、未知范围和确证终止分别保存；无可靠核实则保留限制。取消／failed 不释放未知效果，维护与恢复不派发原命令。验证真实部分提交、丢回执、仍运行、查询失败、错误对象／旧观察不能解除保护。
4. **补偿与恢复竞争**：补偿是关联原操作的新候选／新 external_write，具体范围和批准单独核对；原授权确实包含准确补偿才复用。验证只补已查明范围，不重做已完成部分；备份恢复不能删除当前 running／unknown 的引用和依据。用真实子进程故障演练派发 admission 与维护屏障竞争、旧执行者未退不换库、换库后旧 epoch／generation 不派发。
5. **工程与原生验收**：usage 增加本地受控数据操作／未知核实案例，troubleshooting 加超时／部分效果／补偿与升级说明。完整包先组件、公共 CLI、实际旧包兼容及隔离安装，再冻结具体临时材料由当前默认 Codex 执行新会话；主审复核真实目标、实际调用／数据、原始失败和保护事实，通过后才进入 IMP-014。

重点 V-036／103—105／113—116。本轮有实际目标修改及实际故障注入，不能只用受控引用替代。外部实际效果与整体业务验收仍分开；最后由 verify 按真实业务条件判断，restore／reconcile／补偿本身不冒充业务通过。真实正式环境接入、额外 provider 与后续通用能力作为交付时明确限制／开放问题，不由本轮测试推断。

## 当前具体设计（候选材料模块之后）

材料模块已新增但公共 external 方法仍 unavailable。当前只有私有收集／冻结／只读目标观察接口，不能称派发已实现。初步六项真实组件测试在 material-components-first.txt；尚未跑 alpha.24 全量，也未冻结或调用本轮模型。

下一步候选记录复用不可变 artifact/blob 与原 phase_run，不先新增表。具体执行候选应同时冻结：target（SQLite 路径／environment／对象／scope／稳定身份查询）、execution（Python 入口 argv 的 `{target}`／`{operation_id}` 准确占位、cwd、全部文件及实际闭包审查）、前置查询／准确预期、provider receipt 的只读 SQL、实际完整范围效果查询与预期、能力限制／可选补偿关联。每个 prepare 有独立候选身份，准确批准仅允许一次派发；同请求回放原结果，新请求不能重用同候选重发。

实际运行是冻结 Python 文件、helper、alias 配置和间接 SQL，使用固定解释器，去掉 PYTHONPATH／用户 site 影响；目标用解析后的明确绝对参数，机制须在自己的事务内核对目标／前置并实现声明的 provider 幂等键。运行时不声称从任意 Python 自动证明完整闭包；不支持未枚举的绝对读取、动态目标或脱离进程组的延后／后台工作。实际 provider 收据与当前数据效果分别核实，退出零或纯 stdout 声明不充当业务成功。

拟用 control/external-records/<operation_id>.json 保存不可变非秘密候选／授权／原身份胶囊，control/external 只保留未决引用、胶囊摘要、资源和 sender 保护，不维护第二业务历史。胶囊／冻结材料不随恢复替换；候选正文也进入 prepare 的不可变 blob。丢失原 DB 记录后 reconcile 可以按被保护胶囊在新 epoch 追加“恢复未决保护来源”登记，不能伪造旧 run 存在或继承新的写权限。

sender 在实际 Popen 前持久 intent，之后持久 PID／进程组。外部 sender 不是业务检查：不要把外部命令退出写成 tests passed。维护排空同时检查这些 sender：alive 或 launch_unknown 均不换库，除非已有准确停止证据；本地发送者结束且外部 running／unknown 仍保留时可以保护后恢复。部分提交／超时／丢回执先 unknown，单独 reconcile 只读核实，绝不重发。confirmed failed 只有确证终止且完整范围效果已知才可释放；failed／取消标签本身不释放。

维护取消可通过明确 external_operation_id 扩展现有 maintain.cancel 的分支，取消仅撤销后续派发；不能把已发送效果变为未执行。关联 Change 的外部未决也要阻止普通取消释放。补偿关联原操作但生成新候选／新操作，独立明确批准，保留原部分效果及未知历史。实际 receiver/provider 机制本轮限本地 SQLite，正式 provider 适配作为明确交付局限。

## 当前实现／尚需关闭的门禁

开发包现为 alpha.24／protocol 16／schema 4；外部公共方法仍 unavailable，不是本阶段完成。external_material、external_registry、external_process、external 与 external_work 已形成私有调用链，实际临时 SQLite 测试覆盖冻结间接材料、具体读写授权、一次派发、回执丢失后的保护与只读核实、恢复旧包后由胶囊登记来源、已确认事实不被新观察失败覆盖，以及 Change／Task 的真实检查→verify→archive／封存后数据变化。

数据操作按 design 共用 Change／Task／Verification，不能只登记 operation。简单／复杂 Task 明确 execution_kind=external_write 和 external_target，普通文件 apply 拒绝完成该类任务。候选可保存当前工作绑定；公开外部写入必须有当前 Change／REV／Task／定义／具体方案绑定。已知数据效果与 Task 检查分开：未知后 reconcile 只观察，之后显式 execute stage=checks 仅继续任务检查，不派发旧数据命令。真实数据检查和最终 verify 的数据观察均需实际 scope 授权。

全量首次 protocol16 回归正在执行，尚不写成通过。真实 alpha.21／14 和 alpha.23／15 兼容包按当前显式 14／15→16 升级脚本演练。当前仅开发包，未冻结本阶段、未发本阶段模型请求。

继续实现必须关闭：

- **恢复／sender 协调**：require_drained 尚未接 external_registry.require_senders_stopped；新数据 sender 的 alive／launch_unknown 必须阻止换库，原停止观察及胶囊应随保护现场核对。当前 managed 保护索引已带 protocol_version，用于区分旧15受控引用与16实际派发。实际派发后索引缺失不能按空集合放行；允许明确 unverified 的旧15限制不应让16失去 sender 保护。
- **选中快照自身的未知外部操作**：当前恢复只保留当前 control/external；必须同时从选中16快照的 external_write operations 及不可变 external_capsule blob 提取未决引用，与当前保护并集且核对同ID／摘要／资源冲突。当前更晚已确证终止也可以保守再核实，不能把旧快照 unknown 直接清掉。胶囊已在注册事务写入 artifact/blob，完整包实际保存该唯一附件。恢复前保护胶囊原字节，必要时从准确 blob 新建缺失胶囊；第三种现存值停止覆盖。未能证明快照旧 sender 退出时不换库，不把“截点尚未准入”推断为其以后不会派发。
- **取消／补偿／人工观察**：尚未实现 external.record／compensate 和 maintain.cancel 的 external_operation_id 分支。撤销只阻止后续派发，记录过去事实用 observation_gate 而非写入授权门禁；未知占用不得清掉。补偿需原终止／完整已知范围的当前确证，另有候选／实际具体批准及自己的 Change／Task；人工来源先保留其声明与边界，不用一个成功标签替代实际核实。
- **工作续接**：当前 stage=checks 的元数据 operation 需接已有 maintain.recover 的明确事件核对，不能在仍有旧检查进程时释放占用；resolve_operation 已保守检查原始 started run 的 pending_checks。跨同定义 REV 的只读检查续接应使用已证明 origin_tasks 关系；写候选仍不得重绑或跨旧 epoch 重放。source task result／当前外部目标的 recorded_complete 不在纯 status 运行 SQL；真正 verify 单独观察数据，archive 再核保护及准确 VER 数据依据。
- **公共入口／文档**：CLI 尚未注册 external handlers。execute／compensate 需要现有任务准备；reconcile／record 是按 operation 的观察，不强制当前工作项存在或重开已封存／取消任务。准备回执需返回实际 result_digest 供精确 candidate_ref。目标／数据范围与阶段边界在共享协议、apply／verify／archive／maintain Skill 中单一维护。

### 已修复的恢复字节窗口

在本轮整合补测中发现，原 restore 在校验完整包后到复制 DB 前存在窗口：更改备份 DB 后仍可安装其有效但未批准的 blob。实际 red、插入真实有效 SQLite 内容的探针和 green 分别在 restore-payload-race-*-alpha24。现在 candidate_database 必须核对复制件与选中 manifest 数据库摘要（升级使用明确保护来源摘要）一致后才改 epoch／安装。alpha.23 冻结物不改，后续回归必须包含此新断言；不得只依赖此前 gate 的旧并发覆盖。


## 冻结候选前的补测结果

以上“尚未关闭”是开发时点记录，目前已实现公开四 external 方法／具体 Task 绑定、取消原请求的未来派发、来源报告单列与实际探针、关联原操作的新补偿。新增 external_recovery 模块合并健康现库、当前独立索引及选中快照的未知登记，sender 排空接入维护；缺失16索引拒绝恢复，准确胶囊从 blob 新建缺失附件，第三种值停止。派发已登记但独立索引尚未写入就退出的窗口也保留来源。主锁原持有者真实死亡后可接管旧短锁，仍核查独立 sender／检查进程；不会按锁年龄推断停止。

真实四个恢复缺口 red、dead-writer-versus-sender 对照探针、登记／准入／存活 sender 子进程故障、真实部分提交及提交后超时均保留在本目录。外部专项63项通过；另同定义 REV 真实续接7项通过（与63项重叠，不相加），只读检查沿已证明来源继续，旧写候选仍拒绝重绑。stage=checks 已提交后真实 os._exit 的维护恢复核对原事件和 Task 结果，不重跑数据或检查。

首轮协议16全量604项通过；公开入口首轮614项只有旧方法清单断言未更新，第二轮622项只有新增共享文档引用未随包发布的源码设计页而断链。分别修正准确能力断言与 source-only 导航，22项包测试已通过。当前第三轮完整回归仍执行，不能写成通过。

六场景公开CLI源包及冻结包均21次实际调用通过；两份真实旧包alpha21／14、alpha23／15分别8次定向升级／拒绝演练通过；八Skill校验及两宿主隔离安装发现通过，均未调用模型。当前冻结运行包、控制器、准确scope及后续六会话边界见 model-acceptance-plan.md；当前本轮模型尚未派发。开放限制包括真实正式环境、远程 provider、动态／后台机制与业务项目位置改变后的原目标核实，不由本轮受控结果推断。


## 当前冻结候选与原生执行

冻结源摘要8daa8949bc84ee6e1ccfc5fe644a1c61ed1d73f163265361ebb8d134ff4b2981，运行包ebe4bb163e3c92f60149414d2bd1ee0ac77aa956c663d8aaca4ed3f217dddb7e，80资源。第三轮625项完整回归139.464秒通过；晚加的真实双进程 admission 竞争、提交后本地回执前退出、Popen 后PID登记前退出、另一Change不能绕过未知及另一真实provider仍可用，已一起纳入70项外部专项11.308秒通过。最终含全部补测的全量正在执行；方法级证据与实际源摘要见 acceptance-map.json，不能相加重叠测试数。

冻结公共六场景21命令、真实21／23旧包各8命令、两个宿主隔离安装（均未调用模型）及8个Skill检查通过。当前本轮已按准确scope派发默认gpt-6-astra六新会话；前四个会话通过控制侧界面，但主审轨迹语义复核与后两场景仍待，不能称阶段完成或进入IMP-014。准确运行位置在/tmp/evolve-imp013-native-model-alpha24-current.json，沿原句柄继续观察，不重复启动。


## alpha.24 暂停门槛、alpha.25 修复复验

alpha.24 最终631项全量138.843秒通过，但不包含随后新增并实际失败的来源冲突用例，不能据此标阶段通过。真实探针表明 DB 原候选仍要求20，保护副本被改成19且更新自洽摘要后，reconcile 错报 succeeded 并清占用。正确假设为选择保护副本而未对比可用 operation 已登记来源；原DB原依据未变，也不是旧结果回放。当前新增 require_recorded_reference，核实／取消对比原胶囊摘要和资源，真实胶囊的独立资源／原epoch也须匹配；冲突不覆盖、不核实错误判据、不释放unknown。修复用例green及原始red／probe均保留。

原生alpha24实际5会话／76命令，前四父检查通过；第五模型在restore之后正确因控制侧“不做新备份”与新epoch首写自动保护冲突而停止，未调用reconcile，第六未派发。当前只澄清不额外手动backup，不能关闭自动保护，父检查补充手动backup身份不增加。alpha.24原始失败zip／审阅held记录与冻结包不变。

当前开发及冻结候选alpha.25／protocol16／schema4，业务六场景及实际副作用范围不变；源码6d1218ad483e35a16be466e8b3b83b2943b99f47ab5f520b5b92e4b88a320707，运行包993711f866cc2e85873fefee222c117555bc4fef0b940e435d80b12df89d9ee6。已准备完整回归、同包公开6场景／旧包兼容／隔离宿主复验。原生具体方案改为当前 model-acceptance-plan.md，旧方案另保留model-acceptance-plan-alpha24-held.md。尚未派发alpha.25模型，门槛仍未完成。


## alpha.25 当前验证截点

633项完整回归140.451秒通过，含来源冲突／核实与取消、独立资源冲突和全部派发／维护真实进程补测。按同一993711f866cc2e85873fefee222c117555bc4fef0b940e435d80b12df89d9ee6冻结包，公开六场景21命令、真实alpha21／14与alpha23／15各8命令升级／拒绝、两宿主隔离安装／发现均通过。来源5项专项与澄清自动保护后的两项原生控制侧测试通过；这些不是模型语义通过。当前34个实际V方法引用全指向本轮633完整日志，来源归档acceptance-test-sources-alpha25.zip。

当前alpha.25六新会话已开始，准确scope2365752e4dd9374ce316ce22b376a7ad0f1a96bfe6e6979fd4b7b92267db7f14，仍由实际model/list账户默认选择。句柄84698，位置/tmp/evolve-imp013-native-model-alpha25-current.json。原句柄持续观察，不因工具观察超时再开同一批。功能报告functional-validation-alpha25.json仍标原生门槛pending；IMP-013未完成、IMP-014未开始。


## 结束截点

alpha.25六新会话／82命令完成，主审检查全部命令、六条最终报告、真实provider三条收据、来源胶囊／批准摘要、恢复保护／新epoch、原run缺失未伪造、原data20实际returncode1及当前blocked、历史passed和archived保留、无pending／claims／started。原始summary保持review pending／passed false，不回写伪造原生语义通过；独立主审review和stage-gate-codex-alpha25.json持有结论。原始zip e80708838ab31b182bb6997aa8d52752d8ffa9c03671b00733b231e3df0bee73，1,416,520字节。当前IMP-013按Codex范围通过，进入IMP-014；总体goal未完成。

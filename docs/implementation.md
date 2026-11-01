# Evolve 实施与验收记录

设计基线0.6.2；当前完整本地首版 **0.1.0**（protocol16／schema4）。IMP-001—IMP-014按所记录的当前环境与宿主范围完成，最终[阶段门槛](evidence/imp014/stage-gate-010.json)、[140项映射](evidence/imp014/acceptance-map.json)及[交付说明](evidence/imp014/final-delivery.md)分别保存实际依据。高级阶段沿用户Codex优先范围；最终Claude当前包四场景代表路径通过，第五场景真实429停止，后续三个场景由Codex在同一临时项目接续完成，不宣称Claude七场景全部通过。当前642项回归通过；原失败、未运行范围及历史候选均保留。用户已明确只要求当前环境可执行，其他平台不作为门槛。当前仅本地／私有交付，未公开发布或替用户安装到个人配置。文档校验不代替功能验收。

| 阶段 | 切片 | 状态 | 门槛 |
|---|---|---|---|
| M1 | IMP-001 | passed_current_environment | 两宿主安装／发现及当前环境含空格／中文路径、整包移动已验证 |
| M1 | IMP-002 | passed_current_environment | 同包双宿主实际闭环通过，当前环境完整回归 244 项通过 |
| M1 | IMP-003 | passed_local | 当前 11e3 包两宿主对应场景复验通过；零测试退出 0 仍 blocked，原 alpha.3 缺陷保留 failed |
| M1 | IMP-004 | passed_local | 244 项回归；同一 11e3 完整包两宿主各五新会话、父检查与轨迹复核通过，文案／拒绝探测限制保留 |
| M1 | IMP-005 | passed_current_environment | 当前 11e3 包双宿主生命周期 36 检查／42 条命令通过，保留旧写入器拒绝 |
| M2 | IMP-006 | passed_current_codex_scope | 同一 alpha.14 包 Codex 七场景及实际语义复核、479 项回归通过；依用户最新“先按 Codex 验收”推进，Claude 429 保留为未通过，见阶段门槛记录 |
| M2 | IMP-007 | passed_current_codex_scope | 同一 alpha.14 包 Codex 九场景及 152 条命令复核、5 次正式应用／4 个封存项通过；当前依用户范围收口，Claude 未派发事实保留，后续组合分支仍按对应切片验证 |
| M2 | IMP-008 | passed_current_codex_scope | 同一完整 alpha.15 包五新会话／61 条命令及语义复核、499 项回归、15 条公共 CLI 通过；SQL／数据范围／有限关系／底稿导出／变化后只验收闭合，见[门槛](evidence/imp008/stage-gate-codex-alpha15.json) |
| M2 | IMP-009 | passed_current_codex_scope | 完整 alpha.18／protocol 14，534 项回归、136 条 CLI、Codex 七会话／149 命令及语义复核通过；见[阶段门槛](evidence/imp009/stage-gate-codex-alpha18.json) |
| M2 | IMP-010 | passed_current_codex_scope | 完整 alpha.19，542 项回归、46 条 CLI、Codex 六新会话／152 命令及实际语义复核通过；见[阶段门槛](evidence/imp010/stage-gate-codex-alpha19.json) |
| M2 | IMP-011 | passed_current_codex_scope | 完整 alpha.21，549 项回归、238 条 CLI、八新会话／104 命令及语义复核通过；见[M2 门槛](evidence/imp011/milestone-m2-codex-alpha21.json) |
| M3 | IMP-012 | passed（当前 Codex 范围） | 完整 alpha.23：574 项全量、16 项当前恢复补测、162 条公共 CLI、真实旧包 8 命令及四新会话／51 命令；[阶段门槛](evidence/imp012/stage-gate-codex-alpha23.json) |
| M3 | IMP-013 | passed_current_codex_scope | 完整 alpha.25：633项回归、21次公开CLI、真实旧包各8命令、六新会话／82命令及语义复核通过；[阶段门槛](evidence/imp013/stage-gate-codex-alpha25.json) |
| M3 | IMP-014 | passed_current_environment_and_declared_host_scopes | 642项回归；当前包双宿主代表路径、Codex跨宿主尾部及语义复核；138项有效要求通过、2项明确退出；见[最终门槛](evidence/imp014/stage-gate-010.json) |

## IMP-001 具体实现方案

产物：当前仓库根、八 Skill 和单份 shared／runtime；Codex 兼容清单与 Claude 清单、各自本地市场；Python 完整包构建／摘要检查；纯读 status／doctor；必要用户与开发说明。公共清单随实际本机兼容性验证，不依赖未实测入口。

验证：独立输出包从非工程 cwd 读取资源；两个实际宿主在隔离配置与临时项目安装并发现八 Skill，核对项目范围；移走原始分发目录后缓存能运行 doctor；缺资源、版本混用、未知 schema、身份冲突和未知动作均准确报错且不写目标项目。保存实际命令／结果与限制，不调用模型或把静态检查当模型行为验证。

实现先开放只读能力，其余方法 UNAVAILABLE；之后的接入与业务表按所需切片增加。用户已批准既有复杂方案及依赖，本实现方案是 IMP-001 的工程落地说明，不扩大业务范围。

## 阶段问题与修复

IMP-001 集中修复并复验：

| 发现 | 修复与证据 |
|---|---|
| Codex CLI 安装默认为用户级 enabled=true | 说明中增加关闭用户级、仅开启项目配置的步骤；真实 app-server 两项目对照，目标发现八 Skill、另一项目发现零个 |
| SQLite mode=ro 在 WAL 模式下可能修改共享内存文件 | 只读查询在临时字节快照中打开 SQLite，前后核对源；WAL 已提交数据与目标文件无改动均有行为测试 |
| 源码文档中的设计／开发导航不属于运行包 | 构建时移除明确标注的源码专用导航，测试运行包全部本地 Markdown 链接闭合 |
| 缺内核时启动器原本抛 import traceback | 启动器给明确 PACKAGE_INCOMPLETE 诊断，缺内核测试通过 |
| 同名散装 Skill 与插件版可能重复发现 | 只读诊断报告来源并保留文件，实际冲突行为测试通过 |
| macOS /var 与 /private/var 的同一目录造成测试路径比较失败 | 测试使用规范化路径，修正断言而非修改产品结果 |

实际证据：[两宿主摘要](evidence/imp001/hosts.json)、[原始宿主命令](evidence/imp001/host-commands.json)、[Codex 项目范围对照](evidence/imp001/codex-scopes.json)、[20 项行为测试输出](evidence/imp001/package-tests.txt)。独立发行包摘要为 387f52841f0571ef75e66963eac3dfcf7cac0a78cf804ab190e0a275a2992d23，源码包清单摘要不同（源码专用导航被移除），两者分别校验。

本机环境为 macOS、Python 3.11.9、Codex CLI 0.154.0、Claude Code 2.1.117。Claude /skills 由本地交互界面打开，未发送模型请求；Codex 使用实际 app-server skills/list。八 Skill 通过 skill-creator 的 quick_validate；验证器所需 PyYAML 仅安装于临时开发校验环境，不成为插件依赖。

规格自审：IMP-001 所需包、只读能力、两宿主发现与资源定位有直接证据；V-019／025／029／062／065／131／132／137—140 仅对当前开放分支有证据，V-131 业务小闭环待 IMP-002，V-137 原生 Windows 仍 not_run，不将整个 V 编号标 passed。规范自审：Python 标准库、确定性 owner、单份 shared／runtime、源码与目标资料隔离符合当前规范。实际审查者为当前 Codex，自审不称独立审查。

## 开放问题

公开发行许可证尚未选定。当前保留权利，仅作本地／私有开发验收，不公开发布。最终公开许可与市场上架在所有阶段完成后讨论，不影响当前工程与受控测试推进。

## IMP-002 具体实现方案

在当前包增加显式 JSON 请求入口，内部生成 request／operation 身份；以 project_meta、run、operation、Change／REV、Task、artifact／版本、验证与事件支撑一条小修改路径。初次接入只建立记录设施，不自动批准正式知识。方案呈现与接受、修改授权、检查结果分别保存；任务级实施与整体验收分开。

文件和库写入采用先登记、原字节／候选、短事务、写前摘要核对与 finalize 的可恢复协议；第三种内容保留冲突，不重放命令。写入保护与功能一起实现，幂等重试返回已有事实；只读入口仍不写项目。测试必须覆盖接入中断、重复请求、旧版本、外部编辑、检查失败、审查发现、完成前变化以及最小知识批准边界。

通过真实临时小项目复现失败行为、实施修复、运行相关测试和两维自审、验收与封存；随后从安装缓存运行同一路径。M1 的原生 Windows 覆盖缺口继续保留，在 M1 完整门槛核对前不能进入 M2。

### IMP-002 早期组件验证（历史截点，尚未完成切片）

- 文件协议：原字节／候选先写 journal，前置摘要核对、第三值保留、多文件部分执行续接、保留原可执行权限；内部 operation 路径及 POSIX／Windows 驱动器逃逸均拒绝。
- 短锁与 SQLite：真实子进程非正常退出后仅显式恢复死锁；活进程不接管。请求幂等、同 ID 异输入、旧 epoch、终态结果不可改、事务回滚及 guard 历史回退检测通过。
- 初次接入：建项目库前已有固定 init journal；配置已写而库安装中断后按原 project／run 身份恢复；第三方配置保留。项目名按 TOML 正确引用，检查只配置不执行，不自动建立正式知识。
- 短方案：保存实际呈现文本、范围、验收、检查依据、Task 定义及观察版本；propose 不隐式接受或修改业务文件。编号不因幂等重试重复分配，内部记录／宿主配置不走普通业务写入。
- 首次写前保护：按 UTC 日收集一致 SQLite 备份、配置和必要登记资料，外部字节另列保护附录；损坏备份、未结束 init 或文件 journal 阻止新写入。新增回归先真实复现“已有每日备份掩盖后续未完成 journal”，再调整核查顺序，复验通过。

实际 [63 项组件／运行包测试输出](evidence/imp002/component-tests.txt)通过；这些是临时目录与库中的组件证据，不是宿主业务全流程验收。该历史截点 CLI 仍只公开 status／doctor；当时 connect、plans、store、backup、workspace 尚待组装，未将内部 API 测试冒充公开业务功能通过。当前能力见下文。

该截点的后续工作为接通小修改闭环及必要保护；现有进展、故障修复与剩余门槛见下文。63 项输出保持历史原件，不能当作当前构建的全部验收。


### IMP-002 当前工程与公开工具路径

当前包为 0.1.0-alpha.2，实际开放十个方法：status.show、maintain.doctor、init.connect、propose.create、apply.implement、verify.run、archive.close、init.baseline.propose、init.baseline.apply、maintain.recover。八 Skill 保持单份 shared／runtime。未开放的复杂 spec、独立调查、跨会话学习和完整档案恢复仍返回 unavailable，不以当前小流程代替后继切片。

- 公开 CLI：独立构建并搬移到含中文／空格的安装路径，从非源码工作目录执行接入、方案、修复、真实单元检查、验收和封存；内部身份及版本由准备步骤生成，重试保留原绑定。仅仅 implemented 不代表整体验收通过。
- 增量 init：沿用项目身份、Change 与 Task；配置变化先返回具体候选，呈现后按原摘要应用。按检查 ID 合并并保留未改字节、注释及未知段落；不能无损定位时拒绝模板覆盖，配置与恢复均不执行检查命令。
- 知识：初次基线的候选、具体批准、应用与文件版本分别记录；方案展示不写正式文件，archive 不隐式批准知识，项目待审候选保持可见。
- 文件与检查：每次写入前核对身份、epoch、包、资源与字节依据；长命令在短锁及事务外执行。Task 检查和整体验收分开，规格／规范审查绑定实际现场，旧必需发现需有引用和新依据才可解决。
- 中断：真实子进程在登记、journal、文件提交、Task 完成、验收提交及封存提交边界非正常退出。恢复只登记确定事实，不重跑检查；未提交验收 blocked，已提交验收与封存保留。已有 Task done 和证据不会因补齐回执被抹去。

### 本轮问题、修复与证明范围

| 实际发现 | 修复及复验 |
|---|---|
| 调用者可在 run 开始后修改原请求的 files 数组，扩展已授权输入 | 请求归一化深拷贝；先真实复现额外文件被写入，再验证原绑定不可变 |
| 事实提交后仅 guard 回执失败，错误分支可能再次 finish 或改写既有结果 | 先检查原 run 是否已封口；保留已提交事实，返回需要核实的回执错误 |
| 长期打开的两个 Store 可能从旧 head 形成检查点分叉 | BEGIN IMMEDIATE 后重读当前 head；核对 lineage、数据库文件身份，循环祖先链明确拒绝 |
| 相同数字 schema 的旧／不完整结构仍可能进入写入口 | 校验必需表及执行身份字段；只读诊断保留现场，拒绝写入，不清库或隐式迁移 |
| 主进程退出后，独立 session 中的检查子进程仍可能执行，恢复原先会提前释放占用 | 派发前、实际 PID、结束分别落事件；真实控制进程退出的回归先失败后通过。仍有进程组或缺启动身份时拒绝恢复，status 显示具体待核实执行 |
| verify／archive 提交后、回执前退出缺少记录收尾路径 | 增加只收尾元数据的恢复；已提交事实与证据保持，未提交验收不补造通过；四个实际进程退出用例通过 |
| 检查输出及候选可能包含环境中的已知凭证 | 持久输入／候选拒绝已知凭证，实际命令输出脱敏；受控凭证用例验证未泄漏 |

上一受检构建的完整行为／运行包测试为 **133 项通过**，包清单检查和设计文档检查通过，见[当前构建验证记录](evidence/imp002/runtime-validation-alpha2.json)。这些测试使用临时项目与库；已记录的真实检查退出码与受控审查输入分别保存。当前 Codex 对规格与规范的检查是自审，不能称独立模型审查。

### 两宿主安装缓存复验（上一受检发行包）

[两宿主摘要](evidence/imp002/hosts-alpha2.json)、[实际宿主命令](evidence/imp002/host-commands-alpha2.json)、[Codex 项目范围](evidence/imp002/codex-scopes-alpha2.json)、[业务项目发现](evidence/imp002/codex-business-scopes-alpha2.json)已保存。该受检独立发行包摘要为 `fd1893ecc01054b59ac1b25324443b3ca3e229ba8645de667a8e19450eca6139`，源码清单摘要为 `57cc3eee90a6ecdcfbe3504758353770ca0fd3677fe778384b0e3513cf7544d4`；差异来自构建时剥离源码专用导航，两者分别校验。

此前受检构建的本机 Codex CLI 0.154.0、Claude Code 2.1.117 均安装并发现八 Skill；项目启用范围对照、移除下载副本后缓存 doctor 均通过。该截点只验证独立缓存，Claude 原生模型实际仍依赖其登记安装根，不能据此声称原生加载缓存。两个业务项目各自在宿主中启用并发现插件，再从各自真实安装缓存调用公开 CLI，完成失败算术示例 → 修复 → 实际检查 → 受控验收 → 封存 → 初次正式基线具体批准与应用。增量配置先呈现后应用，保留未知段落，没有运行额外配置的检查。

[Codex 业务摘要](evidence/imp002/codex-workflow-alpha2.json)、[CLI 命令与结果](evidence/imp002/codex-workflow-commands-alpha2.json)及 [Claude 业务摘要](evidence/imp002/claude-workflow-alpha2.json)、[CLI 命令与结果](evidence/imp002/claude-workflow-commands-alpha2.json)明确记录：没有发送模型请求，review 输入为受控夹具观察，不是独立模型审查，也未验证自然语言自主编排。该结果不能直接将 V-131、V-139 或整个 IMP-002 全量标记通过。

### 当前收口顺序与剩余门槛

1. 上一构建的两宿主安装与受控工具闭环已按上文保存；后续代码或运行文档变化重核受影响路径，旧构建证据不自动覆盖新内容。安装／发现、缓存内 runtime 行为与自然语言模型编排继续分别记录。
2. 启动身份未知的检查已增加具体确证登记与收尾：执行 ID、命令摘要、主机和观察时点绑定，不能覆盖系统观测到的在运行进程；实际控制进程退出回归验证恢复不产生检查通过证据。跨主机原控制执行尚不能在当前本地恢复路径接管，继续保持限制。
3. 按 IMP-002 对应 V 的适用分支逐项收口，核对自然语言请求、实际方案呈现及用户指南；受控审查输入不替代未执行的宿主模型编排。只有必需分支通过才进入 IMP-003—005。
4. M1 汇总五个切片及跨会话、经验复用、升级卸载和真实平台证据。**V-137 原生 Windows 仍 not_run，M1 未完整通过，M2／M3 未开始。**

上述待完成项属于既有实施范围；许可证和公开分发渠道仍留最终汇总讨论，不改变当前本地／私有验收范围。


### IMP-002 进一步收口：实际模型与已复现问题

已获用户明确授权，在隔离临时项目中启动 Codex 与 Claude 的真实宿主模型，执行只调查、完整修复、只验收三个场景。当前不把模型退出码或模型自述直接当作通过；实际请求、工具轨迹、源码／独立断言、SQLite 事实及限制分别核对。[模型验收方案](evidence/imp002/model-acceptance-plan.md)与[28 项 V 分支映射](evidence/imp002/acceptance-map.json)已保存。

第一轮模型都完成修复并捕捉封存后受控外部回退；Codex CLI 原配置的模型被当前登录账户拒绝，失败终态单独保留，随后采用 model/list 给出的账户默认模型 gpt-6-astra，未改个人配置或复制凭证。Codex 以官方 app-server 显式 Skill 输入加载隔离安装缓存；Claude 使用本地目录市场。两者的实际加载方式分别记录。

首次人工核对发现两项必需问题，详见[首轮模型复核](evidence/imp002/model-review-first.json)：Claude 从原始分发目录原位加载；模型还使用了项目外固定临时 JSON 文件。移走原分发目录后，Claude 本地 /skills 实际发现零 Skill，说明此前“缓存中可直接运行 doctor”证据不足以证明宿主模型不依赖下载目录。该缺口不被早期 passed_local 表述豁免。

本轮修复：本地安装先将完整包复制到需保留的稳定安装根，市场注册该根，原始下载独立移走；安装指南及两宿主演练同时调整，明确 Claude 的原位加载与独立缓存副本各自作用。请求协议优先标准输入，必要暂存使用项目控制区中的本次唯一文件；宿主提供实际 Skill 路径，避免遍历个人目录猜根。修复后的实际模型复验正在收集，不能将旧构建结论倒填到新包。

组件审查还补齐了以下已复现分支：

- 目标 status 公开实际短方案、Task 定义、批准文档导航与待审候选；源文件字节／mtime 前后不变。历史验收显示 recorded_status 与 unconfirmed 适用性，不把旧 passed 变为当前结论。
- 未知启动可采纳与执行、命令、主机、观察时点绑定的具体停止／未启动确证；仍观察到进程组则拒绝接管。登记确证不产生测试通过或任务完成。
- 纯文案修正只做实际内容检查，没有 argv 测试时不要求额外的执行检查授权；有必需命令时仍拒绝无 checks 授权。复杂规格输入在短方案入口明确拒绝，不静默丢弃。
- 任务范围字节未变、仅其他业务树内容变化时，可在新的现场上实际重跑检查和审查，保留已完成 Task；不靠旧 VER 封存，也不强迫为展示变化重新实施。
- 恢复原 run 一律按契约保留 interrupted，finalized_by 关联维护结果；已提交验收可在核实维护结果后作为封存依据。已封存工作项允许新 VER 复验当前现场，原 Change／Task／历史 VER／封存截点保持，apply 仍不能重开。

[144 项构建验证](evidence/imp002/runtime-validation-alpha2-r2.json)对应封存后复验补丁之前的受检包；补丁后的相关 17 项验收测试另已通过，最终整套与宿主同包复核仍待收口。IMP-002 继续 in_progress；IMP-003 尚未开始，M1 原生 Windows 门槛不变。


### IMP-002 路径绑定与同包复验

文件别名审查先复现五个实际缺陷：目录别名绕过工具配置／正式知识边界、别名改指向后现场指纹不变，以及 prepare 后把候选写入另一个同字节文件。现已按真实目标检查权限边界，在操作事件中绑定项目内实际路径，写入及恢复前重新核对；稳定的项目内目录别名仍受支持，不用禁用全部别名缩小能力。旧操作只复用原 resource 摘要证明，不补造历史绑定；项目搬移后也不能重复领取同一实际文件。

[154 项回归与包验证](evidence/imp002/runtime-validation-alpha2-r4.json)已通过。当前源码摘要为 `14ce54bbbdcbca8c27d77141bc0bdefd27c81a7cb186da3e9a5f6cc7f8ce8d48`，独立分发摘要为 `fd5db9e16e51488ef03677924779c29ade85f929ea94c040fd1ffe654305b1f9`，两者的 Markdown 源码专用段落有意不同。

同一分发包的[双宿主安装及 CLI 业务复验](evidence/imp002/hosts-alpha2-r4.json)已通过：原始下载移除，保留完整稳定安装根；Codex 实际缓存、Claude 独立缓存以及其原生登记安装根分别核对。增量配置、正式基线具体批准与真实应用、失败算术检查至封存都完成；这一组仍使用受控审查输入，真实模型轨迹另行复核。两个宿主的全三场景模型复验与“缺测试只提出方案”的只验收变体正在同一包上执行，未提前标通过。


### IMP-003 开工前的实现细化（待 IMP-002 门槛通过）

1. 开放 evolve-propose 所属的 analyze.investigate：问题、范围、实际来源、只读业务意图、记录意图、观察和假设分别校验；事实保留观察时点与证据，结论允许 answered／partial／inconclusive。验证：独立调查不创建 Change／Task，不写业务或配置，不把无法复现、历史引用或猜测写成本次确认根因。
2. 复用 phase_runs、source_runs 与 evidence 保存主题和不可变结果；previous 绑定所见最新头，短事务中验证同动作／同项目及唯一后继，旧结果保持。验证：幂等重试、旧头争抢、不同主题、来源摘要与纠正引用，记录失败与实际观察分开报告。
3. 将已保存症状判据明确带入获授权的小修复方案和验收依据；继续使用现有 apply／verify 及同 REV 失败修复，不由 analyze 执行业务写入。验证：同一独立预期的失败→修复→复验，缺 red、缺环境、偶发问题保留限制；改变验收含义另行确认。
4. 同步 usage／troubleshooting、Skill 与完整分发包，在两宿主实际执行只调查及获授权修复；保持前切片回归通过后才收口。新增方法的开发版本和证据与 alpha.2 分开，不将当前不可用能力写成已实现。


宿主缺测试变体进一步复现 MODEL-004：内联标准输入被宿主安全规则拒绝后，Claude 把五个请求 JSON 写入项目父目录，删除又被目录边界拒绝。业务修复结果正确不抵消此适配失败，r4 模型报告保留 needs_retest。暂存回退规则已移到每次必读的 shared contract，并明确安全拒绝后的项目内路径；同时真实复现了首次 init 将该请求暂存目录误判为未知档案的问题，已作窄范围识别，其他未知控制内容仍拒绝接入。

[157 项回归](evidence/imp002/runtime-validation-alpha2-r5.json)通过，含独立分发包 CLI 的首次文件输入接入。新源码摘要 `e0bd85488f9133f45dff2b30f7ecbd95749419ea77123f49252a1748656150fe`、分发摘要 `192aa5e7fa89d6dfaf6a93e547b3430aa3c9259f9e1f212ab16a343de91a50ff`。宿主脚本也增加项目父目录遗留检查；这只是补强验收，不能代替实际模型重测。当前模型复验中，IMP-002 尚未收口。


对旧缺测试模型输出另有人工否证：Claude 目测 base64 后声称 journal 候选损坏；实际独立解码得到 sum，SHA-256 与 candidate_digest 一致，该“损坏”没有发生，未据此修改正确日志。该虚假附加结论已在模型复核报告中保留为 MODEL-005，不作为产品缺陷或通过证据；真实缺断言／现场回退及 blocked 结论有实际数据支撑。


### IMP-002 本机门槛收口

当前 [157 项行为回归](evidence/imp002/runtime-validation-alpha2-r5.json)、[同包双宿主安装及 CLI 业务流程](evidence/imp002/hosts-alpha2-r5.json)、[真实模型人工复核](evidence/imp002/model-review-alpha2-r5.json)均已通过本机适用门槛。只调查保留业务字节；完整修复实际接入、呈现／保存方案、修改、检查、双维自审并封存；只验收追加当前 blocked 结果，保留原 Change／Task／历史 VER。缺测试变体没有补写断言，也没有把 Ran 0 tests 的退出 0 当整体验收通过。

修复后的 Claude 原生宿主实际在首次 init 前使用项目内 requests 文件，并在后续写请求中延续同一路径；内联脚本被安全拒绝后也没有扩大目录权限。Codex 的同包只调查场景来自第 07 次隔离运行，之后的 repair／verify 来自第 08 次；第 07 次 runner 把自己创建的 other-project 误作模型遗留的错误已单独记录，未掩盖或改写原结果。两个宿主没有嵌套代理；审查是各自会话自审，当前工程复核由当前 Codex 执行。

模型身份分别为 Codex 的 gpt-6-astra 与 Claude Code 配置的 MiniMax-M2.7。报告保留模型文字的限制：Claude 的“所有非空输入都错”属于过度泛化，只接受实际固定输入与独立断言证据，不将其升级为通用事实。旧轮次错误的 journal 损坏声称也未采用；新复验已正确区分原始值、候选值与当前现场。

IMP-002 标为 **passed_local**，允许进入 IMP-003 的本机开发。各 V 的未开放复杂分支、完整续接／学习和升级恢复仍由后续切片负责，[分支映射](evidence/imp002/acceptance-map.json)不将整个编号冒称通过。**M1 仍 in_progress；V-137 原生 Windows not_run，M2／M3 未开始。**


## IMP-003 实施中

开发版本从 alpha.2 切换至 alpha.3，保留前切片的独立受检包和历史证据。复用 phase_runs／source_runs／evidence／blobs，不新增分析领域表，schema 保持 v1；下述实际降级绕过复现后，protocol 升为 v2。

已实现 answer_only 不建库问答和 record 独立调查，来源字节与实际观察分开保存；未知日期明确为 unknown，不用记录时间冒充。主题由 previous 派生，旧头拒绝第二后继，历史保留后续纠正；父执行沿实际 input_digest／execution_instance 核查活动状态、范围和撤销。实际进程退出后维护只标 interrupted，不造分析结果。

修复方案可引用已保存调查，固定其原 criterion_digest 和检查定义；verify 另需当前 symptom_result，记录原判据、原始输出、实际次数、观察者及限制，继续运行真实检查和双维审查。已经以真实失败算术示例验证只调查不写业务、独立预期保留、同 REV 必需发现修正复查及封存；初步测试不是两宿主整切片通过。下一步集中审查来源／主题／证据门禁并跑整套回归，再构建同包宿主验收。


### IMP-003 协议隔离问题与修复

实际用保留的 alpha.2 包对 alpha.3 生成的诊断 Task 执行 verify：即使没有 symptom_result，旧包仍给 passed，见 protocol-regression-before.json。单纯维持相同 protocol v1 会让旧写入器忽略新增必需语义，不能按“表未变”当作兼容更新。因此 protocol 升为 v2，schema 仍 v1；新旧协议相互拒绝不兼容写入，不自动改标号、迁移或清库。当前只有受控临时夹具，未发现可迁移的真实 alpha.2 试用档案；今后的兼容更新与显式迁移仍归 IMP-005／IMP-012 核对。


IMP-003 当前完整回归为 **183 项通过**，源码摘要 `6553bffd8439ad6c1569c35388dd21cd27eedd6ff0fef71485bfde59e40a4dc6`，独立分发摘要 `240d19be86696a0adbd21c5a4ab461224b37a2b1c2f8fac714ddd7acbe1f77f2`。见[构建验证](evidence/imp003/runtime-validation-alpha3.json)、[12 项 V 分支映射](evidence/imp003/acceptance-map.json)、[同范围宿主验收方案](evidence/imp003/host-acceptance-plan.json)。实际[旧包绕过复现](evidence/imp003/protocol-regression-before.json)与[协议 v2 拒绝写入](evidence/imp003/protocol-regression-after.json)分别保留；不是只用 mock 替代旧写入器测试。

双宿主正在同一分发包上执行安装／CLI 调查修复，以及三类真实模型场景：即时问答不接入、不留档；完整修复先独立保存实际调查，再引用原判据实施、复验和封存；只验收保留现场与完成历史，缺测试时只提出方案。授权仍限先前明确批准的隔离项目／三类受控测试，不扩大外部服务、嵌套代理或真实业务范围。模型退出码不会自动转为 passed，仍须逐条对照轨迹与数据库事实。IMP-003 继续 in_progress，后继切片未开工。


alpha.3 同包的[实际双宿主安装与 CLI 调查修复](evidence/imp003/hosts-alpha3.json)通过，包含即时问答不建库、独立调查不创建 Change、真实 red 保存、原判据修复及复验，之后还验证增量配置与初次知识具体批准。两个宿主实际缓存分别执行，Claude 原生登记安装根另行保留并核对；这组审查输入是受控夹具，不冒充模型语义判断。实际模型进程已启动，原始下载副本移走，模型复核仍未收口。


### IMP-004 开工前细化（待 IMP-003 门槛通过，尚未开发）

1. 以现有 run／Task／REV／来源事实实现只读 resume／next：展示原方案、已做／未做、实际失败、授权与现场差异；多目标明确选择，不将最近聊天当身份，不写 guard 或索引。
2. 正常暂停沿 owner 保存部分结果与下一步，run 安全结束而 Task 保留未完成；新会话从有效来源继续，真正未结束的旧执行才走恢复，不建立独立交接状态机。
3. 增加项目内经验的记录、少量检索与采用反馈；每条经验保留适用范围、版本、实际来源及反例状态，未确认线索不成为正式规则或修改授权。没有新发现记录 no_new_learning，未检查保留 pending。
4. 在同一受控项目让前一次真实工作产生经验，新会话继续部分工作，再在第二次同类任务中实际检索、核实、采用或拒绝并反馈；两宿主分别留证，检索无命中和索引故障分开。完成后再进入 IMP-005，不以静态示例代替跨会话行为。


### IMP-003 当前验收结果与外部条件

[Codex 真实模型人工复核](evidence/imp003/model-review-alpha3.json)通过：即时解释没有接入或留档；完整修复先保存独立分析和真实 red，再引用原判据实施与复验；只验收追加当前 blocked 记录，原封存和完成状态保持。首次 apply 漏传 checks 效果被工具拒绝，未登记业务操作；模型按既有明确测试授权修正请求后完成，没有绕过门禁。

Claude Code 的当前配置模型 MiniMax-M2.7 在首个模型请求返回 **429／2056：Token Plan 用量上限**，进程退出 1，未发生模型工具调用，未创建业务历史库，三类场景均未完成。见[实际额度失败记录](evidence/imp003/claude-model-quota-alpha3.json)。这是真实提供方拒绝，不是插件功能失败或验收通过；保留原失败结果，不自动购买、切换模型或把同宿主 CLI 夹具代替模型验证。

当前 [规格／规范自审](evidence/imp003/self-review-alpha3.json)与 183 项回归、双宿主 CLI 均完成，仍须在额度恢复或用户明确选择其他可用模型后完成 Claude 实际场景并复核。已通过异步问题请求该执行条件，等待答复。**IMP-003 继续 in_progress；IMP-004／005 未开始，M1／原生 Windows 及 M2 门槛保持原范围。**


用户随后明确指定 MiniMax-M3.1-Flash 继续 Claude Code 验收。仅在新隔离测试进程传 --model，不修改个人全局配置或凭证，沿用原受检分发摘要。失败的 M2.7 原件保持，新结果另存，不把模型选择当额度已恢复或验收通过。本轮曾核对到 IMP-005 与 IMP-003 都只依赖 IMP-002，可在 M1 内独立选择；在尚未修改后继实现前收到模型选择，现优先完成 IMP-003 重测，IMP-004／005 仍未开发。


### IMP-003 用户指定模型的实际重测结果

已按用户选择在新隔离进程传入 `--model MiniMax-M3.1-Flash`，宿主 system/init 同名确认，但首次请求仍返回 **429／2056：Token Plan 用量上限**；约 183 秒内宿主自行产生 10 条 API 重试事件，最终退出 1。原测试进程已结束，未启动替代调用。没有成功模型响应、模型工具调用、业务改动或调查档案，三类场景完成数仍为零；初始化模型名称不能证明推理成功或额度已恢复。见[指定模型重测证据](evidence/imp003/claude-model-quota-alpha3-r2.json)，原 M2.7 失败记录保留。

测试脚本新增可选 `--claude-model`，只向 Claude Code 本次进程传参数；其他宿主使用该参数会被拒绝。个人全局配置、凭证和账户未变。验收状态仍为 IMP-003 in_progress，待提供方额度恢复后继续同包受控测试，不自动购买、再换模型或循环重发。183 项运行时回归及双宿主 CLI 证据保持原受检范围，不将本次提供方拒绝记作插件通过。


## IMP-005 实施中：本地保护与宿主生命周期

直接前置 IMP-002 已通过。按 delivery 的分支依赖，在 M1 内核对该独立切片；IMP-003 的 Claude 模型额度缺口不豁免、不标通过，IMP-004 未开工，M2 仍禁止进入。此次不调用模型、嵌套代理或修改个人配置。

1. 复用已有文件日志／一致备份和维护协议，以真实子进程中断与外部编辑验证已做事实、未完成检查及冲突保留。
2. 新增完整包切换回归：在途旧执行遇到安装根改变时拒绝业务副作用；安全停止后独立新 run 使用兼容包，未知 schema／不兼容协议不迁移。
3. 双宿主在新隔离配置和临时业务项目完成真实小修复后，实际禁用、更新、卸载、重装；比较业务／evolve／控制区所有字节及原身份、历史与授权。更新采用同代码、同 schema／protocol 的完整测试派生包，版本和摘要不同，不能冒充新的公开发行或任意未来版本兼容证明。Codex 使用当前宿主支持的 remove/add；Claude 使用实际 marketplace update 和 plugin update。原生 Windows 不以本机路径测试替代。
4. 按实际结果集中修复，再补安装及最小恢复指南和 V 分支映射；未完成项保留，不将静态文档或空列表当成功能通过。


### IMP-005 本机收口与限制

本切片没有新增运行时业务能力、表、协议、后台或依赖；沿用既有本地保护协议，补齐包替换的实际子进程回归、宿主生命周期验收及用户说明。新增六项完整包回归覆盖在途换版本、同版本完整内容替换、兼容新 run 恢复无 OP 手改、第三值冲突／保护门禁、未知 schema 及不凭外部源码记 done。最终 **189 项回归通过（12.398 秒）**，见[实际测试输出](evidence/imp005/component-tests.txt)和[构建验证](evidence/imp005/runtime-validation.json)。

[双宿主实际验收](evidence/imp005/hosts.json)及[人工轨迹复核](evidence/imp005/manual-review.json)通过 36 项本机检查：每个安装运行时先完成真实小修改，再对受控外部回退进行写入后进程退出、只恢复确定事实、重新真实检查与封存；随后实际禁用、兼容更新、缓存副本移到空格／中文路径、卸载和重装。业务、历史、证据、备份和控制区字节在安装操作间保持，两个项目均复用原身份／epoch。原测试断言保持，先前完成的 Change／Task／VER 行不被重写；恢复保护明确不是一致整体还原包。

Codex 0.154.0 使用支持的 remove/add，重新关闭用户级启用并保留目标项目八 Skill、其他项目零 Skill；Claude Code 2.1.117 的实际 update 报告从 alpha.3 更新至受控 alpha.3.lifecycle.1，并提示重启，新会话八 Skill 发现通过。禁用后的本地 /skills 界面明确显示 No skills found，没有用空数组猜发现成功。[实际命令](evidence/imp005/host-commands.json)保留。兼容派生包是测试夹具，不是新的公开发行或任意未来版本兼容证明。

首轮脚本误将显式 init 接入回执也要求为数据库零变化，实际只变更 history.db 与 guard，未改配置或旧事实；已分别验证卸载重装原字节保持、显式重新接入只追加新回执且保留旧行，不更改正确的产品行为来满足错误断言。失败原件与修正见[问题及复验](evidence/imp005/issues-and-fixes.json)。真实旧 alpha.2 写入器对两个最终项目的 status／init 共四次调用均以 SCHEMA_VERSION 拒绝，资料字节未变，见[实际降级拒绝](evidence/imp005/downgrade-alpha2.json)。

本轮源码摘要 `c3d5ea14548b9f918679aa961dce44b263c23a81f59da8372f6dff83720dd905`，受检分发摘要 `c4d24e4dad99c9f75de2b6aa5ba9df8a2ed93f6a7bd76175ba249bb8a7a028e9`，兼容派生包摘要 `b4e244a3caebba4beeb8c3f9819a4b189d15bc58d5192ff5b117d7551cf98cf8`。与 IMP-003 原受检分发相比，只改变三份发行／安装／排错说明，runtime、八 Skill 和 shared 字节相同，见[内容差异核对](evidence/imp005/package-delta.json)。IMP-003 的模型原始证据继续绑定其原包，不据此消除未完成的 Claude 模型门槛。

[11 项 V 分支映射](evidence/imp005/acceptance-map.json)和[规格／规范自审](evidence/imp005/self-review.json)已保存。IMP-005 标为 **passed_local／平台覆盖 partial**，不标整个 V 编号或 M1 全量通过。原生 Windows 仍 not_run；完整迁移、整体 restore 和外部未知效果仍由后继切片负责，不以本机文件恢复代替。**IMP-003 的 Claude 模型额度门槛未关闭，IMP-004 未开工，M1 仍 in_progress，M2／M3 未开始。**


## IMP-004 实施中：正常暂停、续接及真实经验复用

直接前置 IMP-002 已通过，按 delivery 的分支依赖在 M1 内继续。早期“等待 IMP-003 后再开工”是执行安排；当前 Claude 额度条件持续存在，按已经明确的直接依赖推进本独立分支，不关闭 IMP-003 的模型门槛，也不进入 M2。具体[实施任务及剩余验收](evidence/imp004/implementation-plan.json)保留完整切片范围。

开发包切换为 alpha.4，新增 continuation／resume 两个内核模块，八个 Skill 及 owner 集合不变。apply.input.pause 在受管文件段完成后保存已做／未做、下一步和实际原因，跳过检查，Task 保持 in_progress，run completed／partial，并释放安全结束的本地占用。异常仍按真实 journal／恢复处理。新会话明确继续时，独立新 run 引用原 run／result_digest，检查工作定义、原范围与撤销，不让历史记录或 resume 独立授权。新的明确授权不通过隐式扩大旧 grant 获得。

resume／next 是纯查询，恢复实际方案、Task 定义、进度、失败、证据及原授权。唯一目标说明定位，多目标返回选择，不按最近记录猜。指定 Change 仍显示项目级未结束配置／操作；现场变化只观察，不自动登记、覆盖或恢复。分析主题保留当前头、原来源授权、未答问题和后续纠正。未知外部数据仍为 not_observed。

### IMP-004 早期组件截点与兼容边界（201 项，历史）

[201 项实际回归](evidence/imp004/component-tests.txt)通过（12.774 秒），其中新增 12 项暂停／续接回归。[独立分发包的实际新进程查询及续接](evidence/imp004/public-continuation.json)验证 resume／next 不改项目字节，新 apply 执行真实原检查、保留旧 run，正常暂停无需 recover。该观察是工具级，不是双宿主模型或完整验收封存通过。当前源码摘要 `b838e8f31564ae296e4dd471fa696f64a18d267d968b0bf1c7129d13a9c03bd5`，独立分发摘要 `0f73cd0beabb81e94a6ab3062afbc64390e443bbd3919135a523fc3c433c9501`，47 个包文件，见[构建及分支验证](evidence/imp004/runtime-validation-alpha4.json)。

实际[旧 alpha.3 忽略 pause](evidence/imp004/protocol-pause-before.json)会继续检查并记 Task done；因此 protocol 升为 v3，schema 仍 v1。相同真实旧写入器对新协议项目以 SCHEMA_VERSION 拒绝，Task 保持 todo、所有项目字节不变，见[新协议阻断](evidence/imp004/protocol-pause-after.json)。当前工程只用受控临时验收项目，不自动迁移或重置既有试用档案；发现旧档案时保留资料并使用完整旧兼容包。IMP-005 证明的兼容更新限同协议，不推广为跨本次协议边界升级。

**该 201 项历史截点尚未实现项目经验生产、少量检索、采用／拒绝及实际效果反馈，当时 learn 明确 unavailable；宿主后续状态见下节。** 经验必须由前次真实工作产生，候选不成为正式规则；检索与采用、整体通过与可归因效果、无新发现与未检查分别保留。以上剩余项没有被当前暂停／查询测试代替，IMP-004 仍 in_progress，M1 未完整通过。


### IMP-004 项目学习与双宿主 CLI 当前截点

已新增 learning 内核，公开 learn search／record／retro／review／disable；promote 仍 unavailable。继续使用 schema v1／protocol v3，经验内容、状态审阅、实际采用及事后反馈各自追加到现有 run／来源／证据结构，不新建独立交接状态机、搜索服务或物化索引。经验保留原工作、证据摘要、范围／版本／限制；内容版本与状态前驱分开，不按时间或引用次数猜有效性。默认 candidate，业务假设不自动 active；所有状态都不成为正式知识或修改权限。

纯检索最多返回五项，正式知识引用及待审资料不受经验排名隐藏。no_match、not_connected、留档未完整的 incomplete 与来源错误分开；可选经验损坏时 resume 保留原工作及正式背景并显示 unavailable。采用／拒绝需重新绑定实际检索目录及目标文件；反馈需是决定之后同一 Task 的真实 apply／verify，unknown 明确保留，不能把整单通过当作所有引用的因果收益。复盘确实检查后无发现才记 no_new_learning，未检查保持 pending。暂停后的新进程还能恢复原采用版本、决定及当时范围，原记录不改写。

本轮集中修复并保存[问题与复验](evidence/imp004/issues-and-fixes.json)：时间排序会错误重建状态链；相同内容与来源可通过新 ID 绕过停用；重新入档的旧绿灯会被错用为较新反例之后的支持。三项都有修复前实际失败输出，现分别沿明确前驱、拒绝精确重复、按证据 observed_at 而非保存时间核查。开发中另一次证据 ID 归一化漏括号导致真实全量导入失败，已修正并增加构建前 Python 语法校验与独立拒绝构建回归，未把当时文档检查通过算作功能通过。

最终 **231 项全量回归通过（18.703 秒）**，含 28 项学习回归；[实际输出](evidence/imp004/component-tests-learning.txt)、[学习测试](evidence/imp004/learning-tests.txt)与[当前构建验证](evidence/imp004/runtime-validation-alpha4-r2.json)分别保留。源码摘要 `de083e292ab05ba39eb5469ed697efbeefd03081d34fb584b74f83c977529529`，完整分发摘要 `ebd7ed18188f4a4884ffea8cda6595e480e3a75bff8cbd6b90f83b18bde79eee`，48 个文件、18 个实际方法；八 Skill 和十四动作 owner 不变。

[双宿主最新实际工具验收](evidence/imp004/hosts-alpha4-r2.json)及[轨迹／库事实人工复核](evidence/imp004/native-cli-review-alpha4-r2.json)通过 15 项本机检查。每个宿主安装缓存均执行：首次真实调查／修复产生一条候选经验 → 第二对文件的独立失败 → 实际检索内容进入新方案并记录采用 → 文件段正常暂停 → 无旧聊天输入的新 CLI 进程恢复原采用与部分结果 → 原检查、受控双维审查及封存 → 单独 unknown 效果反馈和已检查无额外发现。两项目最终各两条 Change 封存、无 started run 或资源占用，两组原独立断言保持。原下载副本移走，实际 Skill 发现与缓存／Claude 稳定登记根分别核对。

这些工具请求与审查输入为受控夹具，实际工具与数据已经运行，但**没有发送模型请求，也没有证明模型在原生新会话中会自行完成编排**。因此[15 项 V 分支映射](evidence/imp004/acceptance-map.json)、[规格／规范自审](evidence/imp004/self-review-alpha4.json)继续将整切片标为 in_progress。[下一步模型验收范围](evidence/imp004/model-acceptance-plan.md)已经列明正常暂停、新会话与第二任务；运行器及最终预检准备后核对相对原受控授权增加的范围，再派发。当前不以 CLI 夹具代替语义门槛，不进入 M2。

为保持 IMP-003 原包仍可验收，模型控制脚本改从明确指定的完整包加载匹配的只读控制辅助，新增 preflight-only，不再被源码升级到 alpha.4 的协议误阻止。实际恢复预检在 alpha.3／protocol2 原包通过，无模型请求或个人配置变化；[完整原包及摘要](evidence/imp003/preserved-package.json)现保存在工程证据中，仅含插件库存及清单，不含宿主配置、凭证或业务库。原 MiniMax-M3.1-Flash 的额度拒绝仍是最后一次实际模型结果，未自动重发。**IMP-003 模型门槛、IMP-004 真实新会话语义及原生 Windows 仍未关闭，M1 不完整，M2／M3 未开始。**

### IMP-004 模型验收运行器准备完成

新增五个严格按顺序执行的新会话：即时调查、真实文件段后正常暂停、无旧聊天续接、第二文件对采用前次实际经验，以及只验收当前回退。父进程使用实际内核记录与原始独立断言检查，不依赖模型自述；原部分结果、原完成 Task／Change、旧验证及首个文件对均有保留检查，采用记录与实际效果反馈分开验证，允许 unknown。

新增 12 项父检查／范围测试，**全量 243 项通过（20.786 秒）**，包含真实两任务经验闭环的正向夹具和修改独立断言、缺少采用反馈、未授权派发、范围摘要不匹配等拒绝分支。[实际输出](evidence/imp004/component-tests-model-harness.txt)及[运行器准备记录](evidence/imp004/model-runner-preparation-alpha4.json)已保存。审查发现可选缺测试变体未进入授权摘要，现已补齐并回归；本轮未修改插件运行包，48 文件及源码／分发摘要保持上节数值。

两个新隔离宿主配置各实际安装并发现八个 Skill；Codex 未启用的另一个项目发现零个。prepare-only 在创建模型客户端之前退出，未读模型列表、未发模型请求，也未重试先前 Claude 额度失败。五段具体输入、完整包和宿主／模型选择、夹具文件、变体及运行器源码已绑定为两份可审阅摘要，见[最终模型验收范围](evidence/imp004/model-acceptance-plan.md)。实际派发要求新增范围的真实人类授权及匹配摘要；准备成功不会标记模型验收通过。**IMP-004 继续 in_progress，M1 未通过，M2／M3 未开始；IMP-003 原包 Claude 门槛和原生 Windows 缺口均保留。**

用户随后实际回复“授权两个宿主，仅限上述受控验收（推荐）”。重新核对两份范围摘要和运行器源码未变后，在两个全新隔离目录启动 Codex 及 Claude 原生模型运行器；Claude 仅本进程指定 MiniMax-M3.1-Flash，额度拒绝即停。授权原文、对应原问题、实际观察句柄和后续结果见[模型派发记录](evidence/imp004/model-dispatch-alpha4.json)，尚未审查的模型结果不能推为通过。

### M1 原生 Windows 验收准备

现有双宿主发现工具依赖 POSIX 终端，不能直接作为 Windows 验收入口。新增独立的整包重定位运行器，使用含空格／中文的安装、移动和业务目录，从非源码 cwd 执行 doctor、真实调查修复与原判据复验；移动完整运行根后，核对原身份、只读字节不变，再由新 CLI 完成第二任务的经验消费、正常暂停、续接和封存。该入口没有宿主安装／发现或模型调用，不替代这些独立证据。

[Windows 便携材料](evidence/imp001/windows-readiness-alpha4.zip)包含完整 alpha.4 包、三个脚本、说明和字节库存，共 54 项，不含宿主配置、凭证或业务历史。实际解压后在 macOS 完成 11 项正向检查、12＋15 次真实 CLI 请求，以及非 Windows 拒绝、已有输出拒绝、损坏整包拒绝三个分支；[摘要与限制](evidence/imp001/windows-readiness-alpha4.json)已保存。此结果仅证明材料在实际 macOS 环境中可运行，原生 Windows 仍 not_run。

本机只读观察为 Darwin 25.6.0／Python 3.11.9，未在探测的命令中发现原生 Windows 或虚拟机执行入口；不能据此猜测其他未检查机器。Windows 执行方式见[开发说明](development.md)，须在实际 Windows 进程带 require-windows 执行，并另存两个原生宿主的安装、项目启用、发现与生命周期证据。**准备材料不关闭 V-137／M1，也不开放 M2。**

### IMP-004 实际模型发现与同范围修正复测

初轮 Codex／gpt-6-astra 在五个原生新会话中完成全部父检查，但[轨迹复核](evidence/imp004/codex-model-review-alpha4-r1.json)发现即时调查猜测了不存在的动作同名 Skill，并在最终答复误报整包资源缺失；实际 owner 是 evolve-propose，八个 Skill 库存完整。该发现使初轮完整模型验收不能标为通过。另在[Claude 首场景轨迹](evidence/imp004/claude-inspect-review-alpha4-r1.json)中观察到：标准输入被宿主拒绝后，模型为即时问答创建请求暂存文件再清理；最终无目录不等于全过程只读。父检查未覆盖此瞬时行为，需结合原始工具轨迹审阅。

按实际发现集中修改三份运行资源：workflow 先读取 runtime OWNERS 再分派 owner Skill；共享约定先区分即时问答的对话回退与已获授权写请求的文件回退；CHANGELOG 记录尚待复测。没有新增 Skill、业务能力或执行权限，运行代码及 schema1／protocol3 保持。修正源码摘要为 `7f7179ce135f4810d5cf1b76873f482c61946d3b38e7dbcd0ce21d59c3ccdd8a`，完整分发摘要为 `e599c03724bf770268f780637f0f89a7f9f46fb080c97f2e78441e32cfad4f40`，仍为 alpha.4／48 文件／18 方法。**243 项回归再次通过（20.830 秒）**，workflow 的 quick_validate 通过，见[回归原件](evidence/imp004/component-tests-owner-fix.txt)。

修正包已在两个新隔离配置安装／发现并生成新的[Codex](evidence/imp004/codex-model-scope-alpha4-r2.json)／[Claude](evidence/imp004/claude-model-scope-alpha4-r2.json)范围摘要；沿用户对同一四文件／五场景方案内修复复验的实际授权继续，不增加模型选择或副作用范围。Codex 已开始完整复测，即时场景实际读取 owner 映射及 evolve-propose，未再猜不存在的 Skill。Claude 原包运行继续留存其后续场景，结束后再调度修正包，不能把两包结果混用；实际句柄与结果统一见[派发记录](evidence/imp004/model-dispatch-alpha4.json)。

Windows 材料已另存为[修正包 r2](evidence/imp001/windows-readiness-alpha4-r2.zip)，再次从实际解压物完成整包移动、修复及经验续接流程，见[r2 本机证据](evidence/imp001/windows-readiness-alpha4-r2.json)。原包材料和结果保留历史；两个材料都没有原生 Windows 结果。**IMP-004 仍 in_progress，IMP-003 原包门槛与 Windows 覆盖仍保留，M1 未完成，M2／M3 未开始。**

随后 [Codex r2](evidence/imp004/codex-model-review-alpha4-r2.json) 在 e599 完整包完成五新会话并通过复核，确认 owner 路由问题已消除。但 [Claude 原包](evidence/imp004/claude-model-review-alpha4-r1.json) 在续接父检查处退出 1：暂停时 effect_kinds 漏掉原指令已明确允许的后续 checks，续接加入该效果被正确拒绝；模型改以本次新检查授权完成，未形成本案要求的原来源绑定。未放宽子集门禁，也未把新授权路径算作原授权复用通过。原轨迹及两条实际候选经验保留；similar／verify 未被该失败运行器派发。

继续修正暂停与续接指引：保存实际已授予的后续效果／原文，pause 仍只完成文件段并跳过检查；原指令未授予的效果仍不增加，独立新授权按真实新指令留证。当前源码摘要 `ccf3649145893ea476c70f06e3e9ef90e357373937fd8bde92da9e4ed023d6d2`，完整分发摘要 `5fce70d15a7ee8893b2d18b562298bca81e51684a16ee763f054eb915c5273c5`；运行代码、schema1／protocol3、48 文件与18 方法不变。**243 项回归再次通过（21.107 秒）**，apply 的 quick_validate 通过，见[实际回归](evidence/imp004/component-tests-authority-fix.txt)。

两宿主已在新隔离配置完成当前包安装／发现并实际启动同范围五场景复测，范围分别为 [Codex r3](evidence/imp004/codex-model-scope-alpha4-r3.json) 和 [Claude r3](evidence/imp004/claude-model-scope-alpha4-r3.json)；观察句柄保存在[派发记录](evidence/imp004/model-dispatch-alpha4.json)。e599 的单宿主通过不代替当前完整包双宿主结果；Windows r2 材料为较早指引截点，最终平台收口须与最终受检包核对。

[Codex r3](evidence/imp004/codex-model-review-alpha4-r3.json) 已在 5fce 包完成五场景并通过复核，原指令中的后续 checks 权限与原文也确实保留。但 [Claude 同包即时轨迹](evidence/imp004/claude-inspect-review-alpha4-r2.json) 表明：它读到了新回退约定，仍主动加载可选的结构化请求字段并创建临时输入，收尾后目录虽清空，该只读分支仍未通过；不能把父检查通过说成语义修正成功。该 Claude 运行仍在原句柄上观察后续场景，不另启替代作业。

进一步只修改 propose 的材料加载条件：即时解释以实际只读观察和有范围的对话答复完成；用户明确需要结构化校验结果，或明确留档调查时，才分别加载对应请求字段。当前源码摘要为 `c2d5f68477ec79b0a81b565f2498ce65512309df6b3fce6b87a98a9601318841`，完整分发摘要为 `11e30bb2cc61e07331da43c8ba5696e055df378291a71ec2d911eb889ed2566d`，运行代码及协议不变。**243 项回归通过（20.868 秒）**，propose quick_validate 通过；[本次验证](evidence/imp004/runtime-validation-alpha4-r4.json)和 [Codex](evidence/imp004/codex-model-scope-alpha4-r4.json)／[Claude](evidence/imp004/claude-model-scope-alpha4-r4.json) 实际安装预检已保存。此包模型复测待现有 Claude 运行结束后调度，不混用前包的模型结论。

用户对原生 Windows 环境问题已回复“没有”，见[环境答复](evidence/imp001/windows-environment.json)。这不视为豁免 V-137，也不自动创建虚拟机或进入 M2；先继续可独立推进的 M1 模型修正与验收，最终环境缺口如实汇总。

Claude 的 5fce 运行随后在 pause 场景达到原定 600 秒时限退出，已核实原父进程及 Claude PID 均消失，未因观察超时启动替代作业。[终态复核](evidence/imp004/claude-model-review-alpha4-r2.json)区分了两层事实：库中实际已保存 completed／partial、checks=not_run、Task in_progress，且原未来 checks 授权与原文保留；原生模型调用未完成，故不标整个场景通过，也不能凭超时认定额度拒绝。旧控制脚本在超时异常中丢弃了已收部分流，无法进一步归因，原件与缺口保留。

控制脚本现会先保存实际 TimeoutExpired 的部分 stdout／stderr，再传播失败；沿用现有凭证脱敏、原时限、原权限与模型选择，以 timed_out=true／exit_code=null 表达未知退出结果。新增真实子进程超时与脱敏回归，**244 项通过（21.361 秒）**，见[原始输出](evidence/imp004/component-tests-timeout-evidence.txt)。两宿主重新完成零模型请求的安装预检，范围更新为 [Codex r5](evidence/imp004/codex-model-scope-alpha4-r5.json)／[Claude r5](evidence/imp004/claude-model-scope-alpha4-r5.json)；完整运行包仍为 11e3。已在两个新隔离目录分别启动最新 Claude 和 Codex 同包复测，重复出现的即时只读分支仍需原始轨迹复核；实际句柄见[派发记录](evidence/imp004/model-dispatch-alpha4.json)。


[最新版 Codex r4 复核](evidence/imp004/codex-model-review-alpha4-r4.json)确认同一 11e3 完整包五新会话通过本机父检查与轨迹／事实自审：即时调查无请求暂存写入，正常暂停保存完整后续检查授权，续接绑定不可改写的原部分结果，第二任务实际消费前次候选并记录有限效果，当前回退只追加 blocked 验收。此结论限该包、该宿主及本机，不冒称独立模型审查。Claude 同包已完成前三场景，继续观察原句柄，未以自动检查代替最终轨迹结论。

Windows [便携材料 r3](evidence/imp001/windows-readiness-alpha4-r3.json)已与当前 11e3 包对齐，从新解压物实际完成 11 项本机重定位／学习流程检查；它仍没有原生 Windows 或宿主安装证明。用户又明确选择“暂不创建，保留 Windows 未验收门槛”，[原答复](evidence/imp001/windows-environment.json)已保存；不下载或创建 VM，不再重复询问同一环境安排，V-137／M1 保持未通过。

此前 IMP-003 原包 Claude 只有额度拒绝；本轮已实际观察到 M3.1-Flash 完成新包模型场景，因而按原两文件／三场景授权，在完整保存的 alpha.3／protocol2 原包另起隔离复测，见[原包派发](evidence/imp003/claude-model-dispatch-alpha3-r3.json)。仍限所选进程模型、不改个人配置，若额度拒绝即停；原拒绝证据保留，当前新包不冒充旧包通过。所有剩余 M1 门槛完成之前不进入 M2。


### IMP-004 当前切片本机收口

[Codex r4](evidence/imp004/codex-model-review-alpha4-r4.json) 与 [Claude r3](evidence/imp004/claude-model-review-alpha4-r3.json) 已在同一完整 11e3 包各完成五个原生新会话，真实父检查与逐工具／库事实复核通过。Claude 五个原生 session_id 独立、模型均为所选 MiniMax-M3.1-Flash。最终受控回退仅追加 blocked 验收，原业务字节、Task／Change 完成状态、旧验证与候选状态保持，无 started run 或资源占用。两条实际模型轨迹及[完整受检包](evidence/imp004/preserved-package-alpha4.json)均已持久保存。

复核保留[非阻碍观察与纠正](evidence/imp004/claude-completed-case-notes-alpha4-r3.json)：两次个人配置目录探测被原生权限拒绝，未观察到成功读取或提权；暂停答复的“本轮未执行检查”应限为“修复后未执行”，原调查确实执行过失败检查；第二任务答复用了英文，最终时间线另有一处 run 与时间配对不准，实际库事实保留为准。以上不被自动绿灯隐藏，也不据此宣称语言一致性、全过程零文件写入或独立审查。核心门槛未发现越权实际写入、伪造 passing 验收或历史覆盖。

因此 IMP-004 的 M1 适用分支记为 passed_local，[十五项映射](evidence/imp004/acceptance-map.json)与[规格／规范自审](evidence/imp004/self-review-alpha4.json)已更新；不将跨后续切片的整个 V 编号一并标通过。IMP-003 原包 Claude 复测尚未终结，原生 Windows 仍 not_run 且用户暂不创建 VM，**M1 仍不完整，M2／M3 不启动**。


### IMP-003 原包真实缺陷与修正版对应复测

[原 alpha.3 Claude 复测](evidence/imp003/claude-model-review-alpha3-r3.json)已有实际模型响应，非额度拒绝；即时调查在标准输入拒绝后创建并编辑临时请求文件，清理后父检查通过，但全过程只读判据未通过。该问题已由 IMP-004 的共享回退区分与 propose 按需加载修正，原包保持失败历史，不修改原归档或将其重新标为 passed。确认必需失败后停止了原作业后续模型调用，保留已收输出；终态库无 started run 或占用，仅有尚未实施的 ready 工作项，未把主动停止说成插件修复失败。

按[明确的受检基线记录](evidence/imp003/acceptance-baseline-alpha4.json)，用修正后同一完整 11e3 包验证对应原判据，而非继续要求冻结的旧缺陷版自行变正确。即时分支复用该包刚完成的两宿主实际模型证据；两个宿主各在新临时项目补测原两文件的独立留档调查 → 完整修复／原判据复验 → 受控移除测试内容后的只验收。文件范围、原三个场景的判据、原模型选择与权限边界均不扩大，旧失败不被新结果覆盖；两项新作业尚在运行。


### 当前完整包生命周期再核对

同一 11e3 包在两宿主的[实际生命周期复核](evidence/imp005/manual-review-alpha4.json)完成 36 项检查、42 条命令；38 次退出零、2 次真实原始失败和 2 次注入的子进程退出 35 均与受控判据一致。初始／兼容更新／重装各发现八 Skill，禁用的 Codex 及另一项目为零；Claude 本地 /skills 明确显示 No skills found，非仅凭空解析数组判断。

禁用、卸载、重装、整包移动均保持目标资料；显式重新接入仅追加新回执，原身份／配置及旧表行摘要不改。真实文件段异常后独立恢复不重放业务命令或检查，随后实际验收封存。兼容更新使用同代码／schema／protocol 的完整测试衍生包 `0.1.0-alpha.4.lifecycle.1`，不冒称已公开发行或任意未来版本可升级；最小保护资料仍不是完整一致恢复包。本轮没有模型请求，没有原生 Windows 证据，M1 门禁保持。


### M1 当前本机汇总与唯一剩余平台门槛

同一完整 11e3 包的 IMP-003 [Codex](evidence/imp003/codex-model-review-alpha4-r1.json)／[Claude](evidence/imp003/claude-model-review-alpha4-r1.json) 对应复验均已终态退出零并完成轨迹／库事实复核：先保存真实失败、独立预期和原判据，再按原授权修复、真实复验和封存；随后将源码受控回退并清空测试文件，两个宿主均识别 Ran 0 tests／退出 0 不能证明正确，仅追加 blocked 验收，未补写测试或重开历史。原 alpha.3 的实际失败仍单独保留，没有被新包通过改写。

[当前 M1 门禁表](evidence/m1-local-gate-alpha4.json)汇总了 244 项组件／运行器回归、同一包的实际双宿主模型语义、36 项当前生命周期检查、整包重定位与完整资源摘要。IMP-001—005 的适用本机分支均已有证据，模型作业已结束；非阻碍文案、拒绝的目录探测、受控衍生版本和最小恢复限制分别保留。规格／规范复核是当前 Codex 自审，不自称独立模型审查。

**剩余必需门槛是 V-137 原生 Windows**：本机便携材料自检不替代 Windows 进程和两个原生宿主的实际验收。用户明确暂无环境且暂不创建 VM；不下载、不配置新环境，不把该答复视为豁免，也不重复询问同一决定。因此当前仅能报告本机分支通过，M1 整阶段未通过，M2／M3 未开始，整个工程的最终交付尚未完成。


### 用户范围修订与 M1 当前环境通过

用户最新明确“不需要特别考虑windows环境，这个和环境无关，确保当前环境能执行就可以”。[范围依据](evidence/acceptance-scope-current-environment.json)取代此前独立 Windows 前置；[原门禁](evidence/m1-windows-gate-before-scope-change.json)及历史未测／拒绝创建 VM 的记录保留，不将其改写为 Windows 通过。V-137 在当前环境的资源定位、整包移动和空格／中文路径要求继续有效。此前章节中的 Windows 阻塞是历史截点，以本节及开头状态表为准。

已实际重新运行 **244 项回归，21.541 秒，全部通过**，并从同一完整 11e3 包在新的临时项目完成 11 项重定位／调查修复／新进程续接与经验消费检查；[本次执行证据](evidence/m1-current-environment-revalidation.json)与此前两个实际宿主的安装、模型编排和生命周期证据共同构成当前范围验收。M1 因此记为 passed_current_environment，允许推进 IMP-006；M2／M3 的未实现能力和最终全工程交付仍待后续切片。

随后同步安装／使用指南、共享运行约定、变更记录及构建阶段，清除“等待 Windows／额度恢复”和“验收未收口”的过时当前状态；历史截点保留。完整包仅五份说明文件变化，运行时代码和八 Skill 与此前实际双宿主模型受检包逐字一致。[本次说明更新与验证](evidence/m1-current-scope-documentation-refresh.json)记录独立分发摘要 `ef93686dd12eea671d02441beeda7780c7e39a8f2e476bb6277c7ace62d957b2`、源码摘要、具体差异及完整包。新包再次完成 **244 项测试，21.988 秒，全部通过**，以及 11 项当前环境重定位／续接检查；未额外调用模型，不将旧包轨迹标作新摘要的模型实测。

## IMP-006：完整复杂提案与任务条件

按[具体实施方案](evidence/imp006/implementation-plan.md)进入 M2。当前 alpha.5 已接通 propose.create 的复杂分支：完整 spec、用户结果、独立验证方法、不覆盖范围、测试决定引用、AC 与真实条件依赖一起保存，plan_digest 绑定整个实际呈现的文档。只保存提案不接受方案、不改业务文件；status 恢复完整文档，关键问题和相关上下文变化只影响声明的任务，无关知识追加不使全部条件失效。

依赖定义检查循环、未知上游、缺条件依据和无真实顺序的共享输出；所有范围及必需 AC 都须有任务负责。预重构和广泛迁移先保存待执行判据及最终集成边界，尚未执行的行为保持证明不标通过。局部 TASK 编号带 change_id，重复请求不重复分配。复杂 apply／verify／archive 仍明确拒绝，含单 Task 的复杂提案也不能落入简单路径；update 尚未开放。

为隔离旧写入器忽略新条件，protocol 升为 v4，schema 保持 v1；实际完整 alpha.4 写入器对新档案拒绝且原库字节不变，旧完整包保留，不迁移或重建已有档案。首轮全量发现验收控制器固定 protocol3，已限定支持实际 protocol3／4 并保留未知版本拒绝及完整范围摘要；原 v2／v3 包预检仍可用，未启动模型或个人宿主配置。

本截点 **263 项测试通过（22.076 秒）**，含 18 项复杂提案行为测试、实际旧写入器拒绝及原有回归；[原始输出](evidence/imp006/component-tests-spec-proposal.txt)、[构建／自审与未完成项](evidence/imp006/spec-proposal-validation.json)分别保存。独立 50 文件包从非源码 cwd 在中文／空格路径完成 10 项实际 CLI 提案检查，见[结果](evidence/imp006/spec-proposal-cli-proof.json)与[原始请求／响应](evidence/imp006/spec-proposal-cli-trace.zip)。这些是工具行为及受控材料，尚未提供新增复杂场景的原生宿主模型证明。

下一步按原方案接通就绪任务实施、逐项审查、前后行为保持、最终集成门槛及 REV 有效结果复用，再完成两宿主受控验收。IMP-006 保持 in_progress，M2／M3 和工程最终交付尚未完成。

### IMP-006：普通复杂任务实施与整体验收

已接通当前 REV 下的真实 Task 选择、条件门禁、文件实施、任务检查／审查、正常暂停和跨进程续接；新请求由 CLI 冻结 task_id 和全部当前任务版本，重试保留原绑定。只完成上游实施不能替代 verification_passed 条件；真正的上游结果变化只重开相关后继，旧结果及实际来源保留。已声明上下文的传递变化及每项检查约定均核对，不因默认资料目录中无关记录追加而使整项结论失效。

任务验收和整项验收分别保存，Task VER 不能封存整个 Change。最终集成核对全部当前任务、顺序共享输出的最终字节、整项检查和双维审查；任务检查通过后仍可出现真实集成失败。原范围内可引用该失败在同一 REV 修复，旧失败不覆盖；整项通过后出现更新的必需失败仍阻碍封存。中断测试实际在 Task 验收提交后退出 35，后继等待真实元数据恢复，不把未收尾 run 直接当可消费来源。

集中修正版本映射校验、任务发现归属、传递上下文／Task 检查配置核对及旧简单流程错误码顺序。最终 **283 项回归通过（27.507 秒）**，其中复杂提案／执行 38 项（20 项执行用例），[完整输出](evidence/imp006/component-tests-task-execution-full.txt)与[本截点自审／未完成项](evidence/imp006/task-execution-validation.json)已保存。五个改动 Skill 的 quick_validate、源码包清单及文档检查通过。

独立完整 50 文件包从非源码 cwd 在中文／空格路径实际执行 21 条 CLI 命令、13 项检查：未就绪拒绝 → 真实文件段暂停 → 整包移动 → 新 CLI 从原结果及授权续接 → 上游任务验收 → 后继实施 → 真实负数集成失败 → 拒绝封存 → 同 REV 修复 → 最终集成通过和封存。三个原独立测试文件字节保持，最终无 started run；[摘要](evidence/imp006/task-execution-cli-proof.json)及[原始输入／响应](evidence/imp006/task-execution-cli-trace.zip)保留，分发摘要为 `636d87f844db052abc10832da6e6c50b35399c5505485e6f5d2d562dbd4b1a66`。这仍是实际工具流程加受控审查输入，没有原生宿主安装或模型请求。

当前预重构执行仍明确拒绝，不以判据字段代替前后行为证明；REV 尚未开放。下一步完成这两部分及复杂场景双宿主验收后再收口 IMP-006，M2／M3 仍未完成。

### IMP-006：必要预重构的原判据与前后证明

已接通真实前检查 → 原代码／判据字节快照和不可变事件 → 文件段 → 原检查复验。原检查失败、零测试或执行改变现场时不提交候选；后检查失败保留已做文件与原证明，不在已改代码上重新定义“重构前”。只读判据与输出的实际目标必须不重叠，方案后的目录别名变化及实际写前也核对。快照复用现有无路径 artifact 版本，不改正式文档的批准版本或权威。

新增 apply 的 preservation_only=true／files=[] 准备步骤，安全结束为 partial／before_only，Task 保持 in_progress。准备后的文件段可按原 pause 不运行检查，新会话再完成后检查；没有原证明的无检查暂停在写前受阻。原 run／event、原文件字节、真实命令证据、判据和依赖共同核查，证明不能代替当前修改授权。文件提交后和 Task 已 done、run 尚未收尾时分别实际退出 35，再由维护恢复核实原日志；恢复不重跑检查，未完成配对仍待真实执行，已完成事实保留。

最终 **298 项回归通过（30.250 秒）**，其中新增 15 项预重构测试；[完整输出](evidence/imp006/component-tests-preservation-full.txt)和[本截点自审与未完成项](evidence/imp006/preservation-validation.json)已保存。定向用例还确认真实前／后检查进程可取得独立短写锁及 SQLite 写事务；空后检查即使退出零也不能完成。两个修改 Skill 的 quick_validate、包清单与文档检查通过。

完整 51 文件分发包在独立 cwd、中文／空格目录实跑 23 条 CLI 命令、13 项检查：提取报告真正依赖的单次迭代汇总／计数接口并保留原 total 行为 → 只准备原证明 → 无检查文件暂停 → 整包移动及新 CLI 续接 → 后检查实际失败 → 沿同一原证明修复 → 新接口、任务及最终集成通过 → 封存。四个原独立测试文件保持；独立零测试项目拒绝证明且未提交文件。[摘要](evidence/imp006/preservation-cli-proof.json)、[原始命令及证明字节／检查记录](evidence/imp006/preservation-cli-trace.zip)和完整包已保留，分发摘要 `4aa4932c8e7af15cb04940d921f77a1c824f6453ac372cdd1901fd1fe65bb319`。

本证明限已声明检查及输入，不能扩大为未测行为保证；受控 CLI／自审仍不冒称独立模型审查或新增原生宿主验收。下一步实现 REV 比较、范围接受及仍适用结果复用，再完成两个宿主复杂场景验收。IMP-006 继续 in_progress，M2／M3 尚未完成。


### IMP-006：REV 比较、范围接受与结果继承

alpha.6 已开放 update.revise。修订保存完整实际呈现方案、理由和逐任务定义比较；Task 沿 local_key 保持局部编号、新建 UUID，旧 Task／REV／结果不覆盖，退役 TASK 和 AC 编号不回收。格式与展示调整保留含义、已接受依据和仍适用结果；自身定义、上下文、检查及真正上游变化重开相关任务。核心 spec 变化默认影响全部任务，有实际依据的局部影响单独记录；全项含义改变不能沿用旧整体验收。

缩减文件／AC、改写 AC、移出核心约束或丢失原调查判据时，先返回具体 candidate／candidate_digest，保留旧头；实际接受绑定完整新方案、定义摘要、被移出内容和当前文件／上下文／检查依据。其他语义修订可保存草案，但实施和验收前仍需接受；按同一候选接受现有 REV，不重复分配任务。范围移出不删除业务文件，外部编辑不能被默认为已完成。

复用引用实际旧 run／Task VER／整项 VER 与预重构原证明，不克隆假通过记录。原阻碍发现、实际失败修复依据及原证明保留，格式修订后的正常续接仍核对同定义和原授权子集。集中修复了继承失败无法用于修正、共享输出在部分暂停时旧已完成字节遮盖新现场，以及升级路径可能静默失去调查依据的问题。修订提交后实际进程退出 36，再恢复已提交元数据；不重复修订、分配 Task 或运行检查。protocol 升为 v5、schema 仍 v1，真实保留 alpha.5 写入器拒绝新档案且数据库不变。

最终 **325 项全量测试通过（36.741 秒）**，其中 27 项 REV 专项通过；[完整输出](evidence/imp006/component-tests-revisions-full.txt)及[本截点验证／自审](evidence/imp006/revision-validation.json)保留。两处旧包能力断言仍将 update 当作未开放，已随新接口更新并全量复验，初轮输出保留。既有 evolve-propose Skill 按 writing-for-agents 指引增加 REV 分支指针，运行约定、请求协议和安装／使用说明同步；包清单和 Skill 校验通过。

独立 52 文件完整包从非源码 cwd、中文／空格路径执行 **20 条 CLI 命令、7 次真实检查和 15 项断言**：文件段暂停 → 格式修订 → 整包移动 → 新 CLI 沿原来源续接 → 上游实际任务验收 → 后继实施与整体验收 → 局部语义草案拒绝实施 → 具体接受后只重做相关任务 → 旧整项 VER 拒绝封存 → 新整体验收 → 范围缩减先保留旧头、拒绝陈旧接受 → 具体接受与最终封存。原独立测试、历史 Task 行与移出范围的业务文件保持，终点无 started run 或占用。[摘要](evidence/imp006/revision-cli-proof.json)、[原始输入／响应及数据库快照](evidence/imp006/revision-cli-trace.zip)、[完整 alpha.6 包](evidence/imp006/revision-package-alpha6.zip)已保留，分发摘要为 `55be374a378ddb3b3fb2cf6a9b7dab448d8a30278b0def8f849ca94683590fb7`。

以上为当前环境的工具流程与明确受控审查输入，不冒称原生宿主或独立模型验收。下一步准备复杂场景的具体运行器／临时夹具及范围材料，再核对实际新模型授权，完成同完整包的双宿主复杂场景后收口 IMP-006；不恢复独立 Windows 门槛。M2／M3 与最终工程交付仍未完成。


### IMP-006：复杂场景双宿主运行器与隔离准备

运行器新增 structured 分支，复用既有 Codex／Claude 原生传输和安装发现方法，不新增服务、Skill 或运行时方法。七会话对应只提案、预重构文件暂停、仅格式修订、无旧聊天续接、局部均值需求修订、新需求完成封存及只验收外部回退；两个生产文件可写，五个独立测试只读。受检包保持前一 REV 截点的完整 alpha.6，分发摘要仍为 `55be374a378ddb3b3fb2cf6a9b7dab448d8a30278b0def8f849ca94683590fb7`，运行时代码与库存未变。

父检查以实际 SQLite、不可变来源和独立测试核实边界；新均值结果必须有真实的任务检查，不能只增加 AC 文本。新增 13 项运行器回归包括完整七阶段的真实工具流和负例；**全量 338 项通过（41.402 秒）**，见[完整输出](evidence/imp006/component-tests-model-runner-full.txt)和[准备／范围核对记录](evidence/imp006/model-runner-preparation-alpha6.json)。一次负例因漏登记新均值检查先触发另一独立门禁，已补齐夹具前置以验证目标 CORE 保留分支，断言未放宽，初轮输出保留。

两个全新隔离配置实际安装同一完整包并各发现八 Skill；Codex 未启用项目发现零个。实测宿主为 codex-cli 0.154.0／Claude Code 2.1.117。prepare-only 在模型客户端和模型传输之前退出，两宿主均 model_requests_sent=false、passed=false。实际安装缓存逐文件库存核对完成；没有复制个人配置、凭证或初始化业务档案。原始安装、发现及七段输入在[准备材料](evidence/imp006/model-preparation-alpha6.zip)，实际运行器源码与父检查在[源码快照](evidence/imp006/model-runner-alpha6.zip)。

[具体验收方案](evidence/imp006/model-acceptance-plan.md)及 [Codex 范围](evidence/imp006/codex-model-scope-alpha6.json)／[Claude 范围](evidence/imp006/claude-model-scope-alpha6.json)已固定；缺实际授权或摘要不符，在建项／安装／模型调用前拒绝。本次七文件／七会话超出原四文件／五会话授权，依据根 AGENTS 第 3 条完成扩展核对，用户已明确答复“授权两个宿主及同范围复验（推荐）”；现已使用冻结运行器与包派发两个宿主，见[派发记录](evidence/imp006/model-dispatch-alpha6.json)。实际结果仍待复核。IMP-006 保持 in_progress，安装／父检查不代替原生模型语义验收，不恢复 Windows 前置。


### IMP-007：正式文档候选、内容检查与集中审阅

按[独立实施方案](evidence/imp007/implementation-plan.md)推进。alpha.7 已开放 sync.propose／check／review，只保存正式文档具体全文、基线、内容判据、检查和逐项批准／拒绝／延期；不隐含写入正式文件或应用后通过。替代版本不继承旧批准，历史正文和决定可查；最新失败检查阻止沿用旧通过，重试返回原回执。真实进程在候选事实提交后退出 41，再由 recover 只补齐元数据，不重复提案或检查。

集中修复三处已复现问题：init 展示扩展字段误识别为 sync 元数据、旧正文重新提出时从历史版本分叉，以及旧拒绝被 superseded 状态遮盖。最终 **355 项全量测试通过（44.351 秒）**，其中 17 项候选专项通过；[验证与自审记录](evidence/imp007/candidate-validation.json)保留初轮失败及复验依据。源码清单、修改 Skill 和设计文档检查通过。

[完整 alpha.7 包](evidence/imp007/candidate-package-alpha7.zip)在非源码 cwd、中文／空格路径及整包移动后执行 19 条 CLI 命令、4 条受控内容观察和 16 项断言；正式文件保持原批准基线，无伪造 Task／应用后 VER，无悬挂运行。[摘要](evidence/imp007/candidate-cli-proof.json)与[原始输入、响应及一致数据库备份](evidence/imp007/candidate-cli-trace.zip)保存，分发摘要为 `1c7dad5f5df596b8e55a6292296bc3d2763531d98a9a5225bf5c80c3b99959c1`。这些受控观察不替代原生模型语义验收。

sync.apply、必需文档交付、delta 应用与同文件批准链尚未接通；旧完整写入器实际拒绝新 owner 候选，本步骤仍为 protocol v5／schema v1。接通必需 Task 条件及正式应用时先升协议，保留旧完整包。IMP-007 继续 in_progress；IMP-006 的已授权双宿主验收独立使用冻结 alpha.6，M2／M3 尚未通过。


### IMP-006：原生七会话首轮结果与权限边界修复

用户已明确授权两个宿主及同范围必要修复复验。Codex 实际使用账户默认 gpt-6-astra，七个新会话、101 条原生命令项、全部父检查及轨迹／数据库复核通过；原 total 证明跨暂停和格式 REV 保留，均值修订只重开 REPORT，实际新验收后封存，最后只验收正确发现外部回退并追加 blocked VER。历史 passed／封存和 Task done 不变，无 started run 或占用。[Codex 复核](evidence/imp006/codex-model-review-r1.json)及[原生轨迹与临时项目快照](evidence/imp006/codex-model-r1-alpha6.zip)保留；这是该宿主与冻结 alpha.6 范围通过，不代替另一宿主。

Claude 首轮最终结果包含 8 条 permission_denials，旧运行器只看进程退出零，未识别并已启动第二场景。复核发现后立即终止该控制进程组，保留已写事实：CORE in_progress、REPORT todo、无悬挂 run／claim；未假造整批通过。[失败复核](evidence/imp006/claude-model-review-r1.json)与[原始现场](evidence/imp006/claude-model-r1-alpha6.zip)保持 failed。具体不兼容形式是安装根的 Bash ls／cd、shell 复合操作与 $PWD 参数，正常绝对字面路径的单条 CLI 命令在同一原生轨迹中已实际执行成功。

修正运行器为流式读取明确权限拒绝或原生错误即终止该模型进程组并保存原始输出；退出零的 permission_denials／is_error 也不能通过。Codex 意外权限／补充输入请求同样结束批次。Claude 输入明确使用原已有的 Read／Write 和单条命令形式，不提升宿主权限、不改个人配置或模型。真实子进程回归先复现 3 项失败，修复后 **361 项全量通过（45.164 秒）**，含 7 项传输回归；其中实际权限事件后子进程后续文件效果未发生，超时输出仍脱敏保留。见[修复验证](evidence/imp006/native-transport-fix-validation.json)。

修正后冻结运行器使用原 alpha.6 完整包，重新完成隔离安装／八 Skill 发现和无模型预检；[准备记录](evidence/imp006/native-transport-fix-preparation.json)与[源码快照](evidence/imp006/model-runner-alpha6-permission-fix.zip)保留。已依原“同范围复验”明确授权执行 Claude 全新批次，仍为七文件／七会话、MiniMax-M3.1-Flash 及原权限；复验首条工具调用仍为 Bash ls 安装缓存，真实权限拒绝出现时流式 guard 即终止模型（exit -9），控制器退出 1。六个初始业务文件完全未变，未创建 history.db，没有进入后续会话；[复验记录](evidence/imp006/claude-model-review-r2.json)和[原始轨迹](evidence/imp006/claude-model-r2-alpha6.zip)保留。未再派发第三轮，后续先调查正常安装资料在宿主中的可访问布局，不提升权限或重复被拒动作。[派发状态](evidence/imp006/model-dispatch-alpha6.json)单独记录本轮，首轮失败不覆盖。IMP-006 保持 in_progress，M2／M3 尚未通过。


### IMP-007：正式文档实际应用与应用后验收

alpha.8 新增 sync.apply／verify.knowledge，复用原文件 journal、资源 claim 和恢复入口。具体候选版本、已安全收尾的批准／最新内容检查及原正式版本有效后才写入；delta／真实应用／artifact 版本独立保存。重复请求保留回执，已应用旧 delta 不重写当前文件，后继候选不继承批准，格式 REV 保留真实产物而不重放旧应用。

简单方案及复杂 Task 可声明 sync 负责正式文档。候选检查不完成 Task；全部实际产物及 AC 覆盖齐备后仅形成实施结果，verify 仍重新核对实际目标、内容及规范。文档未应用、来源未安全收尾或缺应用后适用通过时不能封存。纯文档可无 Change 单独建立 applied VER；局部文档 VER 不能替代整项验收。实际字节及目标版本留存，外部编辑后新 VER blocked，旧 passed／Task／封存截点保持。

业务关联的 followup 引用真实实现验收，应用／恢复写前和应用后复验均重核定义、业务输出、上下文、检查配置及相关新失败；附带知识可在封存后具体批准应用，不重开原工作。真实进程退出 51／52／53 覆盖登记 journal、文件提交及事实提交；退出 54 覆盖独立内容 VER 记录收尾。恢复不重跑检查或重复完成 Task，第三种内容保留冲突。

专项边界检查实际复现“文档已提交但 run 未安全收尾时下游仍消费 task_completed”，补齐原应用来源／实际字节门禁后同用例阻止下游写入。正式文档位于 evolve/ 时，实际受检 scope 也可作为审查发现位置，避免隐藏文档阻塞发现。schema 升为 v2、protocol 升为 v6；真实保留 alpha.7 完整写入器拒绝新档案且文件／数据库不变，不自动迁移。

最终 **386 项全量测试通过（48.992 秒）**，其中 25 项正式应用专项通过。[验证与自审记录](evidence/imp007/application-validation.json)、[V 分支证明与缺口](evidence/imp007/application-acceptance-map.json)保留初轮失败及修复依据。三个修改 Skill 校验、包清单及设计文档检查通过。新增正式 module 使用同一写入协议，未新增宿主或个人配置。

[完整 alpha.8 包](evidence/imp007/application-package-alpha8.zip)从非源码 cwd、中文／空格路径运行并整包移动后执行 **20 条 CLI 命令、1 次安装包内实际现场观察和 17 项断言**，覆盖具体批准 → 真实应用 → 独立内容验收不足以封存整项 → 整体验收／封存 → 外部改变后的只复验／旧 delta 不重放。无虚构 argv 检查、悬挂 run 或 claim。[摘要](evidence/imp007/application-cli-proof.json)与[原始输入／响应及一致数据库备份](evidence/imp007/application-cli-trace.zip)保留，分发摘要 `5687de463bece00acbb95bd73fe0e5aeabc99a336641c98d26f8ccdf37d2ef8e`。内容观察为明确受控夹具，不冒称独立模型审查或宿主语义验收。

下一步完成同文件批准 patch／前继链、外部版本采纳与多 owner 接入，再准备知识场景的具体原生验收材料。IMP-007／M2 仍未通过；IMP-006 的 Claude 权限门槛仍保留，本轮未调用模型。


### IMP-007：同文件具体批准差异与实际前继链

alpha.9 接通单 sync owner 的精确 UTF-8 原字节范围、old/new 内容和 semantic_target，完整候选必须等于声明差异的实际结果。插入／移出条目分别形成 add／remove delta，整篇候选继续要求原精确基线。批次只保存明确提案引用和逐项决定，分组不隐含批准；应用依赖必须已经实际生效且含义仍保留。

前项改变正式文件后，后项只沿每步已安全收尾的 artifact／application 事实平移原范围；拒绝重叠范围、相同语义目标、未知版本与外部字节。宿主先读取实际组合正文，再具名检查其基线、结果和全部声明语义目标；原提案／批准摘要不变，真实应用另存实际前后摘要和冻结 effect。字节证明不等于领域语义独立，受控内容观察也不冒称模型判断。

初轮同文件 Task 复验实际发现：上游含义已由批准链保留，重新验收后新的整篇指纹却使后继被误阻。修复为文档依赖核对真实 application 引用及仍保留范围，业务代码依赖保持原指纹条件。同文件每个必需 Task 的应用都进入最终验收；第一项新失败仍阻止使用旧整项通过封存。未安全收尾的正式版本也不能成为新候选基线。

真实进程在组合文件写入后退出 55，恢复原冻结 effect，不重新组合到新现场、不重跑检查或重复分配应用。完整旧 alpha.8 写入器实际拒绝新档案，数据库不变。当前 protocol v7／schema v2，完整旧包保留，不隐式迁移。

最终 **402 项全量测试通过（51.956 秒）**，其中 16 项批准链专项通过；[验证与自审记录](evidence/imp007/patch-validation.json)及[本截点 V 分支映射](evidence/imp007/patch-acceptance-map.json)保留失败与复验。包清单、现有 archive Skill 和文档检查通过。

[完整 alpha.9 包](evidence/imp007/patch-package-alpha9.zip)从非源码 cwd、中文／空格路径执行，整包移动后继续使用公开 CLI，完成 **29 条命令及 15 项断言**：两项同文件必需文档方案 → 独立具体批准 → 上游真实验收 → 缺组合观察拒绝 → 保留前项的实际组合 → 上游再次验收 → 旧整项通过遭第一项新失败阻止 → 新整体验收和封存。原批准均保持，实际应用每 delta 一次，查询字节不变，无 started run 或 claim。[摘要](evidence/imp007/patch-cli-proof.json)与[原始命令、结果和一致库备份](evidence/imp007/patch-cli-trace.zip)保留，分发摘要 `f59fbe6748fd70a6afca6984ba661be61c6464ca9a5157260bb17683df22eb6e`。

第 3 项尚需 init／learn 的共同应用路径与不同 owner 的同文件证明，以及外部正式版本采纳／过时提案集成；随后准备具体知识场景原生验收。IMP-007／M2 继续 in_progress，IMP-006 Claude 权限门槛未关闭；本轮没有模型请求或对外操作。

### IMP-007：初次正式文档与 init／sync 实际交付

alpha.10 将结构化 init.baseline.propose／apply 接入已有候选、检查、逐项决定、文件 journal 与实际应用事实。集中 sync.check／review 只记录具体内容观察及用户决定，文件由实际 init owner 写入；后续正式修订由 sync owner 负责。未登记既有文档可按原字节成为正式基线，新文件不存在与空文件分别绑定。普通 apply 仍不能生产正式文档 Task 的结果。

必需初次文档声明 responsible_action=init，绑定真实 Task／AC 和具体方案；应用只形成真实产物，verify 再验收目标。同文件案例先由 init 登记既有未映射文档中的明确狭义差异并实际验收，再由 sync 基于已形成的正式版本提出后续独立差异。保留初次批准与真实 application，后续应用后可再次验收初次 Task，最后核对全部成果并封存。这条顺序不代表尚未建立正式基线时即可预提 sync 候选，也不覆盖 Learn 或整篇初次含义在任意后继改动下的保留。

边界复核实际发现：旧式初次候选尚未应用时，另一候选按不变字节登记正式映射，旧候选仍可能以“初次”的身份覆盖新权威。保留失败用例并补齐两条应用路径的正式映射检查；结构化候选也不能通过旧式内联批准降级。真实退出 56／57 分别验证文件提交及候选元数据提交后的恢复，只核实原事实，不重复检查、应用或 Task 完成。

最终 **415 项全量测试通过（53.409 秒）**，其中 13 项初次 owner 专项通过；[验证与自审记录](evidence/imp007/initial-owner-validation.json)及[V 分支范围](evidence/imp007/initial-owner-acceptance-map.json)保留实际缺口。安装、使用和共享指南已同步，两个修改 Skill、源码清单及设计文档检查通过。schema v3／protocol v8，实际完整 alpha.9 写入器拒绝新档案且数据库不变；旧完整兼容包保留，不自动迁移。

[完整 alpha.10 包](evidence/imp007/initial-owner-package-alpha10.zip)从非源码 cwd、中文／空格路径执行并移动整包，完成 **24 条 CLI 命令和 18 项断言**：完整 init／sync 必需文档方案、具体检查与决定、错误 owner／旧式降级拒绝、两次真实应用、初次 Task 再验收、整项通过与封存。来源分别为 evolve-init／evolve-archive，原初次批准保持，无 started run 或 claim。[摘要](evidence/imp007/initial-owner-cli-proof.json)与[原始输入／响应、一致库备份及控制器](evidence/imp007/initial-owner-cli-trace.zip)保存，分发摘要 `aab23c603db5c71c1c58efb79df181d0db0b4c42e2990b2371f330e2e7da4199`。

Learn 规则 owner、外部正式版本采纳／过时提案集成及具体知识场景的原生验收仍未完成。IMP-007／M2 保持 in_progress，IMP-006 Claude 权限门槛保留。本轮未调用模型、修改个人宿主配置或对外发布；内容观察均为明确受控夹具。

### IMP-007：Learn 实际规则交付与同原基线多 owner 批准链

alpha.11 开放 learn.promote 的 stage=propose／apply，使用同一正式候选、集中检查／决定、文件 journal 和目标验收协议。规则候选明确绑定经验版本、当前状态、留存观察、已知反例和适用范围；假设、无实际证据的引用、未复核反例及停用来源不能升级为规则。经验记录及 candidate／active 状态保持原含义，只有具体批准的规则才由 learn 实际应用，检查脚本或 CI 改进仍归普通 Change。

真实应用将 rule_bindings 与 application／artifact 一起提交，实际来源核查包含该关联。必需规则 Task 只消费实际产物，仍需新的目标验收；已应用来源出现新状态／反例时，查询标待复审，新目标验收受阻，保留正式正文、旧通过和封存事实。已复审的新依据即使不改正文也可形成具体后继候选，经检查／批准后关联新版本，不重放旧 delta。相同被拒正文不能以更换 sync／learn owner 绕过。

同一原始正式文件上的 sync／learn 候选分别呈现并在明确批次中具体批准，先完成上游实际交付和 Task 验收，再沿真实差异链组成后项。必须实际检查组合后的正文；原批准和前项含义保留，前项可追加新 Task 验收，最后整项通过后封存。此分支补充不同 owner 同原基线的工具证据，仍不冒称领域语义由字节证明自动确定。

初轮专项发现漏接 Learn 的文档产物检查入口，补齐后原必需验收断言通过；中断夹具分别受到真实遗留锁和未收尾日志保护门禁阻止，改为验证实际保护与原操作恢复，没有伪造不可发生的中间反例。完整包方法枚举同步新增 learn.promote，仍逐项核对全部真实方法。真实退出 58／59 覆盖规则文件提交及候选元数据提交后的恢复，不重复分配应用、规则关联或执行检查。

最终 **434 项全量测试通过（59.104 秒）**，其中 19 项规则 owner 专项通过；[验证与自审记录](evidence/imp007/rule-owner-validation.json)及[V 分支范围](evidence/imp007/rule-owner-acceptance-map.json)保留失败和修复依据。两个修改 Skill、源码清单与设计文档校验通过，安装和使用说明已同步。当前 schema v4／protocol v9；完整 alpha.10 写入器实际拒绝新档案且库字节不变，旧完整包保留，不自动迁移。

[完整 alpha.11 包](evidence/imp007/rule-owner-package-alpha11.zip)从非源码 cwd、中文／空格目录执行并移动整包，完成 **40 条公开 CLI 调用和 20 项断言**：真实失败／成功检查产生经验 → 初次基线 → 同原基线两个 owner 的必需文档计划及批准 → 错误 owner／过早应用／缺组合观察拒绝 → 实际应用、Task 再验收、整项通过与封存 → 后续采用及真实失败反馈 → 规则待复审与新验收受阻。原正式文件、独立测试、旧 passed 和档案封存保持，无 started run 或 claim。[摘要](evidence/imp007/rule-owner-cli-proof.json)与[实际命令／响应、控制器和一致库备份](evidence/imp007/rule-owner-cli-trace.zip)保存，分发摘要 `c94ecbfca6644e6478f0829890eb4b816584819b28a8cd9ba0f97d1cf51e21ed`。

下一步补外部正式版本采纳、已归档 A 的待审项被 B 替代的集成，再准备具体知识场景原生验收。完整反例复审、对未执行方案的影响及转检查流程保留在 IMP-010，未提前称通过。IMP-007／M2 仍 in_progress，IMP-006 Claude 权限门槛保持。本轮未调用模型或改个人配置，全部新增语义观察与反馈均为受控夹具。

### IMP-007：具体外部全文采纳与已归档提案的后继

alpha.12 接通 sync／learn 的具体 adoption 候选，分别绑定原正式 artifact 版本／摘要、当前外部字节、实际来源与含时区观察。内容必须是实际外部全文，额外改写另起候选；候选、内容检查和具体批准均不改变原正式权威。对应 owner 实际应用后登记 application／artifact，明确报告 adopted_external_bytes=true、file_bytes_written=false，文件字节和修改时间保持。必需采纳 Task 仍需实际产物与新目标验收才能封存，规则来源门禁照常核对。

采纳声明的 edits 来自保留的原正式字节，证明链分别核对注册前驱与实际外部基线。旧已批准狭义差异只在明确批次、真实来源和当前组合观察下继续；整篇／重叠旧含义不能覆盖新版本。之后外部再次编辑，或原正式权威已推进，即使当前又出现相同外部字节，旧采纳仍受阻。真实退出 61／62 验证候选元数据及正式登记前中断的恢复，仅补原事实，不重写文件或重复分配。

实际 A／B 集成覆盖 A 先交付并封存、留延期或已批准未应用知识候选，B 再交付不同实际行为并建立适用验收，新候选明确替代旧版本。旧 A 正文、决定／批准、VER 和封存保持，旧批准不转移，也不能覆盖 B。候选可查 superseded_by，已归档工作项通过 knowledge_proposal_refs 导航旧项和后继；查询不写文件或补事实。

最终 **452 项全量测试通过（61.476 秒）**，其中 18 项外部／过时提案专项通过。[验证与自审记录](evidence/imp007/external-validation.json)及[V 分支范围](evidence/imp007/external-acceptance-map.json)保留覆盖与限制。首轮夹具把同正文、同 owner 的两个版本误当独立家族，修正为真实正式版本先推进、外部字节再返回的场景；没有放宽归并或版本断言。源码清单、archive Skill 和设计文档校验通过。当前 protocol v10／schema v4，真实完整 alpha.11 写入器拒绝新协议且库字节不变，旧包保留，不自动迁移。

[完整 alpha.12 包](evidence/imp007/external-package-alpha12.zip)在非源码 cwd、中文／空格路径及整包移动后，完成 **53 条公开 CLI 调用和 22 项断言**：外部字节未自动成为权威 → 具体采纳及必需 Task 验收 → 原独立批准沿采纳证明链继续 → A／B 实际独立字面量检查 → 旧 A 实现依据与旧批准受阻 → B 新提案／应用 → 原档案和后继查询保持。正式文档变更使 B 原整体验收失效时，运行时正确拒绝 STALE_VERIFICATION，重新检查当前现场、执行实际独立判据并记录新整项通过后才封存；初次控制器错误保留在[原始拒绝轨迹](evidence/imp007/external-cli-initial.zip)。[最终摘要](evidence/imp007/external-cli-proof.json)和[实际命令／响应、控制器及一致库备份](evidence/imp007/external-cli-trace.zip)保存，分发摘要 `60cc0574dc7eb31134f174e1322f592cefeb3ae9290463729c489318772e555f`，无悬挂 run 或 claim。

接下来准备具体知识场景原生验收运行器、隔离安装及范围，再按实际范围核对授权。本轮没有模型调用，文档语义观察均为受控夹具；工具证明不关闭原生门槛。IMP-007／M2 继续 in_progress，IMP-006 Claude 权限门槛仍保留；IMP-009 并发和 IMP-010 完整经验／检查改进保持后续切片。

### IMP-007：冻结原生知识范围及无模型准备

新增 `--knowledge` 验收运行器和 `model_knowledge_checks.py`，以四个临时文件、两份只读独立测试及每宿主九个新会话覆盖初次必需文档、真实 A 实现与经验、同原基线跨 owner 候选／具体决定／应用验收、外部全文采纳、已归档 A 的延期说明被 B 替代，以及最后只验收外部漂移。范围明确列出各阶段具体正式文本与批准／延期，不能重用此前不批准正式知识的算术授权。

父检查核对实际候选／决定／owner／application／rule_binding、真实 CODE 和阶段独立命令、Task／整项验收、正文与后继、旧运行／VER／证据不可改写及未决执行。只读预检、安装准备和模型派发分别执行；缺真实授权或范围摘要不匹配，在建档／模型派发前拒绝。权限、额度和原生错误的立即停止仍沿原传输守卫，未降低宿主权限或允许嵌套代理。

已知 Claude 首条拒绝来自缓存位于业务根外，本轮将登记安装根及独立宿主缓存放到临时项目 `.agents/evolve-acceptance/`；真实发现两者均位于工作根内。初版父检查仅保护缓存，核对 Claude 原位加载机制后补齐实际登记根的共同保护，增加源根被修改而缓存不变的拒绝测试，在没有任何模型请求前重新冻结控制器和安装准备。此处只验证位置与完整性，未将其写成 Claude 原生权限问题已通过。

最终 **463 项全量测试通过（65.254 秒）**，其中 11 项父检查专项通过。受控九阶段另保留真实历史库：4 个已封存工作、5 次正式应用及 1 个实际规则关联，无悬挂 run／claim；语义观察明确为夹具。首轮复用测试 helper 在复杂整体验收时缺默认 Task 身份，修正辅助版本查询绑定，保持真实整项／全部 Task 校验。原始输出、自审及覆盖边界见[准备记录](evidence/imp007/model-runner-preparation-alpha12.json)和[受控事实](evidence/imp007/controlled-parent-walkthrough-alpha12.zip)。

使用保留的完整 alpha.12 包（分发摘要仍为 `60cc0574dc7eb31134f174e1322f592cefeb3ae9290463729c489318772e555f`），Codex CLI 0.154.0 与 Claude Code 2.1.117 在各自独立配置／临时项目实际安装并发现八 Skill，Codex 外项目发现零个；从实际缓存运行 status，项目保持未接入、四文件原字节不变。两宿主都没有创建模型客户端、发送用户模型请求或选择替代账户模型。Claude 本地 `/skills` 准备 UI 的既有默认 M2.7 与实际待派发的进程选择 M3.1-Flash 分别记录，未改个人默认。

[冻结控制器](evidence/imp007/model-runner-alpha12.zip)、[双宿主安装／预检原始证据](evidence/imp007/model-runner-preparation-alpha12.zip)、[Codex 范围](evidence/imp007/codex-model-scope-alpha12.json)、[Claude 范围](evidence/imp007/claude-model-scope-alpha12.json)及[具体模型方案](evidence/imp007/model-acceptance-plan.md)已保存。控制器 SHA-256 为 `edaff36105aa35ddaef94b11b9e59ea0f87d2f678ab8b203c7c2b192f30a7d79`。IMP-007 继续 in_progress，等待新增具体范围授权后实际运行并审阅轨迹；M2 和 IMP-006 Claude 门槛均未关闭。

### IMP-006：临时安装位置与宿主摘要命令说明修复

Claude 第三轮将登记安装根与实际缓存放入临时业务根，原七场景／七文件／MiniMax-M3.1-Flash 与正常权限保持。[位置修复验证](evidence/imp006/installation-layout-fix-validation.json)已通过 466 项全量和 16 项复杂专项。实际前三会话通过：完整提案保持未接受；先保存真实原行为前证明、实施 CORE 文件段后正常暂停；仅展示 REV 保留原授权、任务定义和部分进度。第四会话读取真实 status／resume 后，自行执行 `shasum -a 256` 需要额外权限，流式 guard 立即杀死该原生进程组，控制器退出 1；后三会话未启动。无待处理 run／资源占用，测试及 REPORT 未改，失败原始轨迹与[第三轮复核](evidence/imp006/claude-model-review-r3.json)分别保留，不能当作七场景通过。

现仅补充受控宿主既有 Bash 允许项及现场摘要来源说明：采用 Evolve 实际 status／resume 返回，不再额外调用摘要辅助命令，也不使用其他工具重做被拒摘要。native 权限选项未变，七段场景输入、原文件字节、可写路径与模型逐字段保持原授权范围；[命令说明修复验证](evidence/imp006/command-guide-fix-validation.json)通过 **467 项全量（66.453 秒）及 21 项运行器专项**，真实隔离安装发现八 Skill、保持未接入且无模型请求。[新冻结控制器](evidence/imp006/model-runner-alpha6-command-guide-fix.zip)与[准确范围](evidence/imp006/claude-model-scope-r4-alpha6.json)已保存，并沿原明确同范围复验授权派发 Claude 第四轮；[派发记录](evidence/imp006/model-dispatch-alpha6.json)跟踪实际状态。Codex 已通过结果不重复调用；IMP-006／M2 仍未通过，IMP-007 冻结材料和待新增授权保持不变。

### IMP-006：待批准修订候选与有效 REV 分开验收

第四轮原生前四场景通过，包括跨 REV 沿原前证明续接、CORE／REPORT 独立验收和整项集成，按会话边界保持未封存。第五会话在新均值方案中移出旧阶段“不实现均值”的 behavior／non_goals／tradeoffs，实际 update 正确返回 `scope_confirmation_required` 并保存完整候选；旧 REV 和旧任务仍生效。候选确实绑定了已登记 mean、仅 REPORT 定义变化，但父检查只读当前旧 REPORT，因“缺少 mean”拒绝。模型汇报标题也把候选误称新 REV，详细正文则明确旧版本仍生效。真实第五会话 native 退出零，控制器因父检查退出 1，后两场景未执行；没有权限／额度错误、遗留运行或占用。[第四轮复核](evidence/imp006/claude-model-review-r4.json)和[完整轨迹](evidence/imp006/claude-model-r4-alpha6.zip)保留，不能改写为通过。

先建立原生同形的本地反馈循环，连续两次不足一秒复现；再确认实际候选、登记检查和既有范围确认契约。修复只在父检查及两段场景说明：第五会话可保留真实完整待批准候选，必须核对旧 REV／Task／历史不变、原 AC 保留、CORE 同定义以及 REPORT 的 mean／integration 实际判据；汇报必须区分候选和已生成 REV。第六会话仍须以原固定均值范围具体接受同一候选，实际生成新 REV 后才能实施、验收、封存；候选未生效不能冒充新交付。内核门禁、源码清单和 alpha.6 包未改，原最终五个只读测试、原行为证明、依赖推进、新整项验收与末轮回退失败断言保持。缺 mean 检查或接受时偷换候选均有真实拒绝测试。

[修复验证](evidence/imp006/pending-candidate-fix-validation.json)为 **470 项全量（68.864 秒）／19 项复杂专项通过**，并再次完成真实隔离安装、八 Skill 发现和无模型预检。[冻结控制器](evidence/imp006/model-runner-alpha6-pending-candidate-fix.zip) SHA-256 为 `4637a63dc304561c14ae045695104eb1419b5bdc35d30d747df014ab8875fbcf`，[新范围](evidence/imp006/claude-model-scope-r5-alpha6.json)仍仅原七文件／七会话、两个生产文件可写、原 MiniMax-M3.1-Flash 与效果限制；两段输入只明确既有范围批准分支及报告事实。沿用户明确的必要同范围修复复验授权启动 Claude 第五轮，实际进程见[派发记录](evidence/imp006/model-dispatch-alpha6.json)。Codex 已通过的同包原生结果保持；IMP-006／M2 尚未通过，IMP-007 的冻结材料及新增授权状态不变。

### IMP-006：V-088 自适应梳理指引缺口与同包复验准备

按原 V 映射核对阶段完成要求，发现插件只笼统要求复用资料，没有随包提供选择轻量／定向深入／全局梳理、说明理由和范围、核对关键未知及停止条件的完整指引；不能仅凭既有复杂业务场景关闭 V-088。现将这一设计内义务补在单一 `shared/context.md`，由 workflow 的新工作／续接实施、init 的增量发现和 propose 的方案／调查入口定向引用。梳理深度与任务复杂度独立，复用可信背景，缺口只扩大相关范围，正式知识仍具体待审，不增 profile 或状态表。

版本为 **alpha.13／protocol v10／schema v4**，运行方法及数据库语义保持；源码清单 61 文件，摘要 `516247136070d6a2abb32d499191c5e65279e3558143dc2e23940b72233d0942`，独立分发摘要 `83cee98e7e1807e3347690b7fd633463651f519e9d0c34b91af9dfdedfc9efdd`。[验证记录](evidence/imp006/context-validation-alpha13.json)保留 470 项全量（69.186 秒）、19 项复杂专项和 22 项包／闭合引用检查。三 Skill 通过 quick_validate；系统与内置 Python 缺 PyYAML，venv 引导也失败，随后用独立临时 pip --target 补充校验器依赖，未改个人环境或运行包依赖，见[原始校验记录](evidence/imp006/context-skill-validation-alpha13.json)。

[完整包](evidence/imp006/context-package-alpha13.zip)、[冻结运行器](evidence/imp006/model-runner-alpha13.zip)、[双宿主无模型安装准备](evidence/imp006/context-preparation-alpha13.zip)以及 [Codex](evidence/imp006/codex-model-scope-alpha13.json)／[Claude](evidence/imp006/claude-model-scope-alpha13.json)准确范围已保存。仍是原七文件／七新会话、两个生产文件可写、五个测试只读、同一业务结果和最终判据；首会话补当前临时项目整体结构梳理、续接会话补实际生产／消费链路核对，不增加其他项目、正式知识批准或外部效果。这是修复原 IMP-006 V-088 缺口，沿用户明确必要同范围修复复验授权执行。原生审阅还须核对实际选择、理由、已覆盖来源与未知、停止条件和背景复用，准备不等于行为通过。

Codex alpha.13 原生七场景已派发，见[新同包派发记录](evidence/imp006/model-dispatch-alpha13.json)；Claude alpha.6 第五轮仍单独运行，不并发重启该宿主。其实际结果保留后再决定 alpha.13 同范围复验，不能把不同包证据混为同包通过。IMP-006／M2 保持 in_progress；IMP-007 alpha.12 冻结材料和待新增授权保持，未派发其新范围。

### IMP-006：上游产物上下文与正常暂停来源的运行时修复

alpha.13 Codex 首轮通过提案与正常暂停，在第三会话只读推断上下文会变而停止，实际未调用 update，因此父检查正确拒绝“没有新 REV”。实际 REPORT 上下文包含 arithmetic.py，它又是声明的 CORE 产物；旧完整包在全新受控项目两次重现展示修订丢失已接受含义，确认并非只凭模型推测。Claude alpha.6 第五轮通过前三场景；第四会话重新提交相同 CORE 字节并完成原后检查、任务验收及整项集成，原 before 证明保留，但没有 normal_continuation 关联原文件暂停，父检查拒绝且未进入后三场景。两批原始轨迹分别在 [Codex](evidence/imp006/codex-model-alpha13-r1.zip)／[Claude](evidence/imp006/claude-model-r5-alpha6.zip)保留，复核见 [Codex](evidence/imp006/codex-model-review-alpha13-r1.json)／[Claude](evidence/imp006/claude-model-review-r5.json)，无悬挂 run 或资源占用，失败没有改成通过。

现仅修复对应两处：声明祖先的产物由已有实际依赖结果、产物和条件核对，不再冻结成下游的旧外部上下文；其余固定上下文保持原字节核查。正常文件暂停的来源可由当前 Task 与证明过的同定义 REV 链唯一解析，运行时自动绑定实际 run／result_digest 并标明 resolved_from_task_result；原授权子集、撤销、项目／epoch、定义、源完整性和未决效果继续核查，明确引用更早 before_only 不能代替当前文件暂停。自动解析实际内部来源不等于授予新权限。父检查还收紧为当前 CORE 实际实施／检查尝试的来源，blocked 元数据不能冒充完成。

新版本 **alpha.14／protocol v11／schema v4**。同 schema 的真实 alpha.13 旧写入器已实际拒绝新协议且数据库字节保持，防止旧写入器绕过新续接门槛；不迁移既有资料。源码清单 61 文件，摘要 `6c7b756199664c910ec22ef5d8dad2899ea627077c2ee550851bc78322da07c3`，分发摘要 `c7806c6dbb28c7d344afa513d189fe60c8336218c7172ee0f875fb56c354ff34`。[本轮验证](evidence/imp006/runtime-fix-validation-alpha14.json)保留 **477 项全量（71.977 秒）、25 项复杂、28 项 REV、12 项续接专项通过**；新增反例核对外部上游改动、独立固定上下文漂移、原授权扩张及用 before_only 替代当前暂停仍被拒绝。

又用独立完整包经公共 CLI 重放原生保存的完整方案和四个原判据，共 **12 条命令／9 项断言**：真实前证明、正常文件暂停、纯展示 REV、跨 REV 自动绑定来源、保留原 before 证明、任务及整项真实检查后封存，无待处理 run／claim，见 [CLI 证明](evidence/imp006/runtime-cli-proof-alpha14.json)和[完整原始材料](evidence/imp006/runtime-cli-trace-alpha14.zip)。最初重放器误查不存在的返回字段，修正的是重放器断言，原始失败也保留；受控观察不称独立模型或原生通过。

[完整包](evidence/imp006/runtime-package-alpha14.zip)、[冻结运行器](evidence/imp006/model-runner-alpha14.zip)、[双宿主无模型安装准备](evidence/imp006/runtime-preparation-alpha14.zip)与 [Codex](evidence/imp006/codex-model-scope-alpha14.json)／[Claude](evidence/imp006/claude-model-scope-alpha14.json)准确范围已保存。沿原必要同范围修复复验授权，原七段输入、七文件、两个可写生产文件、五个只读测试、七新会话、模型与效果限制均相同；native 传输权限未变。实际派发另在 [alpha.14 记录](evidence/imp006/model-dispatch-alpha14.json)，仍需两宿主同内容摘要的实际轨迹与 V-088 行为审阅后才收口 IMP-006。IMP-007 冻结 alpha.12 材料与待新增授权保持，不混作已授权新知识决定；M2／M3 尚未通过。

alpha.14 两个宿主的新七场景批次已沿原同范围必要修复复验授权派发，使用各自全新临时项目与相同 `c7806c6d…` 完整包，见[实际派发](evidence/imp006/model-dispatch-alpha14.json)。当前仍是运行中，准备、回归、公共 CLI 重放和模型请求已派发均不作为原生通过结论；任一宿主权限／额度／传输／父检查失败立即停止该批次，保留真实轨迹。

### IMP-007：按修复后 protocol v11 重新冻结无模型准备

当前内核已因 IMP-006 实际问题修复为 alpha.14／protocol v11，不直接把旧 alpha.12 的准备视为当前新写入器已验。现以同一 `c7806c6d…` 完整包重新完成知识范围预检及双宿主真实隔离安装／八 Skill 发现，四个初始文件均保持、项目未接入，模型请求为零，见[当前准备](evidence/imp007/model-runner-preparation-alpha14.json)。477 项全量回归确实包含 11 项知识父检查和九阶段正向流程；[摘录](evidence/imp007/parent-tests-alpha14-from-full.txt)明确不是另一次专项运行，也不替代原生轨迹。

逐字段核对原 alpha.12：四文件字节、九段提示、Codex 默认模型／Claude 进程 MiniMax-M3.1-Flash、具体正式批准／延期及全部效果限制保持；只替换实际修复包、协议和经过核对的辅助源码摘要。[当前包](evidence/imp007/native-package-alpha14.zip)、[冻结控制器](evidence/imp007/model-runner-alpha14.zip)、[安装原始材料](evidence/imp007/model-runner-preparation-alpha14.zip)、[Codex](evidence/imp007/codex-model-scope-alpha14.json)／[Claude](evidence/imp007/claude-model-scope-alpha14.json)准确范围已保存。原 [alpha.12 方案](evidence/imp007/model-acceptance-plan-alpha12.md)、控制器、包及受控历史不覆盖。

新增四文件／九会话与正式知识决定的实际用户答复仍未收到；[当前派发状态](evidence/imp007/model-dispatch-alpha14.json)为 pending／not_dispatched。继续保留原待答问题，不重复发问，不使用已授权算术七会话或目标自动续行代替知识批准。IMP-007／M2 仍 in_progress。

### IMP-006：alpha.14 Codex 七场景与三种梳理深度实测复核

Codex alpha.14 新批次已退出 0，七个独立会话父检查均通过；主审又核对 **101 条实际命令**、七个最终汇报、实际库／文件、两份安装根以及保存的原始证据，见[本宿主完整复核](evidence/imp006/codex-model-review-alpha14-r1.json)与[原始轨迹](evidence/imp006/codex-model-alpha14-r1.zip)。初始完整 spec 未接受；真实 original 前证明及正常暂停保持；纯展示 REV 保留部分进度与接受依据；CORE 沿原文件暂停续接后取得独立验收，REPORT 随依赖推进，整项验收后按本轮边界保持未封存。REPORT 的实际初始上下文仍声明 arithmetic.py 为上游产物，验证了修复后的正常展示修订。

局部均值需求实际停在 scope_confirmation_required 候选，汇报明确“未生成新 REV、旧 REV 仍生效”；第六会话具体接受同一候选后才生成 REV3、仅实施 REPORT、取得新验收并封存，CORE 原结果及前证明保留。最后仅验收实际测得五测试中均值失败，新增 blocked VER，旧 passed／Task done／Change archived 及截点保持，未修复或重开；这个控制性负例保持原样。五份只读测试与安装字节逐字核对通过，无未决运行或占用，无正式知识应用。

V-088 也有实际选择及边界：首会话全局覆盖六文件并在入口、共享接口和测试约束明确后停止；展示修订按轻量核对已保存方案和继承记录；续接按生产／消费链路定向核对当前缺口，明确实现后检查、报告实现和整项集成为停止边界。实际规范观察者标明当前宿主自审，不称独立第三审。三个无匹配／不存在目录的只读探查、预期的初始和末轮测试失败，以及 shell 退出零中返回的 REVIEW_REQUIRED／CONFIG_PRESENTATION 错误均保留；后两者真实纠正，不隐去或改成首尝成功。

[十项 V 证据映射](evidence/imp006/acceptance-map.json)关联 **34 个实际通过测试**与原 CLI／本次原生证据，相关[测试源码快照](evidence/imp006/acceptance-test-sources-alpha14.zip)已保存；不把静态检查冒充自适应行为，也不推断全部全局 V 已通过。当前只确认 Codex 的相同 c7806c6d… 范围通过；Claude alpha.14 仍在运行，见[派发记录](evidence/imp006/model-dispatch-alpha14.json)，因此 IMP-006／M2 尚未收口。


### IMP-006：Claude alpha.14 额度终态与运行器修复

Claude 同包首轮前三场景（提案、原证明及文件暂停、展示 REV）通过父检查；第四个续接会话返回 MiniMax Token Plan 用量上限 **429／2056**，控制器已终止本批次，后续三场景没有派发。[实际复核](evidence/imp006/claude-model-review-alpha14-r1.json)和[完整原始轨迹](evidence/imp006/claude-model-alpha14-r1.zip)保留全部错误与原生内部十次重试；不把前三场景的父检查当作完整宿主通过。终态仍为 CORE 进行中、REPORT 待做、原证明 pending_after，无 VER、悬挂运行或资源占用，四个已存在测试和 report.py 字节未变。均值测试尚未由父进程加入。展示会话另有缓存 ls 和五条管道命令偏离宿主格式约定，虽未触发权限拒绝，仍逐项保留，不宣称干净完整验收。

冻结的旧运行器忽略了 system/api_retry 的限流事件，直到最后 assistant 错误才停止。已先建立真实传输边界失败测试，再仅修正首个 HTTP 429 重试事件立即结束进程组；用同一原始轨迹回放确认停止点从索引 115 的末尾错误前移到索引 105 的首个重试，另以本地进程断言不发下一请求，普通服务器重试仍可完成。[修复证据](evidence/imp006/rate-limit-guard-validation.json)记录 **23 项相关检查及 479 项全量回归通过（70.029 秒）**。这是运行器修复，插件仍为同一 c7806c6d… 完整 alpha.14 包；旧冻结控制器和原生记录未覆盖，也未再调用任何模型。

[修正后的冻结运行器](evidence/imp006/model-runner-alpha14-rate-limit-fix.zip)及两宿主仅预检范围已经准备，未安装新宿主配置或派发。[当前派发账本](evidence/imp006/model-dispatch-alpha14.json)明确 Codex 七场景已通过，Claude 因额度未完成；IMP-006／M2 保持 in_progress，依赖 IMP-006 的 IMP-008 不开工。后续模型验收需先有可用额度，不能自动切换模型／账户或重复探测额度。IMP-007 原九场景授权仍未收到实际答复，未来派发前须在同一业务范围重新冻结采用新停止处理的控制器，不能沿用旧处理器直接启动。


### IMP-007：同步首个限流停止修复的无模型准备

[知识运行器准备](evidence/imp007/rate-limit-runner-preparation-alpha14.json)已采用 IMP-006 验证过的首个限流事件停止处理，知识父检查及其余控制器字节保持，四文件／九提示／具体正式决定与模型效果边界逐字段不变。两宿主仅预检；既有安装根和独立缓存的完整摘要、全部文件以及四个初始业务文件再次核对，均为原 c7806c6d… alpha.14 包且项目未接入，无新模型请求或宿主安装。实际新范围、控制器归档和仍未派发状态已记录；修复前方案、账本和范围保留。

当前仍需 IMP-006 的 Claude 原生验收与 IMP-007 新范围实际授权／双宿主原生验收；本次自动续行不构成知识批准，也不证明额度恢复。组件及文档检查保持与原生验收分开，后续依赖阶段尚未启动。


### 2026-11-01：收到知识验收授权及额度恢复确认

已收到[IMP-007 的实际新范围授权](evidence/imp007/model-authorization-alpha14.json)，及[Claude 额度恢复的实际答复](evidence/imp006/model-availability-restored-alpha14.json)。新旧四文件／九提示／具体知识决定与效果边界保持，受检完整包仍为 c7806c6d… alpha.14；当前冻结控制器均使用首个限流事件即停修复，完整摘要和作用域在各账本记录。已启动 Codex 知识九场景及 Claude 原 IMP-006 七场景；Claude 知识九场景待前批终态后执行，不并行调用同一账户。旧额度错误、历史未派发准备和父检查失败均保留。

目标已随用户实际新输入恢复 active；当前是原生实际验收而非新的准备通过，两个切片仍为 in_progress。各宿主的退出状态、原始轨迹、字节与授权／历史事实及语义审阅全部核实前，不关闭门槛或推进其依赖切片。


Claude 恢复确认后的原范围第二轮已有[实际终态](evidence/imp006/claude-model-review-alpha14-r2.json)：只有 init 和首个 API retry 两条宿主流事件，首请求返回 HTTP429／rate_limit，运行器立即结束进程组；未见后续重试、助手业务动作、项目接入或任何六文件字节变化。未收到最终 2056 细因，不能把这次 429 单独解释成配额耗尽，也不能据人工恢复确认称当前调用成功。旧额度错误和新尝试分开保存；Claude 知识九场景不继续请求或自动换模型。

IMP-007 的[十项 V 映射](evidence/imp007/acceptance-map.json)关联当前 479 项全量中的 27 个真实通过检查，相关[源码快照](evidence/imp007/acceptance-test-sources-alpha14.zip)保存；组件、历史各 owner／补丁／外部采纳分支与原生审阅分列，不因局部检查宣布全局 V 或阶段通过。实际四文件原生范围复用现有 guide.md，没有独立既有 ADR 样本，不能据此声称覆盖所有 ADR 取舍行为。


### IMP-007：Codex 九场景原生验收及语义复核通过

同一 c7806c6d… alpha.14 完整包上，Codex 实际账户默认模型 gpt-6-astra 的九个新会话全部通过父检查，已复核 **152 条实际命令、47 个安全收尾的 Evolve 动作、6 项候选与 5 次实际正式应用**，见[宿主结论](evidence/imp007/codex-model-review-alpha14-r1.json)及[完整原始归档](evidence/imp007/codex-model-alpha14-r1.zip)。初次 guide 具体批准及实际应用保留原字节；A 的代码真实判据和候选经验支持具体 SPEC／RULES，逐项批准与延期不混用，sync／learn 沿真实同文件链实际交付并完成各级验收。具名内容和双轴观察明示当前助手自审，不冒称独立第三审。

实际外部追加经专门观察、检查及具体批准后只登记采纳，字节及 mtime 在采纳期间保持。B 使用原独立字面量 B 判据及新验收，旧 A 判据的当前失败保留；B 的两范围后继保留旧 A 延期原文、决定和可查询关系，不继承批准或恢复旧含义。批准应用 B 后重新运行 B 整项检查，四个工作项均 archived、六个 Task 均 done。末轮父进程只制造已声明外部范围漂移，模型仅新增 applied 目标 blocked VER `2194a9ed-cea9-4186-a9e4-85acc1c9c3ab`，preserve 判据实际 failed，原 12 条 passed、原应用确定事实及封存状态保留；应用的最新验收指针按协议推进，不把它称作整行字节不变。未修复该负例，当前全文保持 unconfirmed。

读取中两次猜测不存在 evolve-sync Skill、一次旧 .evolve/config.toml 路径，以及一次只读 fingerprint 辅助调用漏字段的实际错误均保留；之后使用实际资源／返回字段继续，没有隐藏失败或直接改业务／数据库。一条只读 search／resume 组合命令聚合输出为空，不独立作为事实证明。两个测试及安装／缓存全部包内摘要核对通过，无未决 run／claim，无个人配置修改、嵌套代理、发布或额外知识批准。

当前只确认 Codex 的具体九场景通过，Claude 知识批次仍因其先前受控请求的 HTTP429 未派发；IMP-006／IMP-007 和 M2 继续 in_progress，后续依赖不启动。新增实际知识授权已生效，不再把它写成等待答复；剩下的是 Claude 可用模型条件，不能用 Codex 结果代替另一宿主。

### 2026-11-01：按用户最新要求先以 Codex 验收推进

用户明确“需要3小时重置额度，先按codex来验收”，已保存[当前宿主范围依据](evidence/acceptance-host-policy-20261101.json)。重新核对两个 Codex 复核及原始归档摘要、479 项完整回归和各切片断言，IMP-006／IMP-007 分别取得[复杂功能门槛](evidence/imp006/stage-gate-codex-alpha14.json)和[正式知识门槛](evidence/imp007/stage-gate-codex-alpha14.json)。它们仅表示当前 Codex 验收范围通过，可推进直接依赖，不将 Claude 失败／未派发或跨切片的全局分支记成通过。

下一步按原计划实施 IMP-008；Claude 本轮不调用、不自动安排三小时重试，后续复验保留为开放验收事项。所有实际业务／正式知识及外部数据效果的授权门槛继续保留。

### IMP-008：SQL／数据范围与底稿导出按当前 Codex 范围通过

完整 alpha.15／protocol 12／schema 4 已完成 499 项全量、15 条独立公共 CLI、八 Skill 和文档检查。Codex 默认模型 gpt-6-astra 的五个新会话及 61 条实际命令已逐项复核：只调查、SQL-only 修复封存、有限关系底稿、移走来源后的只读再导出、数据变化后只验收。末轮实际失败保留，旧通过和封存不变。见[阶段门槛](evidence/imp008/stage-gate-codex-alpha15.json)、[实际复核](evidence/imp008/codex-model-review-alpha15-r2.json)和[原始材料](evidence/imp008/codex-model-alpha15-r2.zip)。只确认当前 Codex 与固定 SQLite 场景，不推断生产数据或 Claude 通过；已按直接依赖进入 IMP-009。

### IMP-009：取消、固定前置及跨 owner 组合的实际验证

完整 alpha.16／protocol 13／schema 4 已完成 526 项全量、100 条独立完整包公共 CLI 和八 Skill 检查；另一个完整正常暂停／取消／承接／具体重绑场景在 12 项跨项专项中通过。源码摘要 `01534ff4…`，实际完整包摘要 `92cdd7aa…`。[十三项 V 分支映射](evidence/imp009/acceptance-map-alpha16.json)保存 39 个真实测试引用及源码快照，不将其当全部全局 V 或 M2 通过。

收到用户对六文件、七新会话、初始基线与两项准确知识决定及同范围必要复验的[实际授权](evidence/imp009/model-authorization-alpha16.json)。首批前四会话通过父检查，第五会话已完成候选准备，但父检查器将初次基线的 `delivery=null` 当字典读取而异常停止，后两会话未派发；[失败轨迹](evidence/imp009/codex-model-alpha16-r1-evidence.zip)及原始失败摘要保留，未追改为通过。以原第五会话现场实际复现红灯，再仅改一行判空后同一父检查通过，三个控制器门禁测试通过。见[修复及范围链](evidence/imp009/controller-fix-alpha16-r2.json)。插件包、六文件、七提示、正式决定和效果限制逐字段保持，只有父检查文件摘要改变。

沿已批准的同范围必要复验启动全新临时项目及七新会话，见[第二轮实际派发](evidence/imp009/model-dispatch-alpha16-r2.json)。IMP-009 仍 in_progress；每轮退出零和自动检查均须另行核对实际轨迹与当前文件后才能收口。未调用 Claude、未修改个人配置、未启动嵌套代理或发布。

### IMP-009：真实跨项同文件组合触发的整项验收修复

第二轮前五会话通过，第六会话已准确批准并分别应用两项知识，RULE 通过验收并封存；DOC 的目标及 Task 复验通过，整项却因旧全文摘要受阻，未封存，末轮未派发。实际失败和原始轨迹见[第二轮归档](evidence/imp009/codex-model-alpha16-r2-evidence.zip)。确定性回归同样复现：实际应用保留证明有效、依赖无需重验、Task passed，唯独 whole blocked。[诊断探针](evidence/imp009/cross-formal-whole-probe-alpha16.json)排除了丢失应用证明与 VER 标识变化。

alpha.17 仅修正 structured 整项输出汇总：先由已有协议证明实际正式应用及声明范围仍保留，再使用这些正式文件的当前摘要；业务文件仍使用历史成果摘要，外部未批准字节不能取得保留证明。新增回归实际验收并封存首项，保留原 Task 结果和文件 mtime；追加外部内容后重新 blocked，封存及外部字节保持。曾因改代码后未刷新源码清单而触发完整性拒绝，失败日志也保留，刷新后通过；未绕过包检查。

[当前完整验证](evidence/imp009/runtime-fix-validation-alpha17.json)为 **528 项全量（81.641 秒）、125 条独立完整包 CLI／七组场景、八 Skill 及文档检查通过**。protocol 13／schema 4 保持，无迁移或旧批准重放。源摘要 `5c7257f4…`，完整分发摘要 `677f9c65…`；alpha.16 两个失败批次、各包及控制器保持。六文件、七提示和具体知识决定逐字段保持，沿原必要修复复验授权启动[alpha.17 原生七会话](evidence/imp009/model-dispatch-alpha17.json)，仍须实际轨迹复核，当前阶段未通过。

### IMP-009：补齐原生会话实际要求的复杂调查转修复绑定

alpha.17 首会话真实观察并保存原 red 调查，但复杂方案的根 analysis_basis 被 UNAVAILABLE 拒绝；模型保留绑定并停止，没有创建 A 或修改 total.py，父检查失败后未派发后续会话。见[缺口记录与原始归档](evidence/imp009/native-gap-analysis-alpha17.json)。alpha.16 先前仅在正文引用调查的部分轨迹不能证明工具级绑定，不将其当完整修复依据；阶段始终未通过，也不把必需修复延后到 M2 收口。

alpha.18／protocol 14／schema 4 在复杂 Task 定义中保留真实 analysis_basis、原 symptom 及检查；完整呈现、语义摘要、REV 比较与 source_runs 使用相同来源。单 Task 根引用映射到唯一 Task，多 Task 必须逐项声明；相互冲突、遗漏原检查或更换判据均拒绝。Task 需要实际原症状复验，整项完成另核对安全结束且当前局部依据匹配的 Task 症状 VER。纯展示 REV 可继承原证明，移除绑定仍需具体范围确认。完整旧 alpha.17 写入器已实际拒绝新协议，数据库字节保持；无迁移、旧批准重放或放宽原七提示。

[六项专项](evidence/imp009/structured-diagnostics-alpha18-r2.txt)已通过，包括实际 red／green、无症状观察不能整项通过、完整封存后声明上下文外改仍 blocked、Task 级引用不被忽略及 REV 边界。新原生准备、全量回归及独立完整包公共 CLI 正在验证；当前仍为 IMP-009 in_progress。

### IMP-009：完整 alpha.18 按当前 Codex 范围通过

完整 alpha.18／protocol 14／schema 4 已取得[阶段门槛](evidence/imp009/stage-gate-codex-alpha18.json)：**534 项全量（84.085 秒）、136 条独立完整包公共 CLI／八组场景、八 Skill，以及 Codex 默认 gpt-6-astra 七新会话／149 条实际命令的语义复核通过**。[原始归档](evidence/imp009/codex-model-alpha18-r1.zip) SHA256 为 `d15ad08669ef71fb7856e348c2f8c58070b0e6cc7362a2862d071ee76840ce84`；[实际复核](evidence/imp009/codex-model-review-alpha18-r1.json)与[十四项分支映射](evidence/imp009/acceptance-map-alpha18.json)分列组件、真实进程、公共 CLI 和原生观察，不将并发进程测试称为并行原生模型测试，也不关闭全部全局 V。

首会话现已把实际原调查和症状判据绑定复杂 SUM，原 red、实际 green、当前症状 Task VER 均保留；A 取消后保留完成与验收，B 仍受阻，C 无写采用后以具体 REV 重绑，联合验收与封存通过。DOC／RULE 从同一基线保存准确差异和批次，按逐项具体批准及跨 owner 顺序实际交付；后续合法组合下 DOC 的目标／Task／整项验收和封存均真实通过，未重复批准或重写成果。

末轮保留控制侧 len 回退和外部追加，模型只新增 B blocked VER `04a84b20…` 与规则 applied blocked VER `5141111f…`。前者在依赖门禁处受阻，未派发 integration；后者明确规则文字仍在、当前字节缺批准保留链。原 13 条 passed、四项 archived、一项 cancelled、五个当前 done Task 保持；旧 B REV1 的 in_progress 部分结果继续作为历史保留，无未决运行或占用。没有将其写成“所有历史 Task 均 done”，也未把应用的最新验收指针推进误称整行字节不变。

三批失败及必要修复材料保持，实际受控新会话总数为 19（5＋6＋1＋最终 7），前批局部结果不当完整通过。错误 Task 摘要、缺双轴审查及误入 simple REV 的请求均被安全拒绝，修正后继续；末轮 shell 退出零内的 DEPENDENCY_NOT_READY 也保留。实际审查者标为宿主自审，主审复核不冒称独立第三审。Claude 未调用。当前只推进到 IMP-009 的 Codex 范围通过，接下来按计划实施 IMP-010，M2 汇合及 M3 尚未完成。

### IMP-010：真实反例传播与普通检查改进的完整工具准备

按[实施方案](evidence/imp010/implementation-plan.md)组合现有接口，未新增学习字段或执行接口。固定四文件实验保留原三个列表字面量：原 unit 通过但列表专用实现对一次性迭代器返回 0；只读 guard 将候选测试运行于正确 sum、错误 count、iterator_zero 三变体，旧测试因漏掉后一错误而实际失败。反例关联原经验、已应用规则与未执行 C：原列表事实保留，来源待复审、建议不再可靠，正式正文及旧通过不改；旧绿灯无法消除新的输入域反例。

当前普通 B 新 REV 先让 CHECK 仅修改测试，真实 guard 和 CHECK Task 验收通过，此时当前源码 unit 仍红；再由 FIX 沿实际验收前置仅修 total.py，原 unit／guard、Task／整体验收与封存通过。学习效果绑定实际采用后的 CHECK 定义，保留有界归因，新经验仍 candidate；C 的原采用效果继续 unknown、方案未接受未执行，旧规则来源仍需复审。没有将检查质量通过误写成当前源码通过，也未由 learn 修改 CI／hook／测试。

alpha.19／protocol 14／schema 4 已形成 68 资源完整包，并补齐[agent 学习循环](../shared/learning-cycle.md)及用户说明。[功能记录](evidence/imp010/functional-validation-alpha19.json)保存 **542 项全量（93.035 秒）、46 条独立完整包公共 CLI、八 Skill、真实隔离安装／发现和文档检查通过**。四个新循环组件及四个父检查均通过；后者在独立完整包实际 owner 调用下跑完六阶段，再拒绝 guard 改写及额外第五份业务文件。增强白名单后四项专项另行复验，包和运行时未变，完整原始日志保留；受控夹具观察不冒充原生或独立第三审。

[九项分支映射](evidence/imp010/acceptance-map.json)关联 23 个实际通过测试及源码快照；来源故障、旧延期提案和领域映射等分支注明本轮回归，未声明全部全局 V 通过。当前源摘要 c611ff50…，实际分发摘要 c93cc424…；完整包、公共 CLI 材料、冻结控制器及无模型准备均已归档。r2 只增强派发前四文件边界，六提示、原文决定、实际包和效果范围保持；当前准确范围见[原生方案](evidence/imp010/model-acceptance-plan.md)及[派发状态](evidence/imp010/model-dispatch-alpha19.json)。

IMP-010 尚未发起模型调用。新的 test_total.py 检查修改、guide.md 初次全文及规则决定不属于 IMP-009 的 terms.md 批准与七会话；需取得本次准确四文件／六会话授权后再实际派发，保留原有授权、不重复核对已完成 IMP-009。Claude 不运行，IMP-011／M3 不提前启动。


### IMP-010：具体授权后派发 alpha.19 原生验收

已收到实际用户答复 call_553ff52fd0df4d8f9a2d9cfde8430dc9，授权 Codex、方案列明的 guide.md 具体决定及同范围必要复验；见[授权记录](evidence/imp010/authorization-alpha19.json)。四业务文件、六新会话、原字面量与 guard.py 只读、反例后不重绑规则依据等边界不变。派发前冻结包及全部六份归档摘要核对通过，当前控制器范围 9521202f…，完整包 c93cc424…；见[实际派发状态](evidence/imp010/model-dispatch-alpha19.json)。

原生会话已启动，尚无通过结论；自动父检查后仍须逐段轨迹与数据库语义复核。Claude 继续依用户指示不运行，IMP-011／M3 尚未开工。


### IMP-010：六新会话及语义复核通过

完整 alpha.19（protocol 14／schema 4，分发 c93cc424…）由 Codex 实际默认 gpt-6-astra 完成六个独立新会话、152 条命令，全部父检查和[主审语义复核](evidence/imp010/codex-model-review-alpha19-r1.json)通过。542 项全量、46 条完整包公共 CLI、八 Skill 与隔离安装事实保持；[阶段门槛](evidence/imp010/stage-gate-codex-alpha19.json)只确认本次当前 Codex 范围。

真实反例保留 unit 绿／guard 红及迭代器 0≠3，旧经验变 needs_review，规则正文仍相同但来源复验 blocked。CHECK 经具体接受后仅补独立字面量断言，guard 可接受正确实现并拒绝两种错误；此时真实源码 unit 仍红，FIX 后才全部绿并封存。新经验的 helped 只引用采用之后、同定义 CHECK Task 的真实 VER 与 guard／规格证据，不借用 B 整单成功或自动升级 active。

实际三项封存，C 保持未接受／未执行及原 adopted／unknown；旧 B REV 的部分 Task、七 passed／三 blocked／一 failed VER 全保留。首次 FIX 因未处置旧 F-ITER 而失败，真实复查后追加通过；规则两次来源阻碍、缺少审查／目标或证据的安全拒绝也保留。没有产品或控制器修补／重试，不将原失败改为通过。[原始归档](evidence/imp010/codex-model-alpha19-r1-evidence.zip)及[152 条完整命令轨迹](evidence/imp010/codex-trajectory-alpha19-r1.json)可复核。模型双轴观察为宿主自审，主审复核不冒称第三方独立审查；Claude 未调用。接下来按计划进入 IMP-011 的四类工作组合与适用分支收口，M2／M3 尚未完成。


### IMP-011：同项目四类工作组合开工

按[实施方案](evidence/imp011/implementation-plan.md)复用现有协议，不新增生产 owner 或执行方法；alpha.20／protocol 14／schema 4。新增实际同项目夹具与公共 CLI 入口，覆盖应用 Task 独立验收、坏 SQL 阻碍最终集成、缺模块只验收、原症状 SQL 修复、附带知识延期、有限关系及源文件移走后重导、封存后外部报告错误只验收。新八会话范围尚未派发模型，具体授权在冻结材料完成后核对。

初轮夹具请求缺身份、在旧方案后更换检查定义及候选请求缺身份均被门禁拒绝；修正为初次方案前固定四检查、保留实际绑定后，两个组合组件已通过。控制器目录别名预检发现冻结输入依赖测试运行模块，改为自包含常量后，四个专项及真实八阶段父检查通过；原始失败日志保留。当前尚无生产内核修复。后续全量回归、独立完整包 CLI 和冻结安装准备未完成，不能据此宣布 M2 通过。


### IMP-011：alpha.20 功能与冻结材料就绪，原生新范围待核对

完整 alpha.20（protocol 14／schema 4，分发 4115593f…）已完成 **548 项全量（96.030 秒）及 5 项补充**、**238 条独立完整包公共 CLI**、八 Skill、文档检查与实际隔离安装。补充包含新增 V-101 显示语言／注释不重跑业务检查断言，以及提示内固定四检查后四个父检查专项。具体见[功能证明](evidence/imp011/functional-validation-alpha20.json)。

四类日常组合在一个临时项目中完成，原始对账红、Task 绿而共享集成红、缺模块红、原症状 SQL 修复及两项封存、有限底稿导出／来源缺失重导、外部报告错误只验收均有真实记录。另将跨项／正式知识、数据及学习旧路径在同一完整包重跑，合计 238 条 CLI；公共适配器原先错误把 result_digest 回执字段计入调查正文，导致分析引用被安全拒绝，现校验并剥离后重跑通过，旧失败保留。生产内核只有版本常量变化，无协议或执行语义修改。

[当前 72 项 V 分支映射](evidence/imp011/acceptance-map.json)保存 151 个实际通过测试引用，覆盖 46 项重点 V 与前阶段适用分支；不把 M3 备份恢复／外部效果部分或全部全局 V 写成通过。[冻结八会话方案](evidence/imp011/model-acceptance-plan.md)包含八业务文件、三生产文件的对应 apply、五只读输入／测试、控制侧暂移恢复及外部修改，附带 daily-guide.md 仅候选延期、不批准生效。

准确范围 548623c9…、原生运行器和实际隔离安装准备均冻结；初次准备保留，r2 只将完整四检查直接放进提示，尚无模型请求。新的八文件／八会话组合不属于已完成 IMP-010 授权，[派发状态](evidence/imp011/model-dispatch-alpha20.json)为 pending_human_authorization。待实际新范围答复后才派发 Codex；Claude 不运行。IMP-011／M2 仍 in_progress，IMP-012—014 尚未开工，未把具体准备当原生通过。


### IMP-011：补充审计发现已知冲突的未收尾操作，alpha.21 修复中

等待新增原生范围答复期间，对原 238 条 CLI 的实际命令和数据库快照补充核查，发现 cross-cli/project-6 的已知冲突负例虽在写正文前被拒，却保留一项 started／needs_recovery 和两个占用。原测试只核对拒绝码与正文，不能证明安全收尾；原 alpha.20 测试通过、包、归档和待答方案均保留，但原生派发已暂扣，不用旧“通过”掩盖此新缺口。

[新增真实 red](evidence/imp011/known-conflict-no-write-red-alpha20.txt)和[定向探针](evidence/imp011/known-conflict-no-write-probe-alpha20.json)证实字节与修改时间均未变，全部占用来自同一被拒操作；在占用前使用已解析候选效果可识别同一 DEPENDENCY_NOT_READY。alpha.21 仅把这次前置预演放到资源占用／journal 准备前，保留实际写前和恢复门禁。没有改字段、协议、业务输入、八段提示、候选延期或授权效果；当前 protocol 14／schema 4。后续全量、公共 CLI、冻结与安装准备须按新完整包重做；新的原生范围问题仍待实际答复，不重复发问、不运行模型。


### 后续计划内工作统一授权

实际用户答复 call_05f0a84076f549568b149504edf7e4b8：“后续都统一授权，不需要再询问我”。见[统一授权记录](evidence/continuation-authorization-20261101.json)。后续既定计划内实施、临时项目受控验收及必要修复复验（含各夹具方案列明的具体临时知识决定）沿此授权继续，不再逐切片重复询问。保留原有临时项目／隔离配置、凭证保护、失败保留及不发布／不操作真实生产数据边界，当前仍先用 Codex。

本次 IMP-011 在实际派发前完成必要 alpha.21 修复；八文件、八段提示、四检查、可写范围、候选延期、控制侧变化和效果限制与 alpha.20 冻结范围逐字段完全相同，只有完整修复包及版本／内容摘要变化。549 项全量（97.212 秒）、238 条完整包 CLI 及 12 份数据库实际复核通过。完成准确冻结材料后直接派发，不重复授权核对。


### IMP-011：alpha.21 已沿统一授权启动原生八会话

完整 alpha.21 的 549 项全量、六项正式知识组合专项、238 条完整包 CLI、八 Skill、实际隔离安装及[12 份数据库审计](evidence/imp011/dispatch-readiness-audit-alpha21.json)通过；已知冲突不再遗留 started／needs_recovery／占用，真实中断的保护与恢复测试保持。原 alpha.20 的 548 项及五补充、失败包和待恢复负例均保留，不将旧证据改成修复后通过。

分发 e521b7f7…、准确范围 a0e30a15… 的[更新方案](evidence/imp011/model-acceptance-plan.md)已核对冻结包、归档、文档及范围，八文件／八会话的内容和效果限制与原范围一致。已依据实际“后续都统一授权”直接派发 Codex；[状态与原始路径](evidence/imp011/model-dispatch-alpha21.json)保存实际进程，当前首会话在运行。Claude 未调用，父检查和语义复核前不标 IMP-011／M2 通过，M3 尚未开工。


### IMP-011／M2 当前 Codex 范围通过

完整 alpha.21（e521b7f7…）实际默认 gpt-6-astra 完成八新会话、104 条命令，父检查及[完整轨迹／数据库语义复核](evidence/imp011/codex-model-review-alpha21-r1.json)通过。549 项全量、238 条公共 CLI、12 份数据库与各阶段适用分支证据汇总到[M2 当前范围门槛](evidence/imp011/milestone-m2-codex-alpha21.json)。已知正式冲突的未收尾缺口经真实 red／probe／green 修复，原 alpha.20 证据保留。

两实现项先完成 SQL 原症状复验和应用四模块最终集成后封存，三 Task done；一附带文档仍准确延期、未批准／应用／写正文。随后源文件移走时仅从保存的 partial 关系底稿重导；最终手改报告只验收，实际 integration 因 external:5／external:1 失败，新增 blocked，不还原外部内容。四 passed、二 failed、一 blocked VER 与全部历史保留，无 started／占用。模型双轴审查为宿主自审，主审复核不冒称独立第三方；Claude 未调用。

IMP-011 及 M2 仅按用户当前 Codex／实际环境范围通过，不扩大为全部全局 V 或设计完整首版；完整恢复、受控外部数据执行及最终工程交付仍需 IMP-012—014。后续已获统一授权，按阶段门槛直接推进，无需逐轮询问。


## IMP-012：完整归档与离线恢复开发／派发前审计

已实现 protocol 15／schema 4 的完整集合、受管／执行保护索引、持久维护屏障、14→15 明确升级及准确方案恢复；接口和当前限制见[维护指南](../shared/recovery.md)。14 项专项覆盖真实进程排空、12 个主换库退出点、检查索引替换中断与日志篡改；原失败和探针分别保留。摘要绑定日志修复禁止向方案加入业务文件，保护原检查索引修复换库后停止证据续恢。

alpha.22 首个冻结包已有 573 项全量（124.731 秒）、144 条公共恢复 CLI、八条真实 alpha.21 升级兼容命令、八 Skill 和隔离安装准备。迟到 V-035 审计补测发现手动备份经通用 start 多触发一次全量每日保护；实际 red／双采集探针和冻结材料保留，[派发记录](evidence/imp012/model-dispatch-alpha22.json)明确未调用模型。这不是已通过完整阶段。

alpha.23 仅在 maintain.backup 登记时免除额外自动保护，完整备份本身及普通写前每日策略保留；回归补测实际新 epoch 的普通知识写入仍建立独立同日点。后续四会话控制范围不变，按实际统一授权复验后直接派发，不重复询问。IMP-012 仍 in_progress，IMP-013／014 尚未开工。


## IMP-012：当前 Codex 范围通过，进入受控数据操作

完整 alpha.23／protocol 15／schema 4 的[阶段门槛](evidence/imp012/stage-gate-codex-alpha23.json)已通过，分发摘要 9ef5c0d8…，72 个实际资源。574 项全量 125.712 秒通过；后来对同一运行字节补测的当前维护专项 16 项 14.984 秒通过，覆盖自然的未登记目标冲突、真实双分叉双方保留及其他项目包拒绝，与全量重复项不另加成新总数。冻结包公共 CLI 162 条／14 场景、真实 alpha.21→23 兼容 8 条、八 Skill、文档与隔离安装／发现完成。

四个实际 gpt-6-astra 新会话完成 51 条命令（20／10／9／12），[主审语义复核](evidence/imp012/codex-model-review-alpha23-r1.json)通过。首轮仅 apply total.py，原检查／三 AC 和双轴自审通过并封存，准确批准 Terms 后备份；第二轮只建立备份后 Later；第三轮只用准确 restore plan／原唯一请求保护损坏 DB／sidecar／未批准 Terms，隔离 Later，保留 unknown.md 和业务源码；末轮原检查真实退出 1，逐 AC 为 failed／passed／failed，当前 VER blocked，历史 passed／封存保留。

旧 epoch f741239b… 换为 b18c9c34…，当前 8 completed／1 因恢复封存的 interrupted 备份截点运行，0 started／占用；全部 blob／结果摘要、固定 journal／原请求和 13 份保护原字节已核。外部只保留受控引用为 unknown／requires_reconciliation，未发生派发，不把此证据称真实外部执行。原生 raw summary 的 review pending／passed false 保留，[单独复核](evidence/imp012/codex-model-review-alpha23-r1.json)及门槛负责语义结论。

IMP-013 沿统一授权进入实施，具体方案固定真实受控数据目标、材料／目标批准、实际派发、未知核实和补偿；不执行真实正式数据。IMP-014 仍待前置，未称本工程完整首版通过。


## IMP-013：有限执行材料与具体只读候选

alpha.24 新增尚未接入公共 CLI 的 external_material／external 开发模块；protocol 仍 15／schema 4，外部 execute／reconcile／record／compensate 仍 unavailable，不把候选记录称实际派发。材料模块已用真实临时 SQLite 与 Python entry／helper／alias／间接 SQL 验证六项：执行冻结字节、变更使旧候选失效、实际目标身份／schema／文件替换、只读观察不能 UPDATE 或 ATTACH、动态缺口／链接／容量及 CRLF／冻结副本变化。

候选准备再通过三项：具体 external_read／目标环境与范围授权、实际只读前置／效果快照与不可变 artifact、同请求幂等且无目标写入；前置不符保存 unready，不伪造许可或业务通过。测试日志见 evidence/imp013/material-components-first.txt 和 prepare-components-first.txt。尚未执行本版本全量、公共 CLI 或原生模型；下一步接入持久保护和真实派发／核实。


## IMP-013 当前门槛

完整alpha.25／protocol16／schema4，80资源；633项全量140.451秒、六场景21次公开CLI、真实alpha21／14及alpha23／15各8次升级／拒绝命令通过，两个宿主仅隔离安装／发现通过。默认gpt-6-astra六个新会话、82条命令及主审实际语义复核通过，见[门槛](evidence/imp013/stage-gate-codex-alpha25.json)。实际临时SQLite发生10→20→30→20，丢回执保留unknown；独立核实／checks／verify／archive按边界进行。真实损坏恢复不回滚业务数据，原补偿来源在新epoch核实，未伪造丢失run或重建Task；最后外部19使原data20返回1及当前VER blocked，历史封存保留。

原alpha.24的631项回归没有覆盖随后新增并失败的来源冲突用例：原档案要求20，保护副本被替换成19且摘要自洽时错误采纳了副本，已在25核对原operation胶囊摘要／资源修复。alpha.24原生五会话／76命令中，第五模型正确因控制侧“不做新备份”与必要自动保护冲突停止；第六未派发。当前澄清只禁止额外手动backup，不关闭必要保护，完整六会话已复验，原始失败不覆盖。

当前通过限当前环境内有限同步Python／SQLite受控机制；不称真实生产、远程provider或任意后台机制已验证。Claude原生高级范围依用户先Codex仍保留未运行事实，安装发现不冒充模型验收。IMP-014继续在同一最终工程包整理文档、实际树、兼容与所有当前必需V证据、双宿主代表使用路径，不发布或改变个人配置。


## IMP-014／M3：完整本地首版交付

0.1.0完整包83份资源（另含清单自身），protocol16／schema4；当前维护工程216份文件，目录由真实文件生成，见[实际工程目录](project-layout.md)。README、安装／使用／开发／排错／兼容指南及NOTICE随完整包定位；源码另保留设计、测试和原始验收资料。运行包与源码包的路径及SHA见最终交付记录，不公开发布。

当前全量642项140.984秒通过；422条V测试引用已逐一核对实际AST方法、文件摘要和本轮通过日志。两宿主完整安装15检查／16命令、生命周期38检查／42命令、当前环境中文／空格路径与整包移动、21次外部数据CLI及真实协议14／15各8条升级／拒绝命令通过。140个V稳定编号中138项当前有效范围通过，V-009发布准备与V-040个人库按D-017退出，不冒充通过。

最终Codex五新会话62命令的R3完整业务证据与R4运行时Python逐字相同，R4另完成一新会话8命令的指南容器定向复验。Claude在精确R4完整包上完成四新会话92命令：完整spec、原行为前证明、文件暂停、展示REV与跨会话CORE／REPORT／整项验收。第五只读调查遭429立即停止，旧七场景批次保持未完成；不重试Claude，沿用户Codex优先及统一授权，Codex默认gpt-6-astra在同一稳定临时项目用三个新会话45命令完成准确均值候选、具体接受／仅REPORT实施／新验收封存和控制侧回退后只验收。原五测试、CORE结果和证明保持；最后真实integration退出1、当前VER blocked，历史封存及全部Task终态保留。

实际主审核对完整轨迹、请求／结果／blob／来源及input_checks、独立五测试、当前SQLite检查点和受管文件保护；无live run或占用。宿主双轴检查为自审，主审不冒称第三方独立审查。各旧失败包、权限停止、额度停止、CONFIG_PRESENTATION拒绝及其他安全输入错误原样保留。[阶段门槛](evidence/imp014/stage-gate-010.json)与[M3当前范围](evidence/imp014/milestone-m3-current-scope-010.json)明确范围，不声称全部高级分支已在Claude独立完成。

后续开放选择为公开许可证／仓库及市场上架、OQ-009长期检索／容量实测、OQ-010具体正式provider能力。完整能力验证限当前环境和可固定的同步Python／SQLite受控机制，没有操作真实生产数据。CLI能力目录全限定标识与动作／方法参数的对应提示可在后续改善；现有表与示例给出的参数可执行，没有为输入错误放宽权限或门禁。

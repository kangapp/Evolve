# IMP-006 双宿主复杂场景模型验收方案

状态：alpha.13 Codex 首轮第三场景未保存展示 REV，alpha.6 Claude 第五轮第四场景缺少原暂停来源，两个批次均已因父检查失败停止。原始轨迹见 [Codex 复核](codex-model-review-alpha13-r1.json)／[Claude 复核](claude-model-review-r5.json)。两处运行时问题已建立可重复复现并集中修复，当前为 alpha.14／protocol v11，477 项全量及 25 项复杂／28 项 REV／12 项续接专项通过，独立完整包 12 条 CLI 重放和双宿主无模型准备完成；新的同包复验中 Codex 七场景已复核通过，Claude 前三场景父检查通过、第四会话因 Token Plan 用量上限（429／2056）停止，后三会话未派发，见[本轮复核](claude-model-review-alpha14-r1.json)。随后仅修正运行器的首个限流事件停止处理，当前 479 项全量通过，未再调用模型；双宿主门槛未通过。当前环境为唯一验收环境，Windows 不另设门槛。

以下 alpha.6 材料和各次失败／修复作为历史受检范围保留；新增 V-088 缺口及 alpha.13 同包复验见末节，不以旧包结论替代新指引的实际行为。

## 具体受检材料

完整包为 alpha.6／protocol v5／schema v1，分发摘要 `55be374a378ddb3b3fb2cf6a9b7dab448d8a30278b0def8f849ca94683590fb7`，来自已保存的[REV 完整包](revision-package-alpha6.zip)。运行器为 `scripts/model_acceptance.py --structured`，父检查在 `scripts/model_complex_checks.py`；同原生传输与共享辅助源码一起进入范围摘要。准备模式不创建 Codex 模型客户端、不查询默认模型列表、不发送 Claude 用户请求；安装／发现结果及回归见[准备记录](model-runner-preparation-alpha6.json)。

本轮每宿主七个新会话，全部重新读取项目档案，不携带旧聊天。每宿主独立隔离配置和临时项目；初始六个文件为 arithmetic.py、report.py、test_arithmetic.py、test_summary.py、test_report.py、test_integration.py，局部需求修订前由父进程增加 test_report_mean.py。只允许修改两个生产文件，五个独立测试均只读。允许写当前项目 Evolve 记录和按具体命令登记检查，不批准正式项目知识。

Codex 使用实际派发时账户 model/list 标明的默认模型；Claude 仅该子进程使用用户已指定 MiniMax-M3.1-Flash。正常宿主权限保持；遇到额度、权限或传输失败立即结束该宿主批次，保存实际轨迹，不轮换账户、模型或自动重发。父检查失败也先停止批次，汇总功能问题后按原阶段修复、同范围复验；不把失败的会话或旧包结果改写为通过。

## 七会话顺序与实际判据

1. **只提案**：接入并实际呈现完整复杂 spec；CORE 提取单次迭代 summarize 并保持原 total，REPORT 消费共享接口且依赖 CORE 独立任务验收。保存目标、约束、AC、测试决定、只读上下文、必要预重构和最终集成边界。原 total 检查可通过，新成果测试起初真实失败。提案阶段不接受、不实施或验收。
2. **预重构后暂停**：明确接受上述固定目标内已存档方案，先保存原 total 真实前证明，再完成 CORE 文件段并正常无后检查暂停。保留授权和部分来源，Task 仍 in_progress，REPORT 与全部测试保持。
3. **仅格式修订**：改变展示标题／摘要，保存新 REV，目标／AC／任务定义及依赖含义保持。复用仍适用的部分结果、原证明与已接受依据，不改业务或运行检查。
4. **新会话续接**：从实际部分来源沿同定义新 Task 续接，保留原前证明；完成后检查、CORE 的独立任务验收、REPORT 实施及最终全量集成与双维审查。本轮完成整体验收即停止，不封存，保留活动工作项供下一轮需求修订。
5. **局部需求修订**：父进程增加只读均值测试；新增 include_mean=True，固定两位小数，空输入 0.00，默认输出保持。仅呈现并保存新完整 REV，原 AC 保留并新增均值 AC，CORE 定义／适用结果保留，只重开 REPORT。REPORT 新检查必须真实覆盖 test_report_mean，最终 discover 全量覆盖。本轮不接受或实施新语义方案，不运行检查。
6. **新要求完成**：明确接受已存档且符合给定均值边界的具体修订，只改 report.py，运行原／新任务检查、最终集成、逐 AC 及规格／规范审查后封存。原整项 VER 不代替新要求；CORE 及原行为证明保持。
7. **仅验收**：父进程只在均值分支引入已说明的外部回退；新会话只运行实际验收并追加当前失败／受阻记录，不修复业务／测试、不改旧通过记录或实现终态。

父进程另外逐字核对五个测试、历史 Task／VER／已封存 run／事件／证据、无悬挂执行或占用、原前证明来源与原字节；完成阶段独立运行原测试。模型输出、工具事实与实际限制分别复核；进程退出零或父检查通过仍不自动设置 IMP-006 passed。原生轨迹审阅后集中修复必需问题，再按相同文件／行为边界复验。双宿主不相互代替。

## 精确范围与执行

完整文件、七段原始输入、效果边界及辅助源码摘要分别在 [Codex 范围](codex-model-scope-alpha6.json)、[Claude 范围](claude-model-scope-alpha6.json)。当前摘要：

- Codex：`9e43c19fc7a91b450b42766c5ed81fe5be8125431ace3a3092843fb09361ec61`。
- Claude：`891008fa118ba0f99dc5abc9a338d7f82879d4ae73f4fecfdc1940c7b642e290`。

首次派发必须提供本聊天中实际扩展授权原文与匹配范围摘要，并使用新的隔离输出目录；缺少任一项在建项、安装与模型请求前拒绝。准备成功仍保留 model_requests_sent=false、passed=false。实际固定命令为：

```sh
python3 -B scripts/model_acceptance.py --host codex --package <受检完整包> --out <全新隔离目录> --structured --authorization-text <实际用户授权原文> --expected-scope-digest 9e43c19fc7a91b450b42766c5ed81fe5be8125431ace3a3092843fb09361ec61
python3 -B scripts/model_acceptance.py --host claude --claude-model MiniMax-M3.1-Flash --package <受检完整包> --out <另一个全新隔离目录> --structured --authorization-text <实际用户授权原文> --expected-scope-digest 891008fa118ba0f99dc5abc9a338d7f82879d4ae73f4fecfdc1940c7b642e290
```

输入原文、源码或受检包改变即重新生成和核对范围；同一已授权文件／行为边界内的功能修复复验沿实际授权，新增场景、文件、模型或对外效果仍重新核对。没有实际授权，不调用模型；不复制个人配置或凭证，不启动嵌套代理、不提交、发布或部署。

## 第三轮同范围位置修复复验

前轮 native `Bash ls` 被拒的实际原因是插件缓存位于临时业务根之外。第三轮把完整登记安装根及独立缓存移入该临时项目的 `.agents/evolve-acceptance/`，保持正常宿主权限与原命令允许项，不为原外部目录增加权限。父检查只排除这处明确的准备区域，同时核对两份实际完整包不可改写；其他 `.agents` 文件仍视为未授权业务文件。

[新范围](claude-model-scope-r3-alpha6.json)与原授权范围逐字段比较，除控制器源码摘要和新增布局说明外，受检包、所有文件字节、七段原始输入、可改生产文件、模型、会话数量及效果限制完全相同。原实际用户答复“授权两个宿主及同范围复验（推荐）”覆盖必要修复复验；因此本次沿原授权，只复验受影响 Claude，不重问该范围，也不重复 Codex 已通过调用。IMP-007 四文件／九会话与正式知识决定属于另外的新增范围，仍等待其独立授权。

使用[位置修复冻结控制器](model-runner-alpha6-layout-fix.zip)，SHA-256 `620d0be7262111e097cc4828d3c020e3387d6d7763822eb1fb5ea8a793a6153e`；Claude 准确范围摘要 `1d78c4c72f3908dca70762431e378c9375ca89344c9f3adad88898f3862db6da`。466 项全量／16 项复杂场景专项通过，真实隔离安装发现八 Skill，原受检项目保持未接入；[准备证据](claude-layout-preparation-r3.zip)没有模型请求。随后第三轮使用新的临时项目和七个新会话，仍在权限、额度、传输或父检查失败时立即停止，不自动重发被拒动作或更换模型。

## 本次为什么需要核对

已有真实模型授权覆盖旧两文件／三类意图，以及四文件／五新会话。本次为七文件／七新会话，并新增复杂 Task、前后证明和 REV，超出旧模型验收范围。[根 AGENTS.md](../../../AGENTS.md)第 3 条要求“关键新选择、扩大范围或用户收窄意图时重新核对”。因此先完成具体可审阅材料和非模型验证，再核对本次模型派发授权；这不重问已授权的工程开发或已有模型场景。

## 第四轮既有命令说明修复复验

第三轮失败动作是独立 Bash `shasum -a 256`。原生 guard 立即停止且无后续实施／验收，见[实际复核](claude-model-review-r3.json)。运行器现明确原 Bash 允许项只有 python3、ls、cat、rg；现场摘要使用已有 Evolve status／resume 返回，不重发 shasum，也不换工具重做该动作。未改变权限、原七段行为输入、七文件字节、可写路径、模型和会话数量。467 项全量／21 项专项以及无模型隔离安装通过，见[具体修复](command-guide-fix-validation.json)。

沿原实际明确授权执行第四轮七个新会话；[冻结控制器](model-runner-alpha6-command-guide-fix.zip) SHA-256 `17de79fcf8e300756c9a61878081248aecb2218f32083eccb6bd44797e333d1c`，[准确范围](claude-model-scope-r4-alpha6.json)摘要 `34db572ad971ccf58abcb06263a4b0c0a0ac34af5badaf15d7ab624de53575c0`。仍在任何权限、额度、传输或父检查失败时立即停止批次，不自动重发被拒动作。前轮失败证据不覆盖；实际轨迹和父检查均复核后才判门槛。

## 第五轮待批准候选分支修复复验

[第四轮实际复核](claude-model-review-r4.json)显示，移出旧阶段“不实现均值”的具体描述会按既有门禁保存 `scope_confirmation_required` 候选并保留旧 REV；候选中 mean 检查实际存在。父检查漏掉这个正常待批准分支，模型标题也误称新 REV。先两次本地复现，再修复父检查并明确第五／六会话的报告与接受顺序，见[具体修复验证](pending-candidate-fix-validation.json)。第五会话可保存完整未批准候选，旧有效工作及原检查保持；第六会话仍须具体接受同一候选，生成实际新 REV 后才能实施。原最终五个测试、CORE 保持、mean／集成及最后只验收失败断言不减，运行时范围门禁与 native 权限完全未变。

新[冻结控制器](model-runner-alpha6-pending-candidate-fix.zip) SHA-256 `4637a63dc304561c14ae045695104eb1419b5bdc35d30d747df014ab8875fbcf`，[准确范围](claude-model-scope-r5-alpha6.json)摘要 `150338976bd3f6faa820adacf924343b03aadc9765827f4829b1dbde45dbe748`。仅澄清原第五／六会话中的既有范围确认分支，原七文件／七会话、两生产文件可写、五测试只读、模型和效果边界保持，属于既有明确授权的必要修复复验。470 项全量／19 项专项与无模型隔离安装完成后，沿原实际授权启动第五轮，见[派发状态](model-dispatch-alpha6.json)；失败仍立即停止，不以组件通过代替实际模型结果。

## alpha.13：补齐原 V-088 的同范围复验

原设计要求按项目实际缺口分别选择轻量／定向深入／全局梳理，说明理由、范围、关键未知及停止条件；插件 Skill 缺少该完整执行指引。alpha.13 增加单一 shared/context.md 并由 workflow／init／propose 按条件引用，protocol v10／schema v4 与运行方法保持。完整包、回归、校验及双宿主真实无模型安装见[验证记录](context-validation-alpha13.json)；不得把准备写成原生行为通过。

原七场景、七文件、两个可写生产文件、五个只读独立测试、模型及效果限制保持。首会话只新增“先梳理这个临时项目的整体入口、模块职责、检查方式与关键约束，再形成下述方案；结论限本项目。”；续接只新增“重点核对 summarize 的生产与 report.render 的消费链路及当前判据，沿相关链路解决缺口，已有可信背景直接复用。”其余原始输入及全部最终业务断言保持，前轮待批准候选修复也保持。模型轨迹额外核对真实梳理选择和依据、已有背景复用、覆盖／未知与停止条件；不按代码量或复杂度代替深度。

这是原 IMP-006 义务的必要修复，沿实际“授权两个宿主及同范围复验（推荐）”授权；没有增加临时业务文件、会话类型、模型、正式知识批准或外部效果。使用[实际 alpha.13 包](context-package-alpha13.zip)，分发摘要 `83cee98e7e1807e3347690b7fd633463651f519e9d0c34b91af9dfdedfc9efdd`；[冻结运行器](model-runner-alpha13.zip) SHA-256 `39ef314677609d187b541cd53f310f0d28774978040482b0076815edf38112ea`。准确范围为 [Codex](codex-model-scope-alpha13.json) `c19db884d42a043ef798e7b121443ec0789ede55a008c692124a573e206b01cc`、[Claude](claude-model-scope-alpha13.json) `adee80d60ee537d22c0f3f1a8e8a050207ee8ff59c681431c0ddce2ba606bd7d`。

Codex 新批次已派发；Claude 先等待原 alpha.6 第五轮实际终态和问题复核，不并发发起该宿主新批次。两宿主须在同一 alpha.13 内容摘要上完成实际轨迹复核；旧失败、旧包通过与新包证据分别保留，权限／额度／传输／父检查失败仍立即停止。IMP-007 的四文件／九会话及具体知识决定仍是另外的待授权范围，不在本次派发。

## alpha.14：上游产物上下文与实际暂停来源修复

[Codex alpha.13 首轮](codex-model-review-alpha13-r1.json)在展示修订前停止，未实际调用 update；独立旧包复现确认：REPORT 将已声明上游 CORE 的 arithmetic.py 产物当作固定旧上下文，合法预重构使纯展示修订被误判。alpha.14 只把声明祖先产物交实际依赖结果核对，其他固定上下文与外部漂移照常受阻。[Claude alpha.6 第五轮](claude-model-review-r5.json)实际完成检查但漏掉文件暂停来源；alpha.14 从当前 Task 及已证明的 REV 继承链自动绑定唯一安全结束的真实来源，保留原授权子集、撤销及未决效果核查，早期 before_only 不能替代文件暂停。父检查仍要求当前 CORE 的实际实施／检查尝试引用原文件暂停，blocked 行不能冒充。

[修复验证](runtime-fix-validation-alpha14.json)保留旧包的两条失败复现、新实现的 **477 项全量／25 项复杂／28 项 REV／12 项续接专项**，以及[独立完整包公共 CLI 重放](runtime-cli-proof-alpha14.json)的 12 条命令与 9 项实际断言。重放使用原生保存的完整方案和四个原测试，真实保存前证明、正常暂停、展示修订、自动续接、任务／整项验收及封存；输入明确为受控观察，不称独立模型验收。schema v4 保持，protocol 升为 v11；真实 alpha.13 同 schema 写入器拒绝新协议且库字节未变，旧完整包保留，不自动迁移。

同包原生复验沿原实际“授权两个宿主及同范围复验（推荐）”：相对 alpha.13，原七段输入、七文件字节、可写路径、五个只读测试、七会话数量、模型选择、native 权限选项、效果限制和最终业务断言完全保持，只有包／协议和已审阅修复的源码摘要改变。未增加正式知识批准、外部应用、凭证／个人配置操作、嵌套代理或发布。两个旧批次已终止、失败证据保留，新的两宿主输出目录各自独立。

使用[alpha.14 完整包](runtime-package-alpha14.zip)，分发摘要 `c7806c6dbb28c7d344afa513d189fe60c8336218c7172ee0f875fb56c354ff34`；[冻结运行器](model-runner-alpha14.zip) SHA-256 `d92e670ae98806077babffcf155d9e3408a17ccc5dc87323c0874b6e46bef2c3`。准确范围为 [Codex](codex-model-scope-alpha14.json) `6c6c33527b2a01f7bb40a690ac746bb4ef1e882769e65382d8767e9db354ef0a`、[Claude](claude-model-scope-alpha14.json) `543d81c630d07b101100ea7b87c2b45ae2075d0a31fd57fe5460bd01308d96bd`。[双宿主真实隔离准备](runtime-preparation-alpha14.zip)停在模型客户端之前，模型请求为零；实际派发与终态由[alpha.14 记录](model-dispatch-alpha14.json)单列。V-088 实际梳理行为与全部原七场景仍须审阅；任何权限、额度、传输或父检查失败仍立即停止。


## alpha.14 Claude 额度终态及未来运行器

[Claude 本轮](claude-model-review-alpha14-r1.json)仅前三场景父检查通过，第四会话因 Token Plan 用量上限（429／2056）停止；未完成续接，后三会话未派发。原控制器在原生十次内部重试后的 assistant 错误才终止，不能称为首个额度事件即止。现以真实轨迹和本地失败测试修复为首个 system/api_retry HTTP 429 即结束进程组，23 项相关及 479 项全量检查通过，见[验证](rate-limit-guard-validation.json)。无新模型请求或额度恢复结论。

未来同范围复验使用[修正冻结运行器](model-runner-alpha14-rate-limit-fix.zip)，SHA-256 `f68607800db9467ab268d544ba5e4d8a2b07925b9b404845bbf56eb047de4a0e`；仅[Codex 预检](codex-model-preflight-alpha14-rate-limit-fix.json)／[Claude 预检](claude-model-preflight-alpha14-rate-limit-fix.json)已执行，无新宿主安装或会话。新范围摘要分别为 `c87cf8526ae8993c569194cdad7de9f4c225954bedec91f745a90eadee9c7278`／`c22bb6db0ab16358270a81ea283b683c30c9e0037e64ad83f2312b81da0f218a`，比较确认只有运行器文件摘要变化，七文件／七场景／原模型和效果边界逐字段相同。插件仍为同一 c7806c6d… 包，历史已派发控制器及结果不改写。额度不足期间不重新派发、不自动切换模型或账户。

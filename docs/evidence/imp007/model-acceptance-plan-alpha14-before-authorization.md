# IMP-007 原生双宿主知识验收方案

状态：alpha.14／protocol v11 四文件／九会话原范围不变；已同步首个限流事件停止修复，重新冻结知识运行器并完成两宿主无模型预检，既有安装及四文件字节再次核对通过，见[当前准备](rate-limit-runner-preparation-alpha14.json)。当前共享运行器 479 项全量回归通过，包含 11 项知识父检查；本范围仍等待实际用户授权，Claude 既有额度阻碍未恢复，模型请求为零。原 [alpha.14 准备](model-runner-preparation-alpha14.json)、[修复前方案](model-acceptance-plan-alpha14-before-rate-limit-fix.md)及 [alpha.12 方案](model-acceptance-plan-alpha12.md)分别保留为历史。当前实际环境为唯一验收环境。

## 受检包与执行范围

受检包为[完整 alpha.14](native-package-alpha14.zip)，protocol v11／schema v4，内容摘要 `c7806c6dbb28c7d344afa513d189fe60c8336218c7172ee0f875fb56c354ff34`。alpha.14 修复了声明上游产物的上下文比较及正常暂停来源核对；四个文件的原字节、九段提示、模型、具体知识决定和效果限制与原 alpha.12 完全相同。每宿主一个新的临时项目、九个全新会话；不携带旧聊天。Codex 使用派发时账户 `model/list` 的实际默认模型；Claude 仅本进程指定用户已选择的 MiniMax-M3.1-Flash，不改个人配置或模型默认项。

四个临时文件为 policy.py、guide.md、test_policy_a.py、test_policy_b.py。模型仅可经对应 Evolve 动作修改 policy.py、guide.md 及该项目记录；两个测试始终只读。policy.py 初始 `POLICY = "unset"`；A 与 B 的独立测试分别断言 POLICY 为字符串 A、B。它们表示先后不同的具体标签契约：A 阶段要求 A 判据，B 新要求替代 A 标签后使用 B 判据，旧 A 测试和历史通过保留，当前 A 测试失败不冒称仍通过。完整初始字节、提示词、边界与辅助源码摘要在分宿主范围文件。

安装根及独立宿主缓存置于临时业务根的 `.agents/evolve-acceptance/`，不扩大宿主工作目录或权限。实际安装根与缓存两份完整插件均只读并校验，项目启用配置也受保护。此布局解决此前 Claude 缓存位于工作根外的已知位置问题；它只证明资源已放在工作根内，是否能由模型正确使用仍待原生实测。

## 具体正式文本与决定

初次 guide.md 原文如下，第一会话具体批准此现有全文成为初次正式基线，保留原字节：

```markdown
# 项目约定

当前标签：待定。

审查约定：尚无。
```

A 的两个必需候选分别以此实际初次基线呈现完整新全文并声明独立字节范围：sync 只把“当前标签：待定。”改成“当前标签：A。”；learn 只把“审查约定：尚无。”改成“审查约定：检查当前标签对应阶段的独立字面量测试，并注明范围。”。第四会话分别具体批准这两项；第三项 topic=policy-note 只在初次全文末尾追加空行及“后续说明：标签 A。”，第四会话明确延期，原因是稍后决定说明，不能隐含应用。

外部采纳会话前，父进程只在实际已完成 A 的完整正文末尾追加空行及“外部范围：仅此临时项目。”。第六会话具体批准采纳这份实际全文及该新增范围，不额外改写，文件修改时间保持。

B 的后继 policy-note 基于此时实际正式全文，将“当前标签：A。”改成“当前标签：B。”，并在末尾追加空行及“后续说明：标签 B。”，规则与外部范围保持。第七会话仅保存／检查，旧 A 说明被明确替代；第八会话具体批准并应用准确新版本。最后父进程把“外部范围：仅此临时项目。”改成“外部范围：未知范围。”；这次外部编辑未批准，最后会话只能验收当前目标，不能采纳或修复。

上述具体批准／延期仅属于受控临时项目及对应命名会话，不授权修改插件工程的正式设计或其他业务资料。经验与规则只覆盖此临时标签交付核查；有实际经验来源、反例及局限，经验命中或引用次数不能成为正式批准。

## 九个新会话与实际判据

1. **baseline**：接入；登记 policy_a、policy_b 两个真实独立命令；把初次文档作为必需 init 成果，保存具体内容检查和决定，实际应用、目标验收、封存。业务与测试保持。
2. **deliver_a**：实际呈现并接受复杂“标签 A 与正式约定”方案，任务键 CODE／SPEC／RULES，分别由 apply／sync／learn 负责。SPEC 依赖 CODE 验收，RULES 依赖 SPEC 验收；本轮只交付 CODE、运行 A 的真实判据并取得 Task 验收，记录有实际 CODE 证据的 observed 候选经验，不交付正式文档或封存 A。
3. **candidates**：保存并实际检查上述两个 required 候选及一个 followup 旧 A 说明，均有完整正文、准确原范围和真实来源；正式文件、业务及批准保持。
4. **decisions**：在明确三项批次中具体批准 SPEC 与 RULES，延期旧 A 说明；只记决定，不写文件、实施或验收。
5. **finish_a**：对应 owner 实际应用已批准子集，SPEC 实际验收后 RULES 才能继续；读取实际组合正文，保留前项批准和效果。必需 Task、A 实际检查及整体验收通过后封存，旧说明保持延期。
6. **adopt_external**：父进程形成已列明的外部追加；具体采纳作为新必需文档任务，绑定原正式版本与实际外部字节，检查／批准后只登记现有字节，目标验收通过后封存；旧历史保持。
7. **deliver_b**：新 B 工作实际改 POLICY 为 B，保留两个原测试，执行 B 的独立判据和验收；新 policy-note 引用 B 真实实现依据，准确替代旧 A 待审项，保存检查而不批准／应用或封存 B。
8. **finish_b**：具体批准准确 B 后继候选，由 sync 应用并验收目标；正式文件变化后重新运行 B 的实际判据并取得新的整体验收，再封存。已归档 A 可导航旧延期说明和明确后继，旧决定不转移。
9. **verify**：父进程仅形成所列未批准外部漂移；模型只追加实际目标 blocked／failed 验收。业务、测试、原应用、旧 passed、旧决定及全部封存终态保持。

父检查另核对两个只读测试逐字不变、两个实际插件根完整、核准命令与配置不变、真实 owner／application／rule_binding／内容与实现来源、候选决定与正文不改写、独立范围仍保留、未决 run／claim 为零。会话前后运行适用和不适用阶段的实际字面量判据，区分旧历史与当前契约。原生工具轨迹还需人工式逐项审阅；父检查或进程退出零不会自动设置通过。

## 冻结范围与失败边界

范围摘要绑定完整包、四文件全部初始字节、九段提示、模型选择、安装布局及四份控制器源码。[Codex 预检范围](codex-model-preflight-alpha14-rate-limit-fix.json)为 `f0b384bd558f90e7042fbbc13a31c32f202689604d55ff992d66bcae8e5cb20e`；[Claude 预检范围](claude-model-preflight-alpha14-rate-limit-fix.json)为 `6a56f7af4da39afce4c655b33125fa0012e2e9b76058f792e85ee6511c80ecea`。派发使用[修正后的冻结控制器](model-runner-alpha14-rate-limit-fix.zip)，SHA-256 `9cbf0a3349d31ceb6e1d73e5b9a07efe75e889f030b69162b2adf248e4caf6c6`，不使用后续源码冒充受检材料。[实际无模型安装证据](model-runner-preparation-alpha14.zip)及[历史 alpha.12 九阶段受控事实](controlled-parent-walkthrough-alpha12.zip)分别保存。

解压完整包和控制器后，预检用 `controller/model_acceptance.py --host codex --package <完整包目录> --knowledge --preflight-only`；Claude 另给 `--claude-model MiniMax-M3.1-Flash`。实际执行用新的隔离输出目录，并携带实际用户授权原文及对应精确摘要：

```bash
python3 -B controller/model_acceptance.py --host codex --package <完整包目录> --knowledge --out <新的Codex隔离目录> --authorization-text <实际用户授权原文> --expected-scope-digest f0b384bd558f90e7042fbbc13a31c32f202689604d55ff992d66bcae8e5cb20e
python3 -B controller/model_acceptance.py --host claude --claude-model MiniMax-M3.1-Flash --package <完整包目录> --knowledge --out <新的Claude隔离目录> --authorization-text <实际用户授权原文> --expected-scope-digest 6a56f7af4da39afce4c655b33125fa0012e2e9b76058f792e85ee6511c80ecea
```

占位参数替换为实际路径及带引号的授权原文，准备模式不能视作授权；摘要不匹配会在安装和模型派发前拒绝。当前安装发现：Codex CLI 0.154.0、Claude Code 2.1.117 均发现八 Skill，Codex 另一个项目发现零个。Claude 本地 `/skills` UI 显示既有默认 MiniMax-M2.7，但未发送请求；实际模型阶段明确用进程参数 MiniMax-M3.1-Flash，不改变该默认值。

遇额度、权限、认证、传输或父检查失败立即停止该宿主批次，保存实际结果；不自动重试被拒动作、切换账户／模型或提高权限。修复后仅在实际授权的同一文件、文本、会话及模型范围内复验；新增范围重新核对。禁止嵌套代理、个人配置／凭证修改、外部应用写入、提交、公开发布或部署。不复制个人凭证，不把临时宿主资料打进公开工程。

原 IMP-006 授权覆盖七会话、七文件的算术／报告场景，且明确不批准正式知识；本次是四文件、九会话并含上列具体知识决定。依据 [AGENTS.md](../../../AGENTS.md) 第 3 条“已有具体授权在原范围内继续；关键新选择、扩大范围或用户收窄意图时重新核对”，执行前需要本次范围的实际用户授权。准备／预检无需发送模型请求，本方案不重用原算术授权。

## 当前准备与历史区分

原九会话和具体批准／延期文本逐字段保持；变更仅为当前修复包／协议及核对后的辅助源码摘要。当前[准备记录](rate-limit-runner-preparation-alpha14.json)与[未派发状态](model-dispatch-alpha14.json)明确标记知识授权 pending、model_requests_sent=false。两宿主都实际发现八个 Skill，四个初始文件未变且项目未接入。当前回归的 11 项知识父检查摘录见[原始全量结果中的对应行](parent-tests-alpha14-from-full.txt)，不是另一次专项运行，也不等于原生模型语义验收。

alpha.12 冻结材料及当时的无模型事实保持不变；新 alpha.14 准备不把它们改写成新版本已验收。IMP-006 alpha.14 的七会话模型进程是另一个已授权范围，不批准本方案的正式知识决定。本问题尚未收到实际用户答复，不重新派发重复授权问题，也不因目标自动续行而推定批准。


本次只变更 model_acceptance.py 的首个 system/api_retry HTTP 429 停止处理；比较确认四文件原字节、九提示及具体批准／延期文本、模型、效果和限制完全相同。两宿主只执行 preflight，没有重装或调用模型；原已安装完整包与缓存校验仍为 c7806c6d…，项目未接入。新预检文件的精确范围位于 expanded_scope，派发命令中的摘要对应它，不混用历史控制器。实际知识授权和可用模型条件齐备前，不派发。

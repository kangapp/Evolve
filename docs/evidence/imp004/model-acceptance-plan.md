# IMP-004 宿主模型验收范围（已获扩展授权，执行中）

当前包 alpha.4，schema v1／protocol v3。受检包以 runtime-validation-alpha4-r2.json 的摘要及后续实际安装复核为准。当前 243 项组件／运行器回归及双宿主缓存 CLI 流程有证据，不能代替本方案的真实模型语义验收。

已有模型授权对应 [IMP-002 的两个文件／三个连续场景](../imp002/model-acceptance-plan.md)。本方案增加明确正常暂停、新会话及第二个任务／文件范围。[根 AGENTS.md](../../../AGENTS.md)要求“关键新选择、扩大范围或用户收窄意图时重新核对”，本次四文件／五新会话属于对原受控验收的范围扩展。运行器与最终预检完成后，用户已实际回复“授权两个宿主，仅限上述受控验收（推荐）”；两条实际运行器已启动，授权原文、范围摘要和观察句柄见[派发记录](model-dispatch-alpha4.json)。结果须按实际轨迹复核，启动不代表通过。IMP-003 的原包模型门槛保持独立，原包已[完整保存并恢复预检](../imp003/preserved-package.json)。

## 已完成的派发准备

[运行器及实际预检证据](model-runner-preparation-alpha4.json)记录了两个全新隔离配置的真实安装、原生发现和 243 项回归（20.786 秒，含 12 项父检查／范围测试）。两个宿主各发现八个 Skill；Codex 另一个未启用项目发现零个插件 Skill。prepare-only 在创建模型客户端之前退出，没有读取账户默认模型列表、启动模型会话或重试 Claude 额度。

初轮受检分发摘要为 `ebd7ed18188f4a4884ffea8cda6595e480e3a75bff8cbd6b90f83b18bde79eee`，48 个库存文件；准备时只修改开发验收脚本与证据。Codex 使用派发时账户标记的默认模型；Claude 限本进程选择 MiniMax-M3.1-Flash，不修改个人配置。原 IMP-003 请求曾为 429／2056，本地安装成功不代表额度恢复；本次实际模型响应另按轨迹观察。

可复核的完整范围分别保存为 [Codex](codex-model-scope-alpha4.json) 和 [Claude](claude-model-scope-alpha4.json)。当前摘要：

- Codex：`c912e640690c622be1ab4822846355fcfbec7e11345ea0fa04235637a8217938`。
- Claude：`6240961214666f22c8bc4944165054e3150e194751a3538adb9947a367490fd8`。

摘要绑定包、宿主／模型选择、四个夹具文件原文、五段输入、新会话条件、可选缺测试变体及三个运行器源码。当前选用保留测试的只验收场景，缺测试变体关闭；变更变体、输入或脚本均会改变摘要。派发必须提供真实用户授权原文及匹配摘要，否则在创建临时项目、安装及模型调用前拒绝；准备成功仍保留 passed=false／review pending。

运行入口为工程根下的 `scripts/model_acceptance.py`。已实际执行的准备命令如下，目录必须为全新路径：

```sh
python3 -B scripts/model_acceptance.py --host codex --package /tmp/evolve-imp004-hosts-02/installed-source --out /tmp/evolve-imp004-models-codex-preparation-02 --session-learning --prepare-only
python3 -B scripts/model_acceptance.py --host claude --claude-model MiniMax-M3.1-Flash --package /tmp/evolve-imp004-hosts-02/installed-source --out /tmp/evolve-imp004-models-claude-preparation-02 --session-learning --prepare-only
```

实际派发需去掉 prepare-only、使用新的隔离目录，并带 authorization-text／expected-scope-digest；授权不得用占位文本或脚本自述代替。每个获授权宿主依次执行下述五个新会话；发生真实权限或额度拒绝时保存结果并停止该宿主，不自动重试、购买或更换账户。

## 实际发现后的同范围复测

初轮 Codex 五场景自动通过，但[语义复核](codex-model-review-alpha4-r1.json)发现即时调查误报不存在的动作同名 Skill；[Claude 即时问答](claude-inspect-review-alpha4-r1.json)在标准输入被拒绝后创建了短暂请求文件再清理，未遵守纯对话回退分支。没有据此标记整切片 passed。

修正仅涉及 owner 读取指引、只读／写请求回退区分及 CHANGELOG；运行代码、既定四文件／五场景和副作用边界保持。沿已获授权方案中的修复复验继续，使用新的完整包和独立目录，原轨迹保留。新分发摘要为 `e599c03724bf770268f780637f0f89a7f9f46fb080c97f2e78441e32cfad4f40`，243 项回归／Skill 校验通过。新范围分别为 [Codex r2](codex-model-scope-alpha4-r2.json) 与 [Claude r2](claude-model-scope-alpha4-r2.json)；每次派发仍核对实际摘要，不能把旧包通过或新包的本机预检当成新模型结果。

Codex r2 的五场景已在该包通过复核。Claude 原包随后结束于续接来源父检查：暂停时没有保存原指令已授予的后续 checks，复用被正确拒绝；独立新授权成功不算本案的原授权绑定通过，见[实际复核](claude-model-review-alpha4-r1.json)。补清暂停授权保存方式后，当前完整分发摘要为 `5fce70d15a7ee8893b2d18b562298bca81e51684a16ee763f054eb915c5273c5`，运行代码和语义门禁未放宽；243 项回归／apply Skill 校验通过。当前双宿主实际复测使用 [Codex r3](codex-model-scope-alpha4-r3.json)／[Claude r3](claude-model-scope-alpha4-r3.json)，不混用 e599 的单宿主结论或旧包结果。

Codex r3 在 5fce 包通过五场景复核；Claude 读取了新回退约定后仍为即时问答创建临时输入，见[重复发现](claude-inspect-review-alpha4-r2.json)。进一步把 propose 的结构化材料指针限定于明确的结构化结果／留档需求，即时解释的完成标准为实际只读观察与对话答复。最新完整分发为 `11e30bb2cc61e07331da43c8ba5696e055df378291a71ec2d911eb889ed2566d`；243 项回归及 Skill 校验通过，[Codex r4](codex-model-scope-alpha4-r4.json)／[Claude r4](claude-model-scope-alpha4-r4.json) 安装预检完成，模型尚未派发，先观察现有 Claude 作业到终态。

该旧 Claude 作业已实际超时并核实终止；库中安全 partial 与原生调用未完成分别记录，未冒充场景通过。控制脚本补齐超时部分输出的脱敏保存后，244 项回归通过；原控制源码也已[完整保留](model-controller-before-timeout-fix.zip)。重新安装预检得到当前 [Codex r5](codex-model-scope-alpha4-r5.json)／[Claude r5](claude-model-scope-alpha4-r5.json) 范围，默认 600 秒及授权边界不变。最新 Claude 与 Codex 已在各自新的隔离目录实际派发，完整包均为 11e3；不能沿用旧包模型通过，实际结果与轨迹分别复核。

## 场景及实际判据

所有模型输入使用原生宿主新会话，不传旧聊天记录。限新隔离配置与一次性整数算术项目，八 Skill 和内核来自同一完整受检安装；不访问其他业务、个人配置、凭证或外部应用，不启动嵌套代理，不提交／发布／部署。保留正常权限拒绝，模型输出与实际数据分别核对。

1. 即时调查：原 arithmetic.py／test_arithmetic.py；说明实际代码、症状和限制，明确不接入、不留档、不改业务。父检查验证无记录设施与业务改动。
2. 初次修复后正常暂停：同一原文件范围，先保存实际 red、独立预期、调查与具体短方案；已授权的文件段完成后明确暂停，剩余检查／验收下次继续。必须是 completed／partial、本地占用释放、Task 未 done、没有伪造检查和封存；不能假报中断或通过。
3. 无旧聊天接续：只说明继续项目中明确未完成的原工作。模型从档案恢复原计划、进度与有效范围，用新 run 续接；真实原判据检查、双维审查和封存，原部分 run 不改写。实际前次工作产生一条带范围／来源／限制的项目候选经验，不能预置经验、把规则假设当批准或为满足脚本虚造发现。
4. 第二个同类任务：控制脚本新建 arithmetic_second.py／test_arithmetic_second.py，真实失败、独立预期为 12、0、7；新明确授权只覆盖该文件对。先正式资料，再实际检索前次经验，核对新现场并保存采用／拒绝及理由，按原范围实施、真实检查与封存后追加实际效果反馈。允许 unknown，不强迫正向收益；检索命中不是采用，任务通过不是经验因果收益。原文件和独立断言保持。
5. 只验收：控制脚本明确保留一次现场回退；仅追加当前观察，不改业务／测试、不重开完成状态、不改写旧验证。不能仅凭当前失败断言经验被证伪；来源、范围、时间和归因分别核实。必要缺测试变体仅提出补测方案。

## 收口证据

记录原用户输入、实际模型身份、原生加载根、受检包摘要、逐工具事件、真实父进程独立断言、SQLite 的 Task／REV／run／来源／学习版本、授权与副作用边界。按观察区别真实发现、原始失败、模型推断、未知和未运行检查；双维审查标为会话自审，人工复核不自称独立模型审查。

模型退出零、自动检查通过或自行声称完成，都不能直接设置整切片 passed。先集中修复必需问题、复验受影响组件，再对同完整包复测相应实际场景。两宿主不能相互代替，原生 Windows 仍是独立门槛。模型身份、额度和权限以实际结果为准；Claude 的先前 MiniMax-M3.1-Flash 选择只用于明确指定进程，不改全局配置，不自动购买或轮换账户。


## 当前结果与原包门槛处理

同一 11e3 完整包的 [Codex r4](codex-model-review-alpha4-r4.json) 与 [Claude r3](claude-model-review-alpha4-r3.json) 已完成全部五场景并通过本机核心判据复核，非阻碍文案／原生拒绝探测限制另行保留。IMP-004 当前切片的 M1 分支记 passed_local，不推整个 M1 或全局 V 通过。

IMP-003 原 alpha.3 也已产生实际响应并确认旧只读指引缺陷；其原包结果保留 failed。修复后的对应场景按[明确基线与派发记录](../imp003/acceptance-baseline-alpha4.json)另行复测，不暗中将新包响应改写为旧包通过。用户已明确暂不创建 Windows VM，原生 Windows 门槛不关闭，不进入 M2。

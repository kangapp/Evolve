# Evolve 0.1.0 本地首版交付

设计基线0.6.2，插件0.1.0，内核protocol16，SQLite schema4。IMP-001—IMP-014按已记录的当前环境与宿主范围完成；[最终阶段门槛](stage-gate-010.json)、[M3范围](milestone-m3-current-scope-010.json)和[140项要求映射](acceptance-map.json)分别保存依据。未公开发布、部署或替用户修改个人配置。

## 交付与使用入口

| 内容 | 位置 |
|---|---|
| 插件源码工程 | 当前仓库根；[README](../../../README.md) |
| 完整运行目录 | `dist/evolve-0.1.0/` |
| 独立运行包 | `dist/evolve-0.1.0.zip`；解压后保留整个目录 |
| 完整源码快照 | `dist/evolve-0.1.0-source.zip`；含工程、测试、设计及验收历史，排除dist、缓存和临时项目 |
| 实际目录及工程清单 | [工程目录](../../project-layout.md)、[维护文件摘要](../../../engineering-file-manifest.json) |
| 安装与项目启用 | [安装指南](../../installation.md) |
| 工作请求与日常流程 | [使用指南](../../usage.md) |
| 开发与打包 | [开发指南](../../development.md) |
| 兼容、错误及恢复 | [兼容说明](../../compatibility.md)、[排错](../../troubleshooting.md)、[维护协议](../../../shared/recovery.md) |

运行包有83份受检资源及清单自身，维护工程216份文件。八个Skill共用一份shared／runtime；运行包包含两个宿主及本地市场清单、模板、离线指南、LICENSE和NOTICE，不包含源码测试、验收历史或用户资料。工程组织参考Matt Pocock skills仓库，固定来源及未复制代码的说明见[NOTICE](../../../NOTICE.md)。

拿到运行包后，将整个目录放在稳定安装位置，按安装指南注册到Codex或Claude Code，并只在目标项目启用。先表达：“使用Evolve看看这个项目，先说明理解和方案，不修改业务文件。”首次init只建立项目记录设施；实施按具体授权继续，正式知识另按准确候选批准。换会话可表达“继续这个工作项”，只验收请求会保留阶段边界。

## 实际验收

- **642项全量回归／140.984秒**通过；422条当前V引用逐项匹配实际AST方法、文件摘要与本次通过日志。稳定V编号140项：138项当前有效范围通过，V-009发布准备、V-040个人跨项目库按D-017退出，不列通过。
- 当前完整包两宿主安装／发现／项目范围：15检查、16命令；双宿主生命周期38检查、42命令，保留真实原始红及受控进程退出。当前环境的中文／空格路径、移除下载副本、整包移动与位置独立通过。
- 公开CLI实际受控SQLite数据流程21次；真实旧协议14、15到16的显式升级／拒绝各8命令通过。仅有限同步Python／SQLite，不扩展成任意正式provider证明。
- Codex默认gpt-6-astra的R3五新会话62命令保留为相同运行时字节的完整业务证据；R4另完成一新会话8命令的准确指南容器定向复验。
- **Claude当前R4四个完整代表会话／92命令通过**：完整复杂方案、原行为前证明、文件段暂停、展示REV及新会话CORE／REPORT／整项验收。第五只读调查返回真实HTTP429／rate_limit，立即停止；**原七场景批次未完成**，不能宣称高级尾部在Claude独立通过。
- 沿用户既有Codex优先和统一授权，Codex在同一稳定临时项目另用三个新会话45命令完成准确均值候选、具体接受／仅REPORT实施／新验收封存，以及控制侧回退后只验收。原五测试、CORE结果及原证明保留，原四AC保留并增加第五AC；最后实际integration退出1、当前VER blocked，原封存和Task终态不变。这是混合宿主接续，不是任一宿主七会话全通过。

[功能证据](functional-validation-010-r4.json)、[生命周期主审](lifecycle-primary-review-010-r4.json)、[Codex完整业务主审](codex-model-review-010-r2.json)、[当前指南主审](codex-guide-shape-review-r4.json)、[Claude代表路径主审](claude-representative-review-010-r4.json)及[Codex接续主审](codex-cross-host-tail-review.json)可定位原始轨迹与摘要。当前数据库请求／结果／blob／来源及input_checks核对通过，保护索引与实际检查点和注册文件相符，无live run或占用。宿主两维审查为自审，主审不冒称独立第三方代理审核。

所有失败候选、权限／额度停止和安全输入拒绝均保留；原始model summary的pending／false不改写，单独主审和门槛承担通过结论。文档和结构校验只证明文档／结构，不冒充功能或模型通过。

## 摘要与后续选择

源码资源摘要：`7092b24b1b47b28b44ce48f751955d390758c391a008801f077b727365fee329`。渲染运行包资源摘要：`41a93e83f10e3771195010e91df6742dd8a88e0a47f8ec52587bafce913e56a6`；二者因source-only段移除而不同，不混用。最终两个ZIP的字节SHA保存在交付侧 `dist/SHA256SUMS` 与 `docs/evidence/imp014/final-artifacts.json`；这两份回执在归档后生成，不纳入源码快照自身。

当前仅本地／私有交付，没有公开发行许可选择或真实生产／远程／动态后台provider证明。其他平台不作为本轮门槛，也不补写实测。后续建议先在真实小项目试用，再处理公开许可／仓库与市场上架、OQ-009长期检索／容量实测、OQ-010具体正式provider能力。CLI能力目录全限定标识与动作／方法参数的对应提示可后续改善；当前协议表和示例给出的参数可执行，不为输入错误放宽门禁。

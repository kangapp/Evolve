# 0.6.2：Matt 对比采用与完整小流程实施计划

日期：2026-10-31（Asia/Shanghai）。用户明确认可对比建议，授权直接修订设计和分阶段实施计划，保持既有职责及授权边界，暂不开始编码。当前版本 **0.6.2**；新增 D-025／P-018，所有实施和功能验收仍未执行。

## 修订前保护

[0.6.1 完整快照](pre-matt-revision-0.6.1-20261031.zip)包含 28 个文件：七份当前 Markdown、17 张 SVG、图源、渲染器、manifest 和文档检查器；不重复装入 archive 和缓存。内部 snapshot-manifest.json 保存路径、字节数及 SHA-256，创建后逐项验证。

ZIP SHA-256：`d6ff4faa048f50446d35e044db9cf7ff253097f7ece2f1ba04785fa2cdf311a4`。

旧 [0.6.1 审核记录](design-review-0.6.0.md)与 [0.6.0 重构记录](revision-0.6.0.md)保持原文。前轮聊天 T01—T17 是未执行草案，本轮在 delivery 中用 IMP-001—IMP-014 取代；它们不是业务库中被重编号的 Task。

## 来源与采用边界

Matt 来源固定到 [a496f5513d4a4cf889bc48e189e579f4b0bdf6aa](https://github.com/mattpocock/skills/tree/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa)，该提交时间为 2026-10-29；核对发生于 2026-10-31。manifest 的 1.3.2 标签不证明全部 main 内容已成为已发布版本，本设计按固定源码比较。

- [to-spec](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/to-spec/SKILL.md)／[to-tickets](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/to-tickets/SKILL.md)：采用已有上下文、对外行为测试入口、完整可验证小流程和真实阻塞条件；保留广泛迁移的兼容扩展／迁移／清理例外，不强制长用户故事清单。
- [implement-spec](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/implement-spec/SKILL.md)：认识到上游已有任务图及整规格推进；采用按就绪条件推进和少量来源引用，不采用自动子代理、独立 worktree、合并及 PR 流程。
- [code-review](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/code-review/SKILL.md)：采用规格／规范双维审查；Evolve 扩展到实际工作区快照，适配未提交修改，不要求新代理或自动提交。
- [diagnosing-bugs](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/diagnosing-bugs/SKILL.md)／[tdd](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/tdd/SKILL.md)：采用可捕捉症状的观察办法、独立预期和前后复验；无法复现仍允许保留有标注的假设／历史证据，不能虚构根因或越权加探针，不机械要求所有工作先写测试。
- [domain-modeling](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/domain-modeling/SKILL.md)／[retro](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/retro/SKILL.md)：采用词汇与重要决定的按需沉淀、机械错误优先转检查；沿现有确认和修改闭环，不自动写正式规则、CI 或 hook。
- [setup](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/skills/engineering/setup-matt-pocock-skills/SKILL.md)／[安装说明](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/README.md)：上游支持本地 Markdown 任务及项目资料，并非强制外部 Issue，也并非没有长期上下文。采用整包安装与项目 setup 分离的体验。

安装事实参考 [Codex 插件打包](https://developers.openai.com/plugins/build/plugins)、[Codex 命令参考](https://learn.chatgpt.com/docs/developer-commands?surface=cli)、[Claude Code 插件规范](https://code.claude.com/docs/en/plugins-reference)；这些是核对时的可变官方文档，实施时按实际宿主版本复核。前轮本机只读 `codex --version`／帮助输出显示 0.166.0-alpha.5.1 支持 plugin add 与 marketplace add，不代表 Evolve 已打包或安装。

[skills 安装器源码](https://github.com/vercel-labs/skills/blob/main/src/installer.ts)的普通复制路径以单 Skill 目录为单位；结合 Evolve 的 shared／runtime 兄弟布局，推断不能直接承诺散装安装得到完整包。该渠道后置，整包路线优先。不新建 MCP／Node 服务、自动更新器或公共市场项目。

## 四项主要修订

1. **完整小流程及计划**：补任务拆分判据与迁移例外；M1 五个切片先验证安装、日常小改动、排错、跨会话学习和安全续接；M2 六个切片覆盖复杂功能、正式文档、数据／血缘、多任务和学习改进；M3 三个切片完成恢复、外部操作和完整交付。基础 archive 前移 M1，单写者知识闭环不等待完整并发。阶段门槛与直接产物依赖分开。
2. **审查**：verify 组织规格／规范双维审查，包含相关脏工作区；缺陷有依据、级别、门禁与复查，主观建议不伪装硬规则。修复仍归 apply，只审查不扩张修改权。复用 Verification／Evidence。
3. **排错**：以能识别症状的输入、独立预期和真实观察连接调查与验收；前后结果可比；偶发／无法复现保留限制；临时隔离实验与持久修改／真实环境操作分别授权。
4. **安装升级**：完整包内资源同版本定位，宿主管包、init 接项目、doctor 只读；在途运行固定版本或安全结束后切换；更新不隐式迁移，回退要核兼容；卸载保留项目资料及未知外部保护。M1 要验安装、兼容更新和卸载重装，M3 完善完整范围。真实试用资料跨阶段保留；后继若改结构，具体迁移及恢复须纳入对应切片并确认，未提供时拒绝不兼容写入，不提前建设通用迁移平台。

新增 V-126—V-137 共 12 项断言及案例 S—V；不新增 Skill、顶层动作、领域实体或后台服务。词汇／ADR 按需复用及经验转自动检查也已纳入，不重开单项目、Markdown＋SQLite、无部署等已确认决定。

## 文档与验证

七份当前 Markdown、相关图源及全部 17 张 SVG 同步到 0.6.2。文档检查器增加实施切片的定义、引用、依赖图与验收映射检查，保留图源／渲染器／SVG 摘要及历史快照核对。

实际文档验证（2026-10-31）：

- `python docs/check_design.py` 通过：13 份 Markdown、238 处本地引用、137 项 V、25 项 D、18 项 P；八个 Skill owner／十四动作保持一致。
- 14 个实施切片均有交付及验收映射，22 条直接依赖的目标存在且无环；这是结构检查，不替代对依赖必要性的人工审核。
- 17 张 SVG 已重新生成，345 个文本节点边界及图源／渲染器／SVG 摘要对应检查通过。Edge 无界面渲染抽查图 04／05／07／16，未见截字或元素遮挡。
- 隔离副本的七项负向检查均按预期失败：循环依赖、未定义依赖、缺验收映射、只改图源、只改渲染器、只改 SVG、未定义 V 引用。原项目未注入这些错误。
- 三份历史快照的归档摘要和共 83 个原文件逐项摘要通过，三份文档工具 Python 源码语法检查通过。

没有创建插件源码、SKILL.md、history.db 或真实运行记录，没有执行插件安装、更新、卸载、迁移、业务测试或正式数据操作。上述结果仅验证设计文档与绘图工具；后续验收条目是待实现约束，不是功能通过记录。

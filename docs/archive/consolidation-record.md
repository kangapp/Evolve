# 2026-10-28 文档重组记录

用户确认按五份主文档收敛设计。业务基线继续为 0.5.2，未创建插件、SKILL.md、runtime 或历史库，未执行案例、测试或发布。

## 保护与原文

重组前保存 [完整原文快照](pre-consolidation-0.5.2-20261028.zip)，包含 40 个文件（21 份 Markdown、16 张 SVG 及 3 个图册源／清单），ZIP 内有 snapshot-manifest.json，记录每个原文件的 SHA-256。快照排除缓存；已逐文件核对内容摘要并通过 ZIP 完整性检查。

ZIP SHA-256：`6a397aa3c45db87b395c74e4b23d4aed4037e2bce3a195d871d1a15dbd41e66b`。

快照为重组前逐字原文，不是可恢复业务包，不执行其中任何命令。没有 Git 仓库时也可据此回看原材料。

## 文件到章节的迁移

- AGENT.md → [短建设入口](../../AGENT.md)，详细 G／NG、AC、D／P／OQ、布局及计划分别入正文，不丢编号。
- README.md → [短导航](../README.md)，16 图按主题分布在正文，清单仍为 diagrams/manifest.json。
- architecture.md、domain-model.md → [总体设计](../design.md#architecture)、[领域与权威](../design.md#domain)；运行环境及宿主适配入 runtime。
- multi-skill-plugin.md → [总体职责](../design.md#architecture)及[阶段契约](../workflows.md)，合并原 workflow 的详细步骤，不另保留重复输入输出清单。
- user-guide.md、workflow.md、analysis-workflow.md → [统一工作流](../workflows.md)，分析记录字段入 [runtime](../runtime.md#analysis-records)。
- contracts.md → [唯一命令归属](../workflows.md#commands)及 [配置／工具／模板](../runtime.md#configuration)。
- storage.md、skill-handoff.md、release-and-recovery.md → [数据](../runtime.md#data)、[执行](../runtime.md#execution)、[恢复](../runtime.md#recovery)；发布业务门禁入 [workflows](../workflows.md#release)。
- commands-and-learning.md、experience-governance.md → [知识工作流](../workflows.md#learning)、[知识持久化](../runtime.md#knowledge)、[参考依据](../design.md#references)。
- validation.md、decisions.md → [实施与验收](../delivery.md)，保留 V-001—V-061、D-001—D-014、P-001—P-010 和 OQ 处置；重复的修改流水在原文快照回看。
- examples/analysis-to-release-walkthrough.md → [案例 B](../scenarios.md#investigation)，保留完整逐步内容，调整标题层级和链接。
- examples/analysis-investigation-walkthrough.md → 案例 B 的认知主线及[补充边界](../scenarios.md#edges)，合并重复讲述。
- examples/article-favorites-walkthrough.md → 通用开发步骤归 workflows；部分任务后换会话、验收和人工结果登记以[案例 A](../scenarios.md#new-project)补充新项目路径，原收藏案例逐字版本仍在快照，不把演示编号当真实业务记录迁移。
- design-review.md、design-review-0.5.1.md → 同名历史文件；保留原版本与检查快照，加历史提示并修正文档链接，逐字版本在 ZIP。

## 权威与导航约束

当前有效正文为五份主文档，短 AGENT／README 仅约束及导航。历史区默认不加载；不再保留旧文件的空跳转页，以免继续扩大文件数。

一个规则的负责位置：对象／权威 → design；命令／动作／门禁 → workflows；字段／持久化／恢复 → runtime；计划／验收／决定 → delivery。案例只给实例和预期产物，不成为第二份规范。

## 实际检查

- 当前日常阅读为 7 份 Markdown：五份主文档、短 AGENT 和短 README；历史区为两份审查及本记录。19 份旧拆分文件在逐文件核对快照摘要后移除，没有保留空跳转页。
- 10 份现存 Markdown 的 UTF-8、围栏、232 个本地文件／章节引用检查通过；3 个 JSON／TOML 示例可解析。
- 与保护快照对照：20 个逻辑别名到 9 个 owner 的映射完全相同，61 条 V 验收正文逐条一致，G／NG 定义及 D／P 标识保留。
- 16 张 SVG 均有正文引用且字节摘要与快照一致；7 份当前文档浏览器渲染无失效图片、无效内部锚点或横向溢出，人工查看入口、运行契约及分析路径排版。
- 快照内 40 个原文件均通过摘要校验及 ZIP 完整性检查。临时文档组装脚本已移除，未创建 SKILL.md、sdd-plugin、业务代码或 history.db。

V 系列仍全部是未来实现验收要求，以上仅为本轮文档检查，不能标记任何插件功能测试通过。日期：2026-10-28（Asia/Shanghai）。

# 0.6.0 需求收敛与整体修订记录

记录日期：2026-10-31（Asia/Shanghai）。用户明确要求按已审阅的修订方案整体重构设计。本次更新正式设计与文档图册，不实现插件、不建业务历史库、不安装或执行真实数据操作。

## 修订依据与保护快照

本轮确认：四类工作共用流程；单项目持续积累；按复杂度组织方案／任务；梳理深度按项目与需求调整；未明确修改先调查与方案；正式知识集中确认；候选经验可供调查；按影响验证；允许外部编辑、多任务并存；正式环境数据修改需具体授权；不需要部署或个人库。

[0.5.6 修订前完整快照](pre-revision-0.5.6-20261031.zip)包含 AGENT、五份主文档、README、17 张 SVG、图源和 manifest，共 27 个文件；排除旧 archive 和缓存。snapshot-manifest.json 保存每文件字节长度与 SHA-256，已与归档字节逐一核对。

ZIP SHA-256：`dd007b29fc678e2c734bf026821bf025ee0f1927b160927decc655c53277ea2e`。

原文快照只用于设计追溯，不是可恢复业务数据库包。旧 D／P／V 的当时正文可从中读取，新正文保存当前效力及替代关系，不回写旧历史。

## 25 项取舍的落地

编号沿用本轮审阅方案，正文是规范唯一来源。

### 保留

- **K1** 存储权威 → [design authority](../design.md#authority)；V-017／V-042。
- **K2** 领域及独立分析 → [design domain](../design.md#domain)；V-046／V-072。
- **K3** run／operation／必要恢复 → [runtime execution](../runtime.md#execution)、[recovery](../runtime.md#recovery)；V-003／V-012／V-023。
- **K4** 真实验收与证据 → [workflows verify](../workflows.md#verify)；V-008／V-081。
- **K5** 多 Skill／公共内核／双宿主 → [design architecture](../design.md#architecture)；V-018／V-019／V-107。

### 简化

- **S1** 简单方案正文快照、文件按需 → [workflows propose](../workflows.md#propose)；V-007／V-086。
- **S2** spec → 依赖任务 → 连续实施 → 同节及 [apply](../workflows.md#apply)；V-087／V-090。
- **S3** 封存与正式知识应用分开 → [archive](../workflows.md#archive)；V-010／V-092。
- **S4** 项目内学习与集中审阅 → [learning](../workflows.md#learning)、[knowledge-approval](../workflows.md#knowledge-approval)；V-091／V-098—V-100。
- **S5** 配置子集、语义影响和备份成本 → [configuration](../runtime.md#configuration)、[recovery](../runtime.md#recovery)；V-063／V-101—V-102。

### 移出

- **R1** Release／发布／部署：退出当前模型、命令、配置、模板与计划；V-009 退出，正式数据能力转 V-103—V-105。
- **R2** 个人库／两端提交：退出；V-040 退出，项目备份导出和规则批准保留。
- **R3** 组合发布和部分交付拆分：退出；成果归属与混合现场验证保留 V-097。
- **R4** 自动多代理、强制工作树／Issue／向量库／数据平台：继续作为非目标；不是将原来已有实现删除。V-109。

### 补充

- **A1** 授权优先 → [common](../workflows.md#common)；V-085／V-090。
- **A2** 梳理深度与复杂度分开 → [context](../workflows.md#context)；V-088。
- **A3** 来源、时点、确定性与缺口 → [documents](../runtime.md#documents)、[inputs](../runtime.md#inputs)；V-089。
- **A4** 集中确认绑定具体内容 → [knowledge-approval](../workflows.md#knowledge-approval)、[knowledge](../runtime.md#knowledge)；V-091。
- **A5** 候选线索与反例影响 → [learning](../workflows.md#learning)；V-098—V-100。
- **A6** 外部编辑接纳 → [concurrency](../runtime.md#concurrency)；V-093。
- **A7** 多任务、多会话与冲突 → [multitask](../workflows.md#multitask)、[concurrency](../runtime.md#concurrency)；V-094—V-095。
- **A8** 最小跨任务依赖条件 → [data](../runtime.md#data)；V-096。
- **A9** 按影响检查及混合工作区 → [fingerprints](../runtime.md#fingerprints)；V-097。
- **A10** 具体授权数据操作与未知核实 → [external-effects](../runtime.md#external-effects)；V-103—V-105。
- **A11** 学习效果与早期宿主反馈 → [evaluation](../delivery.md#evaluation)、[milestones](../delivery.md#milestones)；V-107—V-108。

## 原 15 项审查的处置

以下 S／M／G 编号属于原审查，与上面的取舍 S 编号是不同命名空间。

- **原 S1**：保留并修订为通用外部数据操作，执行前登记、具体授权、占用、未知核实与恢复保护。
- **原 S2**：组合发布部分退出；保留成果归属、依赖和混合现场检查，不能把所有问题宣布消失。
- **原 S3**：缩小为明确跨任务条件、版本、证据和直接影响传播，禁止环。
- **原 M1**：受影响已完成任务确定转 todo；run、成果完成、验收及知识应用分别表达。
- **原 M2**：学习效果进入早期固定案例，记录实际采用与结果，不看引用次数。
- **原 M3**：反例影响项目内经验、正式规则复审和待执行方案；个人副本退出。
- **原 M4**：取消每阶段完成点全量备份，补采集预算、容量预检和可审阅整理；唯一证据不静默删除。
- **原 M5**：保留 SQLite 随 Git，明确多任务共享目录、历史分叉保护和人工核查，不自动合库。
- **原 M6**：原始字节审计与固定配置语义分组分开，显示调整不触发全业务复验。
- **原 M7**：重排 M1—M3，宿主最小流程和经验检索提前，真实数据写入与维护完善后置。
- **原 M8**：恢复前对比受管集合，包外受管资料保护隔离，未登记文件保留且不覆盖冲突。
- **原 M9**：TOML 支持受控写入子集及往返校验，不承诺所有格式的无损编辑。
- **原 G1**：轻量体验看重复背景问题、确认次数、阅读量与恢复步骤，不只看文件数量。
- **原 G2**：关键授权、范围、来源、条件及版本有类型，details 不承担关键门禁语义。
- **原 G3**：五份规范维持单一权威；本记录只保留映射和历史，图册 manifest 指向负责章节。

## 文档与图迁移

当前仍为五份主文档＋AGENT／README。保留既有重要锚点；workflows release、runtime release-executor 与 delivery 的历史审查锚点只承担历史定位，正文明确现行范围。

17 张当前 SVG 全部由新图源生成，manifest 带标题、基线和负责章节。原 09-release-status-and-rollback.svg 字节已核对入快照，从当前图册退出，由 09-authorized-data-operations.svg 替代。其余图保持编号／路径并更新内容。

原 G-001—G-010、NG-001—NG-007、D-001—D-016、P-001—P-013、OQ-001—OQ-008、V-001—V-084 和建设 AC-001—AC-014 均有追溯。新增 G-011—G-013、NG-008—NG-010、D-017—D-024、P-014—P-016、OQ-009—OQ-010 和 V-085—V-110。V-009／V-040／V-068 退出专属能力，其余旧条目按新范围修订，编号不重排。

不创建插件、真实 schema、业务测试或宿主安装。Python 文件仅为既有图册渲染和文档一致性校验。

## 本轮实际检查

- 执行 `python docs/check_design.py`：11 份 Markdown、194 个本地文件／锚点引用、1 段 TOML 示例通过；当前入口及五份主文档基线一致。
- G／NG／V／D／P／OQ 的定义编号分别为 13／10／110／24／16／10，无缺号或重复；8 个 Skill 与 14 个顶层动作映射一致。
- 17 张 SVG 的 XML、manifest、负责章节引用、尺寸、316 个文本节点及容器边界检查通过；图源、渲染器及文档检查器 3 个 Python 文件语法可解析。
- 使用本地 Edge 无头渲染检查架构、封存与知识确认、授权数据操作、多任务续接 4 张关键图，文字与连线可读，未见截断或重叠；其余图执行结构和边界检查。
- 0.5.6 ZIP 完整性、总摘要及 27 个文件摘要校验通过；原发布 SVG 删除前已核对快照字节一致。
- 语义走读覆盖未授权修复、知识延期／拒绝、外部修改、跨任务依赖、混合工作区、数据操作未知及旧档案恢复；正文与案例使用同一边界。

以上仅为设计文档、绘图工具与静态契约检查。所有 V 均仍为未来功能验收，案例、插件、真实数据操作、数据库故障注入和宿主演练没有执行。


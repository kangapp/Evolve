# 项目知识交付与迭代维护

完整接入、知识主题迁入、实施前知识影响和封存前收尾时读取本页。分类正文与图文检查见[文档约定](knowledge-documents.md)；具体候选、决定、应用和验收沿[正式知识协议](knowledge-candidates.md)。方法均经共享 JSON CLI 调用，用户不填写内部编号。

## 完整接入

1. 只读发现现有规则、产品资料、入口、关键模块、主要链路、数据和检查；按范围核对关键约束，保存实际来源。已有可信内容优先复用，事实、期望、推断和未知分开。
2. 用 init.connect 建立记录设施；这一步不表示知识交付完成。仅解释或明确只接入记录时保持相应范围。
3. 调用 init.survey，给 scope、sources 和 coverage，逐一覆盖 purpose／domain／behavior／code／contracts／verification／decisions／risks。
4. 读取分类模板，提出项目导航与代码地图或等价已有文档的准确候选。其他知识按实际内容建立。核对来源与图文，按具体决定应用，并用 verify.knowledge 验收实际文档。
5. 全部必需文档应用并验收后调用 init.complete。工具核对当前调查、来源和文档版本；报告范围与缺口。大型项目分批深查，新项目如实描述尚无实现，不能补造入口或测试通过。

survey 输入示意：

```json
{
  "scope": ["."],
  "sources": [{"path": "src/main.py", "expected_digest": "实际SHA-256"}],
  "coverage": [
    {"perspective": "code", "status": "partial", "basis": "实际阅读入口和主要链路。",
     "source_paths": ["src/main.py"], "questions": ["异常重试分支尚未核实。"], "blocking": false}
  ]
}
```

实际请求必须给八项而非只有示例一项。status 为 covered／partial／unknown／not_applicable；covered 引用已保留来源，partial／unknown 保留问题。每项给真实依据，不适用也说明理由。blocking 为布尔值，有阻碍时保持未完成。目标、领域、行为、实现、验证视角未知时，完整交付不能完成。

sources 为实际文件路径及摘要，必须在 scope 内。范围和粒度按调查事实表达，修改日期不冒充观察日期。外部材料沿 analyze 保存观察和时点；项目文档引用实际底稿，尚未重读远端时保留限制，不把本地字节相同当远端新鲜度证明。

## 分类知识与已有映射

typed 候选保留原 content、presentation、acceptance 等字段，并增加 document：

```json
{
  "kind": "codemap",
  "topic": "code-navigation",
  "scope": "主要本地入口与业务链路",
  "mode": "managed",
  "sources": [{"path": "src/main.py", "expected_digest": "实际SHA-256"}],
  "topics": [{"topic": "code-navigation", "section": null}],
  "replaces": []
}
```

kind 为 project／codemap／domain／spec／decision／development／architecture／data／rule。topic 是稳定知识主题，scope 是实际范围；sources 保留字节依据。topics 可把已有文档按多个主题及实际标题登记；省略时使用 document.topic 的整篇主题。sections 默认使用模板标题，也可声明实际互异标题，允许多个职责合并在同一章节；短文以连续段落表达时显式给空数组。structure 判据仍核对该类型全部必要语义，不以标题数量代替内容完整性。

managed 正文位于 evolve/。初次复用已有文档用 mode=mapped，content 编码后的字节必须与现场完全一致，包括换行；沿真实内容检查，不强制原文改成新模板。已登记 mapped 正文的修订应迁入 evolve/，不在原位置静默改写。

映射的 scope、topics 和 acceptance 对应资料实际承担的职责；可靠局部约定可按局部范围复用，缺少的规格信息记录在 survey 或其他适当知识中。四维检查仍需真实完整，不能要求局部原文覆盖整类模板，也不能因为保留字节就假定内容正确。

同一当前主题只有一个权威位置。迁入候选的 replaces 逐项给原 topic、path、artifact_version_id，使用 status 返回的准确值。新文档保存完整当前内容；原文件保留。只替代选定主题，其余章节继续有效。迁入计划同时处理对外入口和知识导航受影响的引用；主题替代记录不自动改其他文档。

修订同一文件时保留其仍负责的全部主题映射；已迁入其他位置的主题不重新接管。省略映射不能隐式删除未涉及主题的导航。

同文件精确正文补丁的合成不同时合成来源、职责、范围等 document 元数据。正式版本前进且元数据不同后，旧 typed 候选应基于当前正文及元数据重新提出，不能凭正文 composition_review 覆盖后来的知识依据。managed 修订的 sources 不引用目标自身（含路径别名）；原文依据已有正式基线版本保留。mapped 初次登记的原文自来源因字节不变仍可使用。

应用前重新核对实际来源、原版本、替代对象和目标字节。status.project.knowledge 给 documents、active、superseded_by、来源适用性和初次交付范围。它是只读导航，查询不补写索引、不运行检查。

## 方案中的知识影响

形成短方案或复杂 Task 时，对已接入知识维护的项目显式给 knowledge_impact，允许经过核查后的空数组。工具至少要求覆盖 scoped 文件及其已登记来源关联的知识主题；Agent 还要核对业务含义和接口等语义影响。

```json
{
  "knowledge_impact": [
    {"topic": "import-behavior", "disposition": "required", "target_path": "evolve/specs/import/spec.md", "reason": "新增重复导入规则。"},
    {"topic": "code-navigation", "disposition": "unchanged", "reason": "入口与模块职责保持。"},
    {"topic": "future-cleanup", "disposition": "followup", "reason": "独立整理，不影响本次交付。"}
  ]
}
```

复杂工作可在各 Task 分别声明，或使用根级默认声明；各 Task 对同一主题的约定保持一致。声明进入任务定义与 REV 比较。取消必需更新、改变目标或降为附带建议，需要沿 update 呈现具体范围差异并按实际决定处理。

required 对应真实文档交付，必要时在原复杂方案增加 owner=init／sync／learn 的 Task，沿既有 required delivery 绑定 AC。未实现目标保留在 Change／REV；实现验收后再将适用行为写成当前基线。正文变化、模块地图误导、业务定义或接口约束改变不能被“文档可延期”掩盖。

## 收尾与下次复用

最终封存前调用 sync.assess，input 给当前 change_id、revision_id 和 observations。每项 observation 给 topic、result、observer、basis，覆盖全部 knowledge_impact：required→updated，unchanged→unchanged，followup→deferred。

updated 要求指定 evolve/ 位置有本次基线之后的新正式版本、最新实际文档验收通过、当前字节及来源仍匹配。unchanged 需要在当前成果下阅读原正文及变化来源，说明含义为何仍适用；工具保留新观察依据，不改写旧来源事实。deferred 保留独立后续事项，不能代替 required。

archive 核对当前实施指纹、知识处理和相关来源，变化后需重查；代码通过、必需知识未完时分别报告进展，整项仍未完成。候选检查、文档验收与业务验收分别保存。

新工作和跨会话继续沿 project.md、status／resume 恢复相关知识，查看 active 及 applicability，核对当前现场。源变化只扩大相关调查；外部编辑保留，历史验收不冒充当前通过。

## 受限事实维护

sync.facts 仅支持 kind=path_move：旧源码位置实际消失，新位置字节与文档已留存来源完全相同。支持 managed 的 project／codemap／development 文档内准确代码路径或 Markdown 链接；正文中的其他路径提法需要显式内容审阅。

自动维护以同一正式版本最近一次安全完成且 passed 的实际文档验收为基础；四维内容及未变化图形沿该依据保持。最新验收失败或尚未验收的正文先完成具体内容检查，不能用路径移动生成新的整篇通过结论。

authorization 除 project_records、knowledge 外，需 facts_maintenance、准确文档 paths，以及 fact_moves=[{from_path,to_path}]。input 给 path、expected_digest、fact_update={kind: path_move,from_path,to_path}。工具推导全部候选字节；额外正文、来源改变、外部编辑、控制文件、未授权移动均拒绝。

该方法依序使用既有 propose／check／review／apply／verify.knowledge，保留 scoped_facts 授权及各子运行。结果给 parent_request_id、application_id 和 factual_verification。重试使用原 request_context 身份和完整原输入；异常中断按 status 的实际子运行 recover 后续接，不能生成新身份重复派发。

此能力不授予修改业务含义、模块职责、规则或已有决定的权限。无法证明受限差异时保存候选，按具体语义决定处理。

## 每项工作的知识复核

新方案及修订给 knowledge_review，按实际含义检查 codemap、domain、spec、decision、development、architecture、data、rule 八类视角。它补充文件来源关联，复用已有 knowledge_impact 和正式候选流程。可将结论与依据相同的视角合为一组，每组包含 views、result（changed／unchanged／unknown／not_applicable）、实际 basis 和可选 source_paths；每个视角出现一次。source_paths 使用实际已读文件，运行时保存其摘要。空项目说明尚无实现及未知，不创建占位文档。

changed 视角在 knowledge_impact 中给具体 topic、views、required／followup、理由及必要目标；正式更新继续展示差异、按具体决定应用和实际文档验收。已有准确文档可以保持不变，说明本次实际核对依据。

收尾 sync.assess 除各 topic 的 observations，还给当次实际 knowledge_review，覆盖原方案结论及当前来源；结论改变先展示并修订方案，不能静默改成 unchanged。封存核对本次实现指纹、原复核定义及最新来源；发生相关变化后重新核对。未声明该字段的历史方案保留其真实缺口，不补造过去已完成八类调查。

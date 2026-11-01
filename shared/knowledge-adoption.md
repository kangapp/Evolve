# 外部正式版本采纳与过时提案

正式 Markdown 已被外部编辑、旧待审内容被后续工作替代时读取本约定。当前版本支持具体外部全文的采纳；观察、内容检查、用户批准、正式版本登记及实际目标验收分别保存。未知修改者保持未知，纯查询不建立正式权威。

## 采纳当前外部全文

先读 status.knowledge_refs 中原 artifact_version_id／registered_digest 和当前外部字节，展示完整旧新内容、来源、实际观察时间及含义影响。未登记文件仍由 init 建初次基线；已有正式规格由 sync.propose，规则由 learn.promote（stage=propose）负责。

沿[候选协议](knowledge-candidates.md)给完整正文和判据，另给 adoption={formal_version_id,registered_digest,source,observer,observed_at,basis}。formal_version_id 与 registered_digest 精确引用原正式版本；observed_at 为含时区的实际观察时间；basis 说明原正文、外部内容及取舍的真实依据，不猜修改者。expected_digest 绑定当前外部字节，content 必须逐字等于这份外部全文。采纳和额外改写分为两个具体候选。

可用 edits 声明原正式字节到当前外部全文的确切差异，范围仍按[差异约定](knowledge-patches.md)；这里的 before 来自原正式版本。工具保留原正式全文，不以当前外部字节冒充它。规则仍需[经验支持与反例](knowledge-rules.md)，采纳不绕过来源门禁。

sync.check／review 登记实际内容观察和具体决定，文件及原正式版本均保持。只有对应 owner 实际应用且原正式版本与当前外部字节仍匹配，才沿同一 journal 登记新的 application／artifact。返回 adopted_external_bytes=true、file_bytes_written=false，明确这是现有外部字节获准成为正式版本，未重写文件。必需交付绑定实际 Task／AC，仍由 verify 重新验收目标后才能封存。

任何进一步外部编辑或原正式权威推进均阻碍旧采纳，即使后来又出现相同外部字节也不能省略原版本核对。未批准采纳时，普通修订继续报告 KNOWLEDGE_EXTERNAL。全文删除不在此采纳分支内。

## 旧批准如何继续

已具体批准的狭义候选，只能沿明确批次中的已批准采纳应用、确切原字节范围及真实来源链继续；实际组合正文还需具名检查。采纳没有声明局部差异、旧候选为整篇、范围重叠或含义冲突时停止相关项。明确采纳不是给其他旧提案的重复批准，也不是允许旧正文覆盖新含义。

## 已归档 A 的候选被 B 替代

新工作已形成不同的实际行为时，关联同步引用 B 的真实适用实现验收；A 的旧通过保留为历史，不能用它覆盖当前行为。后继候选沿同主题／正文识别的原家族生成新版本，旧未应用项标 superseded，保留原正文、决定与批准；新内容不继承旧批准。语义相关但无法按同主题／正文识别的情况由实际审阅说明，工具不猜领域同义关系。

具体候选 status 给 supersedes／superseded_by，关联工作项给 knowledge_proposal_refs 导航，已归档 A 仍可发现旧项及后继。查询只展示已有事实；B 未经过检查、具体批准及实际应用前，不以新提案名称宣称已同步。已应用旧记录不因替代而删除或重放。

## 中断与兼容

maintain recover 核对原实际 journal、原正式版本、具体批准和当前字节，仅补确定事实；纯采纳的恢复也不重写原文件或重复分配应用。不重跑内容观察，第三种字节保留冲突。protocol v10／schema v4 使不理解采纳证明链的旧写入器拒绝新档案；完整旧包保留，不自动迁移或改协议号。

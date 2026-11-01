# 同文件的具体批准差异

同一正式文件有多项待审差异、需要部分应用或沿已批准前项继续时读取本约定。当前版本支持 init 初次建立、sync 规格修订与 learn 规则共用实际文件协议；外部全文先按[具体采纳约定](knowledge-adoption.md)检查、批准并登记实际版本，未采纳字节仍为冲突。

## 明确差异与依赖

sync.propose、结构化 init.baseline.propose 或 learn.promote（stage=propose） 仍呈现完整候选及实际原版本，另给 edits 数组。每项为 {start,end,before,after,semantic_target}：start／end 是原基线 UTF-8 字节的半开区间，不能切开字符；before 必须等于原字节，after 为具体替换文本，semantic_target 明确本项负责的含义。各项范围和语义目标不重复；完整正文必须逐字等于声明差异的实际结果。插入使用空 before，移出条目使用空 after；当前不删除整个正式文件。

未提供 edits 的整篇候选继续要求原精确基线，不能自动参与局部组合。不同主题的具体候选可分别审阅；同主题正文、判据、交付／实现依据、差异或依赖变化仍形成后继版本，旧批准不转移。

dependencies 可给准确的 proposal 四项引用；应用前每个依赖须有已安全收尾且含义仍保留的实际应用。仅有候选、批准或字节碰巧相同不能满足依赖。

init 首次登记已有未映射文档时，可声明狭义初次差异；实际登记后，sync 根据已形成的正式版本提出后续独立候选，保留初次 application 和原批准。新文件初次建立或未声明 edits 的整篇含义按全文绑定，后续改动不能仅凭字节不重叠就声称原全文验收仍适用。预先基于尚未实际建立的正式版本提出后续候选不在此路径内。

sync 与 learn 可基于同一实际原版本分别提出狭义候选，明确批次和顺序后按真实链应用，不重新批准未变前项；规则来源与反例仍按[规则交付](knowledge-rules.md)核对。候选的领域语义与 owner 归属由实际内容观察明确，工具不会仅凭字节范围推断含义。

## 批次只有明确提案列表

sync.review 默认将 decisions 中的提案作为本次批次；也可用 input.batch 给完整 proposal 引用列表，在 decisions 中只决定当前选择的子集。已批准／应用的前项可只列入 batch，不重复批准。sync.check 也可声明所检查的 batch，分组本身不批准或应用任何项目。

各项仍保存实际接受／拒绝／延期及依据。拒绝的旧版本不能靠更换 ID 或分组恢复；延期项以后具体批准时，仍核对原内容和实际当前链。不同的单项批准不会被系统猜成同一批次。

## 应用已批准子集

前项改变正式基线后，工具沿实际 artifact 版本和安全收尾的 application 链核对每一步原／新字节、批准范围及来源。只有明确相关的批次、每步已知的实际差异，以及没有重叠范围或相同 semantic_target 时，才平移后项的原字节位置；不搜索近似文本、不猜领域含义、不覆盖其他字节。

用 status 指定候选读取 effective_candidate：实际 base_digest、result_digest、content、semantic_targets 和 chain。宿主必须实际阅读组合后的完整正文，并在对应 owner 应用的 input.composition_review 给 {base_digest,result_digest,semantic_targets,status:passed,observer,basis}，绑定这份具体内容；基线再变后重新检查。这里是内容检查，不是重复要求用户批准未变差异。字节不重叠不等于领域语义独立；实际观察者必须说明组合是否仍满足各项含义，工具不冒充语义判断。

应用保留原 proposal／批准的 candidate_digest 与 expected_digest，另存真实应用的原／新摘要、差异和证明链。已应用 delta 的重复请求只报告旧事实；改变已批准内容时另建后继候选，不重放旧 ADD。

## 验收、查询与中断

verify 重新阅读当前实际内容并记录新 applied 观察。旧应用的完整文件摘要可能不再相同，但后继已批准的独立差异能证明其负责含义仍保留；status.application.current_matches 表达整篇字节是否相同，effect_state.preserved 只表达声明范围的保留。不能把旧候选检查改称当前整篇验收。

同文件的每项必需文档 Task 都保留实际 application 引用。上游实际再验收可以沿同一保留范围继续满足依赖；任一必需含义的新失败仍阻碍整项封存，不因路径相同丢掉前项。Task／整项和历史／当前结论继续区分。

写前冻结具体 effect 和 journal；maintain recover 只核对原实际基线、批准及组成，不重新组合到另一份新现场，不重复检查或分配 application。外部字节、未知正式版本、范围重叠、含义冲突或缺来源均停止相关项并保留现场，无关项可继续。

旧写入器必须满足项目实际协议；保留兼容完整包，按支持的显式升级路径处理。

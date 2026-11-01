# 多工作项、前置条件与安全取消

## 定位与前置

A/B 工作项和独立分析可同时存在；先定位实际目标和当前版本，多个目标时明确选择。各自有方案、Task、结果和授权；相关关系本身不授权，也不成为阻塞理由。

跨工作项需要真实前置时，在完整复杂方案的具体 Task 声明 `external_dependencies`，与同 Change 的 `dependencies` 分开。短方案或 propose 根上的跨项依赖不受支持；需要这些条件时呈现复杂 spec 与明确上下文。引用从实际 status 取得，不要求用户填写内部编号。

每条外部引用绑定 `upstream_change_id`、`upstream_task_id`、`required_revision_id`、`required_definition_digest`、`condition_kind` 和实际 `basis`，都指同一项目中另一 Change 的当前 Task。四种条件为：

- task_completed：当前定义的实际 Task 成果已完成，相关来源和输出仍适用；不承诺接口已独立验收。
- verification_passed：对应实际且已安全收尾的最新验收通过。复杂 Task 依据其声明范围、上下文和依赖输入核对；简单上游仍保守核对整个工作目录的原验收截点。需独立推进时先在复杂方案明确真实输入边界，不降低条件来绕过变化。
- artifact_available：另给 `condition_ref` 为上游 scope 中的具体成果路径，核对已完成来源及当前字节；文件存在本身不等于来源成立。
- knowledge_applied：另给 `condition_ref` 为上游正式文档 Task 的实际路径，核对对应 owner 的安全应用及批准含义仍保留；候选通过、approved 或 Task 标题不能代替应用。

其他条件不接受 `condition_ref`，也不接受任意表达式。声明图必须无环。上游自产文件从下游固定旧上下文中移出，沿实际依赖输入核查；未声明的真实外部资料仍须明确上下文。

上游取消、定义／固定版本改变、原结果变化或当前必需依据失效时，后继只读视图显示 unmet／revalidation_required；历史 Task 完成、结果和 VER 保留。旧引用不会偷偷追随 latest，重绑通过具体 REV 呈现和接受。相同定义、成果和判据的新通过观察可证明原条件仍成立，不因单纯换 VER ID 强迫重写成果；实际采用的 VER 引用和核实时间单独留证。不同主题及无依赖 C 可继续。

## 资源和混合现场

同 Change 的写动作和同一规范化文件目标共用 claim。无关 Change 可以交替或并行；文件锁不约束外部编辑器。检查在短锁外执行，每次派发、写入和结果提交重新核对前置和占用。检查期间现场改变时保留实际文件与失败／受阻结果，不记当前通过。

verify 的 `verification_context` 保存该截点实际包含的其他工作、已保存结果比较、所需依赖及真实观察来源，`independent_isolation=not_asserted`。in_progress 的声明范围不被推断为已完成成果。整个工作目录指纹含未跟踪输入；Task 的局部依据用于明确的依赖复用，不宣称虚拟机或工作目录隔离。

不同 owner 的同文件正式差异仍沿[批准差异链](knowledge-patches.md)。已批准后项必须保留其依赖的上游含义：原应用链、当前批准候选的确切字节差异和组合正文共同校验；已准备且仍适用的本次候选在写前检查，写后仅观察已知候选字节，恢复沿原证明补事实。实质冲突在写前停止；第三种外部字节保留，批量批准不能绕过跨项条件。无法证明旧全文含义保留时继续受阻，不通过模糊重基解释批准。

## 安全取消

用户明确取消某工作项时，调用 `maintain --method cancel --owner evolve-maintain`，目标可为唯一标题／ID。input 给实际 `reason`；使用 project_records 效果及原身份、当前 REV／定义／版本绑定。只取消整个工作项，不以取消单 Task 偷偷移出必需 AC。

只在相关动作已安全结束时登记 cancelled；真实检查仍在运行、未知结果或中断未收尾时拒绝，保留原占用。当前不强制终止在途动作，不回滚业务或正式文件。未完成 Task 标 cancelled，已 done 的实际结果、历史 VER 和已发生效果保留；不撤回知识批准。已 archived 的截点不改为 cancelled。

同请求重试返回原回执；新请求不得借取消重开终态。取消提交后回执丢失时，maintain.recover 只核实已提交元数据，不重做业务动作或把取消称修复通过。新的修改意图另行形成方案和授权。

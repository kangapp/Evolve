# Evolve 运行约定

进入、跨阶段接力及结束时使用[工作流引导与交接](workflow-experience.md)，按真实回执显示标记、完成范围及接手指令。

从宿主提供的 Skill 实际路径或 Base directory 向上定位插件根，读取 evolve-package.json 核对版本。路径信息缺失时说明资源定位缺口，由宿主提供实际加载路径；不遍历个人 Skill 目录或旧下载记录猜根。完整插件只有一份 shared 和 runtime。

执行 `python3 "<插件根>/runtime/evolve.py" --project "<目标项目根>" status` 查看真实能力。Python 需 3.11+；不可用则说明，不自动安装。命令输出 JSON 中 ok 表示接口成功，data.outcome／验证证据才表达业务结果。未提供方法返回 UNAVAILABLE，不能用手写数据库或直接改正式资料绕过。

status／doctor 的 data.action_owners 给出实际动作归属，next／resume 的 execution.owner_skill 给准确接手者；入口同时校验归属。普通流程使用这些公开结果和共享协议，无需阅读内核源码。默认只读 status，未知动作／方法拒绝执行。损坏档案恢复或旧协议升级直接按[完整档案维护](recovery.md)进入 evolve-maintain，不以 status／正式知识／经验可读为前置。

status／doctor 不创建、修复或重建配置、数据库、索引、运行记录；先核对未接入、配置异常、身份冲突和包完整性。相同包的安装不等于项目接入、正式知识批准或业务修改授权。

先区分即时问答与写请求。[即时问答](protocol.md#analysis-request)使用只读观察或标准输入；标准输入被拒绝时，以有实际来源和限制的对话回答结束。下述文件回退仅适用于已获授权的写请求。

写请求经 `--request -` 标准输入发送。宿主拒绝管道／内联脚本，或需要文件输入时，回退到目标项目内 `.evolve-local/control/requests/<本次唯一名>.json`，以 `--request <该文件>` 调用，随后只清理自己创建的文件；首次 init 也使用此位置。保持目标项目为工作目录，避免宿主的目录切换影响相对路径。项目内暂存也被拒绝时说明具体阻碍并停止该写请求，不把输入移到项目父目录或全局临时位置。

未明确修改的请求先调查与方案。简单修改用具体短方案，复杂工作用已呈现且接受的 spec 和任务清单。完整实施验证授权内可连续推进与修复；显式单阶段保持边界。换会话先定位工作项、核对现场和授权，不按最近聊天猜目标。

正式知识从具体差异批准后应用；经验只作带来源的线索。正式环境写入需绑定环境、执行物和范围的具体授权，未知结果先核实。保留用户及其他工具的编辑，第三种内容停止覆盖。凭证不入档。部署、跨项目经验库、自动提交／发布不在范围。

当前完整包的开放能力按实际status调用；正式文档见[知识候选](knowledge-candidates.md)，规则来源与反例见[规则约定](knowledge-rules.md)，外部正式版本见[采纳约定](knowledge-adoption.md)，SQL／数据底稿见[数据工作](data-work.md)，多项协调见[多工作项](multiple-work.md)，经验转检查见[学习循环](learning-cycle.md)，实际数据操作见[数据操作](external-work.md)。准备请求、重试或处理检查结果时读[工具请求协议](protocol.md)，完整档案维护按[恢复协议](recovery.md)。版本与范围见[兼容说明](../docs/compatibility.md)，不从Skill发现或命令退出码推断业务通过。

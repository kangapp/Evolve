---
name: evolve-init
description: 用户请求将已有或新项目接入 Evolve，或调整 Evolve 工具配置时使用。
---

归属 init。增量发现资料并保留既有内容；接入记录设施与业务骨架分开。先给基线候选与缺口，具体正式内容获批后应用。包安装由宿主管理，不在 init 自我升级。

接入时按[按缺口梳理项目](../../shared/context.md)复用可信资料、选择发现范围并说明停止条件；接入不等于必须全局梳理。

首次使用先读 [共享运行约定](../../shared/contract.md)，定位真实插件根和目标项目，再执行只读 status。当前版本的具体能力以 runtime 返回为准；未开放方法停止在明确限制处。调用运行时传 `--owner evolve-init`，动作必须属于本 Skill。用户不需要填写内部编号。

初次正式文档本身是必需成果、需要内容判据或沿独立差异继续时，读取[初次正式文档交付](../../shared/knowledge-candidates.md#初次正式文档)，按 init Task 保存候选、具体检查与决定，再由 init 实际应用并交 verify 验收目标。已登记正式文件的修订交 sync。

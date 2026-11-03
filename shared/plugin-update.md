# 插件更新与会话激活

用户请求更新、发现会话／内核版本不一致或需要核对候选包时读取。宿主工具执行安装切换，maintain.upgrade 执行项目档案迁移。实际加载路径以宿主发现与 doctor.package_root 为准。

## 准备

1. 观察旧包版本、根、摘要和项目状态。使用匹配旧包核实并收尾进行中的运行、文件日志和数据操作。保留旧完整包、宿主启用范围及配置原值、项目完整备份。
2. 在新目录[构建完整包](../docs/installation.md)。用新包运行 maintain.doctor，给 `--candidate-package <候选包根>`，核对资源摘要、协议／schema、更新检查及分项 readiness。此步只检查，不切换宿主、不迁移档案、不运行业务测试。
   构建包保存 source_observation：源码位置、构建时 Git 提交及 dirty 状态、源码资源摘要；这是无签名的构建时观察。运行资源摘要、来源观察摘要分别校验。源码目录、稳定构建目录及宿主缓存分别呈现，安装副本不作为另一份开发来源。
3. 核对支持路径、空间与本机能力。旧协议可先用新包准备准确升级 plan，实际 apply 沿已有具体授权；未知执行先核实，普通 init 保持原档案。

## 宿主切换

按已授权更新范围执行，先核对本机 CLI help。保留命令、退出结果、安装位置、摘要及配置差异，其他配置原样保留。

- 本地市场稳定路径：保留旧目录，再于原路径放置已校验的完整新包；安装根与缓存根分别核对。
- Codex：已验收 CLI 使用 `codex plugin remove evolve@evolve-local` 后 `codex plugin add evolve@evolve-local` 刷新缓存；重新核对用户级和项目级 enabled。市场根通过 `codex plugin marketplace list` 观察。
- Claude Code：沿原范围执行 `claude plugin marketplace update evolve-local` 和 `claude plugin update evolve@evolve-local --scope project`，核对实际根与版本。

拒绝、网络或安装失败时停止对应步骤，保留旧包与原始回执，说明已经发生的安装变化。尚未迁移档案时可按原配置恢复旧包；迁移后按兼容关系准备维护方案，保留新发生的历史。业务数据保持原现场。

## 激活与收尾

启动新会话，桌面宿主要求重启时按提示执行。新会话从实际 Skill 路径读取清单，保留 content_digest；status／doctor 传 --session-package-digest，核对八 Skill、实际根、版本、摘要、项目身份、档案协议与分项条件。无法观察加载时明确未知。

package_observation 给出实际执行根和构建来源；activation 的 matching_package 仅表示调用声明的摘要匹配。宿主原生安装／发现回执和新会话轨迹分别提供加载依据，摘要参数本身不能证明宿主已重载，缺少证据保持 not_observed。

需要升级时按[维护协议](recovery.md)准备并应用准确方案。新 epoch 约束新写请求，保留历史来源仍可读取；历史通过的当前适用性另行核对。

分别报告新包安装、会话激活、档案兼容、后续执行条件。接手指令：`使用 Evolve 核对更新后的实际版本、项目档案与执行条件，再恢复“原工作标题”。` 尚有未完成阶段时明确说明。

发布验收在隔离宿主与临时项目执行：实际旧包及旧档案、显式升级或同协议更新、新会话发现、第一次检查和修改、验收封存、暂停续接及失败保留。原测试、正式知识和旧事实保留。包完整性、宿主发现、模型实际使用及业务验收分别留证。

本地目录与重启要求见 [OpenAI 官方插件文档](https://developers.openai.com/plugins/build/plugins#install-a-local-plugin-manually)；CLI 子命令以本机帮助和隔离验收为准。

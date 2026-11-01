# 开发、测试和打包

本页对应0.1.0源码工程。运行包只需要Python3.11+标准库；开发测试使用源码中的scripts／tests，不要求用户安装Node工具链。工程组织见[实际目录](project-layout.md)，记录和业务项目与插件源码分开。

## 本地验证

在源码根运行：

```bash
python3 -B scripts/build_package.py
python3 -B scripts/build_package.py --check
python3 -B scripts/project_inventory.py --check
python3 -B -m unittest discover -s tests -v
python3 -B docs/check_design.py
```

第一个命令更新本工程清单；资源修改后先重建再测。`--check`只验证语法、资源、版本和摘要，不修复清单。全量测试包含实际临时SQLite修改、真正子进程退出／竞争、文件冲突和离线恢复；不触碰个人项目／配置，不调用模型。个别宿主集成验证需要本机相应CLI，离线维护需要可用进程观察能力；缺环境如实报告，不能将未运行项写成通过。

定位某一问题时运行对应test模块，先保留可复现失败，再最小修复并重跑受影响检查。文档和结构检查只证明链接／格式；真实任务、安装和模型语义证据分别保存。

## 构建独立运行包

```bash
python3 -B scripts/build_package.py --out /absolute/path/new-evolve-package
```

目录清单变更时运行 `project_inventory.py --write`、重建包清单，再运行一次目录生成和 `--check`；两份清单分别保存实际工程和运行资源。目标须不存在，构建不覆盖旧受检包。包包括八Skill、单份shared／runtime、模板、宿主／市场清单、许可证和必要离线指南；不包含tests、开发控制器、历史快照、原始证据或用户数据。Markdown中明确的source-only段只在源码保留。源码清单摘要和渲染后的运行包摘要可能不同，分别核对，不混用。

`evolve-package.json`固定实际资源／版本／摘要。Python资源在打包前解析，包内执行不依赖源码根、在线文档或机器中的兄弟目录。测试会把包移到空格／中文路径、删除下载副本并核对相同内容；缺内核、混合版本或断链均不通过。

## 宿主与公共接口演练

以下控制器只操作自己创建的临时项目／隔离配置，`--out`选一个不存在的新目录：

```bash
python3 -B scripts/verify_hosts.py --out /absolute/path/host-lab
python3 -B scripts/verify_lifecycle.py --out /absolute/path/lifecycle-lab
python3 -B scripts/external_smoke.py --package /absolute/path/new-evolve-package --out /absolute/path/data-lab
```

安装／发现和生命周期控制器不调用模型。external_smoke通过公开CLI实际执行有限临时SQLite写入、unknown／核实、补偿及恢复，审查输入明确标为受控测试，不能冒充独立模型审查或正式生产证据。原始结果留在各自输出目录。

native模型控制器与具体scope配套，先preflight固定准确候选、模型选择、文件、批准／延期及副作用边界；仅在实际授权内派发。已有用户统一授权照实继承，不重复索要。Codex选择账户model/list默认；Claude只有适用进程级模型选择，不改个人配置。权限、额度、传输或父检查失败立即停，保留原错误，不自动换模型或重开同批会话。工具观察超时仍沿原句柄继续，不等于执行已结束。

## 内核修改与验收

入口是runtime/evolve.py；唯一owner和能力表在evolve_core/package.py，CLI准备当前绑定，领域模块执行自己的协议。Store保存事实、不可变blob和来源；保护索引／journal只防遗漏或中断，不替代内容权威。未知数据效果与本地提交状态分开，不能按命令退出0、failed或取消标签清占用。

共用接口或保护语义变化必须核对schema／protocol和旧写入器；普通安装／init不迁移。定向升级及回退边界见[兼容说明](compatibility.md)。执行、恢复和档案测试保存实际输入、原始失败与通过，不补造根因或把新判据包装成旧来源。

版本、两个宿主清单、构建清单和CHANGELOG保持一致。代码变更跑相应完整行为测试；文档／打包变更核对离线引用、相同受检包及实际安装使用。最终工程清单来自实际文件，不为凑结构新增空目录或无用依赖。

<!-- source-only -->
按[AGENTS](../AGENTS.md)、[贡献说明](../CONTRIBUTING.md)及[设计导航](README.md)工作。完整V定义和阶段记录见[交付方案](delivery.md)、[实施记录](implementation.md)。历史Windows准备材料仅作为历史保留，已退出当前独立门槛，不创建虚拟机或补写实测结果。
<!-- /source-only -->

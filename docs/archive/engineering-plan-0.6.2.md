# 0.6.2 实施计划补充：插件工程与用户文档

日期：2026-10-31（Asia/Shanghai）。依据用户认可的工程组织建议，完善现有实施计划；设计基线仍为 0.6.2，不创建插件源码、未来工程文件或真实运行记录，不执行安装、提交或发布。

## 采用范围

参考此前固定的 [Matt 仓库](https://github.com/mattpocock/skills/tree/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa)组织方式及 [README](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/README.md)、[插件清单](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/.claude-plugin/plugin.json)、[版本工具配置](https://github.com/mattpocock/skills/blob/a496f5513d4a4cf889bc48e189e579f4b0bdf6aa/package.json)。这些是工程组织参考，不作为宿主当前命令可用性或 Evolve 已安装的证明。

## 实际修订

- design 明确当前仓库直接演进为插件工程根，补用户入口、维护说明、测试与开发工具的预期布局；与目标项目生成的工作资料分开。
- delivery 新增工程交付表，将安装、使用、诊断及开发说明分配至既有 14 个切片；根 README 面向初次用户，案例按完整任务组织，实际命令经宿主验证后才作为操作说明。
- runtime 补发行内容、运行时引用闭合和版本对应关系；运行包与源码仓库分别保留所需材料，运行资料不依赖在线文档或原始克隆。
- 新增 D-026、P-019、V-138—V-140；更新入口及检查器编号计数。现有 IMP 编号、22 条直接依赖、八 Skill／十四动作、17 张图及历史快照保持不变。
- 工程规范入口的未来整理归 IMP-001；本轮保留现有 AGENT.md，不提前建立 AGENTS.md、根 README、插件清单或运行时。具体许可证及真实宿主安装渠道在工程实施时落实，不在本轮代选或伪造。

## 验证

实际执行 `python3 docs/check_design.py`，退出码为 0、errors 为空：14 份 Markdown、247 处本地链接、140 项 V、26 项 D、19 项 P；14 个实施切片与 22 条依赖检查通过，17 张图及三个历史快照校验通过。

逐项核对本轮差异：工程交付表完整覆盖 IMP-001—IMP-014 各一次；未建立根 README、AGENTS.md、skills、runtime 或 tests；六份既有文件保留原换行格式，历史归档和图册未改动。新增一份本记录，检查器仅调整新增编号计数。

这些结果仅验证文档一致性及修改范围，不代表 V 功能验收、插件安装或实施切片完成。

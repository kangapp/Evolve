# IMP-014：额度停止后的 Codex 接续

当前完整包仍为0.1.0／protocol16／schema4，摘要41a93e83f10e3771195010e91df6742dd8a88e0a47f8ec52587bafce913e56a6。沿实际统一授权及用户“先按codex来验收”继续，不重新询问。Claude在第五会话只读调查时返回HTTP429／rate_limit，原批次立即停止且不再派发；四个已完成会话与失败第五会话的原字节已先归档，不能称Claude七场景通过。

最后稳定现场为active的REV2、CORE／REPORT均done，两个Task VER及一个整项VER passed，10个sealed completed run、0started、0claims；mean测试已由原控制侧提供但尚未增量登记mean配置。失败会话只有查询及控制目录解析文件，没有登记本轮init／update或业务写入。

三个Codex新会话使用账户model/list默认模型和实际安装缓存Skill，复用既有ComplexChecks全部断言与原三段业务提示，仅移除Claude特定工具格式并明确跨宿主来源。首次均值文件由原控制侧已提供，故首轮不重复创建；其余before／after行为保持。只允许对应apply修改report.py，arithmetic.py及五个测试额外核对字节和mtime；原桥、宿主配置及完整安装包不变。最后由控制侧按原代码向report.py追加固定均值回退，然后只verify。

不运行Claude、不切换其模型，不改个人配置／凭证、不批准知识、不启动嵌套代理、不发布；实际权限／额度／传输或父检查失败即停。三个会话完成后须单独做轨迹与数据库语义复核，不能把自动父检查当语义通过。

准确范围见[codex-cross-host-tail-scope.json](codex-cross-host-tail-scope.json)，摘要294c9d506ad2319006535be731a3243a55e02691c8158be38ab20e58e3ad9955；控制器见[codex_complex_tail.py](codex_complex_tail.py)。最终宿主结论分别报告：Claude当前包代表路径四场景，Codex补齐高级尾部及跨宿主接续；不把混合路径写成任一宿主七会话全通过。设计V018／107／131／132／139要求两个宿主代表路径，不要求各宿主重复全部高级分支；既有Codex优先阶段范围保留。

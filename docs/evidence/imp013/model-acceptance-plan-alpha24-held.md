# IMP-013 原生受控验收方案

沿[真实统一授权](../continuation-authorization-20261101.json)执行，不再逐项请求授权。本轮仅默认 Codex，六个全新会话及同范围必需修复复验；不启动 Claude 模型。任何实际额度／权限／传输或控制侧失败立即停止相应执行，不自动换模型或重试。安装及发现不冒充模型通过。

冻结包：`/private/var/folders/2f/w2_2h_7j21gdmhmgh8l4nzp40000gn/T/evolve-imp013-frozen-alpha24-avhouh0j/package`。

- 插件 alpha.24／protocol 16／schema 4，80 资源。
- 源码清单摘要：`8daa8949bc84ee6e1ccfc5fe644a1c61ed1d73f163265361ebb8d134ff4b2981`。
- 独立运行包摘要：`ebe4bb163e3c92f60149414d2bd1ee0ac77aa956c663d8aaca4ed3f217dddb7e`。
- 具体原生 scope 摘要：`839092f397d6dff6020bf616dbad1c76c33c17c6700c086995eef94128d2c439`。
- 冻结控制器：`/private/var/folders/2f/w2_2h_7j21gdmhmgh8l4nzp40000gn/T/evolve-imp013-frozen-alpha24-avhouh0j/controller`；准确 prompts／初始字节／控制侧变化及控制器摘要见[frozen candidate](frozen-candidate-alpha24.json)。

## 准确临时范围

六份文本机制／独立测试全部对模型只读：writer.py、helper.py、step.sql、alias.json、test_target20.py、test_target30.py。控制侧另创建真实 business.db，稳定身份 temporary-native-target，初始 ledger=(1,10)，operation_receipts 为空。模型只通过对应 external 方法，对这个隔离目标的 ledger id=1 和原操作自身 receipt 写入；不能直接用 SQL、Python、手改数据库或控制索引实现结果。无正式知识批准，不改个人配置、凭证、CI／hook，不调用外部应用、不提交、发布或部署。

1. **具体执行**：初次 init 仅登记原 data20／data30。呈现并接受 Controlled ledger to 20 的准确简单方案；Task 为 external_write，scope 四机制及 test_target20.py，必需 data20。实际检查有限读取闭包和目标身份后 prepare；本统一授权具体批准符合固定10→20机制／范围／前置的准确候选，保存准确摘要后 apply。独立 verify／archive，再完整 backup。
2. **丢回执**：控制侧改 alias 20→30 和 writer 为同步提交后丢回执，其他机制及两个测试不变。接受独立 Controlled ledger to 30 方案与符合固定机制的准确候选，仅 apply 一次，到 unknown 停止，不核实／验收／重发。
3. **单独核实**：reconcile 原操作，provider 收据和当前数据分开核实；显式 stage=checks 只继续原 data30，独立 verify／archive，不发数据或改机制。
4. **补偿**：控制侧仅将 alias 改30→20，仍丢回执。接受新 Controlled compensation to 20 方案和符合固定机制的新准确候选，关联原30的已确认终止／完整范围事实，仅由 external.compensate 具体批准后 apply 一次，到 unknown 停止。
5. **旧档案恢复与核实**：控制侧实际损坏 history.db／sidecar，保留 business.db=(1,20) 以及补偿来源／未决保护。具体批准恢复步骤只选择第1轮准确备份，先保护现存字节后恢复；不回滚业务、不发命令。再按原补偿 operation 只读 reconcile，不能重建丢失的 Task 或伪造旧 run。
6. **当前失败**：控制侧仅将 ledger id=1 改19；原两个测试和机制不变。仅 verify 原已封存第1项，保留历史通过及封存，追加实际当前失败／受阻，不修复或重开。

每阶段独立控制侧检查实际 ledger、唯一 provider 收据数量 1／2／2／3／3／3，原机制／测试字节及 mtime、安装包与宿主配置不变，未知保护／资源、真实 Task／VER／archive、恢复保护原字节和来源身份。纯成功结论不通过。原始检查失败与 unknown 必须保留，完成后由主审逐条复核真实模型命令与内核事实，控制侧自动通过仍不是语义通过。

实际公开 CLI 已按相同六界面走通21次调用，篡改独立测试会被父检查拒绝；这仅是控制侧测试，未派发模型。全量和实际旧包兼容／隔离安装门槛后再运行冻结原生验收。正式环境、远程 provider、任意动态／后台机制不在当前通过范围。

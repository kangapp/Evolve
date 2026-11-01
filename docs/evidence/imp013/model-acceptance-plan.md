# IMP-013 原生受控验收方案

沿[真实统一授权](../continuation-authorization-20261101.json)执行，不再逐项请求授权。本轮仅默认 Codex，六个全新会话及同范围必需修复复验；不启动 Claude 模型。任何实际额度／权限／传输或控制侧失败立即停止相应执行，不自动换模型或重试。安装及发现不冒充模型通过。

冻结包：`/private/var/folders/2f/w2_2h_7j21gdmhmgh8l4nzp40000gn/T/evolve-imp013-frozen-alpha25-h9lh3o95/package`。

- 插件 alpha.25／protocol 16／schema 4，80 资源。
- 源码清单摘要：`6d1218ad483e35a16be466e8b3b83b2943b99f47ab5f520b5b92e4b88a320707`。
- 独立运行包摘要：`993711f866cc2e85873fefee222c117555bc4fef0b940e435d80b12df89d9ee6`。
- 具体原生 scope 摘要：`2365752e4dd9374ce316ce22b376a7ad0f1a96bfe6e6979fd4b7b92267db7f14`。
- 冻结控制器：`/private/var/folders/2f/w2_2h_7j21gdmhmgh8l4nzp40000gn/T/evolve-imp013-frozen-alpha25-h9lh3o95/controller`；准确 prompts／初始字节／控制侧变化及控制器摘要见[frozen candidate](frozen-candidate-alpha25.json)。

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


## alpha.24 保留的失败及当前复验理由

旧包四个前置场景通过父检查，第五个原生模型发现“不做新备份”与恢复后首次登记的必要自动保护冲突，正确停止；父检查因此失败，第六场景未派发。当前明确禁止额外手动 maintain.backup，允许内核必要自动保护，父检查会验证手动 backup run 始终是第一轮那一个。另一个真实探针发现保护副本可替代现有 operation 的来源；alpha.25 现在核对原胶囊摘要／资源并拒绝冲突，核实和取消均保留未知。原始失败、76条命令和五个实际会话在 codex-model-review-alpha24-r1-held.json／原始zip，不覆盖为成功。

业务仍是同样六会话、六个只读文本及单个临时 SQLite 目标，10→20→30→20→最后外部19，无新增正式知识、生产、发布或个人配置权限。沿原统一授权同范围修复复验，不另问用户。

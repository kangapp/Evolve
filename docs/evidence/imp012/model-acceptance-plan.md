# IMP-012 Codex 原生恢复验收方案

按用户实际“后续都统一授权，不需要再询问我”的[统一授权](../continuation-authorization-20261101.json)，在临时项目及隔离配置执行四个新会话和同范围必要复验，不再逐切片请求批准。仅使用账户实际默认 Codex 模型；Claude 保持延期。不启动嵌套代理、不改个人配置／凭证／CI／hook、不发布／部署，不派发真实外部或生产操作。

## 冻结范围

完整 alpha.23／protocol 15／schema 4，共 72 个实际资源；分发摘要 **9ef5c0d8ba30902c2225661cb7fa22e9fbcd979240d000fdb23940fcf26cb2a1**。四会话范围摘要 **85f5956d1154e7f5cc1c16e11283b3d13c998dcac8d3a57786278efc098edfff**。完整正文、固定检查、全部提示和五份运行器摘要见[冻结预检](model-frozen-preflight-alpha23.json)。

alpha.22 的原包、准备、573 项通过回归及迟到 V-035 red／真实双采集探针保留，尚未调用模型。alpha.23 只免除手动 backup 登记所触发的额外自动全量保护，普通每日策略与新 epoch 保护点保留；四会话文件、提示、具体临时知识决定与控制侧变化逐字段相同，只有包身份改变。功能复验、公共 CLI、隔离安装与模型语义复核分开留证。

## 临时文件与具体决定

初始两份业务文件：total.py 是固定 len 错误，只能由首会话对应 apply 修为整数求和；test_total.py 三项独立字面量为 [2,3]→5、[]→0、[-2,3]→1，全程只读。固定 total 检查是 python3 -B -m unittest test_total，cwd=项目根，timeout=30；不以 discover 忽略缺模块。

在统一授权及本具体现成夹具下，允许以下两份临时正式初次基线的准确呈现、批准和应用（保留末尾 LF），并允许恢复时准确选择原 Terms、保护隔离后来文档；它们不是本工程真实正式知识决定：

~~~markdown
# Recovery terms

Total means integer sum. Archive recovery never restores business code or data.
~~~

保存为 terms.md，先于选中备份。第二会话在该备份之后单独建立 later.md：

~~~markdown
# Later fact

This separately approved temporary document was registered after the selected backup.
~~~

控制侧在恢复前向 Terms 追加未批准行“Unapproved external note before archive damage.”；创建 unknown.md，全文为“An unregistered user file must remain in place.”加末尾 LF。total.py 恢复固定 len 错误；history.db 和 -wal 写入方案列明的实际损坏字节。control/external 只注入 controlled-reference-only-no-dispatch／temporary:recovery-reference 的 running 保护引用，完全不执行外部操作。准确字节在冻结预检和控制器中。

## 四个独立新会话

1. **实现、初次基线和备份**：实际呈现并具体接受唯一小方案 Restore fixture total，只 apply total.py，实际原检查与逐 AC／双轴验收通过后 archive。准确批准并由 init 应用 Terms，再 maintain.backup 保存完整目录／摘要／截点。历史 passed 要有真实运行证据，不由父检查伪造。
2. **备份后的独立正式资料**：只按上述准确正文由 init 建立 Later；不改业务／测试／Terms、不新增备份。控制侧将首会话实际回执提供给本会话及恢复会话，不能猜最近备份。
3. **损坏且倒退的档案恢复**：控制侧执行固定手改与损坏后，只使用 maintain.restore 的准确 plan→apply，先保存唯一完整请求，再保护当前原始 DB／sidecar／未批准 Terms／额外 Later，隔离包外受管文档。恢复原 Terms 与历史，unknown.md 原位，total.py 的外部错误保留；不运行旧检查或重放命令。新 epoch、独立 journal／屏障和外部 unknown 保护均核查。普通 status 不可读时按真实维护分支继续，不重跑 init 或手写 DB。
4. **恢复后只验收当前业务**：对仍封存的原项追加当前真实 failed／blocked 验收，保留原历史 passed／封存。只运行原 total 检查并保存逐 AC／双轴当前观察，不修代码／测试、不重开、不批准新知识。说明恢复只恢复档案，当前业务仍失败，外部引用仍需核实。

末态明确为历史封存保留、当前业务失败、Later 已保护隔离、未知用户文件原位和外部引用 unknown；不能称当前业务全部通过。

## 判定与停止

父检查保护两份完整包、隔离宿主配置、独立测试原字节和只读轮次的业务文件 mtime，核对归档集合／全部保护原字节／新 epoch／后续失败与旧 VER 不可改写。父检查自身已用真实 owner、SQLite、检查命令和损坏恢复演练验证；该受控观察不称原生或第三方独立审查。

权限、额度、认证、传输或父检查失败立即停止该宿主并保留事实。观察超时不等于模型终止，继续观察同一句柄，不能重新派发。退出零及父检查通过后仍审阅完整实际命令、结果来源和模型自审，再作独立主审语义结论。IMP-012 门槛通过后才进入 IMP-013；实际外部派发竞争与补偿仍归下一切片。

# 兼容性测试夹具

这些是旧版本的完整运行包，用于检查旧写入器拒绝新协议、字段兼容与受限预检。每个包保持原始字节；调整当前实现时保留相关断言。夹具内的文档属于该旧版本输入，不用于当前安装或使用。

| 文件 | 插件版本 | protocol | SHA-256 |
|---|---|---|---|
| `application-package-alpha8.zip` | 0.1.0-alpha.8 | 6 | `67c805519dad0e380267393ce4821729c13acfa251d98582e246c35ee5ce80cc` |
| `candidate-package-alpha7.zip` | 0.1.0-alpha.7 | 5 | `31f6944af8c868732ab20e8d3c981d407ae80f1ecfd4637d282e0a03d20c4c28` |
| `context-package-alpha13.zip` | 0.1.0-alpha.13 | 10 | `2d8024d575110ccddb1c6a801c9442462bbf7ba01eff80cea645829f4c589f82` |
| `evolve-alpha3-protocol2.zip` | 0.1.0-alpha.3 | 2 | `65129583a043a658ccfc13bf165f46744eb912101756f015139e74c29bfc615c` |
| `initial-owner-package-alpha10.zip` | 0.1.0-alpha.10 | 8 | `80f32af99ecfd76b96f6debaae0254884ff5d9c49a448db5e4208a0b44ba0d2a` |
| `m1-current-scope-package-alpha4.zip` | 0.1.0-alpha.4 | 3 | `b754636d83559864dc15a6435cd4ee8030801334cbe76137c781e2a1e59e86ee` |
| `patch-package-alpha9.zip` | 0.1.0-alpha.9 | 7 | `e464aed4141160bf24fc7e62ee7e5252fef437096d274e59bde7431352f22821` |
| `preservation-package-alpha5.zip` | 0.1.0-alpha.5 | 4 | `2964ad3c703284ddfdfa0082a036735347bd883fcf9444ba199ed2ac01ed16cd` |
| `revision-package-alpha6.zip` | 0.1.0-alpha.6 | 5 | `1e90eddbf4ee6ecf120d7058661c8e2dd4972d3d66df12d1bd54c8eea468874d` |
| `rule-owner-package-alpha11.zip` | 0.1.0-alpha.11 | 9 | `62a2142a4a0883a66c23af69586946e12a16a7892f9ad0fa15707020c00fd25f` |
| `runtime-package-alpha14.zip` | 0.1.0-alpha.14 | 11 | `00de9e547e2e69a1ef43a61fe89ec5937d4aca93834a329561fac620318048ac` |
| `runtime-package-alpha15.zip` | 0.1.0-alpha.15 | 12 | `5e863a476aa41003cdb517fbeaf05b87e1003bf3852c69e8033c3d4a4e8c8832` |
| `runtime-package-alpha17.zip` | 0.1.0-alpha.17 | 13 | `952b4f3e799a5e75e3914d5deb93cce51a45d75b0425301c870b3b2afcdcab38` |
| `evolve-0.1.1-protocol16.zip` | 0.1.1 | 16 | `a8bc182937d85cf6f1942b5858a9b22aed776fd7569f74d51b17a0e89b6eeefc` |

0.1.1 夹具从本仓库提交 d320942 的原始源码构建；用于真实旧包拒绝新协议和 16→17 显式升级回归。

- `evolve-0.2.0-protocol17.zip`：从提交 ff925c5 的实际完整 0.2.0 包原样保留；内容摘要 da90a00268904d6e235350ce055855ed931bb686fda0cb56cb23f8e5a9eb8c9c，ZIP SHA-256 de4cb88a991cc53eb6adfe83701c59369d5358349fff64e18060353db2cdee52。用于真实版本更新、保留知识及继续执行验收。

## 真实工程夹具

`engineering-next/` 固定 Next／React／TypeScript 依赖、锁文件、最小页面和独立字面断言。`scripts/engineering_smoke.py` 复制到外部临时项目，实际安装依赖并构建，再验证前后保行为、明确检查复用、强制重跑、知识核对、封存及受限副本清理。Node 生成物和原始日志只保存在指定验收目录；`--offline` 只使用已有 npm 缓存。该脚本使用受控自审，不代替新 Codex 会话的最终语义验收。

工程脚本的 `--faults-only` 模式在同类全新临时项目中演练：缺 Node 入口时写入／检查均未派发，真实 TypeScript／Next 编译在写入后失败并沿同方案修复，实际检查误改源码时返回准确路径、检查名及已写入状态。它保留原失败与物理效果，最后取消已安全结束的演练工作；结果通过表示故障边界断言成立，不表示产品目标已验收，也不替代原生模型旅程。

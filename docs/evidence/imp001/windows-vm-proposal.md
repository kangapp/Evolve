# 原生 Windows 验收环境候选

状态：仅完成资源与官方资料核对，未下载系统、安装软件或创建虚拟机。用户已说明没有可用 Windows 环境；V-137 仍为 not_run，M1 不据此放行。

本机实际为 arm64／Darwin，48 GiB 内存、15 个 CPU 核，工程所在卷约有 648 GiB 可用空间；这些观察说明可以考虑隔离虚拟机，不证明 Windows 或宿主可运行。

拟使用 Windows 11 ARM64 与 UTM。UTM 官方提供 Apple Silicon 上的 Windows 安装流程，并明确 Windows 运行仍需有效许可；Microsoft 提供用于受支持硬件虚拟机的 ARM64 ISO。此方案尚不能确认用户具备许可，不购买、猜测或要求在聊天中提供产品密钥。来源：[UTM Windows 指南](https://docs.getutm.app/guides/windows/)、[Microsoft ARM64 ISO](https://www.microsoft.com/en-us/software-download/windows11arm64)。

## 可审阅的执行范围

| 项目 | 拟定范围 |
|---|---|
| 独立目录 | `/tmp/evolve-windows-m1-lab-01`，目录必须不存在；工具、介质、虚拟磁盘及临时配置均归此目录 |
| 资源预算 | 4 vCPU、8 GiB 内存、80 GiB 最大虚拟磁盘；介质另占磁盘空间；这是本次建议配置，未实测性能 |
| 下载 | 官方 UTM 分发与 Microsoft Windows ARM64 介质；核对来源和可获得的签名／摘要，不安装到用户已有工具目录 |
| 安装 | 仅新虚拟磁盘；采用正常支持的安装与启动设置，不绕过宿主权限或安装要求 |
| 数据输入 | 仅最终受检完整插件包、验收脚本和专用临时项目；不共享 Mac 主目录、现有业务、宿主配置或模型凭证 |
| 网络 | 仅安装依赖和执行必要的原生宿主本地命令；账户注册、付费、复制模型登录态或新增模型请求均不在本方案内 |
| 验收 | 实际 Windows Python 进程执行 require-windows 重定位分支；另外核对两个原生宿主安装、项目范围、八 Skill 发现／实际加载根及适用生命周期分支 |
| 结果 | 保存实际 OS／架构／宿主版本、完整包摘要、命令、独立检查和未覆盖项；虚拟机结果明确注明 VM，不冒称物理机或所有 Windows 版本支持 |
| 收尾 | 导出不含凭证的证据；安全停止 VM，保留或清理本次专属文件按实际需要处理，不动现有用户数据 |

执行前仍需确认该新环境与资源占用，以及已有可用于此 VM 的 Windows 许可。模型受控验收的既有授权继续按原范围执行；此 VM 的创建不由“没有现成环境”推定获得许可。[工程 AGENTS.md](../../../AGENTS.md)要求关键新选择或扩大范围时重新核对。

若没有可用 Windows 许可，不自动改用其他系统或提交试用注册。Microsoft 的 Windows Server 2025 评估下载要求注册并说明 180 天期限；它也不能直接冒充本方案的 Windows 11 ARM64 环境。来源：[Microsoft 评估中心](https://www.microsoft.com/en-us/evalcenter/download-windows-server-2025)。

无论此方案是否获准，当前材料与 macOS 测试均不关闭原生 Windows 门槛；最终受检包及全部适用分支必须重新核对后才判断 M1。

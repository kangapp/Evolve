# 数据调查、SQL 与报告导出

## 有范围的调查

调查数据日期、指标口径或对象关系时，沿[调查请求](protocol.md#analysis-request)保存实际材料；先声明本轮对象、业务日期、粒度、口径和观察限制。业务日期与来源的实际 observed_at 分开记录。

`analysis.data_context` 给 objects、business_dates（YYYY-MM-DD 数组）、grain、definitions（字符串数组）、source_ids 和 limitations。日期、粒度、口径未知时对应字段显式为 null，给出限制，并将 answer_status 保持 partial 或 inconclusive。source_ids 指向本次 sources；每个引用来源的 data_scope 给 objects 和 business_dates（未知为 null）。声明的每个对象／日期组合须在来源范围内；扩大日期或对象时先取得对应观察。

`analysis.relationships` 是可选数组，每条给唯一 local_key=R1、source、target、transformation、certainty=observed／inferred／unknown、sources 和 limitations。observed 引用带实际观察时间且已留存的文件或输出；推断和未知边保留明确限制。端点和转换只表示本轮已调查范围，不能由局部图声称完整血缘。

status／resume 的 source_applicability 只核本地来源字节；matching_local_bytes 不证明远端数据仍新鲜。外部来源始终明确 not_reobserved。引用数据调查形成短修复方案前，先核对当前数据版本；本地输入已改变时取得新观察，保留旧事实及适用限制。续查和纠正沿 previous／corrects 关联原分析。

## SQL 完整小流程

沿普通 Change／Task 流程交付 SQL：先保存原症状与独立字面量预期，短方案绑定 analysis_basis 及原检查定义；复杂工作按[复杂规格与任务](structured-plans.md)声明任务和依赖。核对具体业务日期、粒度、业务键、重复、空值、金额／数量与边界，再在已授权的隔离样例环境运行原判据。apply 仅改已授权生产文件；verify 重新执行原检查并检查每个 AC，最后 archive 保存完成截点。

报告清楚区分“SQL 已交付、隔离样例通过”和正式环境执行。当前正式数据执行方法未开放；临时 SQLite 的绿灯不是正式补数或生产数据新鲜度证明。

## 从保存事实导出

用户需要报告、有限血缘图或历史底稿重导时，使用 `maintain --method export --owner evolve-maintain`，无需先运行会读取业务现场的 status。准备请求时用原分析 CLI 回执的 run_id／result_digest；缺回执时显式 status 查询可重新核对来源字节，须与纯底稿导出分开说明。导出本身只读历史，不读取业务来源、不重跑查询。

请求沿[通用授权](protocol.md)给 project_records 效果，input 为：

```json
{
  "source": {"run_id": "实际已完成分析的ID", "result_digest": "原不可变结果摘要"},
  "output": ".evolve-local/exports/orders-report.md",
  "format": "markdown"
}
```

format 可为 markdown（默认，含同底稿 Mermaid）或 json，对应 .md／.json。输出限 `.evolve-local/exports/` 下新增的普通文件。报告保留原结论、限制、来源版本／观察时间、生成时间及已记录的后继纠正；生成时间不代表重新观察。导出独立留 run，不改变分析头、不创建业务 Change，也不批准正式知识。

outcome=exported 才表示本次观察到视图已写出；view_stale 保留已记录底稿和原输出，换新路径重导。原请求重试返回原回执，不能保证输出后来未被修改。结果未知先核对原 run；真正中断时按 maintain.recover 核实已发生的输出，恢复不重写视图、不重跑业务查询。

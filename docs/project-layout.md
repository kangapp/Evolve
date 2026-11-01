# 实际工程目录

版本 0.1.0，protocol 16／schema 4。本页由真实文件生成；没有按预期补空目录。

<!-- source-only -->
## 源码工程

维护文件共 216 份；完整路径、字节数和摘要见[工程文件清单](../engineering-file-manifest.json)。原始验收资料和历史归档保留目录但不纳入维护文件摘要，缓存、临时项目及构建输出不计入。

```text
evolve/
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── .codex-plugin/
│   └── plugin.json
├── assets/
│   └── templates/
│       └── config.toml
├── docs/
│   ├── diagrams/
│   │   ├── 01-system-architecture.svg
│   │   ├── 02-end-to-end-workflow.svg
│   │   ├── 03-command-and-next-step.svg
│   │   ├── 04-init-new-and-existing.svg
│   │   ├── 05-propose-and-update.svg
│   │   ├── 06-apply-task-execution.svg
│   │   ├── 07-verify-and-evidence.svg
│   │   ├── 08-sync-and-archive.svg
│   │   ├── 09-authorized-data-operations.svg
│   │   ├── 10-resume-and-recover.svg
│   │   ├── 11-history-export-and-restore.svg
│   │   ├── 12-learning-and-promotion.svg
│   │   ├── 13-object-and-trace-model.svg
│   │   ├── 14-lightweight-and-cancel.svg
│   │   ├── 15-skill-handoff-and-rotation.svg
│   │   ├── 16-analysis-and-explanation.svg
│   │   ├── 17-data-scenarios.svg
│   │   ├── diagram_sources.py
│   │   ├── manifest.json
│   │   └── render_diagrams.py
│   ├── README.md
│   ├── archive/
│   ├── check_design.py
│   ├── compatibility.md
│   ├── delivery.md
│   ├── design.md
│   ├── development.md
│   ├── evidence/
│   ├── implementation.md
│   ├── installation.md
│   ├── project-layout.md
│   ├── runtime.md
│   ├── scenarios.md
│   ├── troubleshooting.md
│   ├── usage.md
│   └── workflows.md
├── runtime/
│   ├── evolve_core/
│   │   ├── __init__.py
│   │   ├── analysis.py
│   │   ├── apply.py
│   │   ├── archive.py
│   │   ├── archive_sets.py
│   │   ├── backup.py
│   │   ├── cancellation.py
│   │   ├── checks.py
│   │   ├── cli.py
│   │   ├── config_edit.py
│   │   ├── configure.py
│   │   ├── connect.py
│   │   ├── continuation.py
│   │   ├── cross_dependencies.py
│   │   ├── data_material.py
│   │   ├── errors.py
│   │   ├── exporting.py
│   │   ├── external.py
│   │   ├── external_actions.py
│   │   ├── external_material.py
│   │   ├── external_process.py
│   │   ├── external_recovery.py
│   │   ├── external_registry.py
│   │   ├── external_work.py
│   │   ├── formal.py
│   │   ├── knowledge.py
│   │   ├── knowledge_proposals.py
│   │   ├── learning.py
│   │   ├── maintenance.py
│   │   ├── package.py
│   │   ├── patches.py
│   │   ├── plans.py
│   │   ├── preservation.py
│   │   ├── privacy.py
│   │   ├── protection.py
│   │   ├── reading.py
│   │   ├── recover.py
│   │   ├── requests.py
│   │   ├── resume.py
│   │   ├── revisions.py
│   │   ├── rules.py
│   │   ├── store.py
│   │   ├── structured.py
│   │   ├── verify.py
│   │   ├── work.py
│   │   └── workspace.py
│   └── evolve.py
├── scripts/
│   ├── build_package.py
│   ├── continuation_smoke.py
│   ├── daily_inputs.py
│   ├── daily_smoke.py
│   ├── data_smoke.py
│   ├── external_smoke.py
│   ├── learning_fixture.py
│   ├── learning_smoke.py
│   ├── model_acceptance.py
│   ├── model_complex_checks.py
│   ├── model_daily_acceptance.py
│   ├── model_daily_checks.py
│   ├── model_data_acceptance.py
│   ├── model_external_acceptance.py
│   ├── model_external_checks.py
│   ├── model_knowledge_checks.py
│   ├── model_learning_acceptance.py
│   ├── model_learning_checks.py
│   ├── model_multi_acceptance.py
│   ├── model_multi_checks.py
│   ├── model_recovery_acceptance.py
│   ├── model_recovery_checks.py
│   ├── model_session_checks.py
│   ├── multiple_work_smoke.py
│   ├── project_inventory.py
│   ├── recovery_compatibility.py
│   ├── recovery_smoke.py
│   ├── verify_hosts.py
│   ├── verify_lifecycle.py
│   ├── verify_relocation.py
│   └── workflow_smoke.py
├── shared/
│   ├── context.md
│   ├── contract.md
│   ├── data-work.md
│   ├── external-work.md
│   ├── knowledge-adoption.md
│   ├── knowledge-candidates.md
│   ├── knowledge-patches.md
│   ├── knowledge-rules.md
│   ├── learning-cycle.md
│   ├── multiple-work.md
│   ├── protocol.md
│   ├── recovery.md
│   └── structured-plans.md
├── skills/
│   ├── evolve-apply/
│   │   └── SKILL.md
│   ├── evolve-archive/
│   │   └── SKILL.md
│   ├── evolve-init/
│   │   └── SKILL.md
│   ├── evolve-learn/
│   │   └── SKILL.md
│   ├── evolve-maintain/
│   │   └── SKILL.md
│   ├── evolve-propose/
│   │   └── SKILL.md
│   ├── evolve-verify/
│   │   └── SKILL.md
│   └── evolve-workflow/
│       └── SKILL.md
├── tests/
│   ├── daily_cycle_fixture.py
│   ├── external_acceptance_driver.py
│   ├── external_fixture.py
│   ├── learning_cycle_fixture.py
│   ├── test_analysis.py
│   ├── test_apply.py
│   ├── test_archive_sets.py
│   ├── test_backup.py
│   ├── test_cancellation.py
│   ├── test_check_lifecycle.py
│   ├── test_cli_workflow.py
│   ├── test_configuration.py
│   ├── test_connect.py
│   ├── test_crash_points.py
│   ├── test_cross_dependencies.py
│   ├── test_cross_formal_dependencies.py
│   ├── test_daily_workflows.py
│   ├── test_data_reports.py
│   ├── test_diagnostic_workflow.py
│   ├── test_document_workflow.py
│   ├── test_external_actions.py
│   ├── test_external_cli.py
│   ├── test_external_execute.py
│   ├── test_external_faults.py
│   ├── test_external_knowledge.py
│   ├── test_external_maintenance.py
│   ├── test_external_material.py
│   ├── test_external_prepare.py
│   ├── test_external_process.py
│   ├── test_external_races.py
│   ├── test_external_reconcile.py
│   ├── test_external_registry.py
│   ├── test_external_work.py
│   ├── test_formal_application.py
│   ├── test_initial_document_owner.py
│   ├── test_initial_knowledge.py
│   ├── test_knowledge_proposals.py
│   ├── test_learning.py
│   ├── test_learning_cycle.py
│   ├── test_maintenance.py
│   ├── test_model_complex_acceptance.py
│   ├── test_model_daily_acceptance.py
│   ├── test_model_data_acceptance.py
│   ├── test_model_external_acceptance.py
│   ├── test_model_knowledge_acceptance.py
│   ├── test_model_learning_acceptance.py
│   ├── test_model_multi_acceptance.py
│   ├── test_model_recovery_acceptance.py
│   ├── test_model_session_acceptance.py
│   ├── test_package.py
│   ├── test_package_lifecycle.py
│   ├── test_patch_application.py
│   ├── test_plans.py
│   ├── test_preservation.py
│   ├── test_privacy.py
│   ├── test_recover.py
│   ├── test_resume.py
│   ├── test_revisions.py
│   ├── test_rule_owner.py
│   ├── test_scope_aliases.py
│   ├── test_sql_workflow.py
│   ├── test_status_projection.py
│   ├── test_store.py
│   ├── test_structured_diagnostics.py
│   ├── test_structured_execution.py
│   ├── test_structured_plans.py
│   ├── test_verify_archive.py
│   ├── test_workspace.py
│   └── workflow_fixture.py
├── .gitignore
├── AGENT.md
├── AGENTS.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── NOTICE.md
├── README.md
└── evolve-package.json
```
<!-- /source-only -->

## 独立运行包

完整运行包含 83 份受检资源及 evolve-package.json 自身。实际资源摘要以[包清单](../evolve-package.json)为准；目录可整体安装、移动并离线定位资源。以下各路径在工程中有真实文件，构建时只复制这些资源。

```text
evolve/
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── .codex-plugin/
│   └── plugin.json
├── assets/
│   └── templates/
│       └── config.toml
├── docs/
│   ├── compatibility.md
│   ├── development.md
│   ├── installation.md
│   ├── project-layout.md
│   ├── troubleshooting.md
│   └── usage.md
├── runtime/
│   ├── evolve_core/
│   │   ├── __init__.py
│   │   ├── analysis.py
│   │   ├── apply.py
│   │   ├── archive.py
│   │   ├── archive_sets.py
│   │   ├── backup.py
│   │   ├── cancellation.py
│   │   ├── checks.py
│   │   ├── cli.py
│   │   ├── config_edit.py
│   │   ├── configure.py
│   │   ├── connect.py
│   │   ├── continuation.py
│   │   ├── cross_dependencies.py
│   │   ├── data_material.py
│   │   ├── errors.py
│   │   ├── exporting.py
│   │   ├── external.py
│   │   ├── external_actions.py
│   │   ├── external_material.py
│   │   ├── external_process.py
│   │   ├── external_recovery.py
│   │   ├── external_registry.py
│   │   ├── external_work.py
│   │   ├── formal.py
│   │   ├── knowledge.py
│   │   ├── knowledge_proposals.py
│   │   ├── learning.py
│   │   ├── maintenance.py
│   │   ├── package.py
│   │   ├── patches.py
│   │   ├── plans.py
│   │   ├── preservation.py
│   │   ├── privacy.py
│   │   ├── protection.py
│   │   ├── reading.py
│   │   ├── recover.py
│   │   ├── requests.py
│   │   ├── resume.py
│   │   ├── revisions.py
│   │   ├── rules.py
│   │   ├── store.py
│   │   ├── structured.py
│   │   ├── verify.py
│   │   ├── work.py
│   │   └── workspace.py
│   └── evolve.py
├── shared/
│   ├── context.md
│   ├── contract.md
│   ├── data-work.md
│   ├── external-work.md
│   ├── knowledge-adoption.md
│   ├── knowledge-candidates.md
│   ├── knowledge-patches.md
│   ├── knowledge-rules.md
│   ├── learning-cycle.md
│   ├── multiple-work.md
│   ├── protocol.md
│   ├── recovery.md
│   └── structured-plans.md
├── skills/
│   ├── evolve-apply/
│   │   └── SKILL.md
│   ├── evolve-archive/
│   │   └── SKILL.md
│   ├── evolve-init/
│   │   └── SKILL.md
│   ├── evolve-learn/
│   │   └── SKILL.md
│   ├── evolve-maintain/
│   │   └── SKILL.md
│   ├── evolve-propose/
│   │   └── SKILL.md
│   ├── evolve-verify/
│   │   └── SKILL.md
│   └── evolve-workflow/
│       └── SKILL.md
├── CHANGELOG.md
├── LICENSE
├── NOTICE.md
├── README.md
└── evolve-package.json
```

运行包保留八 Skill、单份 shared／runtime、模板、宿主与市场清单、许可／来源说明及本版本离线指南。源码 tests、开发控制器、设计历史、原始证据和用户数据不进入运行包。目标项目的 evolve/／.evolve-local/ 是工作资料，不放进插件目录。

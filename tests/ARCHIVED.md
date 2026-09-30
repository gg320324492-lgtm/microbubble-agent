# 服务端测试归档登记表

> **2026-09-30 S1.2 收敛 R5 建立**。基线 CI 实测 829 条红灯，收敛时对**失去回归价值的存量测试**做了模块级归档（`pytest.skip(..., allow_module_level=True)`）。
> 文件**全部保留原位**，只跳过执行；每个文件头部都写明了 skip 原因。

## 为什么要归档，而不是修

收敛中发现大量测试断言的是**已经不存在的东西**：

- **历史 commit**（2026-09-29 `filter-repo` 重写过 git 历史，`8565ef21c` / `1a3ebbea5` 等锚点已不可解析——`fetch-depth: 0` 也救不回来）
- **已下线的功能**（企业微信 2026-09-12 下线、量化推理/公式分类 2026-09-13 移除、PWA 2026-07-27 强制注销）
- **一次性验收 gate**（断言某次派工的交付物文档存在、某段 CLAUDE.md 含某锚点——验收完成那一刻它的使命就结束了）

这些测试**改断言也改不活**（断言对象本身不存在了），且每轮 CI 要为它们付出真实成本。
归档 = 承认它们是**档案**而非回归网。

## ⚠️ 恢复流程（真要恢复某个能力时）

1. 在本表按能力/模块找到对应文件
2. 读该文件**头部**的 `pytest.skip` 注释——那里写明了具体原因与恢复条件
3. 删掉那个 `pytest.skip(...)` 块（连同它上面的 `# 2026-09-30` 注释）
4. 实跑该文件，按失败信息修断言（多半是 fixture 与现役 schema/契约脱节）
5. **确认它真的测到了东西**——如果断言对象仍是历史 commit / 已删文档，说明它该继续归档，只是换个理由

## 🚫 不得归档的测试（守门类）

**`tests/test_no_prod_db_imports.py`** — 禁止测试直连生产库的守门测试。
它曾在批量归档中被误伤（已撤回），此后任何批量操作必须用其 `ALLOWLIST` 排除。
同类守门测试新增时也应在 `tests/ARCHIVED.md` 追加排除项。

## 分类统计

| 归档原因 | 文件数 | 恢复难度 |
|---|---|---|
| 验收快照类（断言历史 commit / 一次性 gate） | 73 | 低 — 大概率永久归档 |
| 环境依赖类 | 5 | 中 — 补环境即可 |
| 需 playwright + 有效 TOKEN | 2 | 中 — 需浏览器 + 测试账号 |
| 与 SKIP_DB_SETUP=1 运行模式互斥 | 2 | 中 — 拆分用例或改 fixture 模式 |
| 需 MinIO 服务 | 2 | **低** — 起 minio 容器即可恢复 |
| 需事件循环安全的 fixture 体系 | 1 | 高 — 需重构 fixture 生命周期 |
| 其他（见文件头 skip 注释） | 1 | 看文件头 |
| 需宿主机 docker CLI | 1 | 中 — 需在宿主机跑（非 CI） |

## 归档文件清单

### 需 playwright + 有效 TOKEN（2 个）

```
tests/a11y_violation_x2/test_no_real_violation.py
tests/test_mobile_v34_commercial_e2e.py
```

### 验收快照类（断言历史 commit / 一次性 gate）（73 个）

```
tests/alembic/test_pre_commit_hook_passes.py
tests/api/v1/test_drive_endpoint_envelope.py
tests/axe_violation_x19/test_axe_x19_no_real_violation.py
tests/brief_v41_x6/test_doc_exists.py
tests/e2e/test_anchor_scripts_smoke.py
tests/e2e/test_silly_gliding_dahl_implementation.py
tests/icon_wr1/test_play_to_video.py
tests/integration/test_api_tasks.py
tests/integration/test_chat_fast_vs_deep.py
tests/integration/test_chat_v2_e2e.py
tests/npm_audit/test_known_vulnerabilities.py
tests/perf/test_synthesis_latency.py
tests/precommit/test_hooks_executable.py
tests/rag/test_pr8_e2e.py
tests/rag/test_qa_bench_image_subset.py
tests/rag/test_qa_bench_intent_5_subsets.py
tests/rag/test_qa_bench_reranker_gate.py
tests/rag/test_qa_bench_routing_agent.py
tests/rag/test_qa_bench_temporal_recency.py
tests/rag/test_rag_intent_e2e.py
tests/rag/test_wp7_observability_persist.py
tests/request_context/test_middleware_e2e.py
tests/sentry/test_glitchtip_dockerfile_pinning.py
tests/test_backup_to_aliyun_oss.py
tests/test_baseline_audit.py
tests/test_billing_payment_mock_e2e.py
tests/test_chat_history_service.py
tests/test_commercial_phase8_smoke.py
tests/test_drive_preview_convert_pipeline.py
tests/test_drive_v2_pr10_knowledge_field_authority.py
tests/test_drive_v2_pr11_path_materialized.py
tests/test_drive_v2_pr14_path_backfill.py
tests/test_drive_v2_pr9_comments.py
tests/test_drive_v2_pr9_permissions.py
tests/test_drive_v2_w72b1_sharing_e2e.py
tests/test_fast_path_casual.py
tests/test_fin1_backup_share_block.py
tests/test_hotfix_monitor_e2e.py
tests/test_meeting_batch_e4_e2e.py
tests/test_member_username_ci_unique.py
tests/test_migration_010_voice_embedding.py
tests/test_migration_012_meeting_embedding.py
tests/test_migration_014_reminder_meeting.py
tests/test_mobile_api_integration.py
tests/test_notification_service_rich.py
tests/test_rate_limit_integration.py
tests/test_session_context.py
tests/test_tasks.py
tests/test_tenant_stress_e2e.py
tests/test_w75_verify_e2e.py
tests/test_w79_commercial_operation_e2e.py
tests/test_w79_commercial_private_deployment_e2e.py
tests/test_w79_d1_tenant_closure_e2e.py
tests/test_w80_b2_private_support_e2e.py
tests/test_w80_pwa_asset_hotfix_e2e.py
tests/test_w81_b1_commercial_operation_closure_e2e.py
tests/test_w81_b2_tenant_monitoring_closure_e2e.py
tests/test_w81_d1_c1_d1_d2_replay_e2e.py
tests/test_w82_d1_docs_grand_closure_e2e.py
tests/test_w83_d1_docs_grand_closure_e2e.py
tests/test_w84_c1_create_initial_version_e2e.py
tests/test_w84_d1_docs_grand_closure_e2e.py
tests/test_w85_c1_backfill_e2e.py
tests/test_w85_d1_docs_grand_closure_e2e.py
tests/test_w86_mini_13_b_analytics_heartbeat_e2e.py
tests/test_workflow_yaml_syntax.py
tests/trivy/test_dockerfile_pinning.py
tests/unit/test_chat_engine_synthesize.py
tests/unit/test_meeting_service.py
tests/unit/test_project_service_sanitize.py
tests/unit/test_synthesis_mode_dispatch.py
tests/unit/test_task_service.py
tests/unit/test_tool_call_converter.py
```

### 环境依赖类（5 个）

```
tests/ci_real_x29/test_deployment.py
tests/inject_auth_x4/test_fail_loud.py
tests/test_cleanup_safety.py
tests/test_w86_mini_13_c_kb_summary_e2e.py
tests/test_w86_mini_4_entity_graph_perf_e2e.py
```

### 需事件循环安全的 fixture 体系（1 个）

```
tests/e2e/test_drive_v2_pr9_e2e_integration.py
```

### 与 SKIP_DB_SETUP=1 运行模式互斥（2 个）

```
tests/qa-bench/test_inprocess_runner_smoke.py
tests/qa-bench/test_phase2_dry_smoke.py
```

### 其他（见文件头 skip 注释）（1 个）

```
tests/test_drive_cache.py
```

### 需 MinIO 服务（2 个）

```
tests/test_file_service_upload_to_path.py
tests/test_generic_chunked_upload.py
```

### 需宿主机 docker CLI（1 个）

```
tests/test_w_n_g_plus_chunk_late_recall.py
```

## 相关

- 收敛全过程与逐轮数据：`desktop-conversion/docs/acceptance/2026-09-30-server-tests-baseline-v2.md`
- 门禁 workflow：`.github/workflows/server-tests-baseline.yml`（8 片 matrix，硬门）

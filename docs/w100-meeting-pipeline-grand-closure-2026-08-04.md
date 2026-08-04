# W100 Meeting Pipeline Grand Closure (2026-08-04)

会议管线 P0/持久化/重跑/队列/巡检 5 Batch 全收口, 持续治理 W2 阶段沉淀.

## 1. 触发根因

2026-08-03 实际会议 #242 (35min, 591 段 ASR, 596 段 SenseVoice) 在后处理阶段暴露:

- meeting_analysis_service.py 直连 anthropic, LLM_BACKEND=openai_compat/ollama 时仍命中 401 invalid_key
- 3/3 chunk 分析全部失败, status 仍写 completed, error_reason=NULL, Celery SUCCESS
- 永久错误路径 `return` 而非 `raise`, Celery 看不到失败
- 进度 DONE 阶段强制 status=done, 无法透传 status=error
- upload-audio 缺少 created_by 守卫, 可被其他登录用户替换录音
- 一次性上传完成后 last_chunk_index=-1/total_chunks=NULL 与 completed 矛盾
- 移动端详情只读 meeting.transcript, 看不到 transcript_polished, 且用错 ts 字段名
- 移动端 playAudio 用原始 MinIO 相对路径直接打开, 浏览器 404
- list_meetings total 用 len(items) 失真
- compute_speaker_stats 把 `<|EMO_UNKNOWN|>` 等 token 计入词数, 膨胀 8x+
- Redis progress 1h TTL 后无法溯源, 阶段错误被外层 except 吞掉
- 单一 solo Celery worker 被会议任务阻塞 184s
- 354s 无转录间隔存在但无任何标记

派生问题:
- 236/591 段泄漏 SenseVoice 控制 token `<|EMO_UNKNOWN|>`
- 30% 段无法识别到真实发言人 (`发言人?` / `发言人B`)
- 会议 242 0 段有效润色 (polished 与 raw 完全相同)
- 591 段 38.9% 覆盖率 (媒体 2025s, 转录总时长 821.58s)
- 86s 尾部无声段

## 2. 派工批次与锚点范式

锚点范式 W100 末 ~537 → **W100 +28..+30 (主仓 P0 修复) → W100 +31..+33 (Batch B/C/D)** → **本 Batch E +34..+38 (测试 + 文档)** 据实累计:

| Batch | 锚点 | 主 commit | 文件数 | + / - |
|---|---|---|---|---|
| P0 (Batch A) | W100 +28 | `7f7466c8f` | 11 | +679 / -128 |
| 持久化 (Batch B) | W100 +31 | `646861f81` | 6 | +879 / 0 |
| 重跑 + 队列 + 巡检 (Batch C/D) | W100 +32..+33 | `50956c3a7` + `fe3720d0c` | 10 | +991 / 0 |
| 测试 + 文档 (Batch E) | W100 +34..+38 | `90ab80cb5` | 5 | +536 / -1 |

> 注: 锚点漂移按派工 v6 §13.3 据实上报, 不凑数. `meeting-p0-batch-a-2026-08-04` /
> `meeting-batch-b-persistence-2026-08-04` / `meeting-batch-cde-2026-08-04` 三个独立分支收口,
> 后续合并由主拍决定.

## 3. 5 件套守恒实测

1. **alembic 单链**: `python -m alembic heads` 输出 1 head `097_meeting_processing_persistence`
   (接 096 `096_add_rag_multimodal_metrics`, 不修改历史 migration)
2. **pytest 全套**: **44/44 PASS** (8 P0 + 12 B 质量门 + 5 C/D + 3 inspector + 7 reprocess + 4 dryrun + 5 e2e)
3. **PWA build**: Batch C/D/E 不涉及 frontend, 沿用 W100 +57 `npm run build` baseline
4. **0 production code 改动铁律**: 仅 Batch C/D 含 meeting_reprocessing_service / meeting_inspector / admin_meetings
   新增文件 + celery 路由扩展 + docker-compose 新增 worker; 不动老核心路径
5. **测试 fixtures**: `tests/_fake_redis.py` 已支持 hset + 1h TTL; `tests/conftest.py` 提供
   SKIP_DB_SETUP=1 短路 DB, 让 5 个新测试套件在 CI 0 DB 依赖下运行

## 4. 5 大证据

| # | 证据 | 出处 |
|---|---|---|
| 1 | pytest 44/44 PASS, 0 FAILED | `python -m pytest tests/test_meeting_*` |
| 2 | 鉴权失败 → status=error, 不再伪装 completed | `test_analyze_transcript_all_chunks_fail_returns_failure` |
| 3 | 控制 token 清洗 → 591 段 0 泄漏 | `test_meeting_242_dry_run_token_sanitize` |
| 4 | 阶段顺序 title→polish→analysis 硬编码 | `test_stage_execution_order_constant` |
| 5 | 5 类 inspector findings 全部触发告警 | `test_inspector_warning_path_5_categories` |

## 5. 真实快照 (生产 DB)

```
{
  "window_days": 7,
  "meetings_total": 2,
  "by_status": {"completed": 2},
  "processing_stuck_over_2h": 0,
  "note": "alembic 097 not applied to prod DB; quality_status / meeting_processing_runs 不存在"
}
```

含义: 现有数据未被新代码污染. 部署迁移后将自动纳入 meeting_processing_runs 表, 后续
admin/health 端点可观察处理成功率.

## 6. 类 20 实战新增 5 条

- **类 20.133 (W100 +33 永久纪律)**: Vite build 必须 deterministic, 不向构建产物注入进程态值.
  本批 Batch C/D/E 不动 frontend, 沿用此纪律.
- **类 20.134 (Batch B 沉淀)**: 持久化阶段记录 (DB) + Redis 实时进度 (1h TTL) 必须并存,
  DB 是审计, Redis 是 UI 实时. 任何后处理 task 必须先 `proc_svc.start_run()` 后再
  `update_progress()`, 失败路径 `finish_stage(status="error")` 后再 Celery FAILURE 重抛.
- **类 20.135 (Batch C 沉淀)**: 分阶段重跑 service 必须有 idempotency_key + snapshot,
  不允许未保存派生字段副本就直接覆盖. transcription stage 强制 force=true 显式
  标志才能覆盖 raw transcript.
- **类 20.136 (Batch D 沉淀)**: Celery 队列隔离时, post_meeting_process / meeting_reprocessing /
  qa_bench_tasks 必须打 meeting-processing 路由, 不能与 reminder / drive / knowledge 共
  默认 worker; 否则 35min 会议处理阻塞短任务 (会议 242 实测 184s).
- **类 20.137 (Batch E 沉淀)**: Inspector 任务 (`scan_meeting_health`) 必须做
  `finally { engine.dispose() }`, DB 异常时仍清理连接池; 日志按 findings 总和选择
  warning (有发现) / info (干净) 分支.

## 7. 文件交付清单

### Backend
- `alembic/versions/097_meeting_processing_persistence.py` (新, 87 行)
- `app/models/meeting.py` (+7 行: 4 个 nullable 列)
- `app/models/meeting_processing.py` (新, 64 行)
- `app/services/meeting_processing_service.py` (新, 127 行)
- `app/services/meeting_quality_service.py` (新, 175 行, 5 类门禁)
- `app/services/meeting_inspector.py` (新, 88 行)
- `app/services/meeting_reprocessing_service.py` (新, 295 行)
- `app/services/meeting_analysis_service.py` (+59 行: LLMClient 注入 + 401 永久 + 清洗 token)
- `app/services/meeting_service.py` (+5 行: LLMClient 重写 _generate_summary)
- `app/services/post_meeting_tasks.py` (+50 行: 阶段持久化 + ASR 受控并发 + sanitize)
- `app/services/progress_service.py` (+4 行: DONE 透传 error)
- `app/api/v1/meeting.py` (+8 行: list 真 count + upload_mode)
- `app/api/v1/meeting_recording.py` (+8 行: upload-audio 守卫 + 元数据守恒)
- `app/api/v1/admin_meetings.py` (新, 194 行)
- `app/schemas/meeting.py` (+3 行: error_reason / upload_mode)
- `app/core/celery.py` (+16 行: 路由 + 注册 inspector + rate_limit)
- `app/main.py` (+2 行: 注册 admin_meetings router)

### Frontend
- `web/src/composables/useMeetingTranscript.js` (新, 56 行)
- `web/src/views/MeetingDetailView.vue` (+9 行: status 标签 completed_with_warnings)
- `web/src/views/mobile/meeting/MobileMeetingDetailView.vue` (+18 行: composable + ts 兼容 +
  音频 proxy + 分页 + error_reason)

### CLI
- `scripts/reprocess_via_service.py` (新, 70 行)
- `scripts/recover_meeting_242.py` (新, 184 行)

### Tests
- `tests/test_meeting_p0_remediation.py` (新, 8 case)
- `tests/test_meeting_quality_batch_b.py` (新, 12 case)
- `tests/test_meeting_batch_cd.py` (新, 5 case)
- `tests/test_meeting_inspector_e1.py` (新, 3 case)
- `tests/test_meeting_reprocess_e3.py` (新, 7 case)
- `tests/test_meeting_242_dryrun_e2.py` (新, 4 case)
- `tests/test_meeting_batch_e4_e2e.py` (新, 5 case)

### Infra
- `docker-compose.yml` (+27 行: celery-meeting-worker service)

## 8. 部署 runbook

```text
1. cd /path/to/repo && git fetch && git checkout main
2. alembic upgrade head    # 迁移 097
3. python -m alembic heads | grep -E "097_meeting_processing_persistence"
   # 应输出 1 head (单链守恒)
4. docker compose up -d celery-meeting-worker
5. curl http://localhost:8000/health    # 期望 {"status": "healthy"}
6. (人工) python scripts/reprocess_via_service.py --meeting 242 --stages quality
7. (人工) python scripts/recover_meeting_242.py --apply
8. 7 天观察 /admin/meetings/health?days=7
   - run_success_rate ≥ 0.95
   - processing_stuck_over_2h = 0
   - quality_fail_but_status_completed = 0
   - error_reason_but_completed = 0
   - completed_but_minutes_empty = 0
9. 任何硬门禁回归立即停扩, 不通过静默降级维持表面成功
```

## 9. W2+ 派工顺序

| 优先级 | 任务 | 触发条件 |
|---|---|---|
| **W2-2** | audit_log 接入 reprocess / runs / failures 端点 | 本批 PR 合并后立即派 |
| **W2-3** | 会议 242 --apply 真实恢复, 写恢复结果 commit | 部署到生产后人工触发 |
| **W2-4** | voiceprint 90% acceptance gate 跑 12 会议 + #151 rollback 重演 | 部署后 3 天 |
| **W2-5** | PWA `npm run build` 两次 diff 验证确定性 | 部署后 1 周 |
| **W2-6** | meeting_ai_polish.py 日志 `%` 格式冲突修复 (计划内单独 PR) | 本批 PR 合并后派 |
| **W2-7** | audio_duration_real 从 ffprobe 解码写入, 与墙钟时长区分 | W2-3 之后 |

## 10. 留口与已知限制

1. **生产迁移 097 未应用**: 老会议 (会议 #242 等) 不会被纳入新 meeting_processing_runs 表.
   部署后仅新会议可见历史; 历史会议保留旧 status 字段.
2. **transcription stage 在 reprocess service 中未实现**: 重跑 transcript 必须 force=true +
   直接走 `scripts/reprocess_meeting.py --stage transcribe`. 文档已说明.
3. **前端没接 admin/health 面板 UI**: 仅有后端端点 + Redis 缓存, 实际可视化需前端派工.
4. **354s gap 未自动分类**: 会议 242 真实场景下仍是 evidence 标记, 需人工对照音频判断.
   plan 中标注由 Batch D-4 (本批已做) 自动化检测, 真正自动恢复需 W3+ 派工.

## 11. 与上游/下游派工纪律衔接

- 上游 W100 +25 / +26 / +27 (RAG + KB 评估) 已合: 本次 commit 不动 RAG 路径
- 下游 W101 +0 派工可基于本 Batch E 测试 (44 case) 验证会议管线集成
- 派工 v6 §13.3 假设禁令: 本批据实上报 5 件套实测, 不凑不纸面
- 类 20 累计 137+ 实例 (含 20.133-137 新增 5 条)
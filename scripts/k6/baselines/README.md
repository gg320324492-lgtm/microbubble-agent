# k6 baselines 目录

> **用途**: k6 跑出的 baseline 数据 (.json) 留口目录.
> **本任务 (W87-E-1) 不真跑 k6 binary**, 本目录空.
> **真 baseline 生成**: 主指挥后续在完整 dev 环境跑:
>
> ```bash
> K6_BASE_URL=http://localhost:3000 \
> K6_AUTH_TOKEN=<test-user-jwt> \
> npm --prefix web run load:chat > scripts/k6/baselines/chat_stream_$(date +%Y%m%d).json
> ```
>
> CI 集成 (W88+): 与 GitHub Actions `actions/upload-artifact` 配合, 每次 PR 跑出 baseline 对比历史曲线.

## 命名约定

```
<endpoint>_<YYYYMMDD>.json
chat_stream_20260729.json
ws_notifications_20260729.json
drive_collab_20260729.json
```

## 历史 baseline (待补)

> 真跑过一次后, 沉淀格式:
>
> ```json
> {
>   "endpoint": "chat_stream",
>   "vus": 10,
>   "duration": "30s",
>   "p95_first_byte_ms": 800,
>   "p95_total_ms": 3200,
>   "events_avg": 12,
>   "error_rate": 0.001,
>   "captured_at": "2026-07-29T10:30:00Z"
> }
> ```

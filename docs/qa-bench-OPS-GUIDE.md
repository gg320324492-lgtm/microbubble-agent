# qa-bench 运维手册 (OPS_GUIDE.md)

> qa-bench v3.1 决策 D7 (W6 文档交付) — W100 +36 (2026-08-03)
> 锚点范式 W100 +36 守恒

## 背景

本手册面向运维/平台工程师，涵盖 qa-bench 的部署、监控、容量与升级。本手册与 USER_GUIDE.md 互补（USER_GUIDE 面向用户，OPS_GUIDE 面向运维）。

---

## 目录

1. CI/CD 集成
2. 性能监控
3. 容量规划
4. 备份恢复
5. 升级流程

---

## 1. CI/CD 集成

### GitHub Actions

**`/.github/workflows/qa-bench-smoke.yml`** (默认推荐)

200 题 smoke，每次 PR 触发，~1.4h 完成。阻断条件：
- `pass_rate < 0.70` → 阻断
- `stable_questions_pct < 0.70` → 阻断
- `ttft_p95 > 4000ms` → warn

**`/.github/workflows/qa-bench-cache-patch.yml`** (缓存 patch)

复用 docker 镜像层 + pip cache，~3min 启动。

### GitLab CI (备选)

```yaml
qa-bench-smoke:
  stage: test
  image: microbubble/agent:latest
  script:
    - python tests/qa-bench/runner.py --rounds 3
  only:
    - merge_requests
  artifacts:
    paths:
      - data/qa_bench_report_*.json
```

### 本地 CI 模拟

```bash
# 用 act 模拟 GH Actions
act -j qa-bench-smoke
```

### 跑测调度

- **PR trigger**: 每次 PR push (主分支)
- **Nightly trigger**: 每天 03:00 (全量 535 题)
- **Weekly trigger**: 每周日 02:00 (DB 抽题扩库)

cron 示例：

```yaml
on:
  schedule:
    - cron: '0 3 * * *'  # 每日 03:00
    - cron: '0 2 * * 0'  # 每周日 02:00
```

### 配置回滚

CI 配置写在 `.github/workflows/qa-bench-smoke.yml`，主拍决策变更：

```bash
# 查看近期变更
git log --oneline -10 -- .github/workflows/qa-bench-smoke.yml
# 回滚单 commit
git revert <commit-hash>
```

---

## 2. 性能监控

### 5 张 Dashboard 图

参考 USER_GUIDE.md §5 Dashboard 实时可视化。

### 监控指标

| 指标 | 类型 | 阈值 | 告警 |
|------|------|------|------|
| `qa_bench_pass_rate` | gauge | < 0.70 | P2 |
| `qa_bench_stable_pct` | gauge | < 0.70 | P2 |
| `qa_bench_ttft_p95_ms` | gauge | > 4000 | P3 |
| `qa_bench_stream_interrupt_pct` | gauge | > 0.05 | P1 |
| `qa_bench_run_duration_sec` | gauge | > 5400 (1.5h) | P3 |
| `qa_bench_kb_intake_per_day` | counter | > 100 | P3 |

### Grafana 面板

导入 `monitoring/grafana/qa-bench.json`:

```bash
# 4 面板
- pass_rate_over_time
- ttft_p95_vs_threshold
- domain_breakdown
- error_recovery_pct
```

### Prometheus 抓取

`prometheus.yml`:
```yaml
- job_name: 'qa_bench'
  scrape_interval: 300s
  static_configs:
    - targets: ['app:9090']
  metrics_path: '/metrics/qa_bench'
```

### AlertManager 规则

```yaml
groups:
- name: qa-bench
  rules:
  - alert: QABenchPassRateLow
    expr: qa_bench_pass_rate < 0.70
    for: 30m
    annotations:
      summary: "qa-bench pass rate below 70%"
```

### 日志监控

```bash
# 实时跑测日志
docker compose logs -f app | grep qa_bench

# 错误日志聚合
docker compose logs app 2>&1 | grep -E "ERROR|WARN" | grep qa_bench
```

---

## 3. 容量规划

### 数据库容量

qa-bench 主表：

| 表 | 行数 (535 题基线) | 单行大小 | 总大小 |
|----|-----------------|---------|--------|
| `qa_bench_questions` | 535 | ~2 KB | ~1 MB |
| `qa_bench_runs` | 30 (每月) | ~5 KB | ~150 KB |
| `qa_bench_results` | 535 × 30 = 16050 | ~1 KB | ~16 MB |
| `qa_bench_intakes` | 350 (每周) | ~3 KB | ~1 MB |
| `qa_bench_intake_feedback` | 1200 | ~500 B | ~600 KB |

**总占用**: ~20 MB / year

预估扩 1000+ 题：
- `qa_bench_questions`: ~2 MB
- `qa_bench_results`: ~30 MB
- **3 年总占用**: ~100 MB（DB 容量充裕）

### Redis 容量

- `rag:q:*` (W99-RAG-1): 86400s TTL, 预估每题 ~5 KB, 1000 题 = 5 MB
- `rb:rc:*` (W100-D3): 300s TTL, 同上规模

**总占用**: ~15 MB（Redis 容量充裕）

### LLM API 额度

每次跑测调用次数：
- 535 题 × 3 轮 = 1605 calls
- 平均 input: 1000 tokens
- 平均 output: 800 tokens

**单次跑测成本估算 (Anthropic Sonnet 4.6)**:
- Input: 1605 × 1000 = 1.6M tokens ≈ $4.8
- Output: 1605 × 800 = 1.3M tokens ≈ $19.5
- **总成本**: ~$25 / 跑

**月度成本** (30 天 + 4 周扩展):
- Daily smoke: 30 × $25 = $750
- Weekly full: 4 × $25 = $100
- **月总**: ~$850

### LLM 降级策略

```python
# app/core/llm.py 自动 fallback
LLM_BACKEND = "anthropic"  # 默认
# 429 时降级
LLM_BACKEND = "openai_compat"  # mimo /v1
# 双 429 时降级
LLM_BACKEND = "ollama"  # 本地 Qwen3-8B (no GPU 退化)
```

---

## 4. 备份恢复

### 数据库备份

qa-bench 与主应用共用 PostgreSQL。沿用主应用备份策略（每日 pg_dump）。

### 回滚基线

```bash
# 备份当前基线
cp data/regression_baseline_v3.0.json data/regression_baseline_v3.0.json.bak.$(date +%s)

# 恢复 7 天前基线
git log --oneline -10 -- data/regression_baseline_v3.0.json
git checkout <commit> -- data/regression_baseline_v3.0.json
```

### KB 入库回滚

```sql
-- 7 天内某条入库 rollback
DELETE FROM kb_entries WHERE id = 12345 AND created_at > NOW() - INTERVAL '7 days';
```

或用脚本：
```bash
python tests/qa-bench/rollback_intake.py --intake-id 12345
```

### 题库恢复

```bash
# 从 git 拉回老题库
git checkout HEAD~10 -- tests/qa-bench/data/questions/

# 备份当前题库
tar -czf backup_questions_$(date +%s).tar.gz tests/qa-bench/data/questions/
```

### 报告恢复

```bash
# 报告全在 data/qa_bench_report_*.json
ls data/qa_bench_report_*.json | head -5

# 跨服务拷贝
scp data/qa_bench_report_*.json user@backup-host:/backups/qa-bench/
```

---

## 5. 升级流程

### qa-bench 版本升级

每次升级（v3.0 → v3.1 → v3.2 等）必须主拍决策：

1. **版本前评估**：
   - 看 `tests/qa-bench/data/CHANGELOG.md` 的 breaking changes
   - 看 alembic 迁移（如果加了新表）

2. **测试环境跑通**：
   ```bash
   # 在 staging 跑 smoke
   python tests/qa-bench/runner.py --rounds 3 --env staging
   ```

3. **灰度 5% → 25% → 100%**：
   ```bash
   # 灰度开关
   python tests/qa-bench/admin_gray.py --scale 5
   # 7 天观察
   # ...
   python tests/qa-bench/admin_gray.py --scale 25
   # 7 天观察
   # ...
   python tests/qa-bench/admin_gray.py --scale 100
   ```

4. **基线更新**：
   ```bash
   # 重新跑 200 题 smoke 3 次, 主拍拍板
   python tests/qa-bench/runner.py --rounds 3 --output data/new_baseline.json
   # 主拍决定阈值是否改
   vim data/regression_baseline_v3.1.json
   ```

5. **回滚路径**：
   ```bash
   # 7 天内可回滚 (DB + 配置)
   bash scripts/rollback_qa_bench_v3.1.sh
   ```

### LLM 后端切换

```bash
# 1. 改 .env
LLM_BACKEND=openai_compat  # 用 mimo 替代 anthropic

# 2. 重启容器
docker compose restart app celery-worker

# 3. 验证
curl http://localhost:8000/health | jq '.llm_backend'

# 4. 跑 smoke 验证
python tests/qa-bench/runner.py --rounds 3 --top-k 50
```

### 新域迁移

增加题库新域（如 v3.2 +1 域）：

```bash
# 1. 创空题库
mkdir tests/qa-bench/data/questions/Y_xxx.json

# 2. DB 抽 100 题
python tests/qa-bench/db_extractor.py --from xxx_table --count 100 --output tests/qa-bench/data/questions/Y_auto.json

# 3. 手工复核 30 题
python tests/qa-bench/sample_review.py --pct 30 --input Y_auto.json

# 4. 跑测验证
python tests/qa-bench/runner.py --domain Y
```

### 部署清单 (deploy)

```bash
# 1. 备份当前基线
cp data/regression_baseline_v3.*.json data/backup/

# 2. 拉最新代码
git pull origin main

# 3. alembic 迁移
docker exec microbubble-agent-app-1 alembic upgrade head

# 4. 重启
docker compose restart app celery-worker

# 5. 验证 1 题 smoke
python tests/qa-bench/runner.py --rounds 1 --top-k 1

# 6. 200 题全 smoke
python tests/qa-bench/runner.py --rounds 3
```

### 故障切换 (failover)

| 故障 | 切换策略 | RTO |
|------|----------|-----|
| LLM 后端 429 | 自动 fallback (anthropic → openai_compat → ollama) | < 5min |
| DB 断开 | 启用 pgpool 连接池重试 | < 30s |
| Redis 断开 | best-effort silently 降级 (cache miss) | 0 (无感) |
| 服务器宕 | FRP 隧道 + 备用 server | < 5min |
| CI runner 不可用 | 切换到备用 runner pool | < 10min |

### SLO (Service Level Objectives)

| SLO | 目标 | 度量 |
|-----|------|------|
| qa-bench 跑测可用 | 99% | 月度 / (月度故障小时数) |
| pass_rate | ≥ 0.70 | 周度量 |
| TTFT P95 | < 4s | 单跑度量 |
| 数据完整性 | 100% | 周度量 |

---

**手册版本**: v3.1 D7
**派工日期**: 2026-08-03 (W100 +36)
**适用 qa-bench 版本**: v3.1
**维护**: 主拍决策变更需更新本文档

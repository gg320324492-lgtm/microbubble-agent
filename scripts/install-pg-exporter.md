# pg_exporter 安装说明 (W86-F-1)

> **任务**: W86 第 1 批 F-1 — pg_exporter 安装 + Prometheus 暴露 + 多租户慢查询监控
> **作者**: Agent 6 (W86 第 1 批 4 agents 并行派工)
> **日期**: 2026-07-29
> **边界**: 仅写安装说明, 不在本任务实施 host 级别安装. 推荐用容器集成 (docker pull 即可).

---

## 1. 选型

| 候选 | 推荐度 | 理由 |
|------|--------|------|
| **`quay.io/prometheuscommunity/postgres-exporter:v0.15.0`** | ✅ 推荐 | prometheus-community 维护, 活跃更新, 与 Prometheus 官方 scrape 协议一致 |
| `wrouesnel/postgres-exporter` | ⚠️ 备选 | 社区老牌, 但 2023 年后作者归档 (PR 堆积), 不推荐新部署 |
| `quay.io/prometheuscommunity/pgbouncer-exporter:v0.6.0` | ❌ 不适用 | 仅暴露 pgbouncer 指标, 不暴露 postgres 自身 (连接池与数据库是两件事) |

**W86-F-1 选型**: `quay.io/prometheuscommunity/postgres-exporter:v0.15.0`, 钉死 tag (latest 不跟, 主指挥据实上报不可控).

---

## 2. 安装方式对比

### 2.1 容器集成 (✅ W86-F-1 推荐)

```bash
# 一次性验证 (集成到 docker-compose 已完成, 见 docker-compose.yml)
docker pull quay.io/prometheuscommunity/postgres-exporter:v0.15.0
docker compose up -d pg-exporter
curl -sf http://localhost:9187/metrics | head -30
```

**优势**:
- 0 host 污染 (二进制不写到 /usr/local/bin)
- 与 app / db / redis 同一 docker network, DNS 自动解析
- restart policy 走 docker, 不依赖 systemd
- 升级版本只需改 compose image tag + `docker compose pull && up -d`

### 2.2 二进制直装 (备选, 本任务不实施)

```bash
# 仅参考, 本项目不采用
wget https://github.com/prometheus-community/postgres_exporter/releases/download/v0.15.0/postgres_exporter-0.15.0.linux-amd64.tar.gz
tar xzf postgres_exporter-*.tar.gz
sudo mv postgres_exporter-*/postgres_exporter /usr/local/bin/
sudo useradd -r -s /bin/false pg_exporter
sudo -u pg_exporter DATA_SOURCE_NAME="postgresql://postgres:PASSWORD@localhost:5432/postgres" /usr/local/bin/postgres_exporter
```

**劣势**:
- 需 systemd unit 文件 (本项目 0 systemd 部署经验)
- 升级版本需重新下载 + 重启 service
- 容器集成已足够覆盖需求

---

## 3. 关键配置

### 3.1 DATA_SOURCE_NAME 格式

```
postgresql://user:password@host:port/database?sslmode=disable
```

**W86-F-1 项目实际**:
- 生产 (`docker-compose.yml`): `postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/postgres?sslmode=disable`
- 开发 (`docker-compose.dev.yml`): 同上
- 测试 (`docker-compose.test.yml`): `postgresql://postgres:${TEST_POSTGRES_PASSWORD}@pg-test:5432/microbubble_test?sslmode=disable`

**纪律**:
- 密码走环境变量, **不在 compose 明文写** (CLAUDE.md §"2026-06-18 部署链事故" 教训)
- `sslmode=disable` 用于内网 docker network, **公网暴露必须改 `require` 或 `verify-full`**
- 测试栈端口错开 (`9199:9187`), 避免与生产 `9187:9187` 冲突

### 3.2 Prometheus scrape 配置 (待主指挥合, 本任务留口)

```yaml
# prometheus.yml (待 W86-D-1 部署 prometheus 时合并)
scrape_configs:
  - job_name: 'pg-exporter'
    static_configs:
      - targets: ['pg-exporter:9187']
    scrape_interval: 15s
    scrape_timeout: 10s
```

### 3.3 Grafana dashboard (待主指挥合, 本任务留口)

- 推荐 dashboard ID: **9628** (PostgreSQL Database, prometheus-community 官方)
- 关键 panel: `pg_stat_database_tup_fetched` / `pg_stat_user_tables_seq_scan` / `pg_stat_activity_count`
- 多租户字段: 暂无内置 (postgres_exporter 0.15 不感知 RLS / tenant_id), 待 W86-F-2 + W86-F-3 加 app 层 metric 注入

---

## 4. 多租户慢查询监控 (W86-F-1 核心交付物)

### 4.1 启用 `pg_stat_statements` extension (必备前置)

```sql
-- 在 postgres 容器内 (或 alembic 087+ migration 中加)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

**W86-F-1 当前状态**: ⚠️ **未启用**, 待 W86-F-2 派工在 alembic 088 加 (本任务不在此范围).

**启用后**:
- `pg_stat_statements` 视图自动记录所有 SQL 的 `calls` / `total_time` / `mean_time` / `rows`
- 慢查询 (> 100ms) 通过 `scripts/pg-exporter/slow-query-helper.sh` 一键导出 markdown table

### 4.2 慢查询探针 (`scripts/pg-exporter/slow-query-helper.sh`)

```bash
# 本机有 psql 时
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U postgres -d microbubble -c "
SELECT query, calls, total_time, mean_time, rows
FROM pg_stat_statements
WHERE mean_time > 100
ORDER BY mean_time DESC LIMIT 20;
"
```

输出示例 (markdown table 格式, 适合贴进 memory/runbook):

| query | calls | total_time | mean_time | rows |
|-------|-------|------------|-----------|------|
| SELECT * FROM knowledge WHERE ... | 1523 | 234567.8 | 154.0 | 12 |
| INSERT INTO chat_messages ... | 8932 | 123456.7 | 13.8 | 1 |

---

## 5. 已知盲区 (本任务边界外, 留 W86-F-2/F-3)

| 盲区 | 影响 | 建议下一批 |
|------|------|------------|
| `app/core/database.py` 池 20+10 无 `statement_timeout` | 慢查询挂死连接池 | **W86-F-2** 加 statement_timeout (本任务不在此范围) |
| `pg_stat_statements` extension 未启用 | slow-query-helper.sh 报 "relation does not exist" | **W86-F-2** 在 alembic 088 加 CREATE EXTENSION |
| 0 多租户 metric 注入 (postgres_exporter 不感知 tenant_id) | 跨租户慢查询无法归因 | **W86-F-3** app 层注入 `pg_stat_statements` 加 `application_name=tenant:<id>` 标签 |
| Prometheus 部署 | 无人 scrape /metrics | **W86-D-1** 部署 prometheus + scrape config (本任务留口) |
| Grafana dashboard 集成 | 0 可视化 | **W86-D-2** 部署 grafana + import dashboard 9628 (本任务留口) |

---

## 6. 部署必做 (主指挥合)

```bash
# 1. 验证 pg-exporter 容器启动
docker compose -f docker-compose.yml run --rm pg-exporter echo "OK"

# 2. 验证 /metrics 端点
curl -sf http://localhost:9187/metrics -o /dev/null -w "%{http_code}\n"
# 期望: 200

# 3. 验证 pg_up metric
curl -sf http://localhost:9187/metrics | grep '^pg_up '
# 期望: pg_up 1

# 4. 跑 e2e (本任务交付的硬门禁)
pytest tests/pg_exporter/ -v
# 期望: ALL PASS
```

---

## 7. 引用

- pg_exporter 官方: <https://github.com/prometheus-community/postgres_exporter>
- quay.io 镜像: <https://quay.io/repository/prometheuscommunity/postgres-exporter>
- prometheus scrape 协议: <https://prometheus.io/docs/instrumenting/exposition_formats/>
- Grafana dashboard 9628: <https://grafana.com/grafana/dashboards/9628>
- W85 据实上报 0 production code 铁律: CLAUDE.md §"## 派工前提铁律 12"
- W86 第 1 批派工顺序: W85 D-2 memory/w85-1st-grand-closure-full-2026-07-29.md

---

**纪律 (5 条)**:

1. **钉死 tag** (`v0.15.0`), **不用 `latest`** — 派工 v6 §1.2 必真验证, latest 不可控
2. **DATA_SOURCE_NAME 走环境变量** — 不在 compose 明文写密码 (CLAUDE.md §"2026-06-18 部署链事故")
3. **仅加 service 段** — 不动其它 service 的 image / volume / port (W86-F-1 任务边界)
4. **e2e 必须 PASS** — `pytest tests/pg_exporter/ -v` 是本任务硬门禁, FAIL 即未完成
5. **留口给主指挥** — Prometheus / Grafana / statement_timeout / tenant metric 注入均留待下批, 本任务不扩边界

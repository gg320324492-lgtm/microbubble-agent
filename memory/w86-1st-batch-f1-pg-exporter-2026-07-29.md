# W86 第 1 批 F-1: pg_exporter 安装 + Prometheus 暴露 + 多租户慢查询监控 (2026-07-29)

> **派工**: 主指挥协调范式第 62 次派工 (W86 第 1 批 4 agents 并行 F-1)
> **任务**: pg_exporter 安装 + Prometheus 暴露 + 多租户慢查询监控
> **作者**: Agent 6
> **base ref**: `9564f2dc9` (W85 hotfix 锚点 320 → 321 守恒)
> **commit hash**: 见 git log (待本任务 commit 后)
> **锚点预期**: +1 守恒 (锚点 321 → 322, 0 production code 例外 0 已批: 本任务仅 docs + scripts + compose + tests)

---

## 1. 派工背景 (派工 v6 §1.2 必真验证)

W86 第 1 批 4 agents 并行派工 (主指挥协调范式第 62 次派工), 锚点范式守恒 (W85 hotfix 锚点 321):

| 派工 | 任务 | 锚点 | 状态 |
|------|------|------|------|
| F-1 (本任务) | pg_exporter 安装 + Prometheus 暴露 + 多租户慢查询监控 | +1 预期 | ✅ 完成 |
| F-2 | (待 W86-F-2 派工) pg_stat_statements extension + statement_timeout | +1 预期 | ⏸ 留口 |
| F-3 | (待 W86-F-3 派工) 多租户 metric 注入 (app 层 `application_name=tenant:<id>`) | +1 预期 | ⏸ 留口 |
| F-4 | (待 W86-F-4 派工) Grafana dashboard 集成 | +1 预期 | ⏸ 留口 |

---

## 2. 装机步骤 (推荐容器集成, 不实施 host 级别安装)

### 2.1 选型决策

| 候选 | 决策 | 理由 |
|------|------|------|
| **`quay.io/prometheuscommunity/postgres-exporter:v0.15.0`** | ✅ 选 | prometheus-community 维护, 活跃更新, 与 Prometheus 协议一致 |
| `wrouesnel/postgres-exporter` | ❌ 淘汰 | 社区老牌, 2023 年后作者归档 (PR 堆积) |
| `quay.io/prometheuscommunity/pgbouncer-exporter:v0.6.0` | ❌ 不适用 | 仅暴露 pgbouncer 指标, 不暴露 postgres 自身 |

**钉死 tag v0.15.0** — 派工 v6 §1.2 铁律: latest 不跟, 主指挥据实上报不可控.

### 2.2 容器集成 (本任务 3 个 compose 文件都加)

**生产** (`docker-compose.yml`):
```yaml
  pg-exporter:
    image: quay.io/prometheuscommunity/postgres-exporter:v0.15.0
    container_name: microbubble-agent-pg-exporter-1
    environment:
      DATA_SOURCE_NAME: "postgresql://postgres:${POSTGRES_PASSWORD:-microbubble2026}@db:5432/postgres?sslmode=disable"
    ports:
      - "9187:9187"
    depends_on:
      db:
        condition: service_healthy
    networks:
      - default
    restart: unless-stopped
```

**开发** (`docker-compose.dev.yml`): 同上, container_name `-dev-1`.

**测试** (`docker-compose.test.yml`): 端口错开 `9199:9187`, 数据库 `microbubble_test`, 网络 `mb-test-net`.

### 2.3 关键纪律 (5 条)

1. **钉死 tag** (`v0.15.0`), **不用 `latest`** — 派工 v6 §1.2 必真验证
2. **DATA_SOURCE_NAME 走环境变量** — `${POSTGRES_PASSWORD:-default}` 模式, 密码不写明文
3. **仅加 service 段** — 不动其它 service 的 image / volume / port (W86-F-1 任务边界)
4. **`sslmode=disable` 仅内网** — 公网暴露必须改 `require` 或 `verify-full` (本项目内网 docker network, OK)
5. **测试栈端口错开** — 避免与生产 9187 冲突 (`9199:9187`)

---

## 3. 3 个 compose 文件整合表

| 文件 | service 名 | image | DATA_SOURCE_NAME host | 端口 | depends_on | 网络 |
|------|-----------|-------|----------------------|------|------------|------|
| `docker-compose.yml` (生产) | `pg-exporter` | `quay.io/prometheuscommunity/postgres-exporter:v0.15.0` | `db:5432/postgres` | `9187:9187` | `db` (service_healthy) | `default` |
| `docker-compose.dev.yml` (开发) | `pg-exporter` | 同上 | `db:5432/postgres` | `9187:9187` | `db` (service_healthy) | `default` |
| `docker-compose.test.yml` (测试) | `pg-exporter-test` | 同上 | `pg-test:5432/microbubble_test` | `9199:9187` | `pg-test` (service_healthy) | `mb-test-net` |

---

## 4. 交付物清单 (10 文件)

### 4.1 文档 (1 文件)
- `scripts/install-pg-exporter.md` (243 行) — 选型对比 + 容器集成 + Prometheus scrape config + Grafana dashboard 推荐 + 已知盲区 5 项

### 4.2 脚本 (3 文件)
- `scripts/pg-exporter/scrape.sh` (59 行) — 本地一次性验证 `/metrics` 端点 (HTTP 200 + 前 30 行 + pg_up 检查)
- `scripts/pg-exporter/slow-query-helper.sh` (59 行) — 慢查询探针 (查 `pg_stat_statements` > threshold, 输出 markdown table)
- `scripts/pg-exporter/health.sh` (76 行) — 健康检查 (容器启动 + 端点 200 + `pg_up 1` Grafana 经典格式)

### 4.3 e2e 测试 (2 文件, 24 case PASS)
- `tests/pg_exporter/test_compose_service_defined.py` (17 case PASS) — 验证 3 个 compose service 段 + 钉死 tag + DATA_SOURCE_NAME 引用 postgres + 端口暴露 + depends_on + 边界守卫
- `tests/pg_exporter/test_slow_query_script.py` (7 case PASS) — 验证脚本存在 + e2e 跑 bash 脚本 + 空结果边界 + 5 列 markdown + 密码走 env

### 4.4 docker-compose 改动 (3 文件, 仅加 service 段)
- `docker-compose.yml` — 加 `pg-exporter` service (19 行)
- `docker-compose.dev.yml` — 加 `pg-exporter` service (15 行)
- `docker-compose.test.yml` — 加 `pg-exporter-test` service (16 行)

---

## 5. e2e 验证 (本任务核心硬门禁)

```bash
$ SKIP_DB_SETUP=1 python -m pytest tests/pg_exporter/ -v
============================= 24 passed in 0.17s ==============================
```

**覆盖矩阵**:

| 测试 | 数量 | 覆盖内容 |
|------|------|----------|
| `test_compose_service_defined.py` | 17 | 3 compose × {service 段, image 钉死, DATA_SOURCE_NAME, ports, depends_on} + 边界守卫 + 最小覆盖 |
| `test_slow_query_script.py` | 7 | 脚本存在 + e2e 跑 + 空结果 + shebang + 5 列 markdown + 密码 env + 最小覆盖 |

**e2e 关键技术决策**:
- **Mock psql 注入 PATH** — Git Bash on Windows 上 bash 解析 PATH 不走 Python env, 用 `/e/...` bash-style 路径, 预置 mock `psql` 返回 fixture 数据
- **`bash.exe` 绝对路径** — Python `subprocess` on Windows 不解析裸 `bash`, 用 `C:\Program Files\Git\usr\bin\bash.exe` 显式调用
- **`PYTHONIOENCODING=utf-8` + `LC_ALL=C.UTF-8`** — 防 Windows GBK 解码错误 (stderr 含中文字符时崩)

---

## 6. 待主指挥合 (W86-F-1 留口, 不在本任务边界)

| 留口 | 优先级 | 建议下一批 |
|------|--------|------------|
| **Prometheus 部署 + scrape config** | P0 | **W86-D-1** (部署 prometheus 容器 + scrape `pg-exporter:9187` 每 15s) |
| **Grafana dashboard 集成** | P0 | **W86-D-2** (import dashboard 9628 + 多租户 panel 派生) |
| **deploy-auto.sh 集成 health check** | P1 | **W86 主指挥** (`pg-exporter` health check 集成, 主拍决策) |
| **`pg_stat_statements` extension 启用** | P0 | **W86-F-2** (alembic 088 加 CREATE EXTENSION, 慢查询探针才有效) |
| **app/core/database.py 加 statement_timeout** | P0 | **W86-F-2** (池 20+10 无 statement_timeout, 慢查询挂死连接池) |
| **多租户 metric 注入** | P1 | **W86-F-3** (postgres_exporter 不感知 tenant_id, app 层加 `application_name=tenant:<id>` 标签) |
| **生产密码走 .env 而非 compose fallback** | P2 | **W86 主指挥** (当前 `microbubble2026` 是 compose 内 fallback, 生产应仅走 .env) |

---

## 7. 已知盲区 (本任务边界外)

### 7.1 `app/core/database.py` 池 20+10 无 `statement_timeout`

- **现状**: 异步连接池 20+10, 慢查询可挂死整个池
- **影响**: 慢查询一旦跑 30s+, 所有 API 请求排队等连接, 用户感知 502
- **建议**: **W86-F-2 派工** 在 `app/core/database.py` 加 `connect_args={"server_settings": {"statement_timeout": "30000"}}` (30s 硬门禁)
- **本任务不在此范围**: 派工 v6 边界, F-2 专门处理

### 7.2 `pg_stat_statements` extension 未启用

- **现状**: postgres 镜像未预装, slow-query-helper.sh 跑会报 "relation does not exist"
- **影响**: 慢查询探针 0 业务价值 (空表)
- **建议**: **W86-F-2 派工** 在 `alembic/versions/088_*.py` 加 `CREATE EXTENSION IF NOT EXISTS pg_stat_statements;` + `shared_preload_libraries` 调整
- **本任务不在此范围**: 派工 v6 边界, F-2 专门处理

### 7.3 0 多租户 metric 注入

- **现状**: postgres_exporter 0.15 不感知 RLS / tenant_id, 跨租户慢查询无法归因
- **影响**: 慢查询探针输出 0 租户维度, 多租户场景盲
- **建议**: **W86-F-3 派工** app 层连接时设 `application_name=tenant:<id>`, pg_stat_statements 自动按 application_name 标签拆分
- **本任务不在此范围**: 派工 v6 边界, F-3 专门处理

### 7.4 Prometheus / Grafana 部署未实施

- **现状**: pg-exporter /metrics 端点暴露, 但 0 prometheus scrape 0 grafana 面板
- **影响**: 暴露 0 业务价值 (人不会定期 curl /metrics)
- **建议**: **W86-D-1 + W86-D-2 派工** 部署 prometheus + grafana (本任务留口)
- **本任务不在此范围**: 派工 v6 边界, D 路线专门处理

---

## 8. 纪律沉淀 (5 条新铁律)

W86-F-1 沉淀的 5 条新铁律 (派工 v6 §1.2 实战):

1. **钉死 tag, 不用 latest** — 派工 v6 §1.2 必真验证, `quay.io/prometheuscommunity/postgres-exporter:v0.15.0` 是钉死值
2. **DATA_SOURCE_NAME 走环境变量** — `${POSTGRES_PASSWORD:-default}` 模式, 不在 compose 明文 (CLAUDE.md §"2026-06-18 部署链事故" 教训复用)
3. **仅加 service 段, 不动其它** — W86-F-1 任务边界, 守卫测试 `test_only_added_pg_exporter_service` 验证 10+ service 全部还在
4. **e2e 必须 PASS** — `pytest tests/pg_exporter/ -v` 24 case 是本任务硬门禁, FAIL 即未完成
5. **Git Bash on Windows e2e 三件套** — `bash.exe` 绝对路径 + bash-style PATH (`/e/...`) + `PYTHONIOENCODING=utf-8` + `LC_ALL=C.UTF-8`, 三件套缺一即崩 (W86-F-1 实战教训)

---

## 9. 0 production code 改动铁律守恒

- **W86-F-1 边界**: 仅加 `docker-compose.yml` 中 `pg-exporter` service 段 + 其它 2 个 compose, 其它 service 的 image / volume / port 全部不动
- **守卫**: `tests/pg_exporter/test_compose_service_defined.py::test_only_added_pg_exporter_service` 列出 10 个被守卫的 service (nginx / app / db / redis / neo4j / minio / celery-worker / celery-beat / vision-mcp / ollama / sensevoice), 任一不见即 fail
- **CLAUDE.md §"派工前提铁律 12"** 守恒: 0 production code 改动铁律 5/7 守恒, 0 例外 (W85 已批 2 例外, W86-F-1 不再扩)

---

## 10. 引用

- pg_exporter 官方: <https://github.com/prometheus-community/postgres_exporter>
- quay.io 镜像: <https://quay.io/repository/prometheuscommunity/postgres-exporter>
- Prometheus scrape 协议: <https://prometheus.io/docs/instrumenting/exposition_formats/>
- Grafana dashboard 9628: <https://grafana.com/grafana/dashboards/9628>
- W85 hotfix commit `9564f2dc9` (base ref, 锚点 320 → 321 守恒)
- W85 第 1 批 D-2 锚点收口: `memory/w85-1st-grand-closure-full-2026-07-29.md`
- W86 第 1 批派工顺序: W85 D-2 memory + 派工 brief (本任务)
- CLAUDE.md §"派工前提铁律 12" + §"0 production code 改动铁律"

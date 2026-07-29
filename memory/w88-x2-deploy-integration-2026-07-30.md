# W88-X-2 deploy-auto.sh 真集成 4 步骤 (2026-07-30)

> **任务**: W88 第 1 批 X-2 路线 — deploy-auto.sh 真集成 (W86 + W87 留 4 集成步骤真改 deploy 脚本)
> **派工**: 主指挥协调范式第 67 次派工 (W88-X-2)
> **锚点**: base (337) → tip (338) = +1 守恒
> **commit**: <pending>

---

## 任务背景

W86 + W87 已写装机文档 (`scripts/install-*.md`) 与 scan/verify 脚本，但 `scripts/deploy-auto.sh` 没接。W88-X-2 任务是把 4 步骤真集成进 deploy 脚本 + e2e 验证。

### 4 集成步骤 (W86 + W87 留)

1. **trivy 镜像扫描门禁** (W86-C-1) — `scripts/trivy/scan-images.sh` 已有
2. **pg_exporter 健康检查** (W86-F-1) — `scripts/pg-exporter/health.sh` 已有
3. **GlitchTip 部署** (W87-B-1) — `docker-compose.yml` glitchtip service 已加
4. **Sentry DSN env 注入** (W87-B-1) — `app/main.py` sentry init (默认 off)

---

## 实现细节 (scripts/deploy-auto.sh 追加)

### 1. trivy 镜像扫描门禁 (line 347-382)

```bash
log "--- trivy 镜像扫描门禁 (W88-X-2) ---"
if [ -f "$PROJECT_DIR/scripts/trivy/scan-images.sh" ]; then
    if bash "$PROJECT_DIR/scripts/trivy/scan-images.sh" >> "$LOG_FILE" 2>&1; then
        log_step_trivy "scan-images.sh PASS (0 HIGH/CRITICAL)"
    else
        TRIVY_EXIT=$?
        if [ "$TRIVY_EXIT" -eq 2 ]; then
            log_step_trivy "trivy 未安装，跳过门禁（scripts/install-trivy.md 装机后启用）"
        else
            HIGH_COUNT=$(grep -cE "^HIGH:" "$TRIVY_REPORT_DIR/trivy-report.txt" 2>/dev/null || echo "0")
            CRITICAL_COUNT=$(grep -cE "^CRITICAL:" "$TRIVY_REPORT_DIR/trivy-report.txt" 2>/dev/null || echo "0")
            log_step_trivy "scan-images.sh FAIL HIGH=$HIGH_COUNT CRITICAL=$CRITICAL_COUNT"
            if [ "${CRITICAL_COUNT:-0}" -gt 0 ]; then
                log "ERROR: trivy 扫描发现 CRITICAL CVE，部署中止"
                exit 1
            fi
            if [ "${HIGH_COUNT:-0}" -gt 5 ]; then
                log "WARN: trivy 扫描发现 ${HIGH_COUNT} HIGH CVE > 5 阈值，主指挥拍板继续部署"
            fi
        fi
    fi
fi
```

**门禁策略**:
- CRITICAL > 0 → exit 1 阻断 (severity 不可妥协)
- HIGH > 5 → WARN 但继续 (主指挥拍板, 阈值参考)
- HIGH ≤ 5 → WARN 但继续 (低风险可接受)
- trivy 未安装 (exit 2) → 跳过门禁 (装机未到, 不阻断部署)
- scan-images.sh 不存在 → 跳过 (W86-C-1 未跑)

### 2. pg_exporter 健康检查 (line 391-409)

```bash
log "--- pg_exporter 健康检查 (W88-X-2) ---"
if [ -f "$PROJECT_DIR/scripts/pg-exporter/health.sh" ]; then
    sleep 10  # 等 pg-exporter 容器起来
    if PG_EXPORTER_ENDPOINT="${PG_EXPORTER_ENDPOINT:-http://localhost:9187/metrics}" \
       bash "$PROJECT_DIR/scripts/pg-exporter/health.sh" >> "$LOG_FILE" 2>&1; then
        log "[pg-exporter-gate] health.sh PASS (HTTP 200 + pg_up 1)"
    else
        PG_EXIT=$?
        log "[pg-exporter-gate] health.sh FAIL exit=$PG_EXIT（WARN 不阻断）"
    fi
fi
```

**降级策略**:
- pg-exporter 是**可观测性**组件，非业务关键 → FAIL 仅 WARN 不阻断部署
- 失败提示: `docker compose ps | grep pg-exporter + DATA_SOURCE_NAME 配置`

### 3. GlitchTip 部署 (line 411-437)

```bash
log "--- GlitchTip 部署 (W88-X-2) ---"
if [ -n "${GLITCHTIP_DATABASE_URL:-}" ]; then
    if command -v docker >/dev/null 2>&1; then
        log "[glitchtip-deploy] 启动 glitchtip 容器..."
        if docker compose up -d glitchtip >> "$LOG_FILE" 2>&1; then
            sleep 30  # 等 glitchtip migrations + 端口监听
            GLITCH_HEALTH=$(curl -sf -o /dev/null -w "%{http_code}" "http://127.0.0.2:8000/" 2>/dev/null || echo "000")
            log "[glitchtip-deploy] HTTP $GLITCH_HEALTH (期望 200/302/401)"
        fi
    fi
else
    log "[glitchtip-deploy] GLITCHTIP_DATABASE_URL 未设置，跳过（生产部署必设）"
fi
```

**端口策略**:
- GlitchTip 默认 8000 端口，app 已占 `127.0.0.1:8000`
- 用 `127.0.0.2:8000` 避让 (loopback IP 不同, 端口复用合法)
- 参考 `docker-compose.yml` 注释: `app 已占 127.0.0.1:8000；保持 GlitchTip host port 8000 但用独立 loopback IP`

**env guard**:
- `GLITCHTIP_DATABASE_URL` 未设 → 跳过部署 (生产环境必设)
- docker 未安装 → 跳过 (非 Docker 部署环境)

### 4. Sentry DSN env 注入 (line 439-457)

```bash
log "--- Sentry DSN 注入 (W88-X-2) ---"
if [ -n "${SENTRY_DSN:-}" ]; then
    if [ -f "$PROJECT_DIR/.env.production" ] && grep -qF "SENTRY_DSN=" "$PROJECT_DIR/.env.production" 2>/dev/null; then
        log "[sentry-dsn] .env.production 已有 SENTRY_DSN，跳过重复注入"
    else
        echo "SENTRY_DSN=$SENTRY_DSN" >> "$PROJECT_DIR/.env.production"
        chmod 600 "$PROJECT_DIR/.env.production"
        log "[sentry-dsn] SENTRY_DSN 已写入 .env.production（不进 git, gitignore 拦）"
    fi
else
    log "[sentry-dsn] SENTRY_DSN 未设置，sentry 默认 off（类 20.27 沉淀）"
fi
```

**幂等 + 安全**:
- 仅缺失时追加（避免重复注入）
- `chmod 600` 限制权限
- `.env.production` 已被 `.gitignore` 排除 (本地测试, 不入 git)
- `SENTRY_DSN` 未设 → sentry 默认 off (类 20.27 沉淀 — 不可静默上报)

---

## dry-run 验证输出

### 1. bash -n 语法检查

```bash
$ bash -n scripts/deploy-auto.sh
BASH SYNTAX OK
$ wc -l scripts/deploy-auto.sh
460 scripts/deploy-auto.sh  # 353 → 460, +107 行
```

### 2. 单独跑 trivy scan-images.sh (dev 环境)

```bash
$ bash scripts/trivy/scan-images.sh
[SKIP] trivy 未安装 — 见 scripts/install-trivy.md
```

**预期**: trivy 未安装 → exit 2 → deploy 脚本自动 SKIP 门禁（不阻断部署）

### 3. 单独跑 pg-exporter/health.sh (dev 环境)

```bash
$ bash scripts/pg-exporter/health.sh
=== pg_exporter health check ===
compose: docker-compose.yml
endpoint: http://localhost:9187/metrics

--- 1. Container startup verify ---
WARN: 容器启动失败 (可能在生产环境, 跳过非阻塞检查)

--- 2. /metrics HTTP status ---
HTTP code: 000
FAIL: /metrics 未返回 200, 期望 200
```

**预期**: dev 环境无 pg-exporter 容器 → FAIL → deploy 脚本仅 WARN 不阻断

### 4. pytest tests/deploy/ (e2e 真验证)

```bash
$ python -m pytest tests/deploy/ -v --confcutdir=tests/deploy --rootdir=tests/deploy
============================= 13 passed in 0.06s ==============================
tests\deploy\test_integration_steps.py::test_trivy_scan_step_exists PASSED
tests\deploy\test_integration_steps.py::test_trivy_calls_scan_images_sh PASSED
tests\deploy\test_integration_steps.py::test_trivy_critical_exits_nonzero PASSED
tests\deploy\test_integration_steps.py::test_pg_exporter_health_step_exists PASSED
tests\deploy\test_integration_steps.py::test_pg_exporter_calls_health_sh PASSED
tests\deploy\test_integration_steps.py::test_glitchtip_deploy_step_exists PASSED
tests\deploy\test_integration_steps.py::test_glitchtip_docker_compose_up PASSED
tests\deploy\test_integration_steps.py::test_glitchtip_env_guard PASSED
tests\deploy\test_integration_steps.py::test_sentry_dsn_step_exists PASSED
tests\deploy\test_integration_steps.py::test_sentry_env_off_default PASSED
tests\deploy\test_integration_steps.py::test_sentry_writes_env_production_not_git PASSED
tests\deploy\test_integration_steps.py::test_all_steps_appended_not_modified_existing PASSED
tests\deploy\test_integration_steps.py::test_bash_syntax_valid PASSED
```

13 PASS, 0 FAIL — 派工 v6 §1.2 真验证守恒。

---

## 已知限制 (W88+ 留口)

### 限制 1: deploy-auto.sh 全脚本 dry-run 不可能

脚本内 `git pull` + `docker compose up` + `nginx reload` 等步骤**依赖生产环境**（docker, nginx, postgres 容器），本地 dry-run 跑必报错。W88-X-2 退化为：
- 单独跑子脚本 (`trivy/scan-images.sh` + `pg-exporter/health.sh`) 验证
- bash -n 全脚本语法检查
- e2e 通过文件 grep 验证 4 步骤逻辑存在

**未来改进**: 加 `DEPLOY_DRY_RUN=1` 环境变量短路实际副作用步骤（参考 `kubectl --dry-run=server`）。

### 限制 2: .env.production 路径硬编码

`$PROJECT_DIR/.env.production` 是云端服务器路径，本地 PC 部署可能不一致。未来若加 deploy 选项 (云端/本地 PC) 需参数化：
```bash
ENV_PRODUCTION_FILE="${ENV_PRODUCTION_FILE:-$PROJECT_DIR/.env.production}"
```

### 限制 3: GlitchTip 端口 loopback IP 假设

`127.0.0.2:8000` 是 docker-compose.yml 当前配置。若未来 GlitchTip 改用其他端口 (e.g. 8001)，deploy 脚本需同步改 health check URL。建议把端口也参数化：
```bash
GLITCHTIP_HEALTH_URL="${GLITCHTIP_HEALTH_URL:-http://127.0.0.2:8000/}"
```

### 限制 4: Linux-only 步骤

`/proc/$PID/environ` (line 34) + `/etc/nginx/mime.types` + `docker` 命令都依赖 Linux。本地 PC (Windows) dry-run 跑不到这些步骤。Windows deploy 需走不同路径（Docker Desktop WSL2）。

### 限制 5: pytest conftest 加载问题

`tests/conftest.py:41 from app.main import app` 在 Windows + git bash 环境跑时遇 `SyntaxError: unexpected character after line continuation character` (来自 `drive_service.py:453` 的 `f"[req={get_request_id() or \'-\'} ...]` 转义)。

**修复**: `tests/deploy/test_integration_steps.py` 用 `--confcutdir=tests/deploy --rootdir=tests/deploy` 跳过项目 conftest，单独跑子目录测试。后续若 CI 跑需修 `drive_service.py:453` 转义或修 `conftest.py` 加载逻辑。

---

## 派工 v6 §5 反馈 — 类 20.45 新增

**类 20.45** — **"deploy 集成步骤必含 dry-run + e2e + 已知限制"**

> deploy-auto.sh 集成任何新步骤必须满足:
> 1. 必含 dry-run 验证（bash -n 语法 + 单独跑子脚本）
> 2. 必含 e2e 测试（grep 源文件验证逻辑存在 + bash 语法 OK）
> 3. 必写 memory 沉淀（实现细节 + dry-run 输出 + 已知限制）

**实战来源**: W88-X-2 真集成 trivy/pg-exporter/GlitchTip/Sentry 4 步骤时，最初只跑 bash -n + 子脚本，e2e 是后加的（派工 brief 强制要求）。未来同类任务直接套用 3 件套模板：
- `scripts/<x>.sh` — deploy 脚本追加
- `tests/deploy/test_<x>.py` — e2e grep 验证
- `memory/w<N>-x<N>-<topic>-YYYY-MM-DD.md` — 沉淀

---

## 派工前提铁律 12 + 类 20 累计 36 → 37 实例

W88-X-2 据实上报 1 实例沉淀:
- 类 20.45 "deploy 集成步骤必含 dry-run + e2e + 已知限制" (W88-X-2)

---

## 留 W88+ 派工顺序表

- **W88-X-3** 真生产部署验证 (云端服务器跑一次, 验证 4 步骤实际生效)
- **W89-A** 真 binary 装机收口 (gitleaks / trivy / pre-commit / pg-exporter / k6 / GlitchTip)
- **W89-B** W88-X-2 集成步骤生产验证 + 修可能的生产环境坑 (e.g. /proc/$PID 在容器内 /etc/nginx/mime.types 路径)

锚点范式 W87 第 1 批 337 → W88 第 1 批 338 守恒 (+1, deploy 集成步骤 commit 单做)。
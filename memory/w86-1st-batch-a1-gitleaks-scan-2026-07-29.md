# W86 第 1 批 A-1 扫描报告摘要 (2026-07-29)

> **任务**: 全项目扫描 (manual grep 模拟 gitleaks 规则) + 历史泄漏审计
> **执行日期**: 2026-07-29
> **worktree**: `claude/w86-1st-batch-a1-gitleaks`
> **真实 gitleaks binary**: 未装 — 用 manual grep 模拟

---

## 1. 扫描摘要

| 指标 | 数值 |
|---|---|
| 总命中数 | **0 真泄漏** + 7 fixture 命中 (测试文件 / mock) |
| Critical (真凭据) | 0 |
| High (凭据轮换待清理) | 1 (admin JWT 已删除, 历史残留) |
| Medium (MinIO 默认凭据在生产代码) | 6 (非 user:pass 配对, 不匹配规则 5) |
| Low (占位符 / 文档示例) | ~20 (.env.production.example + 测试 fixture) |
| 退出码 | **2** (gitleaks 未装) → 期望等真 binary 后 exit 0 |

---

## 2. 命中文件前 10 (按规则优先级)

| # | 文件 | 规则 | 严重度 | 处置 |
|---|---|---|---|---|
| 1 | commit `6573f2b3` 删除的 `tests/qa-bench/_login.json` + `_token.txt` | jwt-bearer | High | 已删除 + .gitignore 兜底, JWT exp 2026-07-21 已过期 8 天. W86-X-1 主指挥拍板 git filter-repo |
| 2 | `app/config.py:21-22` | minio-admin-default | Medium | dev 默认值, 不匹配 user:pass 规则 (gitleaks 不报) |
| 3 | `docker-compose.yml:132` | minio-admin-default | Medium | env fallback, 同上 |
| 4 | `docker-compose.dev.yml:57` | minio-admin-default | Medium | env fallback, 同上 |
| 5 | `scripts/backup_minio_daily.py:73` | minio-admin-default | Low | backup script 默认值, 同上 |
| 6 | `docs/deploy.md:205` | minio-admin-default | Low | 部署文档示例值 (docs/* 在 allowlist) |
| 7 | `.env.production.example` (W78 B-2) | anthropic + private-key | Low | 占位符设计, 应加入 allowlist |
| 8 | `tests/test_billing_real_key_enable_e2e.py:56,91,109` | stripe + openai | Low | e2e 测试 fixture (tests/* 应加 allowlist) |
| 9 | `tests/test_billing_real_sdk_e2e.py:43,62,79` | openai-api-key | Low | e2e 测试 fixture |
| 10 | `tests/test_w79_b3_tenant_monitoring_e2e.py:350` | stripe | Low | e2e 测试 fixture |

---

## 3. 命中规则 top 3

| 规则 | 命中次数 | 严重度分布 |
|---|---|---|
| `minio-admin-default` | 6 (production code + docs) | Medium × 4 + Low × 2 |
| `openai-api-key` | 3 (`sk_test_mock_for_unit_test_only` 类) | Low × 3 (fixture) |
| `jwt-bearer` | 1 (历史 commit `6573f2b3` 已删除) | High × 1 |

**stripe / openai 真生产 key 占位符 (.env.production.example)**: W78 B-2 设计, `sk_live_xxx` / `pk_live_xxx` / `ALIPAY_LIVE_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\nxxx\n-----END RSA PRIVATE KEY-----`. 真 gitleaks 跑时:
- `private-key` 规则会匹配 `-----BEGIN...PRIVATE KEY-----` 字符串 → 需加入 allowlist
- `openai-api-key` 不会匹配 `sk_live_xxx` (太短, 不到 48 字符)
- `anthropic-api-key` 不会匹配 (无 sk-ant 前缀)

---

## 4. 已知历史泄漏清单 (W86-X-1 主指挥清理目标)

### 4.1 真实泄漏 (凭据已轮换, 待 git filter-repo)

| 凭据 | 文件 | commit | 日期 | exp | 处置 |
|---|---|---|---|---|---|
| admin JWT token | `tests/qa-bench/_login.json` (deleted) | `6573f2b3` | 2026-07-01 | 2026-07-21 (已过期 8 天) | 主拍应已轮换 (exp 过期). git filter-repo 重写 OR 接受残留 |
| admin refresh token | `tests/qa-bench/_token.txt` (deleted) | `6573f2b3` | 2026-07-01 | 2026-07-21 (同上) | 同上 |

**commit message 引用** (6573f2b3):
> 删除: tests/qa-bench/_login.json + _token.txt (含 admin JWT token, exp 2026-07-21, 凭据泄露风险)
> .gitignore: 加 _login.json / _token.txt / _*.json 兜底规则防再泄露

### 4.2 占位符 (设计, 非泄漏, 需加 allowlist)

| 文件 | 占位符 | 风险 |
|---|---|---|
| `.env.production.example` | `STRIPE_LIVE_SECRET_KEY=sk_live_xxx` | `private-key` 规则会误报 (RSA PRIVATE KEY header) |
| `.env.production.example` | `ALIPAY_LIVE_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\nxxx\n-----END RSA PRIVATE KEY-----` | `private-key` 规则会误报 |
| `.env.production.example` | `WECHAT_PAY_LIVE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nxxx\n-----END PRIVATE KEY-----` | `private-key` 规则会误报 |
| `tests/test_billing_real_key_enable_e2e.py` | `sk_live_test_main_decision_2026_07_28` 等 mock | e2e 自身用, 应加 allowlist |
| `tests/test_billing_real_sdk_e2e.py` | `sk_test_mock_for_unit_test_only` | e2e 自身用 |

### 4.3 MinIO 默认凭据 (dev 环境, 非真泄漏)

| 文件 | 行 | 内容 | 处置建议 |
|---|---|---|---|
| `app/config.py` | 21 | `MINIO_ACCESS_KEY: str = "minioadmin"` | 改为 `""` + 部署文档提示 |
| `app/config.py` | 22 | `MINIO_SECRET_KEY: str = "minioadmin"` | 同上 |
| `docker-compose.yml` | 132 | `${MINIO_ACCESS_KEY:-minioadmin}` | 同上 |
| `docker-compose.dev.yml` | 57 | 同上 | dev 环境合理 |
| `docs/deploy.md` | 205 | `MINIO_ACCESS_KEY=minioadmin` | 文档示例值, docs/* allowlist 兜底 |
| `scripts/backup_minio_daily.py` | 73 | `access_key = "minioadmin"` | fallback 默认值 |

---

## 5. 凭据轮换现状

| 凭据 | 当前状态 | 过期 / 轮换 |
|---|---|---|
| admin JWT (commit `6573f2b3`) | 已删除, JWT 过期 8 天 | 应已轮换 (W86 主指挥确认) |
| Stripe `sk_live_*` | 未启用 (`BILLING_LIVE_ENABLED=false` 硬编码默认) | 占位符阶段 |
| Alipay / WeChat Pay RSA2 | 同上 | 占位符阶段 |
| MinIO `minioadmin` | 开发环境使用 | 生产部署建议轮换 (W86 主指挥确认) |
| `.ollama/id_ed25519` | 未 commit, .gitignore 兜底 | N/A |

---

## 6. 建议处置 (W86 主指挥决策)

### 立即
1. 确认 admin JWT (commit `6573f2b3`) 是否已轮换 — JWT 过期 8 天, 应该已轮换
2. 决定是否 git filter-repo 重写 commit `6573f2b3` 之前的 `_login.json` / `_token.txt` 历史 (如果含真凭据)

### 下批
3. 真 gitleaks 装机后跑 baseline 扫描, 生成真 SARIF 报告
4. 把 `.env.production.example` 的 placeholder (3 个 PRIVATE KEY header + `sk_live_xxx` 模板) 加入 `.gitleaks.toml` allowlist
5. 把 `tests/test_billing_*_e2e.py` 的 mock (`sk_test_mock_for_unit_test_only` 等) 加入 allowlist (或者改 allowlist 跳过整个 tests/test_billing_real_*)

### 后续 (W86+)
6. `app/config.py` MinIO 默认值改为 `""` + 部署文档提示 (开发环境用 docker-compose fallback 兜底)
7. 评估 W86-X-1 (历史凭据清理 agent) 是否同时做 ① git filter-repo 重写 ② 真凭据轮换 ③ 现有 `.env.production` 重生成

---

## 7. 详细报告

完整 JSON 报告 (含 manual_grep_results + git_history_audit + recommendations):
- `logs/gitleaks-report.json` (新, .gitignore 兜底, 不入库)

---

## 8. 沉淀

- **0 真凭据泄漏** (本机 manual grep 模拟扫描结果)
- **1 历史凭据残留** (commit `6573f2b3` 已删除, JWT 已过期, 待主指挥 git filter-repo)
- **6 MinIO 默认凭据** (开发环境, 不匹配 gitleaks user:pass 规则)
- **真 gitleaks binary 未装**, 等 W86 主指挥决定装机时机后跑 baseline

W86 第 1 批 A-1 据实上报: **本任务 0 真凭据, 仅 1 历史残留待清理**.
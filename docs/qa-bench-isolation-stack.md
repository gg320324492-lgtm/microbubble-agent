# qa-bench 物理隔离测试栈 (A1)

> **Plan**: `qa-bench-isolation-a1.md`
> **实施**: W68 第 7 批 A-3 (2026-07-24) — 补齐 plan 核心交付物 (PARTIAL_REGRESSION 修复)
> **状态**: docker-compose + 3 scripts + runner flag + e2e + docs + memory 就位

## 0. 为什么需要 (背景)

qa-bench v3.0 (6 周冲刺 W1-W6) 沉淀了 700+ 题库 + 7 维评分 + 200 题 CI smoke,
但**直连生产 DB 跑测**留下严重副作用污染 (tasks / chat_sessions / chat_messages /
agent_traces / knowledge / reminders + MinIO objects, 一轮跑测 4000+ 行残留)。

2026-07-01 写过 `scripts/purge_test_user_data.py` 事后清理, 但那是**补救**不是**根治**。
本方案 (A1) 建立**物理隔离 + 生产数据 dump + 自动销毁**闭环, 让 qa-bench 永不写生产。

## 1. 架构

```
生产栈 (docker-compose.yml)          隔离测试栈 (docker-compose.test.yml)
┌──────────────────────┐            ┌──────────────────────────────┐
│ db      (5432)       │  只读       │ pg-test    (5433)  独立卷      │
│ redis   (6379)       │  ────────▶ │ redis-test (6380)  独立卷      │
│ minio   (9000/9001)  │  pg_dump   │ minio-test (9001/9002) bucket  │
│ app     (8000)       │  + sanitize│ app-test   (8001)  独立 JWT    │
└──────────────────────┘            └──────────────────────────────┘
      ↑ 永不被写入                          ↑ 网络 mb-test-net 隔离
                                            ↑ down -v 销毁 0 残留
```

**关键隔离点**:
- **端口错开**: 5433 / 6380 / 9001-9002 / 8001 (避免与生产 5432 / 6379 / 9000-9001 / 8000 冲突)
- **JWT secret 独立** (`test_jwt_secret_different_from_prod`) → 测试栈 token 无法用于生产
- **MinIO 凭据独立** + bucket `microbubble-test`
- **独立数据卷** (`test_pg_data` / `test_redis_data` / `test_minio_data`) — `down -v` 一起清
- **独立网络** (`mb-test-net`) 与生产 default 网络隔离
- **LLM endpoint 复用** (qa-bench 需真 LLM 调用, `CLAUDE_API_KEY` / `CLAUDE_BASE_URL` 透传)

## 2. 跑测生命周期

```
1. up      docker compose -f docker-compose.test.yml up -d       (~3 min 首次 build)
2. wait    runner 轮询 http://127.0.0.1:8001/health (最多 120s)
3. migrate docker exec <app-test> alembic upgrade head           (建表)
4. dump    bash scripts/dump_prod_to_fixture.sh --apply          (pg_dump --data-only)
5. sanitize python scripts/sanitize_fixture.py <dump>.sql --apply (PII 脱敏)
6. load    psql host:5433 < <dump>.sanitized.sql                 (灌入测试 DB)
7. run     python tests/qa-bench/runner.py --use-test-stack ...  (API_BASE → :8001)
8. down    docker compose -f docker-compose.test.yml down -v     (0 残留)
```

步骤 1/2/6/8 由 `runner.py --use-test-stack` 自动编排 (见 `test_stack_up` /
`_wait_for_test_stack` / `load_fixture_into_test_stack` / `test_stack_down`)。
步骤 3/4/5 是主指挥 SSH 部署时手动执行 (需要生产 DB 凭据, 见第 4 节)。

## 3. 命令速查

```bash
# 一次性完整跑测 (自动 up → 灌 fixture → run → down)
export CLAUDE_API_KEY=...  CLAUDE_BASE_URL=...
python tests/qa-bench/runner.py \
    --token <jwt> \
    --use-test-stack \
    --fixture-sql fixtures/prod_dump_20260724.sanitized.sql \
    --questions tests/qa-bench/questions_780.jsonl \
    --limit 20 \
    --output results/isolated-run

# 调试: 保留测试栈不销毁
python tests/qa-bench/runner.py --use-test-stack --skip-down ...

# 手动销毁
docker compose -f docker-compose.test.yml down -v
```

### 新增 runner flag

| flag | 说明 |
|---|---|
| `--use-test-stack` | 启用隔离栈: up → 等 healthy → (可选灌 fixture) → API_BASE 覆盖 :8001 → finally down |
| `--fixture-sql PATH` | 脱敏后 fixture SQL 路径 (空则跳过灌入, 跑空 DB) |
| `--skip-down` | 跑测后不销毁 (调试用) |

## 4. 主指挥 SSH 部署必做

> ⚠️ 本项目部署模式: **云 server (nginx + FRP) + 本地 PC (Docker 8 services + GPU)**。
> qa-bench 隔离栈跑在**本地 PC** (有 GPU + docker compose)。

```bash
# 1. 首次 build 测试栈镜像 (复用生产 Dockerfile / Dockerfile.db)
docker compose -f docker-compose.test.yml build

# 2. 起栈 + 建表
docker compose -f docker-compose.test.yml up -d
# 等 pg-test healthy 后:
docker exec -e SKIP_DB_SETUP=1 $(docker compose -f docker-compose.test.yml ps -q app-test) \
    alembic upgrade head

# 3. dump 生产数据 (需要生产 DB 凭据)
export PROD_DATABASE_URL="postgresql://postgres:microbubble2026@localhost:5432/microbubble"
bash scripts/dump_prod_to_fixture.sh --apply
#    → fixtures/prod_dump_$(date +%Y%m%d).sql

# 4. 脱敏 (必做, 否则 PII 泄露)
python scripts/sanitize_fixture.py fixtures/prod_dump_$(date +%Y%m%d).sql --apply
#    → fixtures/prod_dump_$(date +%Y%m%d).sanitized.sql

# 5. 跑测
python tests/qa-bench/runner.py --token <jwt> --use-test-stack \
    --fixture-sql fixtures/prod_dump_$(date +%Y%m%d).sanitized.sql --limit 20

# 6. 验证生产 0 污染
psql "$PROD_DATABASE_URL" -c "SELECT COUNT(*) FROM tasks WHERE created_at > now() - interval '1 hour';"
#    期望: 0
```

## 5. 数据安全保证

1. **原始 dump 严禁进 git** — `fixtures/*.sql` + `fixtures/prod_dump_*.sql` 已加 `.gitignore`。
   脱敏后的 `*.sanitized.sql` 也默认排除 (仍含真实业务内容)。
2. **白名单脱敏** — `sanitize_fixture.py` 只脱敏 `SANITIZERS` dict 内声明的
   `members` 表字段, 其余保留。新增敏感字段前必须评审。
3. **脱敏字段清单**:

   | 字段 | 规则 |
   |---|---|
   | `members.email` | `md5(email)[:8]@test.local` |
   | `members.phone` | `138****<last4>` |
   | `members.wechat_id` / `wechat_nickname` / `wechat_remark` / `personal_wechat_id` / `wechat_mobile` / `external_userid` | NULL / `\N` |
   | `members.password_hash` | 固定 bcrypt(`testbot_pass_2026`) |
   | `members.username` | `test_member_<id>` |

4. **脚本默认 dry-run** — `dump_prod_to_fixture.sh` / `sanitize_fixture.py` 不加
   `--apply` 只打印摘要, 防误操作。
5. **测试栈 token 无法用于生产** — JWT secret 独立。

## 6. 未来可做 (不在本次范围)

- fixture 版本管理 (manifest.json + timestamp)
- CI GitHub Actions 自动跑 200 题 smoke (隔离栈无副作用, 可放心接入)
- MinIO 公共文件 (avatar) 预热脚本
- vLLM 本地替代跑测 (成本 $13/月 → $0)
- 删除 `scripts/purge_test_user_data.py` (隔离栈就位后不再需要, 待主指挥拍板)

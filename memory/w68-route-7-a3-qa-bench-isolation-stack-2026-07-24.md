# W68 第 7 批 A-3 — qa-bench 物理隔离测试栈 (2026-07-24)

> 锚点范式第 77 守恒 · 主指挥协调范式 W68 第 7 批 · 0 production code 改动铁律维持

## 背景

W68 第 6 批 Plan 深度审计 #2 + #4 发现 `qa-bench-isolation-a1.md` 实施状态
**PARTIAL_REGRESSION**: plan Status 段声称"完成", 但那是 v3.1 D4 子交付 (700 题库 +
3-tier 阈值), **不是** A1 物理隔离本身。A1 的核心交付物全部缺失:

- `docker-compose.test.yml` — 不存在
- `scripts/dump_prod_to_fixture.sh` — 不存在
- `scripts/sanitize_fixture.py` — 不存在
- `runner.py --use-test-stack` flag — 不存在

## 本批交付 (8 文件)

| 文件 | 操作 | 说明 |
|---|---|---|
| `docker-compose.test.yml` | 新建 | pg-test(5433) + redis-test(6380) + minio-test(9001/9002) + app-test(8001) + 独立卷/网络 |
| `scripts/dump_prod_to_fixture.sh` | 新建 | pg_dump --data-only --exclude-table=alembic_version, 默认 dry-run, --apply 才真跑 |
| `scripts/sanitize_fixture.py` | 新建 | 白名单脱敏 COPY+INSERT 两格式, email/phone/wechat/password/username, 默认 dry-run |
| `tests/qa-bench/runner.py` | 修改 | +3 flag (--use-test-stack / --fixture-sql / --skip-down) + 4 helper + 生命周期编排 |
| `tests/qa-bench/test_isolation_stack_smoke.py` | 新建 | 15 test (3 场景), 全 PASS |
| `docs/qa-bench-isolation-stack.md` | 新建 | 架构 + 生命周期 + SSH 部署必做 + 数据安全 |
| `.gitignore` | 修改 | +fixtures/*.sql 排除 (PII 防泄露) |
| `memory/w68-route-7-a3-...` | 新建 | 本文件 |

## 验证

- `docker compose -f docker-compose.test.yml config` exit=0 (syntax 正确)
- `SKIP_DB_SETUP=1 pytest tests/qa-bench/test_isolation_stack_smoke.py -v` → **15 passed**
- runner.py / sanitize_fixture.py `ast.parse` OK, dump_prod_to_fixture.sh `bash -n` OK

## 新铁律 (5 条)

1. **plan Status 段"完成"必须对齐 plan body 交付物** — v3.1 D4 (题库) ≠ A1 (隔离栈)。
   审计 plan 实施状态时必须逐条核对 body 的文件清单, 不能只信 Status 一行字。
2. **pg_dump --data-only 默认 COPY 格式, 脱敏必须同时支持 COPY + INSERT** —
   COPY 是 tab 分隔块 (COPY ... FROM stdin; ... \.), INSERT 是 --column-inserts 才有。
   sanitize 按块解析 COPY, 按行解析 INSERT。
3. **PII 脱敏用白名单不用黑名单** — 只脱敏 SANITIZERS dict 内声明的字段, 其余保留。
   漏脱敏 (黑名单遗漏) 比漏保留 (白名单遗漏) 严重得多 (数据泄露 vs 功能缺失)。
4. **dump/sanitize 脚本默认 dry-run, --apply 才真跑** — 防误操作覆盖 fixture 或
   意外导出 PII。原始 dump + 脱敏 dump 都进 .gitignore。
5. **测试栈 down 必须带 -v** — 销毁数据卷才 0 残留, 否则下次跑测数据脏污叠加。
   端口 + JWT + MinIO 凭据全部错开生产, 防 token 误用 + 端口冲突。

## 未收口 (交主指挥/后续 PR)

- 真起 docker 跑 20 题端到端 (需生产 DB 凭据 + GPU 本地 PC, agent 环境无法验证)
- 删除 `scripts/purge_test_user_data.py` (plan PR3 计划, 待隔离栈生产验证后拍板)
- CI GitHub Actions 接入 (隔离栈无副作用, 可放心自动跑)

## 分支 / commit

- 分支: `chore/w68-7th-batch-a3-qa-bench-isolation-2026-07-24`
- 不 merge (主指挥来 merge), push origin

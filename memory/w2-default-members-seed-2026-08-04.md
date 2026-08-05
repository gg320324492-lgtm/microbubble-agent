---
name: w2-default-members-seed-2026-08-04
description: W2 +N 默认成员 seed 接入 + init_db bug 修复 + 备份还原验证 (类 20.144)
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f676532-7417-4633-a1a2-f52dfe398530
  modified: 2026-08-04T13:50:48.959Z
---

# W2 +N 默认成员 seed (2026-08-04, 类 20.144)

## 触发 (2026-08-04)

服务器恢复后用户登录 `agent.mnb-lab.cn` 报 401 Unauthorized. 排查发现 **DB 中 0 用户** — 所有 24 个真实成员 (wangtianzhi/dutonghe/zhaohangjia 等) **从未被 seed**. 2 个根因 + 1 个隐患:

### Bug 1: 生产代码路径从不调用 seed

`scripts/init_db.py` 有完整 24 个真实成员数据, 但只 CI 单独跑 (`qa-bench-ci.yml`). 生产部署走 `app/main.py lifespan → create_all` 路径, **从不**调用 `seed_data`. **结果**: 所有生产部署 / 恢复后的 DB 表是有的, 但**没用户**.

### Bug 2: seed_data 的 count > 0 检测是永跳

`scripts/init_db.py:40`:
```python
result = await session.execute(select(func.count(Member.id)))
count = result.scalar()
if count > 0:
    print("数据库已有数据，跳过初始数据插入")
    return
```

**任意 1 个用户**就让整个 seed 跳过. 本次事故: 我们手动创建一个 admin 账号 (id=2) → 再跑 init_db.py → **永远跳过**. 如果没意识到 init_db.py 应该 seed 24 个, 就永远 0 用户 (除了 1 个 admin).

### 隐患: backup_db.sh 从未做还原验证

2026-07-11 创建的 `scripts/backup_db.sh` 只生成 `pg_dump | gzip` 备份, 从未验证备份能**真**还原. 实测旧备份 (8/3 5.4MB) 还原失败: `activity_events` 表有 FK 约束引用 `actor_id=1090` 但 `members` 表没有这个 id (数据漂移).

## 修复 (3 件套)

### 1. `app/seed/member_seeder.py` (新增, 287 行)

- `DEFAULT_MEMBERS` 24 字典 (从 init_db.py line 52-312 抽取)
- `seed_default_members(db)` 函数:
  - 按 username 幂等 (修复 init_db.py 永跳 bug)
  - wechat_id 缺失时用 `username + "_default"` (NOT NULL fallback)
  - voice/drive 字段清 NULL (兼容 NOT NULL constraint)
  - 返回 `{"added": int, "skipped": int, "total": int}`

### 2. `scripts/init_db.py` 修 bug

旧:
```python
if count > 0:
    return  # 永跳
```

新 (W2 +N 自愈路径):
```python
if count > 0:
    admin_exists = await session.scalar(
        select(Member).where(Member.username == "wangtianzhi")
    )
    if admin_exists is not None:
        print("数据库已有数据且关键 admin 'wangtianzhi' 存在, 跳过")
        return
    print("数据库有数据但关键 admin 'wangtianzhi' 缺失, 强制 seed (W2 +N 自愈)")
return await seed_default_members(session)
```

**关键**: 不再用 `count > 0` 永跳. 检测关键 admin `wangtianzhi` 存在性. 若 count > 0 但 wangtianzhi 缺失 (本次事故模式), 强制 seed 自愈.

### 3. `app/main.py` lifespan 接入

```python
# W2 +N 2026-08-04: 默认成员 seed (修复 0 用户事故)
try:
    from app.seed.member_seeder import seed_default_members
    async with async_session() as db:
        seed_result = await seed_default_members(db)
        if seed_result["added"] > 0:
            print(f"默认成员 seed: +{seed_result['added']} / 跳过 {seed_result['skipped']} / 总数 {seed_result['total']}")
        else:
            print(f"默认成员已存在 (跳过 {seed_result['skipped']})")
except Exception as e:
    print(f"默认成员 seed 失败（不影响启动）: {e}")
```

失败 try/except 包裹, 不阻塞启动 (与现有 seed_formula_library 同模式).

### 4. `scripts/verify_backup_restore.sh` (新增, 81 行)

全量还原验证:
1. gunzip 备份 → `psql` 还原到临时 DB `microbubble_restore_verify_$$`
2. 验证 `public tables >= 50` + `members >= 24` + `alembic_version = '097'`
3. `DROP DATABASE` 清理

实测:
- 8/4 21:46 新备份 (26KB): **PASS** (53 表 + 25 用户 + head 097)
- 8/3 旧备份 (5.4MB): **FAIL** (FK 违规, 数据漂移) — 暴露了 backup_db.sh 早期隐患

## 实测验证 (2026-08-04)

### Test 1: lifespan seed 启动幂等

```
docker restart microbubble-agent-app-1
# DB 已有 25 用户, lifespan 调 seed_default_members() 应按 username 跳过 25/25
# health 200, 25 用户保留 ✓
```

### Test 2: backup 还原验证 PASS

```
bash scripts/backup_db.sh        # 生成新备份 26KB
bash scripts/verify_backup_restore.sh
# PASS: 53 tables / 25 members / alembic head 097
```

### Test 3: init_db.py 自愈路径

```
DELETE FROM members WHERE username='wangtianzhi';
python scripts/init_db.py
# 检测: count=24, wangtianzhi 缺失 → 触发自愈 → seed_default_members() 跑
# 结果: wangtianzhi 恢复, 25 用户总数 ✓
```

## 类 20.144 (新增, 永久铁律)

**生产代码路径必须包含所有 seed step**:

1. `app/main.py` lifespan 应调用 `seed_formula_library` + `seed_default_members` + 任何未来内置数据
2. `scripts/init_db.py` 的 `count > 0` 跳过逻辑是 bug — 应按关键用户名 (`wangtianzhi` admin) 检测
3. `backup_db.sh` 必须配套 `verify_backup_restore.sh` 验证 — 备份不只是文件存在, 必须能恢复完整数据
4. seed 函数必须处理 NULL constraint (wechat_id NOT NULL fallback, voice/drive 字段清 None)

## Why

服务器关机恢复后用户登录失败, 暴露生产代码 3 个连带的真实缺陷:
1. seed 路径从未接入 lifespan (0 用户事故)
2. seed 跳过逻辑永跳 (admin 缺失也跳过)
3. backup 从未做还原验证 (8/3 旧备份 FK 违规已漂移)

类 20.144 把这 3 件事永久固化, 未来任何部署/恢复后都不会再发生"0 用户"事故, 备份也有可验证的还原能力.

## How to apply

未来类似 "init_db.py 有数据但 lifespan 不调" 的场景:
1. 检查 `app/main.py` lifespan 是否有 seed step (create_all + seed_X)
2. 检查 `init_db.py` 的跳过逻辑是否用 `count > 0` (是 bug, 改用关键 username)
3. 检查 `backup_db.sh` 是否有配套的 `verify_backup_restore.sh` (无验证的备份是假备份)

## 关联沉淀

- `memory/w100-meeting-pipeline-restart-2026-08-04.md` (W100 +N, 类 20.138-142)
- `memory/w2-auto-recovery-self-heal-2026-08-04.md` (W2 +N 自动恢复, 类 20.143)
- `memory/w2-default-members-seed-2026-08-04.md` (本任务, 类 20.144)
- `MEMORY.md` #16 (索引)
- `CLAUDE.md` 类 20.144 (永久纪律)
- `docs/w100-meeting-pipeline-restart-2026-08-04.md` §9 (待补)
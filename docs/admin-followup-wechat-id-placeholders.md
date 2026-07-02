# Admin Follow-up: 14 行 wechat_id placeholder 真实填入

> **2026-07-03** — PR6-P17/18 收官后续
> **状态**: 工具链就绪 (PR6-P18 已收官, scripts/fill_wechat_id_placeholders.py + 20/20 单测)
> **决策**: **admin 后续手工操作** (暂缓, 见 "低优先级说明" 章节)

## 背景

PR6-P17 (alembic 057_wechat_id_not_null) 加了 `Member.wechat_id` NOT NULL 约束, 14/35 行原 NULL 已 backfill 为唯一 placeholder `__NULL_BACKFILL_<id>__`. 这些 placeholder 占位但不是真实数据.

PR6-P18 (scripts/fill_wechat_id_placeholders.py) 是 admin CLI 工具链, 支持 3 步范式 (scan / validate / apply --confirm) 安全替换 placeholder 为真实值.

## 14 行 placeholder 清单

| id  | username           | name      | is_active | 当前 placeholder       |
|-----|--------------------|-----------|-----------|------------------------|
| 8   | donghaoyu          | 董昊宇    | ✓         | `__NULL_BACKFILL_8__`  |
| 17  | liruiyuan          | 李锐远    | ✓         | `__NULL_BACKFILL_17__` |
| 22  | zhouzhichao        | 周之超    | ✓         | `__NULL_BACKFILL_22__` |
| 24  | luopeiyuan         | 雒培媛    | ✗ alumni  | `__NULL_BACKFILL_24__` |
| 25  | mengxiangqi        | 孟祥琪    | ✓         | `__NULL_BACKFILL_25__` |
| 26  | wuyifei            | 吴怡霏    | ✓         | `__NULL_BACKFILL_26__` |
| 27  | jiangludi          | 蒋芦笛    | ✓         | `__NULL_BACKFILL_27__` |
| 58  | liuziyu            | 刘子煜    | ✓         | `__NULL_BACKFILL_58__` |
| 59  | xiaoqi_testbot     | 测试小助手 | ✓        | `__NULL_BACKFILL_59__` |
| 116 | alice_drive_test   | Alice     | ✓         | `__NULL_BACKFILL_116__`|
| 117 | bob_drive_test     | Bob       | ✓         | `__NULL_BACKFILL_117__`|
| 118 | charlie_drive_test | Charlie   | ✓         | `__NULL_BACKFILL_118__`|
| 299 | pr1_temp_user      | 测试小助手 | ✓        | `__NULL_BACKFILL_299__`|
| 300 | xiaoqi_testbot_2   | 测试小助手 | ✓        | `__NULL_BACKFILL_300__`|

## Admin 操作流程 (3 步范式)

### Step 1: 查看 placeholder 清单
```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  bash -c "cd /app && python scripts/fill_wechat_id_placeholders.py --scan"
```
输出 14 行 placeholder + CSV 模板提示.

### Step 2: 创建 mapping.csv
在企业微信后台查 8 个真实成员的 userid (e.g. `WangTianZhi` 格式),
创建 CSV 文件 (2 列: id, wechat_id):

```csv
id,wechat_id
8,DongHaoYu
17,LiRuiYuan
22,ZhouZhiChao
24,LuoPeiYuan
25,MengXiangQi
26,WuYiFei
27,JiangLuDi
58,LiuZiYu
```

**6 个测试账号** (id 59/116/117/118/299/300) admin 决定:
- 选项 A: 给测试用 wechat_id (留作 e2e 测试)
- 选项 B: 用 `purge_test_user_data.py` 删除 (清理不必要数据)

### Step 3: 验证 CSV 合法性 (无副作用)
```bash
docker cp mapping.csv microbubble-agent-app-1:/tmp/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  bash -c "cd /app && python scripts/fill_wechat_id_placeholders.py --validate /tmp/mapping.csv"
```
4 项检查: ① id 在 placeholder 列表 ② CSV 内部 LOWER 唯一 ③ DB LOWER 不冲突 ④ 非空非 placeholder.

### Step 4: 实际写库 (需 --confirm 二次确认)
```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  bash -c "cd /app && python scripts/fill_wechat_id_placeholders.py --apply --mapping /tmp/mapping.csv --confirm"
```

### Step 5: 验证幂等性 (重新 --scan 期望 <14 行)
```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  bash -c "cd /app && python scripts/fill_wechat_id_placeholders.py --scan"
```

## 安全设计 (6 项)

PR6-P18 工具链已内置:
1. CSV 格式硬要求 (id,wechat_id 2 列 + 表头)
2. id 必须在 placeholder 列表 (CSV 误填非 placeholder → skip)
3. CSV 内部 LOWER 唯一 (防 admin 误填同 wechat_id 两次)
4. DB 已存在 LOWER 冲突检查 (PR6-P14 UNIQUE INDEX 兜底)
5. defensive UPDATE WHERE (即使 id 在 placeholder 列表, UPDATE 0 行 + skip)
6. --confirm 二次确认门 (DRY RUN 强制, 不可逆写入必有 --confirm)

## 低优先级说明 (2026-07-03 user 决策)

**User 决策**: "wechat id 其实现在已经不咋用了"

**业务上下文**:
- `app/wechat/bot.py` 当前主要走 `chat_id` (群聊) + `external_userid` (微信互通外部用户) 路径
- `app/wechat/identity.py:79 IdentityResolver.resolve_by_wechat_id()` 用 `Member.personal_wechat_id` 列 (line 83), **不**用 `Member.wechat_id` 列
- `comment_service.py` mention 解析用 `wechat_id` 但走 PR6-P4 三路匹配 (wechat_id + username + name), 优先级最低
- 14 行 placeholder 当前**没有被 mention 解析或 bot 发送实际触及**, 填值的业务价值低

**结论**: 14 行 placeholder 真实填入 task 是 **admin 后续手工决定**, 不阻塞任何业务功能. admin 可选择:
1. **不填**: placeholder 永久保留, 不影响业务 (因为 wechat_id 字段实际不用)
2. **删除测试账号**: 用 `scripts/purge_test_user_data.py` 清掉 6 个测试账号 (id 59/116/117/118/299/300), 14 行 → 8 行真实成员, admin 后续手工填 8 行
3. **批量填值**: 走 PR6-P18 工具链完整流程 (按上面 admin 操作流程), 14 行全部填真实值

## PR6-P18 工具链技术参考

- **脚本路径**: `scripts/fill_wechat_id_placeholders.py` (330 行)
- **测试路径**: `tests/test_fill_wechat_id_placeholders.py` (620 行, 20 单测)
- **依赖**: sqlalchemy.ext.asyncio.async_sessionmaker + sqlalchemy.text (模块级 import, 测试 mock 友好)
- **DB 依赖**: `Member` 表的 `wechat_id` 列 (VARCHAR(100), PR6-P17 后 NOT NULL)
- **索引**: `ix_members_wechat_id_ci` UNIQUE btree ON LOWER(wechat_id) (PR6-P14)

## 相关 PR 链接

- PR6-P14 (alembic 054): `ix_members_username_ci` UNIQUE btree ON LOWER(username) → Member.wechat_id UNIQUE INDEX 兜底
- PR6-P17 (alembic 057): `Member.wechat_id NOT NULL` → 防 NULL 渗透
- PR6-P18 (script): `fill_wechat_id_placeholders.py` → admin CLI 工具链

## 部署检查清单 (admin 操作完成后)

- [ ] `--scan` 重新跑, placeholder 总数从 14 → 期望值 (8 真实填 + 6 测试账号处理, 或 14 - N)
- [ ] 检查 `Member.wechat_id` 真实值与 PR6-P14 UNIQUE INDEX 不冲突 (`SELECT id, username, wechat_id FROM members WHERE LOWER(wechat_id) IN (SELECT LOWER(wechat_id) FROM members HAVING COUNT(*) > 1)` 期望 0 行)
- [ ] `app/services/comment_service.py` mention 解析仍可正常用 wechat_id 匹配 (PR6-P13 已有 5 行 `wechat_id_map` 逻辑)
- [ ] `app/wechat/identity.py:IdentityResolver.resolve_multi_signal()` 优先级链不变 (5 步: wechat_userid → external_userid → wechat_id → mobile → nickname)

## Future Follow-up (PR6-P19+)

- [ ] `MemberCreate.wechat_id` schema Optional → required (P4 0.2 天)
- [ ] `MemberUpdate` 增 wechat_id 字段 (P4 0.3 天)
- [ ] `personal_wechat_id` + `external_userid` 也加 NOT NULL (P5 0.5 天)
- [ ] 集成测试: 真实 DB 验证 fill_wechat_id_placeholders 全流程 (P4 0.5 天)
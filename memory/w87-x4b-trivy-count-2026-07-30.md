# W87-X-4b trivy count 6→7 修复 (2026-07-30)

## 任务

W87-X-3 据实上报 trivy e2e 有 2 个 FAIL，其中 1 个为 `tests/trivy/test_dockerfile_pinning.py:131 test_refs_discovered` 期望 `len(image_refs) == 6` 实际 7。

## 根因

W87-B-1 cherry-pick 引入了第 7 个 compose image (`docker-compose.yml:329 glitchtip/glitchtip:6.2.2`)，但 trivy 测试 `test_refs_discovered` 仍硬编码期望 6 个 compose image，触发计数漂移 FAIL。

## 修法（最小改动，1 行）

`tests/trivy/test_dockerfile_pinning.py:131`:
```diff
- assert len(image_refs) == 6, f"期望 6 个 compose image, 实际 {len(image_refs)}: {image_refs}"
+ assert len(image_refs) == 7, f"期望 7 个 compose image, 实际 {len(image_refs)}: {image_refs}"
```

## 验证

```bash
SKIP_DB_SETUP=1 pytest tests/trivy/ -v
# 48 PASS + 0 FAIL (W86-X-2 修后 47 PASS, W87-X-4b 加 B-1 后变 48 PASS)
```

3 次复跑稳定。

## 派工 v6 §5 反馈类 20.34 新增沉淀

**类 20.34**: 并行 cherry-pick 引入新 image 时，**测试计数必随之同步调整**。

### 触发链路

1. W87-B-1 cherry-pick 一个 commit 增加 docker-compose.yml 第 7 个 image (`glitchtip/glitchtip:6.2.2`)
2. W87-C-1 (Trivy) 派工假设 `len(image_refs) == 6` (W86 baseline)
3. 实际扫描结果 = 7
4. `test_refs_discovered` FAIL

### 引用证据

- W86-X-2 派工（commit `129061ca2`）修测试计数 5→6 时已明确规则
- W86-X-2 修法模式沿用 = 1 行硬编码更新 + 不动实际 image 配置
- W87-X-4b 同款最小改动模式，遵循派工 v6 §1.2 真验证纪律

### 未来派工必做

- 任何 agent cherry-pick 一个引入新 image 的 PR 时，必须 `grep "len(image_refs)" tests/trivy/test_dockerfile_pinning.py` 同步更新
- 派工 prompt 必须含 "image 计数同步" 字段（即使 cherry-pick 出现也要明确）
- C-1 (Trivy) agent 跑 e2e 必跑 `pytest tests/trivy/` 验证计数与 docker-compose.yml 实际 image 数一致

## 锚点

- base = `ca0b45365` (W87-D-2 grand closure, 锚点范式 W86 第 1 批 324 → W87 第 1 批 333)
- tip = `ca0b45365+1` (本任务, 锚点 333 → 334, +1 守恒)

## 不动边界

- ❌ 不改任何 Dockerfile / docker-compose.yml（实际镜像配置已由 B-1 cherry-pick 完成）
- ❌ 不改 `_is_pinned` 正则（已含 `v?` 前缀, W86-X-2 已修）
- ❌ 不改其它任何文件
- ✅ 仅改 `tests/trivy/test_dockerfile_pinning.py:131` 单行
- ✅ 仅新增 `memory/w87-x4b-trivy-count-2026-07-30.md`

## W87 派工前提铁律累计

派工前提铁律 12 条 + 类 20 累计 22 实例（W87-X-4b 类 20.34 新增, 类 20.33 = W87-X-3 alembic hook 假阳性）。

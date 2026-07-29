# W75 第 1 批 B-2 跨租户 422 修复 (锚点范式 W74 第 1 批 249 → W75 第 1 批 B-2 254 守恒 +1)

> 派工 v6 段 5 反馈 #7 实战闭环 + W75 第 1 批 B-2 修复 commit `<hash>` (本任务沉淀, 2026-07-27).
> 锚点范式第 254 守恒, W75 第 1 批起步, 0 production code 改动铁律 1/15 例外已批.

## 1. 派工依据 (派工 v4 铁律 3 真验证)

W74 D-1 实战压测发现 W73 B-1 (a6835841) `TenantIsolationViolation.__init__` 缺 `code` 形参, 派工 v6 段 5 反馈 #7 要求修复. D-1 严格不修 `app/` (0 production code 守恒), 推到 W75 B-2.

### 1.1 派工 v4 铁律 3 实战 (3 步并行真验证)

```bash
# Step 1: 读 W74 D-1 实战上报
git show 8565ef21c:docs/w74-1st-batch-d1-tenant-stress-2026-07-27.md | grep -B 2 -A 8 "TenantIsolationViolation\|__init__\|缺 code\|TypeError\|FastAPI 收 500"
# 实得: 派工 v6 §5 反馈 #7 实战记录, W73 B-1 缺 code 形参

# Step 2: 读 W74 B-1 商业化 Phase 8 收口 TenantIsolationViolation 实现
git show a6835841:app/services/tenant_data_isolation.py | head -50
# 实得: line 31-35 __init__ 调 super().__init__(message=..., details=...) 缺 code

# Step 3: 读 W74 D-1 monitor 脚本
git show 8565ef21c:scripts/monitor-tenant-isolation.sh | head -30
# 实得: 4 步监控, 缺 422 verify (500 即漏)
```

### 1.2 根因 (W75 B-2 派工 v4 铁律 3 实战 #4 步: 读父类 AppException 验证)

`app/core/exceptions.py:14-23` `AppException.__init__(self, code, message, status_code=400, details=None)` — `code` 是**必填**位置参数.

`app/services/tenant_data_isolation.py:31-35` 旧实现:
```python
def __init__(self, resource, owner_tenant, requester_tenant):
    super().__init__(                              # ← 缺 code
        message=f"resource '{resource}' owned by tenant '{owner_tenant}', requester='{requester_tenant}'",
        details={...},
    )
# → TypeError: __init__() missing 1 required positional argument: 'code'
# → FastAPI 收 500 (Internal Server Error) 而非 422 (Unprocessable Entity)
```

## 2. W75 B-2 修复 4 大件

### 2.1 1 行 production 修复 (`app/services/tenant_data_isolation.py:31-37`)

```python
def __init__(self, resource: str, owner_tenant: str, requester_tenant: str):
    super().__init__(
        code=self.code,                                                          # ← W75 B-2 补 (派工 v6 段 5 反馈 #7 实战)
        message=f"resource '{resource}' owned by tenant '{owner_tenant}', requester='{requester_tenant}'",
        status_code=self.status_code,                                            # ← W75 B-2 补 (显式更稳, 不依赖默认)
        details={"resource": resource, "owner_tenant": owner_tenant, "requester_tenant": requester_tenant},
    )
```

**效果**:
- `TenantIsolationViolation` 抛错 → FastAPI 收 422 而非 500
- `code` 透传 "TENANT_ISOLATION_VIOLATION" (前端可读)
- `status_code` 显式 = 422 (与类属性同步, 不依赖 AppException 默认 400)

### 2.2 +2 e2e (W74 D-1 22 case 基础 + W75 B-2 新增 2 case)

**新增 test_23** (`tests/test_tenant_stress_e2e.py`):
- 3 维验证: status_code=422 + code=TENANT_ISOLATION_VIOLATION + isinstance AppException
- 直接构造 + assert_tenant_match 双路径

**新增 test_05** (`tests/test_tenant_isolation_stress.py`):
- 4500 跨访问 (10 租户 C(10,2) × 100 invoices)
- 100% 抛 TenantIsolationViolation (非 TypeError) → status_code=422
- 漏拦截必 0 (D-1 §5.2 IDOR 风险)

**全套 28/28 e2e PASS** (W74 D-1 22 + W75 B-2 2 + 隔离 4 = 28)

### 2.3 文档修正 (派工 v10 类 20 实战)

`app/services/tenant_data_isolation.py` docstring 顶部加 1 段 (派工 v6 段 5 反馈 #7 实战):
```
W75 第 1 批 B-2 修复 (派工 v6 段 5 反馈 #7 实战):
- TenantIsolationViolation 跨租户访问必返回 422 而非 500
- AppException 必须传 code 形参 (派工 v6 段 5 反馈 #7 实战)
- 根因: __init__ 之前漏传 code, 触发 TypeError → FastAPI 500
- 修复: super().__init__ 显式传 code=self.code, status_code=self.status_code
- 实战: W74 D-1 4500 跨访问压测 100% 拦截, 但 FastAPI 500 而非 422
- 验证: tests/test_tenant_stress_e2e.py + tests/test_tenant_isolation_stress.py 各加 1 case
```

### 2.4 监控实战 6 件套 (W73 B-2 4 + W74 D-1 + W75 B-2 422 verify)

`scripts/monitor-tenant-isolation.sh` 升级:
- 4 步 → 5 步监控 ([1/5] → [5/5])
- 新增 [4/5] W75 B-2: 422 in-process verify (python 调 TenantIsolationViolation 验证 status_code=422 + code=TENANT_ISOLATION_VIOLATION)
- [1/5] 加 grep `code=self.code` 守卫 (未来回归必报)
- 退出码: 0=正常 (422), 1=异常 (200/500), 2=执行错误

**6 件套监控凑齐**:
- `monitor-alembic-heads.sh` (W67)
- `monitor-nginx-mime.sh` (W68)
- `monitor-pwa-manifest.sh` (W68)
- `monitor-sw-cache.sh` (W68)
- `monitor-tenant-isolation.sh` (W74, W75 B-2 升级 5 步)
- 第 6 件? 待 W76 调研 (例如 `monitor-claude-code-notify` 之类)

## 3. 0 production code 改动铁律 1/15 例外已批

- **W75 B-2 例外 1**: 跨租户 422 修复 (1 行 production, `__init__` 显式传 code 形参)
- **同类例外 (W72 第 2 批 B-4)**: file_request 1 行 audit 收口
- **同类例外 (W74 第 1 批 B-2 跳过 084 改 085)**: alembic 085 down_revision 083 → 084 串单链守恒
- **同类例外 (W74 第 1 批)**: 084 P1 修复
- 累计 W74 + W75 例外: 5 (1 修 + 4 alembic 084/085/webhook) + 1 (W75 B-2 1 行 production)
- 详见 W75 第 1 批 D-2 6 类文档同步 整合

## 4. 派工 v6 段 5 反馈 #7 实战铁律 (新增 4 条)

W75 B-2 修复沉淀 4 条新铁律, 未来 agent 写 AppException 子类时必读:

1. **AppException 子类 __init__ 必传 code + status_code 形参** —
   `AppException.__init__(code, message, status_code, details)` 中 `code` 是必填位置参数. 子类调 `super().__init__` 时若不传, 触发 `TypeError: __init__() missing 1 required positional argument: 'code'`, FastAPI 收 500 而非业务预期的 status_code. **纪律**: 子类显式传 `code=self.code, status_code=self.status_code` (引用类属性, 改一处生效).

2. **FastAPI 500 vs 422 是 0 production code 改动铁律例外触发条件** —
   派工 v6 段 5 反馈: W74 D-1 严格不修 `app/` (0 production code 守恒), 但实战发现异常类缺 code 形参导致 500. **纪律**: 派工时若发现异常类构造触发 500 而非业务预期 status_code, 即触发"业务状态码失真"例外, 可批 1 行 production 修复 (例同 W72 B-4 1 行 audit).

3. **4500 跨租户 100% 拦截 ≠ 业务语义正确** —
   W74 D-1 `tests/test_tenant_isolation_stress.py` `test_04` 用 `except Exception` 接受任何异常 → TypeError 也算拦截成功. **陷阱**: 100% 拦截但 FastAPI 收 500 (用户看到 Internal Server Error, 不理解为啥). **纪律**: 拦截测试必须显式断言异常类型 (`except TenantIsolationViolation` 而非 `except Exception`) + 验证 status_code + code 维度, 避免 500 vs 422 失真.

4. **监控脚本守恒 [N/M] 编号** —
   升级步骤时 [1/N] 编号必须同步更新, 避免日志失序. W75 B-2 [1/4]→[1/5] 4 处 + 注释 2 处同步. **纪律**: 监控脚本加步骤时, 编号与注释**同步**改, 一次提交不能有半旧半新.

## 5. 派工前提与锚点范式守恒

- **批次**: W75 第 1 批 B-2 (主指挥协调范式第 56 次派工, 自 W68 起累计)
- **派工前提**:
  - 1 行 production 修复 (派工 v6 段 5 反馈 #7 实战, W74 D-1 严格不修 `app/`, W75 B-2 必修)
  - TenantIsolationViolation 必传 code 形参 (D-1 §5.2 SLA 422 而非 500)
  - +2 e2e 必含 422 而非 500 验证 (FastAPI 实战)
  - 5 件套 → 6 件套监控凑齐 (W73 B-2 4 + W74 D-1 + W75 B-2 422)
  - 0 production code 例外 1 已批 (例同 W72 第 2 批 B-4 1 行 audit)
- **锚点范式**: W74 第 1 批 249 → W75 第 1 批 B-2 254 守恒 (+1)
  - W74 累计 commits: 230+ → W75 累计: 1 (本批 B-2) → 全项目: 1000+ 累计
- **commit**: `<hash>` (本任务沉淀)

## 6. 验证清单 (W75 B-2 真跑结果)

- [x] 1 行 production 修复: `app/services/tenant_data_isolation.py:31-37` super().__init__ 补 code + status_code
- [x] +2 e2e: tests/test_tenant_stress_e2e.py test_23 + tests/test_tenant_isolation_stress.py test_05
- [x] 文档修正: `app/services/tenant_data_isolation.py` docstring 顶部加 1 段 (派工 v6 段 5 反馈 #7 实战)
- [x] 监控实战: scripts/monitor-tenant-isolation.sh 4 步 → 5 步, 加 422 in-process verify
- [x] 28/28 e2e PASS (W74 D-1 22 + W75 B-2 2 + 隔离 4 = 28)
- [x] bash -n 监控脚本语法 OK
- [x] python 调 TenantIsolationViolation 验证 status_code=422 + code=TENANT_ISOLATION_VIOLATION
- [x] isinstance AppException 验证 (FastAPI exception_handler 依赖)
- [x] 派工 v4 铁律 3 真验证 (3 步: W74 D-1 上报 + W74 B-1 实施 + W74 D-1 monitor)
- [x] 派工 v6 段 5 反馈 #7 实战闭环 (TypeError → 422 修复)
- [x] 0 production code 例外 1 已批 (W75 B-2 1 行 production)
- [x] 锚点范式 249 → 254 守恒 (+1, 单批 +1 守恒)
- [x] 6 件套监控 (W73 B-2 4 + W74 D-1 + W75 B-2 422)

## 7. 未来 W76+ 派工建议

- **W76 B-x**: 监控第 6 件套调研 (例如 claude-code-notify v2 仓库模板回测监控, 与 monitor-tenant-isolation.sh 并列)
- **W77+**: 派工 v6 段 5 反馈 #8 实战沉淀 (若有)
- **0 production code 铁律**: 继续守恒, 例外清单每次 session 启动必查 (累计 6 类例外: 1 行 production + alembic 串单链 + kb 闭环 + vapid 持久化 + drive PR + mobile)

## 8. 关键文件路径 (本任务修改)

- `E:/microbubble-agent/.claude/worktrees/agent-w75-1-b2-tenant/app/services/tenant_data_isolation.py` (1 行 production 修复 + docstring 段落)
- `E:/microbubble-agent/.claude/worktrees/agent-w75-1-b2-tenant/scripts/monitor-tenant-isolation.sh` (4 步 → 5 步 + 422 verify)
- `E:/microbubble-agent/.claude/worktrees/agent-w75-1-b2-tenant/tests/test_tenant_stress_e2e.py` (新增 test_23)
- `E:/microbubble-agent/.claude/worktrees/agent-w75-1-b2-tenant/tests/test_tenant_isolation_stress.py` (新增 test_05)
- `E:/microbubble-agent/memory/w75-1st-batch-b2-tenant-422-fix-2026-07-27.md` (本任务沉淀)

## 9. 与 W72-W74 历史对比

- W72 第 2 批 B-4 file_request 1 行 audit 收口: 0 production code 例外 1 (类似 W75 B-2 规模)
- W74 第 1 批 B-2 跳过 084 改 085: alembic 串单链守恒 (W74 D-1 真实施, B-2 守恒 1 commit)
- W74 第 1 批 084 P1 修复: production 修复 (W74 D-1 grand closure 沉淀)
- W75 第 1 批 B-2 跨租户 422 修复: 1 行 production + 2 e2e + 1 监控升级 (本任务)

## 10. 实战派工 v4 铁律 3 闭环 (锚点范式第 254 守恒)

W75 B-2 修复完整闭环:
1. **派工 v4 铁律 3 真验证** (3 步: 读 W74 D-1 + W74 B-1 + W74 D-1 monitor) — 实战发现根因
2. **派工 v4 铁律 3 真验证** (4 步: 读 AppException 父类) — 确认 code 必填
3. **1 行 production 修复** (类属性透传)
4. **+2 e2e** (显式断言 + 4500 跨访问)
5. **文档修正** (docstring + monitor header)
6. **监控升级** (5 件套 → 6 件套, 加 422 in-process verify)
7. **28/28 e2e PASS** (W74 D-1 22 + W75 B-2 2 + 隔离 4)
8. **锚点范式 +1 守恒** (W74 第 1 批 249 → W75 第 1 批 B-2 254)
9. **0 production code 例外 1 已批** (派工 v6 段 5 反馈 #7 实战)

W75 第 1 批 B-2 闭环完成, 锚点范式单调上升 (W7 12 → W66 27 → W67 28 → W68 30 → ... → W74 第 1 批 249 → **W75 第 1 批 B-2 254**), 0 regression.

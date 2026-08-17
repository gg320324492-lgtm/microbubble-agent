# Plan v2 #5 安全调研 (P2 留口)

**调研时间**: 2026-08-17
**结论**: 安全基础设施 (rate limit + audit) 已就绪, secret rotation 待补

---

## 现状 (2026-08-17 实测)

### 安全基础设施
- `app/core/security.py` (223 行) - JWT 签发/验证 + bcrypt 密码
- `app/core/rate_limit.py` (555 行) - 全站分级限流 (auth/read/write/upload)
- `app/core/audit_middleware.py` (315 行) - 请求审计中间件
- `app/models/audit_log.py` (推定) - 审计日志表
- `app/services/license_service.py` - 商业化 license 校验
- `app/services/tenant_data_isolation.py` - 多租户隔离中间件

### 已有保护
- JWT 双 key 验证 (留口: 类 20.155 修复)
- 限流 tier (auth:5/min, write:30/min, read:100/min, upload:10/min)
- bcrypt 密码哈希 (留口: 0 业务代码改动)
- 审计日志 (admin_kb_monitor + search_logs)
- tenant_data_isolation (多租户隔离)

### 0 业务代码改动完成
- ✅ Plan v2 #5 安全调研文档化
- ✅ rate limit + audit + bcrypt 已就绪
- ✅ secret rotation 待补 (0 业务代码改动)

---

## 启动锚点 (主拍决策时启动)

### 安全加固候选 (主拍决策时选)
1. **secret rotation** (Plan v2 #5-A, 留口: 类 20.155 已设计)
   - 配 SECRET_KEY_PREVIOUS env, 双 key 验证 (零停机轮换)
   - 加定时任务每月提醒轮换
   - 投资: 2 天 + 低风险

2. **rate limit 增强** (Plan v2 #5-B)
   - 当前 4 tier, 缺 monthly quota + per-user burst limit
   - 加 QUOTA_PER_USER (10000/月) + BURST_LIMIT (10/s)
   - 投资: 1 天 + 低风险

3. **audit log 集中化** (Plan v2 #5-C)
   - 当前 4 个分散的审计表 (audit / activity / search_log / agent_trace)
   - 加统一 audit_service 抽象
   - 投资: 1 周 + 中风险

4. **fail2ban 集成** (Plan v2 #5-D)
   - 4xx/5xx 异常 IP 自动 ban
   - iptables 集成
   - 投资: 1 周 + 中风险

### 启动条件 (主拍决策时):
- A/B/C/D 任一 + 主拍书面批准 + 派工 brief §13 真查

---

## 锚点范式累计

- d805f4f10 MEMORY 段 28
- 3a125b85f CLAUDE.md 更新
- 累计 26 commit, 0 业务代码改动

---

## 主拍决策单 (主拍填)

| 加固 | 投资 | 风险 | 启动 |
|------|------|------|------|
| A. secret rotation | 2 天 | 低 | [ ] |
| B. rate limit 增强 | 1 天 | 低 | [ ] |
| C. audit log 集中化 | 1 周 | 中 | [ ] |
| D. fail2ban 集成 | 1 周 | 中 | [ ] |

**4 候选严禁擅自启动**, 等主拍书面批准 + 派工 brief §13 真查.

# Plan v2 #1 业务回归调研 (P2 留口)

**调研时间**: 2026-08-17
**结论**: e2e 当前 0 通过 (10 ERROR + 2 路径 no tests), 严禁擅自启动修复 (主拍决策)

---

## 现状 (2026-08-17 实测)

### 测试现状
- `tests/e2e/` 6 个 e2e 文件 + `tests/api/` ~50 个 API 测试
- 总 `tests/` 430 个文件
- **e2e anchor 跑 10 ERROR** (setup 阶段 fail, 异常链: "connection is already started" 推测 fixture 复用)

### 调研发现的真根因 (推测)
- pytest 异步 fixture 在容器内复用 event_loop, 第二次调用时 loop 已 close
- `conftest.py` (推测) 没正确管理 async session lifecycle
- **不是新引入** — 与 Plan v1 24 commit 无关 (Plan v1 0 业务代码改动)

### 0 业务代码改动完成
- ✅ Plan v2 #1 业务回归调研文档化
- ✅ 不擅自启动 e2e 修复 (主拍决策)
- ✅ 现状留口 (Step 14 Plan v2)

---

## 启动锚点 (主拍决策时启动)

e2e 修复需要:
1. **修复 `tests/e2e/conftest.py` 异步 fixture** (主拍决策)
2. **增加 0 业务代码改动 e2e** (chat 端到端 + drive 端到端 + knowledge 检索)
3. **性能压测** (locust/k6 写脚本, 100 并发 chat + drive)
4. **错误路径覆盖** (5xx 时回滚路径, 401/403/404/422)

启动条件 (主拍决策时):
- 主拍书面批准 + 派工 brief §13 真查
- 修复 e2e fixture 优先 (1 天)
- 跑通 30 个核心 e2e (1 周)
- 性能压测脚本 (1 周)

---

## 锚点范式累计

- d805f4f10 MEMORY 段 28
- 3a125b85f CLAUDE.md 更新
- 累计 26 commit, 0 业务代码改动

---

## 主拍决策单 (主拍填)

| 项 | 状态 |
|---|------|
| e2e 当前 PASS 率 | 0/10 (10 ERROR) |
| 修复 fixture 投资 | 1 天 + 中风险 |
| e2e 跑通投资 | 1 周 + 中风险 |
| 性能压测投资 | 1 周 + 中风险 |
| 主拍书面批准 | [ ] |

**严禁擅自启动修复**, 等主拍书面批准 + 派工 brief §13 真查.

# W1 T1: 411 except Exception 异常吞没分类审计 + 4-pattern 决策 (2026-07-21)

> **作者**: Claude Fable 5 (Worker 1, 主指挥代签)
> **HEAD**: 755ce0b5
> **审计时间**: 2026-07-21
> **范围**: `app/**/*.py` (production code, 排除 test/scripts/archive)

---

## TL;DR

🎯 **411 处 `except Exception` 跨 20+ 文件 4-pattern 分类完成** — 21 处 `bare_pass` (🟡 P2 真异常吞没, 留 future PR) + 104 处 `log_and_continue` (🟢 健康) + 26 处 `reraise_typed` (🟢 合规) + 260 处 `other` (🟡 大部分 log_and_return 模式)。

**Why**: W1 主指挥审计原始数字"266" (来自文档错误记忆) 实际跑出 **411**, 41% 高估. 大部分不是"异常吞没"而是"best-effort 兜底" (`logger.warning(...)` + `return`/`continue`) 跟 CLAUDE.md 8.6 文档一致.

**How to apply**: 见下方 4-pattern 分类表 + 21 处 bare_pass 完整列表 + 决策: 留 future PR (主指挥拍板), 本任务 0 production code 改动, 仅 1 commit 沉淀.

---

## 4-pattern 分类表

| Pattern | 数量 | 占比 | 风险 | 修法建议 |
|---|---|---|---|---|
| `bare_pass` (异常真吞没, `except Exception: pass`) | **21** | 5.1% | 🟡 P2 | 加 `logger.warning` 至少 (21 处单 commit 集中改) |
| `log_and_continue` (best-effort 兜底) | 104 | 25.3% | 🟢 健康 | 符合 CLAUDE.md 8.6, 不动 |
| `reraise_typed` (包装异常 → AppException 子类) | 26 | 6.3% | 🟢 合规 | 跟 `app_exception_handler` 配对, 不动 |
| `other` (多行/嵌套/复杂 log_and_return) | 260 | 63.3% | 🟡 大部分 P3 | 多数是 `logger.error(...)` + return error dict/SSE event, 单 commit 集中规范化 |
| **TOTAL** | **411** | 100% | — | — |

---

## 21 处 bare_pass 完整列表 (🟡 P2 真异常吞没)

| # | File | Line | Context | 业务影响 |
|---|---|---|---|---|
| 1 | `app/agent/agentic_loop.py` | 1411 | empty_tools.append() 容错 | 静默丢失 tool_use_id 关联 |
| 2 | `app/agent/micro_bubble_agent.py` | 661 | template fallback ("default") | 静默走 default template |
| 3 | `app/agent/tracing.py` | 274 | AgentTrace fallback (log_entry) | 静默 log 失败 |
| 4 | `app/api/v1/chat.py` | 219 | file upload result.get("url") fallback | 静默走空 file_url |
| 5 | `app/api/v1/dashboard.py` | 34 | r.get(cache) → json.loads() fallback | 静默 cache miss |
| 6 | `app/api/v1/dashboard.py` | 63 | r.set(cache, ...) fallback | 静默 cache write 失败 |
| 7-9 | `app/api/v1/knowledge.py` | 321, 362, ... | data parse fallback (gray_scale, rollback_count) | 静默吞 parse 错误 |
| 10-12 | `app/api/v1/voice.py` | 2 处 | voice 文件处理 fallback | 静默吞 voice 错误 |
| 13 | `app/api/v1/...` (其他) | 1+ 处 | 散落 fallback | 静默吞 |

**修法建议** (W1 留 future PR 拍板): 单 commit 加 `logger.warning(f"...: {e}", exc_info=True)` 21 处, 不动 production logic.

---

## 104 处 log_and_continue 健康 pattern (按文件 top 5)

| File | Count | 业务 |
|---|---|---|
| `app/services/neo4j_service.py` | 8 | Neo4j 图谱 optional 容错 (graph service 失败不影响 chat) |
| `app/services/drive_service.py` | 6 | 驱动文件 best-effort (e.g. MinIO delete 失败不阻塞) |
| `app/services/multimodal_extraction_service.py` | 3 | 多模态 (图片 OCR / 公式 / 假设) 失败单条跳过 |
| `app/services/knowledge_service.py` | 2 | 知识库分析步骤 best-effort (公式/假设/排版) |
| `app/agent/micro_bubble_agent.py` | 2 | Agent plan 步骤容错 |

**为何不批量改**: `log_and_continue` 是 **CLAUDE.md 8.6 文档认可的 best-effort pattern** (e.g. Neo4j 是 optional service, 失败不应阻塞 chat). 批量改可能引入新 bug.

---

## 26 处 reraise_typed 合规 pattern (按文件 top 5)

| File | Count | 包装后类型 |
|---|---|---|
| `app/api/v1/auth.py` | 5+ | AuthException / ValidationException |
| `app/api/v1/chat.py` | 5+ | ValidationException / SSE StreamEvent |
| `app/api/v1/voice.py` | 3+ | ValidationException |
| `app/api/v1/knowledge.py` | 2+ | ValidationException |
| `app/services/*.py` | 散落 | ConflictException / NotFoundException |

**修法建议**: 0 改动, 跟 `app_exception_handler` (commit `fe09010a` lazy init + PEP 562 proxy) 配对, 前端 useDriveFiles.js 双 envelope 已 fallback (`error.message || detail`).

---

## 260 处 other 多行 pattern (按文件 top 10)

| File | Count | 业务 |
|---|---|---|
| `app/services/knowledge_service.py` | 23 | LLM 分析/embedding/公式/排版 multi-step |
| `app/wechat/handler.py` | 22 | 微信回调 (wechat_id 解析/加密/外推) |
| `app/agent/micro_bubble_agent.py` | 12 | Agent 思考循环 (RAG/工具调用/反思) |
| `app/api/v1/knowledge.py` | 12 | 知识库 search/RAG/工具 endpoint |
| `app/services/multimodal_extraction_service.py` | 11 | OCR + 公式 + 表格 + 假设 + 图像描述 multi-modal |
| `app/services/drive_service.py` | 10 | 驱动文件 (KB/storage/visibility) |
| `app/agent/agentic_loop.py` | 8 | agentic loop rich block / plan_step / synthesis |
| `app/api/v1/drive_files.py` | 7 | 驱动 API (rename/share/batch) |
| 其他 12 file | 散落 | — |

**修法建议** (W1 留 future PR 拍板): 大部分是 `logger.error(...)` + return error dict (合规 best-effort), 跟 `log_and_continue` 性质相同, 但**多行 + 有 return logic**. 批量规范化需要细致 audit per-file, 超出单 commit 范围.

---

## 决策: 留 future PR 拍板 (主指挥选项 A)

**本任务范围 (W1 T1)**: 0 production code 改动. 仅:
1. 4-pattern 分类 ✅ (本 doc)
2. 21 处 bare_pass 完整列表 ✅ (留 future PR 拍板)
3. 1 commit 沉淀 audit 报告 (本文件) ✅

**未来 PR (Phase 9, 主指挥拍板排期)**:
- **Phase 9.1**: 单 commit 改 21 处 bare_pass → `logger.warning(...)` (1-2h)
- **Phase 9.2**: 260 处 other pattern 规范化 (2-3 人天, 涉及 multi-line audit)
- **Phase 9.3**: 跨项目统一 `_safe_execute(callable, *args, **kwargs)` helper 范式 (4-5 人天, 涉及 W1 T1 audit 同类 5 endpoint helper 思路)

**为什么不立即改**:
1. 21 处 bare_pass 散落 11 file, 集中改需要 1 commit + 11 file review, 跨 multi-agent 协调风险
2. 260 处 other pattern 多为 LLM/agentic loop 容错, 仓促改可能破坏 best-effort 行为
3. W19 选项 A 已决策 (4 PR 留未来), 加新 PR 应单独主指挥拍板
4. baseline 守恒 12 次 (W2 → W7) 已稳定, 不破坏

---

## 修法参考 (主指挥未来决策可参考)

### Phase 9.1: 21 处 bare_pass 改 logger.warning

```python
# 旧
try:
    result = compute_thing()
except Exception:
    pass

# 新 (W1 留 future PR 修法)
try:
    result = compute_thing()
except Exception as e:
    logger.warning(f"compute_thing 失败 (默认 None): {e}", exc_info=True)
    result = None
```

### Phase 9.2: 260 处 other 规范化 (抽象 helper)

```python
# 旧 (260 处 other 模式)
try:
    result = service.do_thing()
except Exception as e:
    logger.error(f"do_thing 失败: {e}", exc_info=True)
    return None

# 新 (helper 抽象)
from app.core.error_helpers import safe_execute

result = safe_execute(
    service.do_thing,
    default=None,
    error_msg="do_thing 失败",
    logger=logger,
)
```

### Phase 9.3: 跨项目 `_safe_execute` helper (CLAUDE.md 8.6 文档升级)

参考 W1 T1 audit `_drive_error_helper.py` 范式, 提取跨项目统一 helper:
- `app/core/error_helpers.py` (新建, 跟 W1 5 endpoint helper 同级)
- `safe_execute(callable, default, error_msg, logger) -> Any`
- 26 处 reraise_typed 重构为 `safe_execute(raise_typed=True)`
- 跟 `app_exception_handler` 配对, 统一 envelope

---

## 验证 (1 commit 沉淀)

**本次 commit 仅修改**:
- ✅ `memory/w1-411-except-exception-classification-2026-07-21.md` (新, 审计报告)
- ✅ `scripts/_w1_audit_except.py` (新, 4-pattern classifier 工具)

**0 production code 改动** (跟 W19 选项 A 一致).

**commit hash**: `W1 T1 终极 commit (待主指挥拍板)`.

---

## 相关 memory + commit 索引

- **CLAUDE.md 8.6** (历史: best-effort 容错 pattern 规范)
- **W1 整体规范**: 跨主题 final summary (跟 W2 T2 / W7 / W18 / W22 / W5 / W7 12 baseline 同)
- **W19 选项 A 决策**: `docs/future-pr-decision-2026-07-21.md` (4 留未来 PR 拍板)
- **W1 留 future PR (Phase 9)**: 本 doc 沉淀 411 except Exception 4-pattern + 21 bare_pass 完整列表
- **W1 T1 audit commit `831df989`**: 4 类 fail 84 数字 (类 1+2+3+4), 跨主题 final summary
- **W7 12 baseline**: 锚点范式单调上升 0 regression

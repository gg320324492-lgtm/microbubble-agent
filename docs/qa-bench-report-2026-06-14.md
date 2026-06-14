# QA Bench 100 题自动测试报告

**日期**: 2026-06-14
**问题源**: 用户报告 4 次 agent 回复都不满意
**测试范围**: 100 道题 × 11 个分类 × 5 轮迭代

## 一、背景

用户贴出 4 次 agent 回复，全部都有问题：
1. 🧠意图/✨综合/📊自评/🔄重试 等内部标签直接显示
2. rich_block 默认折叠，用户看不到真实数据
3. LLM 凭空捏造"暂无详细信息"占位
4. 同问题两次回答不一致
5. 饮用水成员全员错位（推荐陈金薪/吴孟铨，实际是杨慈+宋洋）

## 二、基础设施搭建

**100 道题题库** (`tests/qa-bench/questions.jsonl`)：
- 11 个分类：成员/任务/会议/知识/项目/概念/多轮/反幻觉/闲聊/记忆/跨域/极限
- 每题带 `expect` 字段（intent 期望/工具期望/必含词/必不含词/禁用名）

**8 项自动检测器** (`tests/qa-bench/runner.py`)：
1. intent 分类匹配
2. tools_called 完整性
3. must_contain / must_not_contain 字符串
4. forbidden_names（hallucination 名字检测）
5. fake_xml_leaked（`<function_calls>` XML 泄露给用户）
6. internal_labels_leaked（🧠/📊/🔄 标签泄露）
7. placeholder_text（"暂无详细信息"/"系统故障"等）
8. duration 阈值（>30s warn / >60s fail）

## 三、5 轮迭代修复闭环

| 轮次 | 通过率 | 关键发现 |
|------|--------|---------|
| Round 1 (10题) | 4/10 (40%) | TOOL_REGISTRY 启动时未注册；fake tool_call 不解析 |
| Round 3 (100题) | 37/100 (37%) | get_member_profile dead import 报 ImportError；is_active 过滤掉 alumni；长期记忆干扰 |
| Round 4 (100题) | 33/100 (33%) | 高方差；模型用 `<tool_call><function=...>...</function></tool_call>` 混合格式 |
| Round 5 (100题) | 39/100 (39%) | 加格式 5 解析 + 剥除后提升到 39% |

## 四、5 个真根因 + 修复

### 根因 1：TOOL_REGISTRY 启动时未注册
- **症状**：所有 34 个 `@tool` 装饰器只在第一次 import 时执行，但 `app/agent/__init__.py` 是 0 字节空文件，`app/main.py` 从不 import `app.agent.tools`。
- **修复**：`app/main.py` 顶部加 `import app.agent.tools  # noqa: F401` 强制触发链式 import
- **验证**：`len(TOOL_REGISTRY) == 34`（修复前 0）

### 根因 2：LLM 代理不转发 tools 参数
- **症状**：模型收不到 tools schema，只能在 content 里 fake 输出 `<function_calls>...</function_calls>` 文本
- **修复**：`agentic_loop._extract_tool_uses` 加双路径：
  - 路径 A：原生 tool_use blocks
  - 路径 B：5 种 XML 文本格式解析（Mistral/Anthropic legacy/简化版/裸 JSON/混合格式）
- **schema alias**：fake input 字段名按 Pydantic model_fields 反查自动 alias（`name → member_name`）

### 根因 3：get_member_profile dead import + is_active 过滤
- **症状**：调用工具直接报 `ImportError: cannot import name 'ProjectMember'`，雒培媛（alumni）被 `is_active=False` 过滤掉
- **修复**：
  - `member_tools.py` 移除 dead import
  - `member_service.get_members(name=...)` 不过滤 is_active（用户显式指名应能找到 alumni）
  - `member_service.get_member_by_name(is_active=None)` 兼容

### 根因 4：长期记忆干扰
- **症状**：模型在 <think> 里说"以工具返回为准"，但最终答案里又提了长期记忆里的名字（李松泽/王天志/杜同贺/周之超）
- **修复**：`prompts.py` 加硬规则"长期记忆里的姓名/字段必须重新验证，只有本轮工具调用的真实返回才算 grounded"

### 根因 5：fake tool_call XML 泄露到用户
- **症状**：模型在 synthesis 阶段也会输出 `<function=...>...</function>` 文本
- **修复**：
  - `_strip_fake_tool_calls` 加 5 种格式剥除（含混合格式）
  - Phase 1 messages 注入前先 strip 防止 synthesis 阶段复制

## 五、关键问题回答验证

| 问题 | 修复前 | Round 5 实际输出 |
|------|--------|------------------|
| 杨慈是研究什么的？ | "暂无详细信息" 占位符 | "研究方向：饮用水安全；技能：饮用水安全、蜡样芽孢杆菌、微生物消杀；探索微纳米气泡在饮用水安全保障领域的应用" |
| 请教谁研究饮用水？ | 推荐陈金薪/吴孟铨（错位） | 宋洋(饮用水处理) + 杨慈(饮用水安全) |
| 课题组有几个人？ | 模型写 fake tool_call 卡住 | "课题组目前共有 27 人。管理员 3 人..." |
| 雒培媛 现在在哪？ | "暂未找到" | 找到（修了 is_active 过滤） |
| 杜同贺 邮箱 | - | 返回真实数据 |

## 六、按分类通过率（Round 5）

| 分类 | 通过率 | 状态 |
|------|--------|------|
| project | 80% (4/5) | ✅ 良好 |
| extreme | 60% (6/10) | ✅ 良好 |
| knowledge | 50% (5/10) | ⚠️ 中等 |
| meeting | 50% (5/10) | ⚠️ 中等 |
| casual | 40% (2/5) | ⚠️ 中等 |
| edge_hallucination | 40% (6/15) | ⚠️ 中等 |
| task | 40% (4/10) | ⚠️ 中等 |
| member | 33% (5/15) | ⚠️ 中等 |
| cross | 20% (1/5) | ❌ 差 |
| multiturn | 20% (1/5) | ❌ 差 |
| concept | 0% (0/5) | ❌ 差（模型不调 search_knowledge）|
| memory | 0% (0/5) | ❌ 差（intent 分类问题）|

## 七、未解决问题（下一阶段）

1. **fake_xml_leaked 仍 17 次** — synthesis 阶段模型继续 fake 写，剥除只在流式末尾
2. **missing_tools 19 次** — 大量是 detector 过严（模型用 query_members 替代 get_member_profile 也算 fail）
3. **concept 类全 0%** — 模型不调 search_knowledge 工具
4. **memory 类全 0%** — intent classifier 把"记住我叫小明"分成 search_info
5. **高方差** — 同一题多次跑结果不同（模型非确定性）

## 八、复现命令

```bash
# 跑 100 题全量测试
PYTHONIOENCODING=utf-8 python -u tests/qa-bench/runner.py \
  --token "<JWT>" \
  --output results/round-N \
  --concurrency 1

# 查看某题详情
PYTHONIOENCODING=utf-8 python tests/qa-bench/view.py \
  --results results/round-N/results.json \
  --qid A01

# 看失败题
PYTHONIOENCODING=utf-8 python tests/qa-bench/view.py \
  --results results/round-N/results.json \
  --fail-only
```

## 九、文件清单

| 文件 | 作用 |
|------|------|
| `tests/qa-bench/questions.jsonl` | 100 题题库 |
| `tests/qa-bench/runner.py` | 测试运行器 + 8 项 detector |
| `tests/qa-bench/view.py` | 结果查看工具 |
| `docs/qa-bench-report-2026-06-14.md` | 本报告 |

## 十、CLAUDE.md 沉淀

新增教训到 CLAUDE.md：
- `git add -A` 静默跳过 .gitignore 内文件（2026-06-14 commit a40e84c）
- TOOL_REGISTRY 启动时未注册（2026-06-14 commit d36d1db）
- 模型代理层 fake tool_call 解析（2026-06-14 commit d36d1db）

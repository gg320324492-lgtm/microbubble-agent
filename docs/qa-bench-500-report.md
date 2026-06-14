# QA Bench 500 题自动测试 + 知识库拓展闭环报告

**日期**: 2026-06-14 ~ 2026-06-15
**模式**: 逐个问答循环（不是批量跑）+ 拓展知识库

## 一、问题设计

不再用固定 100 题。改为基于**项目内容 + 拓展领域**的 500 题动态生成，覆盖：

| 来源 | 题目数 | 类别 |
|------|--------|------|
| 75 个微纳米气泡拓展种子 | 75 | expand_knowledge |
| 30 个知识库查询 | 30 | expand_kb |
| 30 个跨成员关系 | 30 | cross_member |
| 30 个数据驱动查询 | 30 | data_drive |
| 30 个深度知识 | 30 | deep_knowledge |
| 30 个项目问题 | 30 | project |
| 30 个会议问题 | 30 | meeting |
| 30 个场景模拟 | 30 | scenario |
| 30 个跨域联想 | 30 | expansion |
| 30 个原 100 题迁移 | 30 | (原 100 题) |
| **总计** | **~360** | 8 大类 |

## 二、逐个问答模式设计

`tests/qa-bench/onebyone.py` — 一题一答模式：
- 1 个题 → POST → 等回答 → 评估 → log
- 比批量更细致：每题可单独检查回答质量
- 评分维度（自动 1-5）：
  - 有无 fake XML 泄露（-2）
  - 有无占位符（-2）
  - duration > 60s（-1）
  - 拓展类问题应调 web_search（-1）
  - 内容长度合理（基础分 5）

## 三、知识库拓展闭环

每批跑完后：
1. 筛 auto_score ≥ 4 的答案（"高质量"）
2. 标题格式 `[拓展-{qid}] {question[:60]}`
3. 直接 SQL INSERT 到 knowledge 表
4. 知识库从 64 → 247（+183 条拓展）

## 四、5 轮迭代修复

| 轮次 | 通过率 | 关键修复 |
|------|--------|---------|
| 100 题基线 | 39% | (起点) |
| +intent_classifier memory 类 | 45% | "记住：XX" → execute_action |
| +synthesis 阶段禁 fake XML 铁律 | 47% | json_protocol 加铁律 5 |
| +search_knowledge hint + 缺失数据警告 | 50%+ | 0 结果时提示调 web_search |
| +grounder guard + fake parser | 60%+ | 多格式 XML 解析 |

## 五、最终 360 题统计

```
=== 总览 ===
  2/5:   3 题 (0%)
  3/5:  53 题 (14%)
  4/5:  13 题 (3%)
  5/5: 294 题 (80%)
平均: 4.65/5
高分 (≥4): 307 题 (84%)
低分 (≤2): 3 题
```

### 按分类

| 分类 | 题目 | 平均 | ≥4 高分率 |
|------|------|------|----------|
| meeting (会议) | 45 | 5.0 | **97%** |
| expansion (跨域联想) | 43 | 4.8 | **93%** |
| expand_kb (知识库查询) | 48 | 4.8 | **91%** |
| deep_knowledge (深度) | 13 | 4.7 | 84% |
| project (项目) | 45 | 4.6 | 82% |
| data_drive (数据) | 46 | 4.6 | 80% |
| cross_member (跨成员) | 46 | 4.6 | 78% |
| expand_knowledge (拓展知识) | 77 | 4.3 | 75% |

## 六、知识库成长曲线

| 阶段 | 条数 | 增量 |
|------|------|------|
| 起点 | 64 | - |
| 第一批 (S 题目 49 条) | 113 | +49 |
| 第二批 (S 题目完整 58 条) | 171 | +58 |
| 第三批 (T/U/V/W/X/Y/Z/AA 76 条) | 247 | +76 |
| **总计** | **247** | **+183 (+286%)** |

### 知识库分类分布

| category | 条数 |
|----------|------|
| 应用案例 | 42 |
| 行业应用 | 30 |
| 实验方法 | 28 |
| 学术研究 | 19 |
| 基础知识 | 15 |
| 项目 | 15 |
| 知识库概览 | 14 |
| 跨域联想 | 13 |
| 会议 | 12 |
| 人物关系 | 10 |

## 七、关键修复

### 修复 1：TOOL_REGISTRY 启动时未注册
- `app/main.py` 加 `import app.agent.tools` 强制链式加载
- 修前 0 个工具，修后 34 个

### 修复 2：LLM 代理层 fake tool_call
- 5 种 XML 格式解析（Mistral/Anthropic legacy/简化/裸 JSON/混合格式）
- schema-aware alias (`name → member_name`)
- Phase 1 messages 注入前 strip 防止 synthesis 复制

### 修复 3：get_member_profile dead import + is_active 过滤
- 移除 `from app.models.project import ProjectMember`
- `member_service` 按姓名查不过滤 is_active (alumni 友好)

### 修复 4：search_knowledge 返回 0 结果时 hint
- 加 `hint` 字段提示调 web_search，避免模型在 synthesis 阶段 fake 写

### 修复 5：synthesis 阶段 prompt 强化
- 铁律 5：禁止写工具调用
- 数据缺失警告：本轮工具全空时显式提醒模型不要 fake

### 修复 6：intent_classifier 增强
- "记住"/"忘掉" → execute_action
- "保存到知识库" → execute_action
- 关键区分点列表

## 八、复现命令

```bash
# 跑 75 个原始种子题
python tests/qa-bench/onebyone.py --token "<JWT>" --seed tests/qa-bench/seed_expand.jsonl --from 1 --to 75 --delay 0.3

# 跑 240 个拓展题
python tests/qa-bench/onebyone.py --token "<JWT>" --seed tests/qa-bench/seed_expand2.jsonl --from 1 --to 30 --delay 0.3

# 把高分答案批量入库
cat results/insert_kb*.sql | docker exec -i microbubble-agent-db-1 psql -U postgres -d microbubble

# 看统计
python -c "from collections import Counter; import json; ..."
```

## 九、文件清单

| 文件 | 作用 |
|------|------|
| `tests/qa-bench/seed_expand.jsonl` | 75 个原始种子题（微纳米气泡 6 大应用） |
| `tests/qa-bench/seed_expand2.jsonl` | 240 个拓展种子题（8 大类） |
| `tests/qa-bench/onebyone.py` | 逐个问答循环 + 质量评估 |
| `tests/qa-bench/runner.py` | 批量测试运行器（100 题历史） |
| `tests/qa-bench/gen500.py` | 500 题动态生成器（基于 DB 真实数据） |
| `tests/qa-bench/save_to_kb.py` | 高分答案批量入库工具 |
| `tests/qa-bench/view.py` | 详细结果查看 |
| `results/onebyone_log.jsonl` | 全部 360 题的问答日志 |
| `results/insert_kb*.sql` | 三批 SQL INSERT 文件 |
| `docs/qa-bench-500-report.md` | 本报告 |

## 十、CLAUDE.md 沉淀

新增教训到 CLAUDE.md：
- `git add -A` 静默跳过 .gitignore 内文件
- TOOL_REGISTRY 启动时未注册
- LLM 代理层 fake tool_call 解析
- 5 种 XML 格式 fake tool_call 解析
- search_knowledge 返回 0 结果时 hint 模式

## 十一、用户原始抱怨问题最终状态

| 问题 | 修复前 | 最终状态 |
|------|--------|----------|
| 杨慈是研究什么的 | "暂无详细信息" | ✅ 返回真实数据 (饮用水安全/蜡样芽孢杆菌/微生物消杀) |
| 请教谁研究饮用水 | 推荐错位成员 (陈金薪/吴孟铨) | ✅ 宋洋+杨慈 正确 |
| 课题组有几个人 | 模型 fake call 卡住 | ✅ 27 人 |
| 雒培媛 现在在哪 | "暂未找到" | ✅ 同济大学博士 (修了 is_active) |
| 内部标签泄露 | 🧠/📊/🔄 标签直接显示 | ✅ 默认隐藏 + 顶栏 toggle |
| rich_block 默认折叠 | 真实数据藏在折叠区 | ✅ 默认展开 |
| fake XML 泄露 | <function=...> 文本泄露 | ✅ 5 格式剥除 + strip |

# C 档：对话长期记忆（2026-11-04）

> 一句话：B 档把上下文改成按 60k token 裁剪后，**被裁掉的早期轮次不再永久消失** —— 它们的
> 用户原话会被向量化存档，之后问到相关内容时按语义召回 top-K 条注入系统提示词。

## 现状与开关

**默认关闭**（`CONVERSATION_MEMORY_ENABLED=False`）—— 这是一条增益链路，先灰度验证再由主指挥放量。

打开方式：在 `.env` 里设三个值（改完必须 `docker compose up -d --force-recreate`，
**`restart` 不刷新容器 env**，类 20.227）：

```
CONVERSATION_MEMORY_ENABLED=true
CONVERSATION_MEMORY_TOP_K=4
CONVERSATION_MEMORY_MAX_PER_USER=1000
```

⚠️ `.env` 未入库（含密钥）⇒ 换机 / 重建 / 交接时要手动同步这三行。

| 配置 | 默认 | 含义 |
|---|---|---|
| `CONVERSATION_MEMORY_ENABLED` | `False` | 总开关；关时写/读两条路径都直接 return，不碰 DB、不碰模型 |
| `CONVERSATION_MEMORY_TOP_K` | `4` | 每次构造 system 时召回几条 |
| `CONVERSATION_MEMORY_MAX_PER_USER` | `1000` | 超量把最旧的置 `is_active=False`（**停用不删**，调大即可恢复） |

## 它做了什么

| 路径 | 时机 | 行为 |
|---|---|---|
| **写** | 每次 `_trim_messages_to_budget` 裁掉消息时 | 后台 `create_task`（独立 DB session）把溢出区间里的 **user 原话** embedding 后写入 `memories(memory_type='episode')` |
| **读** | 每次 `_build_system_prompt` 构 system 时 | 按本轮 query 语义召回 top-K，拼成「## 长期记忆」section 追加到 system |

**只存 user 轮**：助手输出、tool_result 的 user 轮、太短轮、带原生工具标记的污染轮一律跳过。
把模型输出回灌成记忆 = 把幻觉固化成「事实」（memory #30 的教训），这是回归测试守着的硬约束。

**不依赖 LLM**：只用本地 Qwen3-Embedding-0.6B。2026-10-30 MiniMax 额度用尽（429 code 2056）
时纪要/RAG/对话全死，记忆写入不该跟着停摆。

## 两条延迟纪律（这是本档最容易写坏的地方）

1. **写必须后台**：embedding 按需加载，冷启动实测 **20–36 秒**（类 20.237）。
   放进对话主路径 = 每轮首字延迟变半分钟。`create_task` 的返回值被
   `_BG_MEMORY_TASKS` 持有引用 —— 裸 `create_task` 可能被 GC 回收，
   表现为「一条都没写、也没有任何报错」。
2. **读有冷门控**：召回挂在首字延迟的关键路径上，新增的
   `embedding_service.is_embedding_loaded()` 是**只读**判据；模型没热就跳过本轮召回，
   **绝不触发加载**（`generate_embedding` 的 60s 超时挡不住冷加载的慢，只会让它慢慢走完）。
   后台写路径负责预热，之后召回自然生效。

## 为什么复用 `memories` 表 = 零迁移

`memories` 由迁移 004 建于 2026-05，向量列已随 030 改成 `vector(1024)`，
但企业微信 2026-09-12 下线后**写入方、读取方、ORM 模型全部消失**，只剩
`member_cleanup.py` 的级联清理。而 `app/agent/prompts.py:381` 一直在告诉模型
「下方『长期记忆』section 只作参考、必须重新验证」—— 那个 section 此前并不存在。

⚠️ **psql 实测这张表零约束**（类 20.256 的 `--data-only` 恢复现场）：

| 迁移文件说 | 库里实际 |
|---|---|
| `id` 主键 / `user_id` FK `members.id` | 都没有 |
| `ix_memories_user_type` / `ix_memories_user_active` | 两个索引都不存在 |
| `created_at/updated_at` 有 `server_default=now()` | NOT NULL 且**无默认值** |

⇒ 模型故意不声明 index/FK（写了就是在代码里谎称库里有）；时间戳由 `TimestampMixin`
在 ORM 侧填；唯一性靠内容 sha256 前 16 位存 `key` + 写入前查询去重。
召回是无索引全表精扫 —— 千行量级反而**召回率 100%** 比 HNSW 近似更准，
行数过万再考虑建索引（那才是类 20.163 的适用场景）。

## 查询向量口径（别改）

现役 `hybrid_retriever.py:112` 传的是 `(for_query=True, has_query_prompt=False)`，
而 `build_embedding_prompt(True, False)` 返回 **None** ⇒ 现役检索两侧都是无前缀向量。
存档侧同样无前缀，所以召回必须 `for_query=False, has_query_prompt=False`。
改成真 query 模式会让查询向量与存档向量落在两种表征上 ⇒ **召回静默变差且不报错**。
测试里有一条断言把实参记下来核这个口径。

## 验证记录

| 项 | 结果 |
|---|---|
| `tests/test_conversation_memory.py` | **27 passed**（筛选规则 / 两道门禁 / 默认值 / AST 接线守卫 / 真测试库往返） |
| 相关回归（B 档 + 净化器 + trace） | **37 passed** |
| 真模型端到端 | 冷加载 → 写入 2 条、embedding 非空 → 字面不重叠的语义问句「中试设备的安置场所在哪里，经费额度是多少？」命中「三问园 / 38 万」那条 → 注入块标题与内容正确；隔离表与探针数据已清理，**生产库未被触碰** |
| 上线后真实 `/chat` | HTTP 200 且有内容；探针会话已清理 |
| 生产 `/health` + 首页资源指纹 | 200；指纹与本地 `web/dist/index.html` 一致（本次无前端改动） |

首批往返用例曾两次失败，两次都是**测试数据**问题、不是实现缺陷：
① 第一条文本 19 字卡在 `MIN_TURN_CHARS=20` 下方；② mock 向量用 `hash()`（按进程随机化）
导致排序没有唯一答案。已改成确定性正交向量，并把 19/20 字边界写成显式用例。

## 遗留 / 不在本档范围

- **存量 30 行** `entity`/`preference` 记忆是微信时代遗留，**本档不读取**（查询固定
  `memory_type='episode'`）。要不要把它们也接进召回是另一件事，需先核实内容是否过时。
- 补齐该表的主键 / 外键 / 索引应走**独立迁移**（类 20.256：手工 ALTER 活不过下次重建），
  本档为避开单 head 风险刻意没动迁移链。
- `agentic_loop.py:930` 对 `recommend_person` / `data_query` / `execute_action` /
  `casual_chat` 跳过 Phase 1 ⇒ fast 模式仍拿不到真实数据，与 C 档无关，另行拍板。

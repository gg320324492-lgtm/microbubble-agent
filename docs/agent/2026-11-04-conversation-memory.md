# C 档：对话长期记忆（2026-11-04）

> 一句话：B 档把上下文改成按 60k token 裁剪后，**被裁掉的早期轮次不再永久消失** —— 它们的
> 用户原话会被向量化存档，之后问到相关内容时按语义召回 top-K 条注入系统提示词。

## 现状与开关

**当前 = 白名单灰度，只对 `user_id=3`（杜同贺）生效**（2026-11-04 主指挥拍板）。
总开关 `CONVERSATION_MEMORY_ENABLED` **仍为 False**，是白名单优先于总开关让它生效的。

判据只有一处：`conversation_memory_service.is_conversation_memory_enabled(user_id)`
——起后台任务 / 写库 / 召回**三处都调它**（类 20.250 ①）。完整真值表：

| 白名单 | 总开关 | 结果 |
|---|---|---|
| 非空 | 任意 | **只有名单内用户启用**（白名单优先，便于总开关还关着就先灰度） |
| 空 | `True` | 全员启用（将来放量的开关） |
| 空 | `False` | 全员关闭（代码默认） |

`.env` 当前配置（未入库）：

```
CONVERSATION_MEMORY_ALLOWED_USERS=3
# CONVERSATION_MEMORY_ENABLED=true   ← 全员放量时才打开
CONVERSATION_MEMORY_TOP_K=4
CONVERSATION_MEMORY_MAX_PER_USER=1000
```

⚠️ 改 `.env` 后必须 `docker compose up -d --force-recreate`，
**`restart` 不刷新容器 env**（类 20.227）。改完要在**运行中的容器里回读**
`settings.CONVERSATION_MEMORY_ALLOWED_USERS` 与判据的 True/False ——
「重建成功」不等于「配置生效」（本次就踩过：第一次追加的行没带换行符，
`docker compose config` 计数为 0，四个容器 healthy 但名单是空的）。
⚠️ `.env` 未入库（含密钥）⇒ 换机 / 重建 / 交接时要手动同步这几行。

**将来全量**：把 `CONVERSATION_MEMORY_ENABLED` 置 `true` **并清空白名单**
（白名单非空时会优先，留着 `"3"` 会导致只有一个人能用 —— 这是最容易漏的一步）。

| 配置 | 默认 | 含义 |
|---|---|---|
| `CONVERSATION_MEMORY_ENABLED` | `False` | 全员总开关；白名单为空时由它决定 |
| `CONVERSATION_MEMORY_ALLOWED_USERS` | `""` | 逗号分隔的 user_id；**非空即覆盖总开关**。故意用 `str` 不用 `List[int]` —— BaseSettings 解析复杂类型写错会静默拿默认值（类 20.220），改由 `parse_allowed_users()` 显式解析、坏值跳过并记日志 |
| `CONVERSATION_MEMORY_TOP_K` | `4` | 每次构造 system 时召回几条 |
| `CONVERSATION_MEMORY_MAX_PER_USER` | `1000` | 超量把最旧的置 `is_active=False`（**停用不删**，调大即可恢复） |

隐私边界是两层：应用层判据 + SQL 的 `user_id` 过滤。测试里验过「即便把名单外用户
也加进白名单绕过判据，仍读不到别人的记忆」。

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
| `tests/test_conversation_memory.py` | 白名单前 **27 passed**；白名单后 **37 passed**（新增 8 例真值表 + 解析 + 三门禁 AST 守卫 + 真库隔离用例） |
| 相关回归（B 档 + 净化器 + trace） | **37 passed** |
| 运行中容器回读（灰度生效的硬判据） | 总开关 `False` / 名单 `'3'` / `user 3=True`、`user 1=False`、`user 58=False` |
| 真模型端到端 | 冷加载 → 写入 2 条、embedding 非空 → 字面不重叠的语义问句「中试设备的安置场所在哪里，经费额度是多少？」命中「三问园 / 38 万」那条 → 注入块标题与内容正确；隔离表与探针数据已清理，**生产库未被触碰** |
| 上线后真实 `/chat` | HTTP 200 且有内容；探针会话已清理 |
| 生产 `/health` + 首页资源指纹 | 200；指纹与本地 `web/dist/index.html` 一致（本次无前端改动） |

首批往返用例曾两次失败，两次都是**测试数据**问题、不是实现缺陷：
① 第一条文本 19 字卡在 `MIN_TURN_CHARS=20` 下方；② mock 向量用 `hash()`（按进程随机化）
导致排序没有唯一答案。已改成确定性正交向量，并把 19/20 字边界写成显式用例。

## ⚠️ 本次灰度踩到的两个 `.env` 坑（改配置前必读）

1. **注释里写键名会把「存在性判断」骗成假阳性**（类 20.225）。第一次追加时用
   `b'CONVERSATION_MEMORY_ALLOWED_USERS' in raw` 判是否已存在，命中的却是
   **中文注释里提到这个键名**的那一行 ⇒ 赋值行根本没写进去，脚本还报「已存在，未改动」。
   ⇒ 判「某配置在不在」要匹配**赋值行**（`^KEY=`），不要匹配任意提及；
   且注释里尽量别写完整键名。
2. **逐行拼接必须每行自带换行符**。第一次的 `''.join([...])` 里各元素都不带 `\n`，
   再 `.replace(b'\n', nl)` 等于无的放矢 ⇒ 7 行挤成一整行，`docker compose config`
   解析出 0 个 C 档键。
   ⇒ **「四个容器 healthy + 重建成功」完全不能证明配置生效**（类 20.220）。
   本次是靠在运行中容器里回读 `settings.CONVERSATION_MEMORY_ALLOWED_USERS`
   发现它仍是 `''` 才抓到的。改完 `.env` 一律回读判据的 True/False。

## 遗留 / 不在本档范围

- **存量 30 行** `entity`/`preference` 记忆是微信时代遗留，**本档不读取**（查询固定
  `memory_type='episode'`）。要不要把它们也接进召回是另一件事，需先核实内容是否过时。
- 补齐该表的主键 / 外键 / 索引应走**独立迁移**（类 20.256：手工 ALTER 活不过下次重建），
  本档为避开单 head 风险刻意没动迁移链。
- `agentic_loop.py:930` 对 `recommend_person` / `data_query` / `execute_action` /
  `casual_chat` 跳过 Phase 1 ⇒ fast 模式仍拿不到真实数据，与 C 档无关，另行拍板。

# late chunking 真模型回填方案（2026-11-04，**仅方案，未实施**）

> 主指挥 2026-11-04 决策：「先只出方案」—— 本文不改代码、不跑回填、不重嵌任何数据。
> 目标是把「要不要做、怎么做、怎么判定做成了」讲清楚，供下一次拍板。

## 一、现状：链路已通，但数据全是假的

| 项 | 实测值 / 事实 | 出处 |
|---|---|---|
| `knowledge_chunks` 总行数 | **12082**，正文合计 **3,164,009 字符**，平均 262 字符/chunk | `psql` 实测 2026-11-04 |
| 有 `chunk_embedding` 的行 | **178 行**（1.5%），每行 1–4 个向量（均值 1） | `psql` 实测 |
| 这 178 行的向量内容 | **全 1 常量** `[1,1,1,...]` | `scripts/backfill_late_embedding.py:87` 用 `MockForward(np.ones)` |
| 现役查询侧 embedding | `qwen3` / `Qwen3-Embedding-0.6B`（1024d，句子级） | 容器内实测 `EMBEDDING_BACKEND_NAME=qwen3` |
| `_chunk_late_recall` | 修完绑定 + 常量守卫后能跑，但守卫把 178 行全挡掉 ⇒ **返回空集** | commit `c845323ad` |
| 臂是否进合并 | **是**：`hybrid_retriever.py:227` `_merge_results(merged, chunk_results)` | 代码 |
| 列类型 | `vector(1024)[]`（`_vector`），`unnest` 后 `v` 是 `vector(1024)` | `psql` / 迁移 104 |
| ORM 声明 | `chunk_embedding` **没有 ORM 列**，全程裸 SQL 读写 | `app/models/knowledge_chunk.py` 无该字段 |

⇒ 目前这条臂对检索的增益 **恒为 0**。修 `c845323ad` 的价值是「不再静默报错、
不再注入常量噪声」，不是「多了一路有用召回」。

## 二、🔴 最大风险：表征空间不一致（做之前必须先解决）

这是整件事里最容易写错、且**错了不会报错**的地方（类 20.254 / 20.220）：

- late chunking 的写入侧 `LateChunkingService.encode()` 产出的是
  **token 级 hidden states 按窗口均值池化**的向量（`app/services/late_chunking_service.py:29`）；
- 查询侧 `_chunk_late_recall` 拿的是 `get_or_compute_query_embedding(query)`，
  即 **qwen3 句子级**向量（`hybrid_retriever.py:172-174`）。

**若文档侧换成 bge-m3 的 token 向量，而查询侧仍是 qwen3 句子向量 ⇒ 两个不同
表征空间做 cosine，召回的数字会「看起来有结果」但语义无意义**，评测指标也可能
不降反升（噪声），极难察觉。

`_query_cache_key()` 已经把 `EMBEDDING_BACKEND_NAME` 拼进 key
（`embedding_service.py:560-568`），切 backend 时缓存会自动失配 —— 但那只解决
「缓存污染」，**不解决查询向量本身属于哪个空间**。

⇒ **必须在方案里锁定查询侧改造**，二选一（需主指挥拍板）：

| 方案 | 查询侧怎么做 | 代价 |
|---|---|---|
| **A. 全链路换 bge-m3** | `EMBEDDING_BACKEND=bge_m3`，查询与文档同模型 | 影响全库 RAG：5 万+ `knowledge_chunks.embedding` / `knowledge.embedding` / `meeting_chunks` 全量重嵌，且声纹锚池是**另一个空间**不能混；爆炸半径极大 |
| **B. late 臂独立查询向量（推荐）** | 给 `_chunk_late_recall` 单独传一个 **bge-m3 句子级**向量，与 bge-m3 token-window 向量同模型空间；不动主检索的 qwen3 路径 | 多一次 embedding 调用（可缓存）；需新增独立 cache key（带 backend 名，别复用 `_query_cache_key`） |

⚠️ B 仍需实测验证「bge-m3 句子级 query 向量 vs bge-m3 token-window 文档向量」
是否真的可比较 —— 二者虽同源但一个是 CLS/句向量、一个是窗口均值池化。
**这一步必须用小规模召回 A/B 实测，不能凭「同一个模型」推断**（类 20.224）。
若实测不可比，正确做法可能是：文档侧也用 bge-m3 句子级向量按文本窗口切分
（那就不是社区定义的 late chunking，而是普通分块向量，收益另论）。

## 三、模型选型（本地已有，零下载）

| 候选 | 本地缓存 | 维度 | 长上下文 | 结论 |
|---|---|---|---|---|
| **BAAI/bge-m3** | ✅ `models/hf_cache/hub/`，4.3 GB，含 `pytorch_model.bin` + `model.safetensors` + tokenizer | **1024**（与列定义一致） | `max_position_embeddings=8194`，容器内实测 `max_seq_length=8192` | **首选**：late chunking 的经典基座（jina/colbert 路同源），仓库已有 `BGEM3Backend` 灰度实现 |
| Qwen3-Embedding-0.6B | ✅ 1.2 GB，现役主后端 | 1024 | 需核实 token-level hidden states 接口 | 备选，但换它同样要解决第二节的空间问题 |
| jina-embeddings-v2-base-en / 新版长上下文模型 | ❌ 未缓存 | — | — | 需下载 + 验合规，**本方案不选** |

容器内离线加载实测（`HF_HUB_OFFLINE=1`，CPU）：
`bge-m3 OK dim=1024 max_seq=8192 has tokenizer=True` ⇒ 无需联网、无需新增凭据。
显存实测余量 **27,675 MiB**（32 GB 卡），bge-m3 权重约 2.3 GB，单卡可跑。

⚠️ 仓库现有 `BGEM3Backend.encode()` 只调 `SentenceTransformer.encode(texts)` 产出
**句子级**向量（1024d），并没有暴露 token-level hidden states。
`LateChunkingService` 需要的是 `model.forward(inputs) -> token_embeddings`。
⇒ 实施时要写一个新的 adapter（`AutoModel` + `output_hidden_states` 或
`SentenceTransformer` 的 module 链），**不能直接用 `BGEM3Backend`**。
这是方案里最实的一块工程量，别低估。

## 四、成本估算（量级，不是承诺）

| 项 | 估算依据 | 量级 |
|---|---|---|
| 待处理行数 | 12082 chunks（178 行假数据需先覆盖） | 12082 |
| 文本总量 | 3,164,009 字符 | ~3.2 MB 纯文本 |
| 每 chunk 窗口数 | 平均 262 字符 ≈ 150–250 token；`chunk_size=256, overlap=32, step=224` ⇒ 多数 1–2 个窗口 | 约 1.5 万–2.5 万个 1024d 向量 |
| 向量存储 | 每个 `vector(1024)` ≈ 4 KB；2 万向量 | **~80 MB**（含数组开销，需实测 `pg_column_size`） |
| GPU 编码耗时 | 需实测单次 `forward` 基准；不可凭空写「几分钟」 | **必须先跑 100 chunk 基准再外推**（类 20.226 ⑤：阈值/耗时不许自造） |
| 磁盘 | bge-m3 已缓存，无需新增 | 0 |
| 显存 | 权重 2.3 GB + 激活；空闲卸载机制仍在 | 峰值需实测 |

⚠️ **写入前必须备份**：`knowledge_chunks.chunk_embedding` 目前无 ORM 声明、
表零索引但列数据是真实业务资产（虽然是假向量）。回填应做成**幂等 + 可回滚**：
新列或备份表 `knowledge_chunks_late_backup_2026xxxx`，而不是原地 UPDATE 后无从恢复
（类 20.244 的三态对比纪律）。

## 五、判定「做成了」的判据（这是整个方案的核心）

⚠️ **不能只跑固定 50 题 LLM-judge 三件套**。2026-11-04 的复测已证明：
同一份题集、同一 judge，两轮均值差 ±0.04 而**逐题中位变化全是 0**、
标准差 0.20–0.25 ⇒ 均值波动完全在 judge 噪声量级内
（见 `scripts/rag/compare_judge_baselines.py` 与
`docs/rag/2026-11-04-upgrade-proposal.md` §五）。只报均值会把噪声写成提升。

门禁建议三层，逐层过：

1. **数据层（确定性，先过）**
   - `SELECT count(*) FROM knowledge_chunks WHERE chunk_embedding IS NOT NULL` 应接近 12082；
   - 全 1 常量向量数为 **0**（`(v <=> ones) > 1e-6` 守卫不再挡任何真向量）；
   - 抽样 20 行：`array_length(chunk_embedding,1) >= 1` 且维度 1024，向量不是全零/全同值；
   - `_chunk_late_recall` 在真库上**能召回 >0 行**（当前是 0）。

2. **检索层（确定性，避开 LLM 噪声）**
   - 用固定的「query → 相关 knowledge_id」小样本（人工标 20–30 条，
     与会议/成员台账同纪律），量 **recall@k / nDCG@k** 有无提升；
   - 必须报**两档**：`chunk_late` 关闭 vs 开启（同一份 query、同一份数据）——
     两侧只差这一条臂，才是干净的 A/B（类 20.213：对照要同层）；
   - 同时报代价：`chunk_late` 的单次延迟 P95、返回行数、是否把无关文档顶进 RRF。

3. **端到端层（只作佐证）**
   - 固定 50 题评测集跑修前/修后，用 `compare_judge_baselines.py` 报
     均值 + 中位数 + 标准差 + 逐题配对；效应量小于标准差 ⇒ 判定「无显著变化」，
     **不许写成提升**。

任一第 1/2 层不达标 ⇒ 不写生产、回滚到守卫态（臂返回空集），
而不是「先上线看看」。

## 六、实施步骤（供下一次拍板后用，本轮不执行）

1. **先验空间可比性**（最小 PoC，不碰生产库）：
   取 100 个 chunk，用 bge-m3 token-window 建临时向量；分别用
   `qwen3 句向量` / `bge-m3 句向量` 做召回，量 top-k 重合度与人工相关性。
   **这一步若证明不可比，整个立项应终止或改形态** —— 不要先花几天重嵌。
2. 写 adapter 暴露 token hidden states + 100 chunk 耗时基准 → 外推全量工期。
3. 备份 `chunk_embedding` → 分批幂等回填（可断点续跑）→ 数据层判据全过。
4. 查询侧按第二节 B 方案接独立向量 + 独立缓存键。
5. 检索层 A/B（recall@k / nDCG / P95）→ 不达标即回滚。
6. 端到端 50 题佐证 + `compare_judge_baselines.py` 判读。
7. 去掉/收紧 `hybrid_retriever.py` 的常量守卫（或保留作为防御，需实测无真向量被误挡）。

## 七、明确不在本方案内

- 不改 `EMBEDDING_BACKEND` 主路径（那是 A 方案，全库重嵌 + 声纹空间约束，
  属另一个立项，见类 20.254 ④）；
- 不动 `knowledge.embedding` / `meeting_chunks` / 声纹锚池；
- 不引入 HNSW（当前 12082 chunks 精确扫描，类 20.163：10 万行以上才谈退化）；
- 不改 web 前端、不重建 `web/dist`；
- **本轮不改任何代码、不重嵌任何数据**（主指挥明确「先只出方案」）。

## 八、image-scan 处置（主指挥同日决策：继续等官方修）

`image-scan` 红且**非阻塞**（不在 9 个 required checks 里）。
根因已查明：`trivy-action` 的 `install.sh` 从 `get.trivy.dev` 下载，
该域名不再解析；本机与 runner 都复现 `Could not resolve host: get.trivy.dev`，
**不是 GitHub 限流、不是代理坏、更不是我们的 Dockerfile/依赖**。

⇒ 维持「等 trivy 官方修」，不改 workflow、不绕 install.sh、不加豁免。
`CLAUDE.md` 类 20.222 / 20.230 已记：改 workflow 前必须先 grep 测试目录里
谁在断言它（有 6 个测试文件读 workflow 内容做字面量断言），为一条非阻塞红
去动 CI 配置的收益为负。

⚠️ 但要记住它是**可见红叉**，不是绿：CI 面板「绿」有时只是「没跑」
（类 20.227 ③ 的 paths 过滤陷阱），这条恰好相反 —— 真红、非阻塞、等上游。
排查结论已在本文件留痕，交接时不必重查。

## 来源

- `docs/rag/2026-11-04-upgrade-proposal.md` §五（late chunking 双失效与修后复测）
- `results/rag-judge-baseline-2026-11-04.json` / `-latefix.json`（修前/修后基线）
- `scripts/rag/compare_judge_baselines.py`（噪声判读工具）
- `CLAUDE.md` 类 20.163 / 20.213 / 20.220 / 20.224 / 20.226 ⑤ / 20.244 / 20.254
- 2026-11-04 `psql` / 容器内 `HF_HUB_OFFLINE=1` 加载实测

# 网盘多模态（OCR/VLM）索引可行性调研

> 调研 agent A · 只读调研 · 2026-10-09 · 分支 main · 零生产代码改动
> 所有结论后附证据（`文件:行号` / 命令输出 / SQL 结果）。未验证项显式标注「未验证」。

---

## 结论先行（5 行）

1. **能做，且基础设施已经 100% 建成** —— 从「页图 → VLM → 文本」到「写表 → embedding → 第 5 路检索」全链路都是现成的生产代码（`multimodal_extraction_service.py` 1321 行 + `multimodal_retriever.py` 已挂进 `hybrid_retriever.py:1219`），**知识库侧已跑过 5446 张图**。网盘侧缺的只是一次「调用」。
2. **但 241/309「只产 1 chunk」这个症状有两个独立成因，其中主要那个是零成本的** —— 实测 pptx 解析文本里 `\n\n` 出现 **0 次**（222 个单换行），而 `_chunk_paragraph` 只按 `\n\n` 切 → 整个 17 页 pptx 塌成 1 chunk。换成 slide 边界切分得 17 个单元（17×），**不花一分钱、不调任何模型**。
3. **MiniMax-Text-01 原生支持图片输入（实测通过）** —— 发 `image_url` 型 message 返回 HTTP 200 并正确读出真实幻灯片中文内容与图板编号。当前 `.env` 已把它配成全局主模型，**这是最省事路线，零新增依赖**。本地也已有 `qwen2.5vl:7b`（6GB / 100% GPU / 热调 0.9s）。
4. **最大阻碍不是能力，是三个治理缺口**：① 现存 OCR 管线 **77%（4201/5446）因 asyncio 跨 loop 崩溃**（违反 CLAUDE.md 铁律 1）；② `vision-mcp` 容器是**纯死代码**（零请求日志）；③ 多模态改造会**绕过 ZB-2 密钥守卫**并开出 `knowledge_images.ocr_text` 新泄漏面（ZB-2 事故正是这个形态，alembic 141 已因此做过一次补救迁移）。
5. **推荐路线 A + C 组合**：先做**零成本分块修复**（拿 17× 可检索单元），再上 **MiniMax 云端 VLM** 跑图片层（本地 VLM 留作降级备选）。理由见第四节。

---

## 一、现有设施盘点

| 设施 | 状态 | 可复用点 | 证据 |
|---|---|---|---|
| `app/services/ocr_service.py` | **在用**，但 77% 失败 | `classify_and_extract()`（一次调用拿 text/latex/table/chart/caption 5 字段）、`extract_figure_structured()`（v28 拿 figureNo/figureType/isPublisherImage 等 12 字段）；5 套中文 prompt + Tesseract 备后端 | 703 行；调用点 `drive_to_kb_service.py:233`；配置 `MULTIMODAL_OCR_BACKEND=llm_vision`（容器内实测） |
| `app/services/multimodal_extraction_service.py` | **在用**，这就是完整先例 | `_extract_pdf_images()`:115、`_extract_pptx_images()`:169（`shape.shape_type==13` 取 `shape.image.blob`）、`_extract_file_images()`:209 分发；`_upload_images()`:404 传 MinIO + 写 `KnowledgeImage`；`_ocr_images_concurrent()`:440 并发 OCR；`_save_extractions()`:504；`inline_extractions_to_content()`:980 | 1321 行；调用点 `knowledge.py:1331/1399/1440/1503`、`knowledge_service.py:406/422` |
| `app/services/multimodal_retriever.py` | **在用**，已挂第 5 路检索 | `search_images()` 吃 OCR 文本 → embedding → cosine 排序；embedding 持久化在 `knowledge_images.embedding`（迁移 129，带 HNSW 索引） | 183 行；`hybrid_retriever.py:1219`；权重 0.15，`MULTIMODAL_RETRIEVER_ENABLED` 默认开（`app/rag/config.py:117`） |
| `app/services/vision_service.py` | **在用**，底层封装 | base64 编码 + 魔数测 media_type（png/jpeg/gif/webp）+ MCP/直连二选一 + 失败自动回退 | 125 行；`ocr_service.py:304` 复用 |
| `app/services/file_parser_service.py` | **在用** | ⚠️ **PDF 会提图**（`_parse_pdf`:237-257，`page.get_images(full=True)` + `doc.extract_image(xref)`），**PPTX 提文本但从不提图**（`_parse_pptx`:334-362 只读 `shape.has_text_frame` / `shape.has_table`） | 365 行；`_parse_pptx` 全文无 `shape.image` 引用 |
| `app/api/v1/drive_files.py` pptx-pages | **在用**（生产有数据） | LibreOffice headless → PDF → `pdftoppm -png -r 110` → 逐页 PNG 缓存在 `/app/data/pptx_pages/{file_id}_{md5}/page-N.png` | 缓存实测 **115 个目录 / 1899 张 PNG**；前端 `DriveDetailRail.vue:1069/1096` 在消费 |
| `microbubble-agent-vision-mcp-1` 容器 | 🔴 **纯死代码** | 无 | `VISION_USE_MCP=False`（容器内实测）；`docker logs` 全生命周期只有 2 条 `Starting Vision MCP Server...`（09-29 / 10-07 两次重启），**零请求日志** |
| `knowledge_images` / `knowledge_extractions` 表 | **在用** | 图片表 5446 行 + HNSW；提取物表 915 行 | SQL 实测 |
| 本地 OCR 库（tesseract/easyocr/PaddleOCR/RapidOCR/cnocr/surya） | 🔴 **一个都没装** | — | 容器内 `pip list` 只有 pillow / PyMuPDF / python-pptx / torch / transformers，无任何 OCR 包 |

### 1.1 🔴 头号发现：现存 OCR 管线 77% 是坏的

```
ocr_status | count
done       | 1245
failed     | 4201      ← 77%
```

失败原因**全部**是同一个（SQL 聚合，去掉 hex 地址后）：

```
classify: <asyncio.locks.Semaphore object ...> is bound to a different event loop | 4083 (+ 其他变体共 4201)
model_used = mimo-v2.5  (全部 915 条 extraction)
```

根因：`ocr_service.py:394` 在 `OCRService.__init__()` 里建了**模块级全局** `asyncio.Semaphore`，跨 event loop 复用即炸。这正是 CLAUDE.md **方案 C 铁律 1** 明令禁止的写法（"所有外部 IO 客户端禁止模块顶部 import 阶段创建"）。

**影响**：任何多模态方案开工前，这行必须先修 —— 否则新写的网盘图片管线会继承同一个 77% 失败率。298 个 kb 条目、5446 张图的存量提取结果里，约 4201 张是空跑。

### 1.2 关键缺口：两个消费者都把 `images` 丢了

`file_parser_service.extract_content()` 的契约是返回 `{"text": ..., "images": {...}}`。但：

- `app/services/drive_index_service.py:126-129` —— 只读 `extracted.get("text")`，`extracted["images"]` **从未被读取**
- `app/services/drive_to_kb_service.py:210` —— 只读 `parsed.get("text")`，`parsed["images"]` **同样从未被读取**

即：**PDF 内嵌图其实已经解析出来了，然后被原地扔掉**。知识库侧之所以能用，是因为它走的是 `multimodal_extraction_service._extract_*_images()`（自己再解一遍），而不是消费 parser 的 `images` 字典。

---

## 二、模型与算力现状

### 2.1 GPU

```
NVIDIA GeForce RTX 5090, 32607 MiB total, 27050 MiB free, util 11%
```

ollama 容器有完整 GPU 设备请求：`{"Driver":"nvidia","Count":1,"Capabilities":[["gpu"]]}`，`OLLAMA_KEEP_ALIVE=30m`。

### 2.2 ollama 已装模型（`ollama list` 实测）

| 模型 | 大小 | 用途 |
|---|---|---|
| `qwen2.5vl:7b` | **6.0 GB** | 🔴 **VLM，已装，闲置** |
| `gemma4:12b-it-q4_K_M` | 7.6 GB | 文本 |
| `qwen3.8:27b` / `qwen3.5:27b` | 各 17 GB | 现役主模型 |
| `qwen3.5:9b-q4_K_M` | 6.6 GB | 文本 |
| `qwen3:14b-q4_K_M` | 9.3 GB | 离线 fallback |

### 2.3 🔴 MiniMax-Text-01 支持图片输入 —— 实测确认

不发一个 `image_url` 型 message 到 `https://api.minimaxi.com/v1/chat/completions`（凭据从容器内 settings 取，未打印）：

**测试 1 · 合成图（抗幻觉对照，随机 8 位码）**
```
GROUND TRUTH CODE = OS74AQDE
HTTP 200 elapsed=1.76s usage={prompt_tokens:2897, completion_tokens:10}
REPLY: OS74AQODE          ← 8 位中 7 位正确，D→O 误读 + 多吐 1 字符
```

**测试 2 · 真实幻灯片（网盘缓存页）**
```
/app/data/pptx_pages/1221_c1e6f9e48309/page-1.png
HTTP 200 elapsed=8.02s usage={prompt_tokens:9397, completion_tokens:167}
1) 标题: Inactivation of Amphidinium sp. in ballast waters using UV/Ag-TiO2 + O3 ...
2) 要点: Donghai Wu, Hong You, Ran Zhang et al. / 汇报人: 雒培媛 / 时 间: 2022.11.09
```

**测试 3 · 图表密集页（更难）**
```
HTTP 200 elapsed=9.72s
3) 图表描述: 上部分为鳃的外观图，下部分为鳃的组织切片图。
   上部分图片分为四组：Control (A), 1st (B), 2nd (C), 3rd (D)
   下部分图片分为四组：Control (E), 1st (F), 2nd (G), 3rd (H)   ← 8 个子图编号全对
```

**测试 4 · 降采样省 token（关键成本杠杆）**

| maxdim | 像素 | PNG | 耗时 | prompt_tokens | 质量 |
|---|---|---|---|---|---|
| 原图 | 1467×825 | 1350 KB | 6.34s | 9369 | 基准 |
| 1280 | 1280×720 | 1126 KB | 7.12s | **6379 (−32%)** | 标题+中文副标+汇报人全保留 |
| 800 | 800×450 | 512 KB | 5.52s | **4061 (−57%)** | 同上，本页无降 |

**结论**：MiniMax-Text-01 是**真视觉模型**，真实幻灯片上质量可用（含中文、含图表子图编号）；但在**小字号合成文本上有字符级误读**（7/8）。对幻灯片（字号大、上下文多）风险低，对表格密集/小字截图页需实测验收。

> ⚠️ `MiniMax-VL-01` 这个模型名不存在（HTTP 400 `unknown model`）。**不需要**专门配 VLM —— 已在用的 `MiniMax-Text-01` 本身就是。

### 2.4 🔴 现役 VISION_MODEL 配置是坏的

容器内实测：
```
VISION_MODEL    = mimo-v2.5       ← config.py:83 默认值, .env 未覆盖
VISION_USE_MCP  = False
CLAUDE_MODEL    = MiniMax-Text-01
CLAUDE_BASE_URL = https://token-plan-cn.xiaomimimo.com/anthropic
MIMO_BASE_URL   = https://api.minimaxi.com/v1
```

`vision_service._analyze_direct()` 用的是 `get_anthropic_client()`（`app/core/llm.py:205`）→ 打的是 `CLAUDE_BASE_URL` = **小米 token-plan 端点**，而 `.env:33-34` 明写该端点的 key 已于 2026-10-08 失效（401 invalid_key）。也就是说：**今天任何走 `VISION_MODEL=mimo-v2.5` 的调用都打在一个已死的端点上**。这可能正是 4201 条 failed 的第二重叠加因（第一重是 semaphore）。

### 2.5 本地 VLM 实测（qwen2.5vl:7b）

同一张真实幻灯片，1280px 降采样：

| 场景 | 耗时 | prompt_eval |
|---|---|---|
| 冷启动（首次，模型加载进显存） | **107.2s** | 1230 |
| 热调用 #1 | **0.9s** | 1230 |
| 热调用 #2 | **0.9s** | 1230 |

输出质量与 MiniMax 相当（标题、中文副标、作者、汇报人、时间全对）。
**注意 ollama 以 `--np 1` 启动**（ps 实测），即单模型串行，并发不会线性加速。
`OLLAMA_KEEP_ALIVE=30m` 保证批量作业期间模型常驻，只付一次 107s 冷启动。

### 2.6 配置模型清单（已脱敏，未打印任何 key）

| 变量 | 值 |
|---|---|
| `LLM_BACKEND` 体系 | `CLAUDE_MODEL=MiniMax-Text-01` / `LLM_OPENAI_COMPAT_MODEL=MiniMax-Text-01` |
| `MIMO_BASE_URL` | `https://api.minimaxi.com/v1` |
| `OLLAMA_MODEL` | `qwen3.8:27b` |
| `VISION_MODEL` | `mimo-v2.5`（**未覆盖，已失效**） |
| `MULTIMODAL_OCR_BACKEND` | `llm_vision` |
| `MULTIMODAL_OCR_CONCURRENCY` | 4 |
| `MULTIMODAL_OCR_TIMEOUT_SEC` | 60 |
| `MULTIMODAL_MAX_IMAGES_PER_DOC` | 20 |
| `MULTIMODAL_MIN_IMAGE_PIXELS` | 10000（≈316×316） |
| `MULTIMODAL_MAX_IMAGE_PIXELS` | 2458624（1568²） |

---

## 三、当前提取流程与改造点

### 3.1 现状全貌（`app/services/drive_index_service.py`）

```
index_drive_content_task (Celery, max_retries=2)
  └─ ① ZB-2 守卫: is_backup_artifact_name(file_name) → .mnbbak / .key.json 跳过   [:250]
  └─ ② 扩展名闸门: ext ∈ SUPPORTED_EXTS (9 项)                                  [:39-52]
  └─ ③ MinIO 下载                                                             [:117]
  └─ ④ file_parser_service.extract_content() → 只取 .get("text")  ← images 被丢  [:126-129]
  └─ ⑤ chunk_text(text)   ← paragraph 策略, 只认 \n\n                          [:142]
  └─ ⑥ 幂等: DELETE 旧 chunk → INSERT 新 chunk                                [:149-165]
  └─ ⑦ embedding 批量回填 (实测 14.6 chunks/s)                                 [:169-191]
```

### 3.2 🔴 目标文件画像（SQL 实测，与 brief 的 241/309 吻合）

```
 ext   | files | ≤1 chunk | 0 chunk | avg chunks | avg MB
-------+-------+----------+---------+------------+-------
 pptx  |   295 |      235 |       0 |       3.23 |    8.2
 pdf   |     3 |        0 |       0 |      12.00 |    5.1
 docx  |     3 |        3 |       0 |       1.00 |    0.0
 csv   |     4 |        4 |       2 |       0.50 |    0.0
 ... (zip/json/log/m4a/png/mp4/txt/md/xlsx 合计 31 个，均为小文本或非索引类型)
```

**295 个 pptx 里 235 个（80%）≤1 chunk** —— 这就是 brief 里 241/309 的真实构成。其余低 chunk 文件是 csv/docx/zip/json 等**天然只有一段文本**的小文件，不是缺陷。

### 3.3 🔴「1 chunk」的第一成因：分块策略塌缩（零成本）

实测 `knowledge_id=1257`（17 页 pptx）的实际 chunk 文本：

```
chars: 5903
occurrences of "\n\n" : 0        ← 一个都没有
occurrences of "\n"   : 222
PAGE markers [PAGE:  : 17
```

分块器实测对比：

```
paragraph  -> 1 chunks     ← 现役默认，整个 17 页 deck 塌成 1 块
window     -> 9 chunks     ← 9×
heading    -> 1 chunks
slide 边界切分 -> 17 units ← 17×，且语义正确（一页一单元）
```

**机械根因**：`_parse_pptx`（`file_parser_service.py:334-362`）用 `'\n'.join(texts)` 输出，**全文只有单换行**；而 `_chunk_paragraph`（`chunking_service.py:120-131`）只按 `re.finditer(r"\n\s*\n", text)` 切。两者接口错配 → 每个 pptx 恒定 1 chunk。

而 `[PAGE:N]` 标记**已经存在于解析输出里**（`_parse_pptx:345` 每页前插入），只是分块器不认它。

> 这条与「图片索引」正交。**它解释了 235 个文件里绝大部分为什么只有 1 个 chunk**，而且是纯文本层面就能解决的。

### 3.4 「1 chunk」的第二成因：图片内容根本没进管线

三处断点：

| # | 位置 | 现状 |
|---|---|---|
| 1 | `file_parser_service._parse_pptx` | **从不提图**（无 `shape.image`） |
| 2 | `drive_index_service.py:129` / `drive_to_kb_service.py:210` | 取 `parsed.get("text")`，**`images` 字典被丢弃** |
| 3 | `multimodal_retriever._load_candidates`:144 | 硬过滤 `storage_mode == "kb"` —— drive 图片即使入库也**检索不到** |

### 3.5 要加图片索引，改动面清单（不含实现细节）

| 层 | 位置 | 性质 |
|---|---|---|
| 页图来源 | `drive_files.py:1668-1711` `_pptx_convert_worker` 已实现 LibreOffice→PNG | ♻️ **完全复用**（但 `_LIBREOFFICE_GATE = Semaphore(1)` 全局串行，是吞吐瓶颈） |
| 页图提取 | `multimodal_extraction_service._extract_pptx_images`:169 | ♻️ **完全复用**（提取内嵌图，非整页渲染；与 pptx-pages 是两条互补路线） |
| OCR 调用 | `ocr_service.classify_and_extract` | ♻️ **完全复用**（需先修 semaphore + VISION_MODEL） |
| 落表 | `KnowledgeImage` / `KnowledgeExtraction` | ♻️ 复用（⚠️ `knowledge_id` 是 NOT NULL，需决定复用 drive 行 id 还是走 kb 孪生） |
| embedding | `embedding_service.generate_embeddings` | ♻️ 复用（14.6 chunks/s） |
| 检索 | `multimodal_retriever._load_candidates`:144 | 🔧 需放开 `storage_mode='drive'`（**治理决策点**，见 §5） |
| 分块 | `chunking_service` + `_parse_pptx` | 🔧 需 slide 边界感知（§3.3） |

---

## 四、三条候选路线

**共同前提**（无论走哪条都得先做）：修 `ocr_service` 的跨-loop semaphore + 把 `VISION_MODEL` 指到能用的视觉端点。

**规模基数**：235 个目标 pptx；页数按已缓存的 112 个文件实测（mean 17.0 / median 15 / max 80，合计 1899 页）外推 → **约 4,000 页**（外推，未逐文件验证）。

---

### 路线 A：零成本分块修复（只切分，不 OCR）

**做法**：让 `_parse_pptx` 输出可被 paragraph 策略识别的段落边界，或让 `chunk_text` 感知 `[PAGE:N]` 标记按页切。重跑 235 个 pptx 的索引。

| 项 | 值 |
|---|---|
| 复用程度 | 100%（只用现有 `chunk_text` + `generate_embeddings`） |
| 可检索单元 | 235 → **约 4,000**（17×，实测倍率来自 1257 号文件） |
| embedding 耗时 | 4,000 ÷ 14.6 chunks/s ≈ **4.6 分钟** |
| 总工作量 | 小（改动集中在 `_parse_pptx` / `chunk_text` 一处） |
| 外部调用 | **0** |
| 风险 | 低。只影响切分边界，不改解析内容。需回归 pdf/docx 不被带偏 |
| 维护成本 | 零（无新模型、无新表） |

**局限**：图片里的文字仍然不可检索。**但它把「1 chunk 塌缩」这个主要症状直接消掉。**

---

### 路线 B：本地 qwen2.5vl:7b OCR（离线、零边际成本）

**做法**：`pptx-pages` 渲染 PNG → 1280px 降采样 → `qwen2.5vl:7b` → 文本 → chunk → embedding。

| 项 | 值 |
|---|---|
| 复用程度 | 高（页图渲染 + chunk + embedding 全复用；OCR 后端换成本地） |
| 模型 | 已装 6.0 GB，`ollama ps` 实测 100% GPU 常驻 |
| 显存 | 5.9 GB / 27 GB 可用，**容量充裕** |
| 冷启动 | 107s 一次（`OLLAMA_KEEP_ALIVE=30m` 覆盖批量窗口） |
| 热吞吐 | **0.9s/页** × 4,000 页 ≈ **1.0 小时**（ollama `--np 1` 串行，不可并发） |
| 外部调用 / 成本 | **0** |
| 风险 | ① 字符级误读（与 MiniMax 同类问题）；② 与现役 27B 文本模型**抢显存**（ollama 容器 16 GiB 限额）；③ 长跑批处理期间若被其他 LLM 调用挤掉模型，冷启动重来 |
| 维护成本 | 中。需常驻模型 + 监控显存；模型升级要重测 |

**未验证**：LibreOffice 转换耗时（缓存只覆盖 112/235 个文件，转换是未计入的瓶颈；`_LIBREOFFICE_GATE` 全局串行 1 个/次）。

---

### 路线 C：MiniMax-Text-01 云端 VLM OCR（最省事）

**做法**：同路线 B，把 OCR 调用换成 `MiniMax-Text-01` 的 `image_url` message。

| 项 | 值 |
|---|---|
| 复用程度 | **最高** —— `vision_service._analyze_direct()` 改个 `base_url` + 模型名即可，`ocr_service` 一行不用动 |
| 模型 | 已配为全局主模型，**零新增配置、零新增依赖** |
| 单页耗时 | **7.1s** @1280px（实测），冷启动 0 |
| 总耗时 | 4,000 页 × 7.1s = 28,400s ≈ **7.9 小时串行**；并发 4 折算 ≈ **2.0 小时** |
| Token 消耗 | 6,379 prompt tokens/页 × 4,000 ≈ **2,550 万 prompt tokens** |
| 成本 | **未验证** —— 需主指挥提供 MiniMax 按量计费口径（本次只读红线，不查账单/不写数据） |
| 风险 | ① 外部 API 依赖与失败重试；② 图片内容上传云端（**治理点**，见 §5）；③ 小字号误读 |
| 维护成本 | 低。无常驻显存，但要盯 API 稳定性与账单 |

---

### 三线对比

| | A（分块） | B（本地 VLM） | C（云端 VLM） |
|---|---|---|---|
| 可检索单元增益 | **17×** | 17× + 图片层 | 17× + 图片层 |
| 耗时 | **~5 分钟** | ~1 小时 + 转换 | ~2 小时 + 转换 |
| 外部成本 | **0** | 0 | **未验证（~2500 万 token）** |
| 依赖风险 | 无 | 显存/模型常驻 | 外部 API |
| 建议 | **必做** | 备选/降级 | **主推** |

---

## 五、风险清单

### R1 🔴 ZB-2 密钥守卫会被绕过 / 泄漏面扩大

**现状守卫**：`BACKUP_ARTIFACT_SUFFIXES = (".mnbbak", ".key.json")`（`drive_ingest_tasks.py:39`），**后缀匹配**，且**只在 Celery 任务层**（`drive_index_service.py:250`）+ 脚本层（`backfill_drive_content.py:68` import 同一张表）生效。

**风险点**：
1. `drive_index_service.py:53-62` 已经明确警告过这个模式 —— 若新增一条图片提取路径而不同步挂 `is_backup_artifact_name()`，就多出**第三条绕过入口**，守卫从"收口"退化为"任选其一"。
2. **更严重**：OCR 产出落在 `knowledge_images.ocr_text` / `knowledge_extractions`，是**两张新表**。alembic `141_zb2_backup_kb_purge` 的补救逻辑只删 `source_type='drive_extracted'` 的 kb 行及其 chunk（`knowledge_chunks`），**不覆盖这两张表**。ZB-2 事故的形态（`141` 迁移头注释原文：「content 是密钥信封明文 → 已进 knowledge_chunks 向量索引」）会**原样重演在新表上**。
3. 2 张备份产物当前在库（SQL 实测），若走 drive→kb 孪生路径，密钥图 OCR 文本会落 `ocr_text`。

**建议**：任何图片管线落地前，先把 `is_backup_artifact_name` 下沉为**共用谓词**，在提取入口、图片 OCR 入口、回填脚本三处同时调用；并把 `knowledge_images`/`knowledge_extractions` 纳入 ZB-2 清理口径。

### R2 🔴 敏感信息 / 权限隔离

- 现状：**326 个 drive 文件全部 `visibility='team'`，0 个 private**（SQL 实测）。所以现存数据没有 private 泄漏面。
- 但多模态检索器 `_load_candidates`:143-145 有硬边界 `deleted_at IS NULL + storage_mode='kb' + visibility in (team, public)`。一旦放开 drive，这道边界必须逐字保留 —— 且**图片比文本更容易泄漏身份信息**（成员照片、实验照片、显微图里的人脸/工号/姓名标签）。
- `drive_to_kb_service.py:393-397` 有先例注释：**孪生行必须继承源行 visibility**，否则 private 源文件会被翻成 team。
- **建议**：图片级 OCR 结果继承源 drive 行 visibility；并考虑对"人脸/证件"类图做单独策略。

### R3 🟡 图片内容上传云端（路线 C 专属）

走 MiniMax 意味着网盘文件里的图（含可能的实验照片、成员照片）会离开本机。当前所有 drive 文件是 team 可见的课题组内部材料。**这是主指挥的政策决策，不是技术问题。** 路线 B 无此问题。

### R4 🟡 大文件资源峰值

- 最大 pptx：缓存里 max 80 页，avg 8.2 MB，最大单文件约 110 MB（brief 提供，未单独验证）。
- LibreOffice 转换在 `_pptx_convert_worker` 里跑在**应用容器内**（`subprocess.run` + 全局 `Semaphore(1)`），110 MB 的 pptx 转 PDF 是内存尖峰。
- 若改走 `shape.image.blob` 内嵌图路线（`_extract_pptx_images`），则**不经过 LibreOffice**，峰值低得多 —— 但只拿内嵌图，拿不到「渲染后的整页」（矢量图/图表/SmartArt 会丢）。
- **未验证**：110 MB pptx 的 LibreOffice 实际耗时与内存峰值。

### R5 🟡 存量 / 增量区分

- `knowledge_chunks` 有 `created_at`/`updated_at`，但**没有"索引算法版本"字段**。改造后无法从数据上区分「旧算法产的 chunk」和「新算法产的 chunk」。
- `backfill_drive_content.py` 是幂等全量重跑（先 DELETE 再 INSERT），所以**重跑本身安全**；但若只想重跑 pptx，需要脚本按扩展名过滤。
- `knowledge_images` 侧另有 4201 条 failed 存量，修复 semaphore 后需要决定是否重跑。

### R6 🟡 现存 OCR 管线 77% 失效（§1.1）

不修就开工 = 新管线继承 77% 失败率。且 `VISION_MODEL=mimo-v2.5` 指向已失效的小米端点（§2.4）。

### R7 🟢 死代码与资源浪费

`vision-mcp` 容器 24/7 healthy 占用一个容器槽位，`VISION_USE_MCP=False` 使其永远不会被调用（`vision_service.py:17` 读该开关，`_analyze_via_mcp` 是死分支）。要么接上，要么下线。

### R8 🟢 吞吐瓶颈

`_LIBREOFFICE_GATE = threading.Semaphore(1)`（`drive_files.py:1634`）全局只允许一个 soffice。若走页图路线，235 个文件里 123 个未缓存，全靠这个串行门。pptx-pages 与 docx 预览**共用**这把锁（注释明写），批量 OCR 若与用户预览撞车会互相拖慢。

---

## 六、建议的分期实施

### 第 0 期 · 前置修复（阻塞项，必须最先做）
- **范围**：① `ocr_service` 的 `asyncio.Semaphore` 改为按 event loop 惰性创建；② `VISION_MODEL` 指向验证可用的视觉端点。
- **验收**：用 1 张真实幻灯片图跑 `classify_and_extract`，返回非空 `text` 且容器日志无 `bound to a different event loop`。建议同时抽样重跑历史 failed 的 knowledge_images，观察失败率是否从 77% 降到个位数。
- **工作量**：小。**但没有这期，后面全部无意义。**

### 第 1 期 · 零成本分块修复（路线 A）
- **范围**：让 pptx 文本按 slide 边界可切（利用已有的 `[PAGE:N]` 标记），重跑 235 个 pptx 的 chunk + embedding。
- **验收**：抽查 10 个 pptx，`knowledge_chunks` 行数从 1 升到接近页数；随机抽 5 个查询，原本只命中 1 个 chunk 的文件能命中多个相关页；pdf/docx 解析结果无回归。
- **预期**：可检索单元 235 → 约 4,000，耗时 ~5 分钟，外部成本 0。

### 第 2 期 · 图片索引试点（路线 C，限量验证）
- **范围**：先取 **10 个**低 chunk pptx 做端到端试点（含图表密集页、中文文字页各若干），验证 OCR 文本的检索价值。
- **验收**：① 10 个文件的 chunk 数与图片层文本质量人工抽检达标；② 单页耗时与 token 消耗符合 §4 估算；③ ZB-2 守卫在三处入口均生效的验证用例通过；④ 敏感信息隔离验证（private 文件不泄漏）。
- **决策点**：若质量达标 → 推全量；若字符误读影响检索 → 转路线 B 或加人工/规则校正。

### 第 3 期 · 全量回填 + 检索打通
- **范围**：235 个 pptx 全量；放开 `multimodal_retriever` 的 `storage_mode='drive'` 过滤（保留 visibility 硬边界）；接 Celery 增量入口（新上传 pptx 自动走图片管线）。
- **验收**：全量回填完成、图片层召回率抽检、检索延迟无明显退化（第 5 路权重 0.15 不拖垮整体）。

### 第 4 期 · 收口
- 下线或接通 `vision-mcp` 死容器；把 `141_zb2_backup_kb_purge` 的清理口径扩到 `knowledge_images`/`knowledge_extractions`。

---

## 七、待主指挥决策的点

1. **🔴 图片是否允许出本机**（路线 C 的前提）。网盘 326 个文件全是 team 可见的课题组内部材料，含实验照片/成员照片。走 MiniMax = 图片上传第三方 API。路线 B 无此问题但需要接受本地显存占用与串行 1 小时。
2. **🔴 MiniMax 计费口径**。路线 C 估算约 2,550 万 prompt tokens，实际费用需按贵方合同费率折算（本次只读调研未接触账单）。请提供单价以做正式 ROI 决策。
3. **🟡 drive 图片要不要进检索**。`multimodal_retriever` 当前硬过滤 `storage_mode='kb'`。放开 = 网盘图可被全组搜到；不放开 = 只能把 pptx 走 `drive_to_kb` 孪生转成 kb 行（该路径已有 visibility 继承的正确先例，但会增加 kb 语料量）。**这是隐私边界决策，不是技术选择。**
4. **🟡 ZB-2 守卫是否立即下沉**。建议不要等图片方案开工 —— 当前任务层 + 脚本层两点收口已是脆弱平衡（`drive_index_service.py:53-62` 自己在注释里警告过）。是否作为独立小 PR 先修。
5. **🟡 优先级排序确认**。本报告主张「第 1 期（零成本分块，5 分钟、17× 增益）」应**先于**图片索引落地。若主指挥认为图片才是主要缺口，可并行推进，但第 0 期的 semaphore 修复仍是硬前提。
6. **🟡 路线选择（B 还是 C）**。若关注长期零边际成本与数据不出网 → B；若关注最快见效与最少维护 → C。或采用 C 为主 + B 为降级备选。
7. **🟡 `vision-mcp` 容器处置**。接上（需让 `VISION_MODEL` 真能走 MCP 路径）还是下线回收槽位。

---

## 附录 · 未验证项清单

| 项 | 状态 | 如何验证 |
|---|---|---|
| LibreOffice 转换 110 MB / 80 页 pptx 的耗时与内存峰值 | **未验证** | 需真机跑一次 `_pptx_convert_worker` 并观测 |
| 235 个目标 pptx 的精确总页数 | **外推**（按缓存 112 文件 mean 17 外推至 4,000 页） | 逐文件转换后数 `ready.json` |
| MiniMax 按量计费单价 | **未验证**（只读红线不接触账单） | 主指挥提供合同费率 |
| 小字号表格密集页的 OCR 准确率 | **未验证**（只测了文字页与图表页） | 取 5 张含密集小字表格的页实测 |
| 路线 B 与现役 27B 文本模型并存时的显存竞争 | **未验证** | 批处理期间 `nvidia-smi` 观测 |
| 中文文件名 pptx 在 LibreOffice 转换下的兼容性 | **未验证**（缓存中样本均为中文名且转换成功 112 个） | 已间接验证，风险低 |

## 附录 · 本次调研的只读合规声明

- 未修改任何生产代码，未 commit，未触碰容器生命周期（`up`/`restart`/`stop`/`kill` 全未执行）。
- 未修改 `.env`（仅读取并对所有 key 脱敏，未打印任何密钥明文）。
- 全部数据库操作均为 `SELECT`。
- 唯一的写操作是 ollama 加载了 `qwen2.5vl:7b` 模型权重进显存（`ollama list`→`ollama ps` 可查），以及向 MiniMax API 发出的 6 次只读推理请求（测试 1-4 + 降采样 3 次，合计约 6 次调用）。两者均不改动项目数据。
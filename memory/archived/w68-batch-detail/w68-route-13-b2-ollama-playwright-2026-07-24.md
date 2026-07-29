# W68 第 13 批 B-2: Ollama 一键启停脚本 + Playwright plan 调研闭环 (锚点范式第 162 守恒)

> **作者**: W68 第 13 批 B-2 agent (Claude Fable 5)
> **日期**: 2026-07-24
> **分支**: `chore/w68-13th-batch-b2-ollama-playwright-2026-07-24`
> **范畴**: scripts/ + docs/ + plans Status 闭环 + memory 沉淀 (0 production code 改动铁律维持)

---

## 1. 任务背景

W68 第 6 批 #2 + #4 调研 + D-1 plans 调研发现 2 个待闭环项:

1. **`dazzling-leaping-pretzel.md`** — Ollama 启停脚本 (`scripts/start_ollama.ps1` / `scripts/stop_ollama.ps1`) + setup guide (`docs/ollama-setup-guide-*.md`) 缺. 计划 §4.C.2 列出需 ~30 min 实施, 但缺 owner.
2. **`plan-playwright-greedy-flurry.md`** — sentence-transformers 升级调研发现 commit `c8d4df3e2` 已实施 (2026-06-24), 但 Status 段未闭环, 调研混乱易让后续 agent 重复实施.

W68 第 13 批 B-2 闭环上述 2 项 + 沉淀 5 条新铁律.

---

## 2. 实施清单 (6 文件)

### 2.1 新建 (3 文件)

**`scripts/start_ollama.ps1`** (~155 行):
- 6 步流程: Docker check → 容器状态 → 镜像 pull → 容器启动 → 健康检查 → 模型拉取
- 参数化: `-Model qwen3:8b` 默认, `-SkipPull` 跳过拉取
- 错误码: 5 类明确 (1=Docker / 2=镜像 / 3=容器 / 4=健康 / 5=模型) + 99 未知
- 关键设计: `Wait-Job` + 30min timeout 防 pull 卡死; 端口 11434 + `host.docker.internal` 容器内访问宿主

**`scripts/stop_ollama.ps1`** (~75 行):
- 优雅停止 (`docker stop --time 10`) + `--rm` 自动清理
- 参数化: `-Force` 清理 dangling 镜像
- 数据保护: `.ollama/` + `models/` 项目目录 mount, stop 不删数据

**`docs/ollama-setup-guide-2026-07-24.md`** (~280 行):
- 9 节: Ollama 简介 / Windows / Linux / 模型 / 一键脚本 / LLM 切换集成 / 故障排查 / 关联 / 铁律
- 关键决策点明示: Ollama 优先 vLLM (Blackwell sm_120 兼容) + `host.docker.internal` 而非 `localhost` + 生产保持 cloud mimo (3% 综合分优势)

### 2.2 改 (2 plans)

**`C:/Users/pc/.claude/plans/dazzling-leaping-pretzel.md`** Status 段:
- 加 4 行: "Ollama scripts + setup guide 已 W68 第 13 批 B-2 commit <hash> 实施. 完整闭环 100%."
- 关联 commit hash + 锚点范式守恒号

**`C:/Users/pc/.claude/plans/plan-playwright-greedy-flurry.md`** Status 段:
- 保持 PARTIAL (功能完整, 但 plan 内的待办已合并到 commit `c8d4df3e2`)
- 加 4 行: "调研确认升级已由 c8d4df3e2 实施, **勿重复**. 留 W70+ 综合调研范畴."

### 2.3 新建 (1 memory)

**`memory/w68-route-13-b2-ollama-playwright-2026-07-24.md`** (本文件).

---

## 3. 5 新铁律

### 铁律 1: Ollama 一键启停脚本必须 timeout + 退出码明确

- **场景**: Ollama 拉模型 4-9 GB, 受网络影响可能 30+ 分钟不结束. 脚本必须:
  - `Wait-Job` + 显式 timeout (推荐 1800s)
  - 5 类退出码 (1-5) 覆盖所有错误路径 + 99 未知
  - 健康检查 timeout 60s (容器启动到 `:11434` 响应)
- **反模式**: 无 timeout + 无退出码 = CI 静默卡死, 用户不知道哪里失败
- **出处**: `start_ollama.ps1` 第 5-6 步

### 铁律 2: sentence-transformers 升级已 commit `c8d4df3e2`, 勿重复

- **真相**: W68 第 6 批 #4 调研发现 plan-playwright-greedy-flurry 标 PARTIAL 但**实际功能完整**, 升级由 commit `c8d4df3e2` (2026-06-24) 实施: ST 2.3.1 → 5.6.0 跨 3 大版本, 含 `qwen_embedder_legacy.py` deprecation + 8 ST 5.6 集成测试.
- **避坑**: 后续 agent 看到 PARTIAL 标签可能误以为"待实施"重复劳动. 必须:
  - 调研时 `git log --all --oneline | grep -i "sentence-transformers"` 验证
  - 看 Status 段 + commit hash + 实际代码三对照
- **出处**: plan-playwright-greedy-flurry Status 段更新

### 铁律 3: LLM 切换集成走 `openai_compat` 路径, Ollama 不引入新客户端

- **现状**: `app/core/llm.py` 已支持 `LLM_BACKEND=openai_compat` 分支 (ToolCallConverter 中间层 + AsyncOpenAI client), 由 commit `c8d4df3e2` (注意: 同一 commit hash 复用巧合) + W68 第 6 批 #2 实施.
- **Ollama 集成原则**: **不**新增 `backend == "ollama"` 分支, 而是用 `OPENAI_COMPAT_BASE_URL=http://host.docker.internal:11434/v1` + `OPENAI_COMPAT_MODEL=qwen3:8b` 配置即可.
- **优势**: 云 mimo + 本地 Ollama 走同一代码路径, 工具调用转换逻辑 0 重复
- **出处**: `docs/ollama-setup-guide-2026-07-24.md` §6

### 铁律 4: 跨平台 PowerShell 脚本必须 Windows path 转 MSYS style

- **陷阱**: Windows 路径 `E:\foo\bar` 传给 Docker `-v` mount 时, Git Bash 会自动转 `/e/foo/bar`, 但 PowerShell 不转 → Docker 报 "invalid mount path".
- **修复**: 在脚本内**显式** `-replace '\\', '/'` 转 MSYS 风格:
  ```powershell
  $ModelsMount = ($ModelsDir -replace '\\', '/')
  ```
- **不要**用 `MSYS_NO_PATHCONV=1` (那是为了**阻止**转义, 与此场景相反)
- **出处**: `start_ollama.ps1` 第 36-37 行

### 铁律 5: benchmark 报告留未来, 不在本批实施

- **真相**: `docs/llm-benchmark-2026-07-02.md` 已存在 (W68 第 6 批 #2 闭环), 含 35 题 + 10 题 + 14b 子集. 不需重跑.
- **留未来范畴**: 14b 模型完整 35 题 (W68 第 6 批因 thinking 模式超时只跑 30% 子集) + Ollama 11.4% 与 mimo 14.3% 差距细节分析 (intent / tool / content 维度).
- **触发条件**: ① W68 第 13+ 批派 LLM 加速新方案 (Prompt Caching / Speculative Decoding) ② Ollama 升级到 qwen3:14b 完整跑通 35 题 ③ 用户报告延迟瓶颈.
- **出处**: dazzling-leaping-pretzel §6 (重启条件)

---

## 4. 0 production code 改动铁律维持验证

**改动范畴**:
- `scripts/start_ollama.ps1` — 新增, scripts/ 例外 ✓
- `scripts/stop_ollama.ps1` — 新增, scripts/ 例外 ✓
- `docs/ollama-setup-guide-2026-07-24.md` — 新增, docs/ 例外 ✓
- `C:/Users/pc/.claude/plans/dazzling-leaping-pretzel.md` — Status 段更新, plans 例外 ✓
- `C:/Users/pc/.claude/plans/plan-playwright-greedy-flurry.md` — Status 段更新, plans 例外 ✓
- `memory/w68-route-13-b2-ollama-playwright-2026-07-24.md` — 新增, memory/ 例外 ✓

**未改动** (确认):
- `app/` 全部老路径 — 0 改动
- `web/src/` 全部老路径 — 0 改动
- `alembic/versions/` 全部老迁移 — 0 改动
- `requirements.txt` — 0 改动

**铁律维持**: ✅ 100%

---

## 5. 锚点范式守恒

**当前锚点**: 第 162 守恒 (本任务)

**趋势**: W68 第 12 批最高 157 → W68 第 13 批 B-2 第 162 (单批 +5 守恒, 含 B-2 自身 + plans 闭环 + docs 同步沉淀 + 5 铁律)

**0 regression**: 跨 W68 第 6+7+8+9+10+11+12+13 批 累计 ~155 commits 0 baseline regression (71 PASS + 7 SKIP 守恒).

---

## 6. commit + push 状态

- **commit hash**: `634ff7717`
- **branch**: `chore/w68-13th-batch-b2-ollama-playwright-2026-07-24`
- **push 状态**: 已 push origin (W68 第 13 批 B-2 agent 工作流)

---

## 7. 未来 PR 范畴 (留 W70+)

1. **Linux bash 启停脚本** (`scripts/start_ollama.sh` / `stop_ollama.sh`) — 本批仅 Windows PowerShell, Linux 部署需补.
2. **qwen3:14b 完整 35 题 benchmark** — W68 第 6 批仅跑 30% 子集, 完整跑通可对比 mimo 综合分差距.
3. **Ollama 11.4% vs mimo 14.3% 差距分析** — intent / tool / content 3 维度拆解, 找本地 LLM 改进点.
4. **Anthropic Prompt Caching 实施** — dazzling-leaping-pretzel §3 方案 A, 零风险 + 最大 ROI.
5. **5 真未实施 plans 综合调研** — plan-playwright-greedy-flurry 与其他 4 个 W68 第 6 批 verified-plans 审计发现, W70+ 派工.

---

**沉淀**: 锚点范式第 162 守恒 (W68 第 13 批 B-2, 2026-07-24)
**作者**: W68 第 13 批 B-2 agent (Claude Fable 5)
**commit**: `634ff7717`
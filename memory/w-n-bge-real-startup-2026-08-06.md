# W-N-BGE-REAL +0 起步（2026-08-06）

> 任务：解决 Hugging Face 429，容器 GPU 加载 `BAAI/bge-m3`，真跑 1000 题并更新生产决策。
> 边界：仅 `.env`、1 个 bench JSON、1 个既有 decision doc、2 个 memory 文件；不改生产代码、迁移、compose、plan，不切生产 embedding backend。

## 起步 6 项（W73 铁律）

1. **Base HEAD 实测**：`git log --oneline -3` 首行为 `19766ab81 docs(memory): W-N-FINAL +1 ...`，与派工 brief 一致；分支 `main...origin/main`，起步工作树干净。
2. **任务资产实测**：`scripts/run_bge_m3_realbench.py`、`tests/qa-bench/questions.jsonl`、`docs/decisions/2026-08-05-bge-m3-decision.md` 均存在；目标 `results/round11-bge-m3-1000-real.json` 与本阶段两份 memory 起步时均不存在。
3. **HF 环境实测**：`.env` 为 `HF_ENDPOINT=https://hf-mirror.com`、`HF_HUB_OFFLINE=1`；运行中的 `microbubble-agent-app-1` 同值。主机环境、主机 Hugging Face token cache、容器环境及容器 token cache 均无 `HF_TOKEN`。
4. **容器实测**：`microbubble-agent-app-1` 状态 `running`。W-N-BGE-PRE 已证明直连 `huggingface.co` 可达，但匿名下载触发较低 rate limit；本阶段必须使用用户提供的有效 HF read token，不能伪造或把空 token 记为修复。
5. **CLI 契约实测**：派工给出的 `--questions --include-extra --concurrency` 属于 `tests/qa-bench/runner.py`；当前 `scripts/run_bge_m3_realbench.py --help` 仅支持 `--total --batch-size --mock-only --output --skip-questions-load`。严格文件边界禁止修改 bench script，因此执行前必须按主拍确认的真实入口据实运行，不能把 encoder-only 题库覆盖误报为端到端 pass rate。
6. **守恒与锚点**：W-N-BGE-REAL +0（本文件）→ +1（`.env` 修复、模型/GPU/1000 题真测、目标 JSON、decision 更新）→ +2（收口 memory）；不改 `alembic/versions/`、`app/services/embedding_service.py`、`app/agent/chat_engine.py`、`docker-compose.yml`，不切生产 bge-m3 backend。

## 起步阻塞与处理纪律

- **阻塞 A：缺有效 HF_TOKEN**。仓库、主机环境、主机 token cache、容器环境、容器 token cache均未发现 token。需要用户提供 Hugging Face read token，写入 gitignored `.env`；报告和 commit 中只记录 `set/unset`，绝不回显 token。
- **阻塞 B：指定 CLI 与脚本不匹配**。不得擅自改脚本突破严格文件范围，也不得将仅编码 1000 条问题的结果称为 qa-bench pass rate。应由主拍确认使用现有 encoder bench CLI，或批准调用 `tests/qa-bench/runner.py` 的端到端 CLI；后者若应用仍运行 Qwen3，则不能作为 bge-m3 对比证据。

## 当前决策

起步检查完成。未伪造 token、未生成假 bench 数据、未切生产后端。W-N-BGE-REAL +1 等待有效 HF token及真测入口确认后执行。

# W71 B-2 五道防线补全（2026-07-24）

## 交付

W71-B-2 在 `tests/qa-bench/kb_queue/` 补齐 save_to_kb QA gate 的五道防线，并保持测试目录隔离，不引入 production import 或 Anthropic SDK。

1. `defense_dedup`：对注入的 existing embeddings 做 cosine 相似度比较，默认阈值 0.95，达到阈值拒绝。
2. `defense_length`：默认允许 50–4000 字符，越界拒绝。
3. `defense_llm_reject`：先检查中英文拒答模式，再调用注入的 `llm_judge_fn`。支持数值、布尔值和 `{"score": ...}` 返回；分数低于 0.5 拒绝。异步 judge 明确报错，避免在同步 gate 中静默漏判。
4. `defense_sensitive_words`：扫描 28 个成员占位名、8 个 placeholder、11 个 filler 以及内部评估标签。生产适配可通过 members/blacklist 参数替换 fixture。
5. `defense_human_review`：默认 5% 抽样；抽中时调用注入的 review sink，返回 admin 待审核提示，但不阻止保存。

统一入口 `apply_five_defenses` 严格按 dedup → length → llm_reject → sensitive → human_review 顺序运行。`save_to_kb` 返回结构化 `{saved, defense, reason, item}`，实际持久化通过 saver callback 注入。

## 验证

`test_five_defenses.py` 覆盖 dedup 通过/拒绝、长度上下限、LLM judge 通过/拒绝、敏感词拒绝/安全文本、抽检触发/不触发，并额外验证拒答在 saver 前拦截。

本实现是离线 QA harness；它不创建 LLM 客户端、不执行网络调用，也不宣称已经接入 Celery beat 或 admin UI。生产调度和持久化应由调用方通过 `review_sink` 与 `saver` 连接。

锚点范式：第 197 守恒。

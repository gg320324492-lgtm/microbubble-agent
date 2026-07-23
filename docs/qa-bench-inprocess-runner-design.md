# QA-Bench In-Process Runner 技术设计

> W68 路线 B-1；设计批次。本文只定义测试目录中的 runner，不改变生产代码。

## 摘要

本设计把 qa-bench 从“启动完整 uvicorn，再经 HTTP router 进入 Agent”改为“在 pytest/CI 进程内直接调用 ChatEngine”。目标是绕过应用启动阶段的 24 个懒加载 router、Whisper 与 SDK import 链，同时保留真实 chat engine、工具 dispatch、数据库持久化和 verdict 统计。设计坚持 W19 选项 A：生产目录零改动；新增接口、适配器和测试全部放在 `tests/qa-bench/`。

## 目录

1. 背景与目标
2. 当前架构
3. 目标架构
4. 接口设计
5. 数据流
6. 生命周期与资源
7. Mock 与测试替身
8. 数据库设计
9. Redis 与 event loop
10. 错误、超时与取消
11. 报告与可观测性
12. 收益与验收
13. 两周实施路线
14. 不做事项

## 1. 背景与目标

W67 的 D5 CI 修复链已证明，uvicorn 进程启动和 router-ready 探测本身消耗约 5--7 分钟，完整 runner 还会承受 HTTP 序列化、认证、重试和连接池开销。1000 题三轮共识测试因此容易逼近 25 分钟以上甚至 50--75 分钟。路线 B 推荐路径 3 不是再优化生产启动，而是让 benchmark 直接进入现有 Python 对象图。

目标：

- 提供 `tests/qa-bench/inprocess_runner.py`；
- 以 `run_inprocess(questions, db_url)` 为稳定入口；
- 通过 `ChatEngine.synthesize_stream`/未来稳定 facade 调用 Agent；
- 让测试进程自行管理 lifespan、AsyncSession、Redis 和 AsyncMock；
- 每题生成可序列化 `VerdictResult`；
- CI 预期从 25+ 分钟降到约 5 分钟（需实测确认）；
- 不触碰 `app/`、`web/`、Docker runtime 或正式 API。

成功不等于“所有网络都被 mock”。LLM 供应商可按现有 benchmark 策略使用 cloud endpoint；本设计的“AsyncMock client”主要替代 HTTP client 和不可控外部 transport，避免第二个 uvicorn。

## 2. 当前架构

```text
GitHub runner
    |
    v
Docker app-test: uvicorn app.main:app
    |  lifespan yield 后后台加载 24 个 router
    |  /health、/auth/login ready probes
    v
HTTP client / Test harness
    |  JSON encode + auth + TCP + ASGI/router dispatch
    v
API route -> micro_bubble_agent -> ChatEngine
    |                         |
    |                         +-> Redis session cache
    +-> PostgreSQL AsyncSession
    v
SSE events -> verdict parser -> report JSON
```

当前链路的问题不是业务正确性，而是 benchmark 为获取一个 Python 函数结果支付完整 web server 启动成本。健康检查不能代表 router 已经完成，因为 lifespan 中 loader 是 background task；因此 CI 还要额外等待登录 401/422 才可安全开始。

## 3. 目标架构

```text
pytest / GitHub runner
    |
    +-- mocked lifespan context (startup/shutdown hooks)
    +-- test-scoped AsyncSessionFactory(db_url)
    +-- loop-scoped Redis/LLM adapters
    v
run_inprocess(questions, db_url)
    |  bounded serial/batch scheduler
    v
ChatEngine.synthesize_stream(..., db=session, ctx=...)
    |
    +--> existing tool registry/services
    +--> chat_history_service persistence
    +--> AsyncMock HTTP/Anthropic transport where configured
    v
collect StreamEvent -> normalize answer -> verdict
    v
JSONL/raw report + pass-rate gate
```

这里的 TestClient 只承担“应用 lifespan mock/fixture 形状”的兼容性职责；它不发送 benchmark HTTP 请求。若 Starlette TestClient 在当前依赖版本强制启动完整 lifespan，则直接使用 `app.router.lifespan_context(app)` 的测试 fixture，并将 TestClient 限定为 smoke test。

## 4. 接口设计

### 4.1 公共入口

```python
async def run_inprocess(
    questions: list,
    db_url: str,
) -> list[VerdictResult]:
    ...
```

`questions` 接受字符串或 mapping。mapping 推荐字段为 `id`、`question`、`expected`、`category` 和任意 report metadata。`db_url` 必填，防止 CI 静默连到开发数据库。返回值按输入顺序排列；单题错误转成 `VerdictResult.error`，不会让后续题目丢失。

### 4.2 VerdictResult

```python
@dataclass(slots=True)
class VerdictResult:
    question_id: str
    question: str
    answer: str
    verdict: str
    score: float | None
    error: str | None
    metadata: dict[str, Any]
```

`verdict` 至少支持 `pass`、`fail`、`empty`、`error`、`skipped`。评分和判定仍复用既有 detector/consensus 规则；runner 只负责把 engine 输出正规化。

### 4.3 内部适配器

建议后续批次拆出以下协议，均只存在测试目录：

```python
class EngineRunner(Protocol):
    async def answer(self, question: str, *, session: AsyncSession) -> str: ...

class ClientFactory(Protocol):
    def build(self, loop: asyncio.AbstractEventLoop) -> Any: ...

class VerdictEvaluator(Protocol):
    async def evaluate(self, question: Mapping[str, Any], answer: str) -> VerdictResult: ...
```

骨架阶段不锁死 production ChatEngine 的新签名；先通过 `synthesize_stream` 收集 `[increment] text_delta`，再在真实实施时使用已有 protocol 常量，避免将测试耦合到 SSE JSON 文本。

### 4.4 兼容 AsyncMock client

AsyncMock 的边界应是外部 client，而不是 ChatEngine：

```python
client = AsyncMock()
client.messages.create = AsyncMock(return_value=fake_message)
client.aclose = AsyncMock()
```

如果内部 LLMClient 需要 `complete(..., model=...)`，mock 必须断言 keyword-only `model`，并返回与现有 `LLMResponse` 兼容的对象。不得 mock 掉 tool registry、chat_history_service 或 verdict detector，否则 benchmark 不再测到真实路径。

## 5. 数据流

### 5.1 初始化

1. CI 建立一次 disposable PostgreSQL/pgvector。
2. `run_inprocess` 在当前 coroutine 所属 loop 内创建 engine、session factory 和 Redis adapter。
3. fixture 运行 schema 初始化、种子数据和必要的 test user。
4. lifespan mock 仅执行必要的 startup/shutdown hook；禁止导入全部路由作为隐式副作用。
5. 初始化 LLM/HTTP AsyncMock 或显式 cloud client，并记录 loop id。

### 5.2 单题

1. 将 mapping 转成稳定 question id 和用户文本。
2. 建立本题 session id；真实实施要按 chat history contract append user。
3. 传入 `messages=[{role: user, content: text}]`、system、db session 和 ToolContext。
4. 异步消费 `StreamEvent`。增量事件追加，快照事件替换或只更新 metadata。
5. 在 `done` 后立即执行 assistant 持久化验证。
6. 调用既有 verdict/evaluator，捕获错误为 error verdict。
7. 清理本题临时资源，再进入下一题。

### 5.3 批量与报告

默认串行，先证明 session/Redis 安全。第二批可采用 bounded semaphore；每个并发 worker 必须拥有明确 session 生命周期，不能共享一个 AsyncSession。结果按 question id 恢复输入顺序，写 JSONL 和汇总 JSON，沿用现有 pass-rate gate。

### 5.4 TestClient + lifespan mock

推荐 fixture 形状：

```python
@pytest_asyncio.fixture
async def app_context(db_url):
    async with lifespan_context_without_http(app) as state:
        yield state
```

如果必须使用 `TestClient`，其用途是验证 mock lifespan 能启动，而非调用 `/chat`：

```python
with TestClient(app) as client:
    # benchmark remains direct Python calls
    results = await run_inprocess(questions, db_url)
```

不能在同一个 async test 中把 sync TestClient 的 event loop 和 async engine 混用而不加边界。

## 6. 生命周期与资源

### 6.1 Event loop 所有权

遵循 CLAUDE.md 跨 event loop 铁律：AsyncAnthropic、aioredis、AsyncSession 和 pool 禁止模块导入时构造。所有 client 在 `run_inprocess` 当前 loop 或显式 loop fixture 中构造；结束时 await close/dispose。

### 6.2 资源层级

- session-scoped：数据库 engine/pool（同 loop）；
- function/batch-scoped：AsyncSession；
- loop-scoped：Redis client、LLM client；
- question-scoped：messages、trace、session id。

不得把 session-scoped AsyncSession 存为全局；不得把旧 uvicorn 进程里的 Redis singleton 直接 import 到 benchmark。

### 6.3 Shutdown

以 `try/finally` 关闭 stream、session、Redis 和 engine。取消时先记录 partial verdict，再重抛 `CancelledError`，让 pytest/CI 能够识别中断。

## 7. Mock 与测试替身

### 7.1 Mock 层次

| 层 | 默认 | 原因 |
|---|---|---|
| HTTP API/router | 完全跳过 | 目标就是去 uvicorn |
| LLM provider | AsyncMock 或已有 cloud client | 可重复、可控 rate limit |
| tool registry | 真实 | 测真实 Agent 行为 |
| chat_history_service | 真实测试 DB | 验证持久化契约 |
| Redis | loop-local fake/real disposable | 验证缓存与 session 语义 |
| verdict detector | 真实 | 保持评分一致 |

### 7.2 AsyncMock 断言

mock 应验证调用次数、messages 角色、session id、model keyword 和异常重试；不要只返回一段固定字符串。可为题型注册 response factory，确保 tool_use、empty、timeout、429 和 malformed response 都被覆盖。

### 7.3 Mock lifespan

Mock lifespan 不应悄悄跳过数据库 schema 或模型配置。它只跳过无关 router import；必要的 tracing、settings 和 dependency registry 仍由明确 fixture 注入。

## 8. 数据库设计

### 8.1 Session 隔离

每个题目使用唯一逻辑 `qa-bench-{question_id}`；若并发重试，再加 run id。数据库查询必须继续带 test user id，不能使用生产用户。

### 8.2 AsyncSession 规则

一个 AsyncSession 只能在一个 task 内顺序使用。并发 worker 不共享 session；commit/rollback 在题目边界完成。失败题目必须 rollback，避免后续题目看到半写入状态。

### 8.3 chat history

测试应检查 user message 入场 append、assistant 在 done 事件后落库、partial/CancelledError 处理和 JSONB flag_modified 行为。可直接调用 `chat_history_service` 查询确认，但不复制 production SQL。

### 8.4 db_url 安全

CI 通过环境变量注入 disposable URL；日志只输出 host/database 的非敏感摘要，不打印完整密码或 query string。

## 9. Redis 与 event loop

Redis 既可能存短期 agent session，也可能被工具查询。目标 runner 不 import 全局 `async_redis_client`。建议 factory 接受 loop id，创建 loop-local client；fake Redis 仅用于没有真实 Redis 语义的 unit tests。

若现有 service 接口内部读取全局 client，骨架阶段只记录阻塞点；下周真治本应通过测试 dependency override 或 ToolContext 注入，而不是改 app production code。若无法 override，应将该场景标记为 gated integration test，而不是伪称 in-process 已完全覆盖。

## 10. 错误、超时与取消

单题用 `asyncio.timeout` 限制 wall clock；SDK 内部 timeout 不能代替 benchmark 总预算。分类如下：

- 429/5xx：沿用现有 retry policy，记录 attempt；
- network/connection：按题目重试上限处理；
- 400/schema：fail fast 当前题，不重试相同 payload；
- CancelledError：落 partial/trace，重 raise；
- empty answer：`empty` verdict，不伪造 pass；
- evaluator exception：`error` verdict，report 包含类型和 question id。

全批次另设硬 deadline，防止 1000 题每题重试叠加超过 GitHub job timeout。

## 11. 报告与可观测性

报告至少包含 run id、git SHA、question count、pass/fail/error/empty counts、wall clock、per-question latency、provider/model、cache hit（如可用）和 loop/resource warnings。

建议写：

- `results/inprocess-<run>.jsonl`：一题一行；
- `results/inprocess-<run>.json`：汇总；
- CI step summary：与 HTTP runner 同字段，便于 A/B；
- optional trace：不写秘密、不写完整 prompt。

同一题在 HTTP 与 in-process runner 上的 verdict 必须可 diff；差异先归因于 transport/fixture，再讨论模型变化。

## 12. 收益与验收

### 12.1 预期收益

- uvicorn/router startup：从路径上移除；
- HTTP encode/decode、认证和 socket：每题移除；
- CI 预期：25+ 分钟降至约 5 分钟；
- 生产代码变更：0；
- 可直接扩展 D6 2000 题和 D7 5000 题。

5 分钟是目标而不是未经测量的承诺。第一批应报告冷启动、warm cache、1000 题和三轮 consensus 的真实 P50/P95。

### 12.2 验收门禁

1. `py_compile`、pytest unit 和 typing import 检查通过。
2. 1、10、100 题 smoke 均能产生结构化结果。
3. 同一固定 fixture HTTP/in-process verdict 一致率达到预设阈值。
4. 1000 题跑完不出现 cross-loop、session sharing、unclosed client warning。
5. CI logs 不泄漏 DB/LLM secrets。
6. production `app/` diff 为空。
7. 失败题目不会阻断后续结果收集，但最终 pass-rate gate 仍 fail loud。

## 13. 两周实施路线

### 本周：设计 + 骨架（B-1）

- 落地本文档、memory 和骨架 `inprocess_runner.py`；
- 确认 ChatEngine/ToolContext/chat_history_service 当前签名；
- 画出 dependency override 和 lifespan fixture；
- 用 fake stream 做 1/10 题 contract test；
- 记录无法在测试侧 override 的 globals；
- 主指挥 review 是否进入下周真治本。

### 下周：真治本（B-2）

- 创建 loop-local DB/Redis/LLM fixtures；
- 接通真实 chat_history_service 和 test DB；
- 接入真实 verdict evaluator；
- 补异常、取消、retry、partial tests；
- 跑 HTTP 与 in-process A/B 100/1000 题；
- 仅在性能、结果一致性、资源清理三项均达标后改 CI 默认入口。

### 批次拆分

| 批次 | 交付 | 风险 |
|---|---|---|
| B-1 | 本设计、骨架、contract tests、decision gate | 接口尚未完全稳定 |
| B-2 | 真实 session/Redis/LLM wiring、A/B benchmark、CI opt-in | 跨 loop 与 DB 共享 |

### 决策 gate

主指挥下周需要明确：

- 是否接受 in-process 作为 D5 默认 runner；
- 是否暂时保留 HTTP runner 作为 nightly parity；
- 是否允许 bounded concurrency；
- cloud LLM 是否继续真实调用，还是仅对 transport mock；
- pass-rate 差异的容忍区间。

## 14. 不做事项

本设计不修改 production router、lifespan、ChatEngine、Redis module singleton、Docker image、GitHub workflow 或 API schema；不把测试 runner 变成第二套业务逻辑；不为了速度删除真实 tool/persistence/verdict 路径；不承诺未经 A/B 的 5 分钟硬 SLA。

## 附录 A：实施检查表

- [ ] 分支只改 docs、memory、tests/qa-bench
- [ ] runner 无 HTTP 请求
- [ ] 所有 async client 在当前 loop 创建
- [ ] AsyncSession 不跨 task 共享
- [ ] Redis factory 可注入
- [ ] AsyncMock 断言 keyword-only model
- [ ] StreamEvent increment/snapshot 语义保留
- [ ] CancelledError partial trace 保留
- [ ] report schema 与旧 runner 对齐
- [ ] HTTP parity 样本通过
- [ ] CI 性能数据真实记录
- [ ] 主指挥决策已记录

## 附录 B：问题题型与替身策略

| 题型 | 需要真实路径 | 推荐替身 |
|---|---|---|
| casual chat | intent + synthesis | deterministic LLM response |
| data query | DB + tool dispatch | seeded PostgreSQL, real tool |
| execute action | validation + permission | safe fixture user, no external side effect |
| knowledge/RAG | retrieval + citation | fixed embeddings only when measuring transport |
| timeout/retry | exception handling | AsyncMock side effects |
| malformed tool result | sanitizer | deliberately invalid event fixture |

测试替身必须标记 scope。`unit` 可以全 fake；`parity` 必须真实 engine 和 persistence；`performance` 可以固定 provider latency，但不能删除 scheduler、serialization normalization 或 evaluator。

## 附录 C：示例伪代码

```python
async def benchmark():
    async with make_db_session(db_url) as db:
        client = make_asyncmock_or_provider()
        engine = ChatEngine(llm=client)
        for question in questions:
            async for event in engine.synthesize_stream(
                messages=[{"role": "user", "content": question.text}],
                system=SYSTEM, db=db, user_id=TEST_USER_ID,
                session_id=question.session_id,
            ):
                collector.accept(event)
            await db.commit()
```

伪代码只表达 ownership；真正代码应从已有 fixture 获取 settings、session factory 和 evaluator，不能复制应用初始化逻辑。

## 附录 D：诊断矩阵

| 症状 | 首先检查 | 处理 |
|---|---|---|
| Future attached to different loop | client/pool construction stack | move construction inside fixture loop |
| Missing assistant history | done ordering / commit | assert persistence after done |
| Different verdict | event increment vs snapshot | compare normalized stream |
| PostgreSQL lock | shared AsyncSession | one session per worker |
| Redis stale data | key/session namespace | run-specific prefix + flush disposable DB |
| slow despite bypass | provider latency or evaluator | separate transport and engine timings |
| TestClient hangs | sync/async lifespan mismatch | direct lifespan context |
| unclosed client | fixture finalizer | await close in finally |

## 附录 E：安全与合规

Benchmark 只使用 disposable 数据库和 test identities。题目文件、模型响应、trace 和 report 不得包含生产 JWT、MinIO credentials、Redis password 或完整 Anthropic/Mimo headers。CI artifact retention 应按项目 policy 设置；失败日志使用 question id 而非完整 prompt。

## 附录 F：可逆迁移策略

CI 先增加 opt-in `--runner inprocess`，保留 `--runner http`。连续两批 A/B 后才切默认；任何 parity、resource leak 或 pass-rate regression 都回退 flag，而不是回滚 production。该策略使路线 B 可逆且符合 W19 选项 A。

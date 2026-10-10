# L-14 交接：DB 密码轮换导致的测试失能与硬编码残留

> **交接时间**：2026-10-09
> **交接方**：desktop-conversion 会话（已完成诊断与第一批修复，**未提交**）
> **接手方**：microbubble-agent 仓的 agent
> **性质**：纯环境/文档问题，**代码逻辑无缺陷**

---

## 零、接手前必读：父仓工作树是共享的

`E:\microbubble-agent` 父仓**被多个 agent 会话同时使用**。本轮实测到：

- 本窗口的 9 个文件改动**与别的会话的改动混在同一工作树**
- 别的会话在期间提交了 `text_splitter.py`（+88 行）、`multimodal_extraction_service.py` 等
- 曾出现"agent 报告文件被并发修改"（`7db39f2b1` 被别的会话代为提交）

**接手第一件事**：`git status` 看清工作树，**只 `git add` 自己要改的文件**，绝不 `git add -A`。

---

## 一、根因（一句话）

**DB 密码轮换过，仓库里 25 个文件仍硬编码轮换前的旧密码 `microbubble2026`，
用它们跑测试会精确复现 `InvalidPasswordError`。**

**代码本身没坏** —— 用 `.env` 现值跑 `tests/test_auth.py` → **8 passed in 39.28s**。

### 错误传播链

`tests/conftest.py:44-50`：
```python
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    _settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
                          .replace("/microbubble", "/microbubble_test"),
)
```
它**只借用 `DATABASE_URL` 的凭据+host，只换库名**。
所以 `DATABASE_URL` 密码错 → 测试 URL 密码也错 → `InvalidPasswordError`。

### 本机跑测试需要的三个条件（缺一即失败）

| # | 条件 | 本机现状 |
|---|---|---|
| 1 | `TEST_DATABASE_URL` + `DATABASE_URL` **两个都设** | ❌ shell 里**双 UNSET** |
| 2 | 密码用 `.env` 现值（旧值失效） | ❌ 文档里全是旧值 |
| 3 | 只能在容器内跑（db 容器**未发布主机端口**） | `docker port` 输出为空 |

**可用的跑法**（实测通过，密码从 `.env` 取，勿硬编码）：
```bash
cd E:/microbubble-agent
PW=$(grep '^DATABASE_URL=' .env | sed 's|.*postgres:\([^@]*\)@.*|\1|')
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://postgres:${PW}@db:5432/microbubble_test" \
             -e DATABASE_URL="postgresql://postgres:${PW}@db:5432/microbubble_test" \
             microbubble-agent-app-1 python -m pytest tests/test_auth.py -q --no-header
```

> ⚠️ **真实容器名是 `microbubble-agent-db-1`**，不是 `microbubble-agent-postgres-1`
> （CLAUDE.md 原本写错了，本窗口已改）。

---

## 二、已完成（第一批，未提交）

**9 个文件，+48/-18，复验全绿**：

| 文件 | 改动 |
|---|---|
| `CLAUDE.md` | `:611` 容器名 `postgres-1` → `db-1` |
| `docs/CLAUDE-history.md:6575` | 命令改为从 `.env` 取密码 |
| `memory/database-engine-singleton-bug-2026-07-20.md:80` | 同上 |
| `docs/qa-bench-isolation-stack.md:99` | 同上 |
| `tests/realenv/README.md` | **2 处**（不是 1 处），同上 |
| `scripts/auto_intake_rollback.py:24` | 静默 fallback → fail-loud |
| `scripts/bench_cold_hot_routing.py:52-53` | 同上（改为 `get_dsn()` 从 env 取完整 DSN） |
| `scripts/clean_project_descriptions.py:44` | 同上（**保住了 `_get_db_password()` 的 `.env` 路径**，只改最后一层 fallback） |
| `scripts/migrate_projects_cleanup.py:41` | 同上 |

### scripts 的修法语义（不是换密码，是改行为）

```python
# 改前：静默用错密码
DB_PASS = os.environ.get("DB_PASS", "microbubble2026")

# 改后：缺 env 就报错退出
DB_PASS = os.environ.get("DB_PASS")
if not DB_PASS:
    raise SystemExit(
        "DB_PASS 未设置。密码已轮换, 不再内置默认值。\n"
        "从 .env 取当前值: export DB_PASS=$(grep '^DATABASE_URL=' .env "
        "| sed 's|.*postgres:\\([^@]*\\)@.*|\\1|')"
    )
```

**理由**：静默 fallback 到失效密码比直接报错更糟——让人以为连对了库。

### 已完成的验证（可复核）

- ✅ **凭据泄露检查：所有 git tracked 文件零个 `mnbEnf`**（新密码没进 git）
- ✅ `grep microbubble2026 <9 文件>` = 空
- ✅ 4 个 scripts `py_compile` 全 PASS
- ✅ **fail-loud 实测**：缺 env 时 `SystemExit` 正确触发

---

## 三、待做（4 项，按优先级）

### 【P1】2 个未归档的 tests 跟上项目惯例 ⭐ 建议下一个做

**文件**：
- `tests/test_drive_pr9_comment_delete.py:44-47`
- `tests/test_drive_v2_pr17_dedupe.py:42-45`

**现状**（⚠️ 勘误：不是"完全硬编码"，是 `os.getenv` 带**过期默认值**）：
```python
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:microbubble2026@db:5432/microbubble_test")
```

**关键事实**：
- **未归档**（`tests/ARCHIVED.md` 里没有）→ 会真跑
- 实测用正确密码 → **16 passed in 64.80s**，旧密码是唯一问题
- **CI 是绿的**：`server-tests-baseline.yml:117` 已显式设 `TEST_DATABASE_URL`，env 覆盖掉旧默认值
  ⇒ **不是 CI 恒红点，是"本地/新同事手跑时的地雷"**

**项目已有标准答案**（`tests/conftest.py:52-54`）：
```python
def get_test_database_url():
    """测试库 URL — 测试内自建 engine 用 (原生产 URL 回退的替代, 2026-09-12)"""
    return TEST_DB_URL
```
conftest 注释已写明 2026-09-29 那次轮换就解决过此问题，**这两个文件漏改了**。

**建议改法**（改动最小，沿用既有惯例）：
```python
from tests.conftest import get_test_database_url
TEST_DATABASE_URL = get_test_database_url()
```
**保留各自自建的 `test_engine`/`db` fixture 不动**——它们刻意绕过 conftest 的 db fixture
（docstring 说明是为躲 alembic 057 问题），不要一并改掉。

**改完必须验**：用上面的 `docker exec` 命令跑，应仍是 16 passed。

---

### 【P2】剩余 11 个硬编码旧密码的文件

**配置模板类**（改成占位符或指向 env）：
- `.env.example`
- `observability/grafana/provisioning/datasources/default.yaml`

**scripts 类**（照第一批的 fail-loud 模式改）：
- `scripts/dump_prod_to_fixture.sh`
- `scripts/verify_realenv_e2e.sh`
- `scripts/pg-exporter/slow-query-helper.sh`

**tests 类**：
- `tests/qa-bench/gen_base.py:931`
- `tests/qa-bench/gen500.py:931`
- `tests/pg_exporter/test_compose_service_defined.py:116`（**仅注释文字**，非可执行 URL，优先级最低）

**⚠️ 生产/CI 路径，需单独验证后再动**：
- `docker-compose.yml` + `docker-compose.dev.yml`
  —— 是 `${POSTGRES_PASSWORD:-microbubble2026}` **fallback 默认值**（生产实际走 `.env`，
  仅 `.env` 缺失时生效）。改生产 compose 按 **类 20.215** 必须：
  ```bash
  docker compose config                                    # 语法验证
  docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' <核心容器>  # 抽验
  ```
  ⚠️ 类 20.215 血泪教训：上次注释实验块时把 `healthcheck` 和 `restart` 一起注释掉，潜伏整月
- `.github/workflows/qa-bench-smoke.yml`（158/218/265/272/294 行，共 5 处）
  —— 需决定 secrets 处理方式

**不做**：`docs/archived/` 下 7 个文件（按 CLAUDE.md 档案铁律，历史快照保持原样）

---

### 【P3】两处过期自引用（本窗口发现，未改）

`CLAUDE.md:612` 与 `:360` 都写着「CLAUDE.md 752 行铁律」，但：
- CLAUDE.md 现为 **773 行**
- 2026-09-30 三层重排已把历史挪到 `docs/CLAUDE-history.md`

⇒ **自引用的行号已失效**。建议改成不带行号的引用（如"见 CLAUDE.md 重启纪律段"）。

---

### 【P4】jose 加密层无直测（**增强，非修复，建议单独立项**）

`tests/test_auth.py` 的 8 个用例全是 **HTTP 层**（登录/刷新/鉴权/限流），
jose 的 encode/decode 只被**间接**覆盖（通过 `/auth/login` 返回的 token）。

**缺**：token 篡改检测、过期处理、**alg confusion 攻击**
（把 `alg` 改成 `none`，或从 RS256 换 HS256 的经典攻击）。

> ⚠️ 我们刚升级了 `python-jose` 3.3.0 → 3.4.0（认证核心）。虽然已用独立脚本实测
> **新旧版 token 逐字节相同**、双向可解，但那是临时手段，**不是常态化保障**。

---

## 四、纪律提醒（踩过的坑，别重犯）

1. **绝不能把新密码写进任何 git 文件**。`.env` 是 gitignore 的，新密码进 git = 凭据泄露。
   正确做法是**改成"读 `.env`/环境变量"**，不是"把新值替换进去"。
   每次改完必跑（**git ls-files 驱动**，只遍历版本控制内的文件 —— 未跟踪的 worktree
   副本、`.env`、`data/`、`web/dist/` 天然不会出现，无需手工写 exclude 过滤）：
   ```bash
   git ls-files | grep -E '\.(md|py|sh|yml|yaml|example)$' \
     | xargs grep -l -e 'mnbEnf' -e 'microbubble2026' 2>/dev/null
   ```
   —— 期望**无输出**。

   ⚠️ **两个串都要搜**：本文档正文用的是 `microbubble2026`（已轮换的旧值），
   而纪律条目里历史上写成 `mnbEnf`。只搜其中一个会**假阴性** —— 看起来"干净"，
   实际根本没搜到目标串。`git ls-files` 版本不落盘密码字面量，符合第 2 条纪律。

   **预期残留（非零也正常）**：L-14 收尾后活代码/活配置已清零，但
   `docs/archived/`、`memory/` 下的历史记录**刻意保留旧串** —— 那是事故复盘的事实
   原文，改掉会失真。判定标准是「剩下的命中是否都在归档目录」，而不是「总数是否为 0」。

2. **`.env` 里的真密码不要写进本文档/对话/日志**。本文档所有命令都用 `$(grep ... .env)` 现取。

3. **同文件并行编辑会互相覆盖**。本轮 3 个 agent 并行改 `requirements.txt`，
   agent B/C 都报告"文件被并发修改"，**所幸三处落在不同区段**（第 4/83/90 行）才没出事。
   ⇒ 派多个 agent 改同一文件时，要么串行化，要么确保改不同区段。

4. **Windows 本机 pip 读 UTF-8 文件会报 `UnicodeDecodeError: 'gbk' codec`** ——
   加 `PYTHONUTF8=1` 即可。**这不是缺陷**（文件本身 UTF-8 无 BOM 正常，容器是 Linux UTF-8，
   既有中文注释早已存在且 CI 从未出问题）。

5. **本机没装 psycopg2**（`scripts/` 大多 import 它就断），
   要验脚本逻辑得先建 venv 装依赖，或进容器跑。

---

## 五、一句话结论

**测试没坏，代码没坏。** 8 passed / 16 passed 都证明功能正常。
问题纯粹是「**密码轮换后，25 个文件没跟着更新**」，其中：
- 第一批 9 个**已修完待提交**
- 2 个 tests 跟上 conftest 惯例即可（P1）
- 剩余 11 个分批处理，生产 compose / workflow 需单独验证（P2）

**与 L-12 同一种病**：门禁在，但你不知道它跑没跑。
区别是 L-12 是超时被吞，L-14 是密码错导致测试根本没执行。

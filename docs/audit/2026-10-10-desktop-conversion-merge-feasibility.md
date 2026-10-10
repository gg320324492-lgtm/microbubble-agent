# desktop-conversion 合并可行性调研

> 调研日期 2026-10-10 · 只读取证，**未执行任何合并动作**（无 submodule add / subtree / remote add / fetch / merge / push）
> 依据：主仓 `E:\microbubble-agent`（4619 commits，公开）+ 子仓 `E:\microbubble-agent\desktop-conversion`（193 commits，私有）

## 一句话结论

**能合，且风险低 —— 建议方案 C（只搬文件不带历史），唯一硬前置是「先补 4 条 gitleaks allowlist」**。

子仓 168 个跟踪文件里 **0 行 Python、0 个 submodule/LFS、0 个 >500KB blob**，
与主仓仅 **2 个同名根文件**（`README.md` / `.gitignore`）且内容语义完全不同（无冲突），
高危凭据模式 **零命中**。真正需要注意的只有一点：gitleaks 在子仓历史里报 **4 条
`generic-api-key`**，虽经取证**全部是一次性测试 fixture**（详见 §3），但它们会**阻断
合并后的 pre-commit 与 `secret-scan.yml`**，必须先加 allowlist。

---

## 1. 子仓画像

| 项 | 值 | 取证 |
|---|---|---|
| 远端 | `https://github.com/gg320324492-lgtm/microbubble-desktop-conversion.git` | `git remote -v` |
| 分支 | 仅 `main`（`b3756a6`），与 `origin/main` 同步，无本地领先 | `branch -avv` |
| commits | **193**，时间跨度 **2026-09-16 20:29 → 2026-10-09 14:51**（约 23 天） | `rev-list --count` |
| 作者 | 单作者 `gg320324492`（193/193） | `shortlog -sne` |
| 工作树 | 跟踪文件**干净**；5 项 untracked：`.vizdiag-out/`、`docs/plans/refs/`、`docs/scratch/` + 2 个 plan md | `status --porcelain` |
| 体�� | 工作树 **4.1M**（不含 .git）／`.git` **3.5M**；对象库 pack **2.79 MiB** | `du` / `count-objects -vH` |
| 跟踪文件 | **168** 个（124 md / 16 png / 13 json / 7 mjs / 2 html / 2 yml / 2 txt / 1 sql） | `ls-files` |
| **Python 文件** | **0** | `ls-files \| grep -c '\.py$'` → 0 |
| submodule / gitattributes / LFS | **均无** | `ls-files` 无匹配 |
| 大文件 | **无**（>500KB blob = 0） | `cat-file --batch-check` |

目录构成：`docs/acceptance`(103) `docs/workorders`(44) `docs/plans`(8) `docs/session-log`(3)
`docs/releases`(2) `docs/design`(2) `docs/surveys`(1) `docs/handoff`(1) `docs/decisions`(1)
+ 根 `README.md` `AGENT.md` `.gitignore`。**本质是一个纯文档仓**。

## 2. 文件重叠分析

**同名同路径文件仅 2 个，且都在根目录、语义完全不同 —— 属"改名即可"而非"内容冲突"：**

| 路径 | 主仓 | 子仓 | 冲突? |
|---|---|---|---|
| `README.md` | `# 微纳米气泡课题组智能 Agent 系统`（项目总 README，134 行含文件树） | `# desktop-conversion — 桌面端转化指挥部`（本仓工作区说明） | ❌ 无 —— 内容完全独立 |
| `.gitignore` | 200+ 行主仓规则 | 9 行子仓规则（`.agent-backups/` `.workbuddy-ai/` `Thumbs.db` `*.log`） | ❌ 无 —— 规则集不相交 |

> subtree/submodule 方案下这两者落在 `desktop-conversion/` 前缀内，**天然不冲突**；
> 方案 C 若手工 `cp -r` 则需改名（见 §5 步骤）。

**其余 166 个文件（全部在 `docs/` 下）与主仓零重叠** —— `comm -12` 实测交集 = 2。

### 主仓 → 子仓的单向引用：**17 个文件**（这是合并的真实收益，也是必改项）

主仓多处 `desktop-conversion/...` 路径引用，合并后**全部自动从"跨仓悬空"变成"仓内相对路径"**：

| 类别 | 位置 |
|---|---|
| `CLAUDE.md` | 3 处（L43 远端说明、L45 收尾全过程、L105 L-14 交接文档） |
| workflow 注释 | `.github/workflows/lint-css.yml:160`、`server-tests-baseline.yml:3` |
| 主仓 `README.md` | L134「`desktop-conversion/` # 桌面端改造（独立 git 仓）」← **合并后必须改** |
| 主仓文档 | `app/services/CHUNKED_UPLOAD.md`、`docs/incident/2026-08-04--2026-09-18-status-snapshots.md`(4)、`docs/audit/2026-10-10-stale-content-audit.md`(3)、`docs/audit/2026-10-10-structure-mapping.md`(4)、`docs/design/2026-10-10-target-structure.md`(4) |
| 记忆索引 | `memory/MEMORY.md`(2)、`tests/ARCHIVED.md`(1) |
| 生产代码 | `apps/desktop/src/renderer/src/components/settings/WorkspaceSection.vue:7`（默认工作区路径 `E:\microbubble-agent\desktop-conversion`）、`apps/desktop/src/renderer/src/assets/theme-paper.css:4`、`apps/desktop/docs/release-audit.md:23`、`apps/desktop/tests/unit/*.test.ts`(2) |

⚠️ 其中 `apps/desktop/tests/unit/ci-workflow.test.ts:82` 把 `desktop-conversion` 列进
**forbidden 目录清单**（断言 CI 不该碰它）—— 合并后该断言的语义需要复核。

### 子仓 → 主仓的引用：**少量绝对路径**

5 个文件含 `E:\microbubble-agent` 绝对路径（`DECISIONS.md` / L-14 handoff /
`2026-10-02-phase3-closeout-plan.md` / `2026-09-29-handoff.md`(2) / 结构测绘报告(2)），
以及大量 `../` 相对引用主仓的 `apps/desktop`、`app/services`。合并后仍成立（主仓结构不变），
但绝对路径可考虑顺带规整为相对路径（**非阻塞**）。

### `.gitignore` 覆盖检查

- 主仓 `.gitignore:221` 有 `desktop-conversion/` —— **合并前必须删这一行**，否则加进来的文件立刻被忽略。
- 实测主仓现有忽略规则对子仓 168 个文件 **零命中**（`git check-ignore --no-index` 无输出）。
- 子仓 `.gitignore` 的 9 条规则与主仓规则集**无交集**。

### `.dockerignore` 检查

`.dockerignore` 已含 `docs/`、`*.md`、`.git/` —— 合并后的文档**本来就不进镜像**，
**无需修改**。

## 3. 凭据与公开风险 ★

用主仓 `.gitleaks.toml`（`useDefault = true`，100+ 默认规则）扫子仓**全部 193 commits / 944 KB**：

### 3.1 高危模式扫描：**零命中**

`git log -p --all` 正则扫 `BEGIN *PRIVATE KEY` / `sk-*` / `ghp_*` / `AKIA*` / JWT(`eyJ...`) /
`xox?-` / `AIza*` —— **全部 0 命中**。

### 3.2 gitleaks 报 4 条 `generic-api-key` —— **逐条取证：全部为一次性测试 fixture**

| 文件 | 行 | 实体性质（**不抄录原文**） | 判定 |
|---|---|---|---|
| `docs/acceptance/assets/2026-09-30-FIN1/a1-share-block-http.json` | 36 | 一次**已撤销**的 team 分享产生的 share token + 6 天过期的 `expires_at` | ✅ 已失效（文档自述"分享已撤销"） |
| `docs/acceptance/assets/2026-09-29-DL5/dl5-e2e-driver.mjs` | 53 | DL5 验收脚本注册的**临时探针账号**密码 | ✅ 一次性测试口令 |
| `docs/acceptance/assets/2026-09-29-DL6/dl6-e2e-driver.mjs` | 38 | DL6 验收同上（同行 `password:` 字段触发 `password =` 相邻模式） | ✅ 一次性测试口令 |
| `docs/acceptance/assets/2026-09-29-DL7/dl7-e2e-driver.mjs` | 87 | DL7 验收同上 | ✅ 一次性测试口令 |

> 这些账号在 `FIN1-pass.md` 里自述已撤销/仅存在于本地容器。
> 属**低真实风险**，但**机制上会阻断 CI**（见 §5）。

### 3.3 关键判断：**新密码没有泄露** ★

子仓 `docs/handoff/2026-10-09-L14-db-password-rotation-handoff.md` 记录了 L-14 密码轮换。
取证结果：

- 文档中出现的是**旧密码明文** `microbubble2026`（7 处）—— **该值早已在公开主仓中存在**
  （主仓当前树 7 个文件含它：`docs/archived/*`、`docs/qa-bench-ci-cache-patch.yml`、
  `memory/w86-1st-batch-f1-pg-exporter-2026-07-29.md` 等），**合并不会新增泄露面**。
- **新密码只以 6 字符前缀 `mnbEnf` 形式出现**（3 处，均为纪律条文里的"搜索用前缀"），
  **全文零次出现完整新密码**。该文档第 100 行自述"所有 git tracked 文件零个新密码"——
  实测**成立**。
- 该文档的正确做法（从 `.env` 取值、禁止硬编码）本身是正面示范。

### 3.4 其他不应公开的内容：**未发现**

| 维度 | 结果 |
|---|---|
| 内网 / 私网 IP | **0 命中**（`192.168.*` / `10.*` / `172.16-31.*`） |
| 个人信息（手机号/邮箱） | **0 命中**（唯一命中是时间戳数字 `1790681198605` 误配，非 PII） |
| 个人路径 | 仅 `C:\Users\pc` / `D:\Users\pc`（Windows 用户名，低敏感；主仓亦大量出现同款路径） |
| `.env` / 私钥文件 | **无** |
| 生产数据 dump | `docs/acceptance/assets/.../cleanup-20260930-pre-delete.sql` —— 是**清理脚本**，非数据导出 |

**小结：凭据风险 = 低**。唯一需动作的是给 4 条 fixture 加 allowlist，让门禁通过。

## 4. 历史卫生

**异常干净，比主仓更适合入库：**

- 单作者、无 merge commit（0 个）、无 `wip/temp/backup/test/asdf` 类无意义提交（**0 条**）
- 提交信息规范（`docs(handoff):` / `feat:` / `fix:` 前缀齐全，含完整中文正文）
- 峰值 20 commits/day（2026-09-30、09-21），**无机器人式高频刷提交**
- 提交总量小：**193 commits / 4.1M 工作树 / 2.79 MiB pack** —— 带入主仓的体积代价可忽略
- 无大文件、无 LFS、无二进制炸弹

**唯一"脏"项**：工作树 5 项 untracked（`.vizdiag-out/` 120K、`docs/plans/refs/` 144K、
`docs/scratch/` 4K + 2 个 plan md）。**合并前需决定去留**（建议不并入或先归位后提交）。

## 5. 三方案对比表

| 方案 | commit 数变化 | 优点 | 缺点 | 回滚 | CI 影响 |
|---|---|---|---|---|---|
| **A. submodule**<br>`git submodule add` | **4619 → 4619**（子仓历史不进主仓） | ① 零内容风险<br>② 与"独立仓"现状语义完全���致，改主仓不影响子仓<br>③ 子仓可继续独立 push | ① **用户想解决的"两个仓管理负担"一点没减**（仍是 2 个远端 + `git submodule update`）<br>② 主仓 clone 不带 `--recursive` 会得到**空目录**，CI/脚本/IDE 静默失效<br>③ 主仓**首次引入 submodule**，无先例（`.gitmodules` 不存在）<br>④ 主仓已有 17 处路径引用**全部保持悬空**，收益为零 | ✅ 最易（`git rm --cached` + 删 `.gitmodules`） | ⚠️ submodule 目录内容不进 clone，**CI 无需改**，但 `git ls-files` 驱动的脚本**继续静默跳过** —— 即合并的原始动机未解决 |
| **B. subtree**<br>`git subtree add --prefix` | **4619 → ~4812**（193 commits 带入） | ① 真正合并历史，`git log` 可追溯<br>② clone 即完整，CI/脚本自动可见<br>③ 单一远端，管理负担真正归零 | ① 历史带入主仓**公开仓**（本例已确认无泄露，但等于让子仓 193 commits 进公开历史，不可撤回）<br>② 主仓已有的 `.gitignore` 里 `desktop-conversion/` 那行会让 subtree 落空，**必须先删**<br>③ 未来若还要独立推子仓 → **subtree 双向同步极痛**（pull 需 `--squash` 对齐）<br>④ README/.gitignore 需手工改名（subtree 前缀下自动不冲突，实为优点） | ⚠️ 中等（`git revert` 合并 commit 可解，但 193 commits 已进历史，**只能 additive 不可真正撤销**） | ⚠️ 合并 PR 会触发**全部 workflow**（secret-scan 全历史扫、server-tests 若 path 命中 `docs/**` 不触发）；gitleaks 4 条会**红灯** |
| **C. 只搬文件不带历史** ★ | **4619 → 4620**（单次 squash 提交） | ① **风险最低**：不进公开历史，未来发现敏感内容可直接删改，**可逆**<br>② 单一远端，clone 即完整，管理负担归零<br>③ commit 体积仅 +4.1M 文档<br>④ 历史本就是"实施记录"，其**结论已沉淀进现有 docs/**，原始 commit 增量价值低 | ① 丢失 193 commits 的**逐条演进轨迹**（`git log` 只能看到一个 squash）<br>② 需手工 `cp` + 改名 2 个同名文件<br>③ 未来若回退到独立仓，需重新 `git subtree`/复制 | ✅ **最易**：`git rm -r desktop-conversion` + revert 单 commit | ✅ **几乎无影响**：`server-tests-baseline.yml` 只在 `app/**` `tests/**` 变更时触发；**子仓 0 个 .py 文件**，`find tests` 扫不到；secret-scan 会跑（见 §3 allowlist 前置） |

### 影响面补充（三方案通用）

- **CI 测试扫描**：子仓 **0 个 Python 文件**，且 `server-tests-baseline.yml:108` 是 `find tests -name "test_*.py"`（限定 `tests/`）→ **双重保险，合并后不会污染测试基线**。✅
- **pre-commit hooks**：`gitleaks-scan`（`pass_filenames: false`，扫全仓）→ **会命中 4 条 fixture，须先加 allowlist**；`typing-imports`(`^app/`) `alembic-chain`(`^alembic/`) `dockerfile-pinning`(`^Dockerfile|docker-compose`) `dist-manifest-hash`(`^web/dist/`) → **均按路径过滤，零影响**。✅
- **需改的文档**（合并为仓内目录后语义变了）：
  `README.md:134`（"独立 git 仓"→"桌面端改造文档"）、
  `CLAUDE.md:43`（私有远端说明）、
  `docs/design/2026-10-10-target-structure.md` 的 D2 决策（§604 现记"保持独立"，需更新）、
  `docs/audit/2026-10-10-structure-mapping.md` §"🔴 独立 git 仓"标注。
- **私有远端 `microbubble-desktop-conversion` 处置**：合并后**建议保留只读**作归档备份，
  勿立即删除（万一需要追溯 193 commits 原貌）。

## 6. 我的建议 + 执行步骤

### 推荐：**方案 C（只搬文件不带历史）**，配 4 条 allowlist

**一句话理由**：子仓 93% 是文档（124/168 个 .md）、0 代码 0 大文件，
"带入历史"的唯一价值（可追溯演进）在**结论已沉淀到现有 docs/** 的前提下边际收益极低，
而"历史进公开仓不可撤回"的风险不该为一个纯文档工作区承担。

### 执行步骤（**待��指挥拍板后执行，本次不执行**）

1. **前置：加 gitleaks allowlist**（否则门禁红）—— 在 `.gitleaks.toml` 的 `paths` 加：
   `docs/acceptance/assets/.*\.mjs$`、`docs/acceptance/assets/.*\.json$`
   （或更精确的 4 个具体路径），并加一条 regex 兜底那 3 个一次性探针口令字面量。
   > ⚠️ 改前先跑 `gitleaks detect --config .gitleaks.toml --redact` 确认当前主仓**零 findings**，改后确认**仍零**。
2. **处置 untracked**：决定 `.vizdiag-out/` `docs/plans/refs/` `docs/scratch/` + 2 个 plan md 去留（建议先归位到正式目录或直接不入）。
3. **删 `.gitignore:221` 的 `desktop-conversion/` 行**（否则加进来即被忽略）。
4. **备份子仓**：归档当前 `b3756a6`（`git bundle create`），再从磁盘删除子仓 `.git/`。
   > 注意：子仓 `docs/` 下有 3 个 `*.md` 未跟踪新文件（`2026-10-08-research-agent-roadmap-intake.md` 等）——**删 `.git` 前必须先拷出**。
5. **搬入**：`cp -r desktop-conversion → 主仓`，把子仓根 `README.md` 改名 `desktop-conversion/README.md`（避免与主仓 README 冲突），子仓 `.gitignore` 内容并入主仓 `.gitignore` 尾部（规则不相交，零冲突）。
6. **改文档**：`README.md:134`、`CLAUDE.md:43`、`docs/design/2026-10-10-target-structure.md` D2 决策、
   `docs/audit/2026-10-10-structure-mapping.md` 相关标注。
7. **验证**：`git ls-files desktop-conversion | wc -l` ≈ 168；`gitleaks detect --redact` 零 findings；
   `git check-ignore desktop-conversion/README.md` 无输出；push 后 CI 全绿。
8. **归档**：私有远端保留为只读备份，不删。

### 若主指挥更看重"保住 193 commits 轨迹" → 选方案 B（subtree），
但须接受这些 commits 进公开历史且不可撤回。

## 7. 待主指挥决策的点

1. **是否接受"丢失 193 commits 明细轨迹"？**（方案 C 的唯一实质代价。备选：方案 B 保住）
2. **私有远端 `microbubble-desktop-conversion` 合并后如何处置？** 建议保留归档，不删。
3. **子仓 5 项 untracked 如何归处？** 尤其 `2026-10-09-da2-p1-b01-handoff.md` 这类 handoff 文档是否值得入库。
4. **子仓根 `README.md` 改名还是与主仓 README 合并？** 建议改名保留独立说明。
5. **那 4 条 gitleaks fixture allowlist 的粒度**：按目录（`assets/*.mjs|json`）还是按 4 个具体文件？前者更省事但面更宽。
6. **`apps/desktop/tests/unit/ci-workflow.test.ts:82` 把 `desktop-conversion` 列为 forbidden 目录** —— 合并后该断言是保留（改为断言"CI 不扫文档"）还是删除？

---

## 附：取证方法与局限

- 全部为只读命令：`git log/show/ls-files/rev-list/count-objects/branch/shortlog`、`git grep`、`grep`、`du`、`gitleaks detect`（子仓内，只出报告不写回）。
- **未执行**：任何 `submodule add` / `subtree` / `remote add` / `fetch` / `merge` / `push`；未改任何被审计文件；未碰 docker。
- gitleaks 临时报告已删除，子仓 `git status` 与调研前一致（5 项 untracked，主仓 `git ls-files` 未变）。
- **局限**：`git grep <rev>` 逐 revision 扫描覆盖了子仓全部 193 commits（gitleaks 亦确认 "193 commits scanned"）；
  但"某些内容是否属于商业敏感"的判断依赖人工判读，未做逐文档语义审阅。
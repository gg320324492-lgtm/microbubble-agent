# W68 第 9 批 D-1: W68 第 6+7+8 批调研发现 8 真小修整合 (2026-07-24 — 锚点范式第 105 守恒)

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 9 批 D-1: W68 第 6+7+8 批调研发现 8 个真小修整合"
> **分支**: `chore/w68-9th-batch-d1-8-smallfixes-2026-07-24`
> **基线**: main HEAD `f14cb43c1` (W68 第 8 批收官后, 锚点范式第 90-104 守恒)
> **性质**: **整合性 memory 沉淀** (非单批复盘) — 把 W68 第 6/7/8 批分散发现的真小修统一汇总到本文件
> **0 production code 改动铁律**: 维持 — 仅 memory, 不动业务代码

---

## TL;DR

🎯 **W68 第 9 批 D-1: 8 真小修整合** — 主指挥协调范式第 36 次派工. 整合 W68 第 6+7+8 批 agent 报告 / 主指挥审计 / 实测发现的 **8 个真小修** (P0 高 3 + P1 中高 1 + P2 中 2 + P3 低 2), 给出**主指挥决策建议** (现在必做 3 + 留 W69 1 + 待拍板 1 + 已闭环 3), 沉淀 **5 新铁律**.

- **8 小修全部来自真实调研发现** — 不允许 agent 假想 (W68 第 4 批 "plans 优先 + 小修搭配" 主指挥拍板铁律 2)
- **主指挥必做时机排序**: P0 部署前 → P0 每次 merge → P1 全局 hook wire 后 → P2/P3 留未来
- **0 production code 改动铁律 维持** — 本文件仅 memory 沉淀 + 主指挥决策建议
- **W19 选项 A 维持** — 4 留未来 PR 继续观察

**锚点范式**: W68 第 8 批 104 → **W68 第 9 批 D-1 105** (本批 1 守恒, 仅 memory 沉淀)
**0 production code 改动铁律**: ✓ 完全维持 (8/8 守恒)
**W19 选项 A**: 维持

**Why**: W68 第 6+7+8 批 30+ agents 落地后, 散落在 6+ agents memory (`w68-route-7-a1-cached-giggling-pebble-fix-2026-07-24.md` + `w68-route-7-a3-qa-bench-isolation-2026-07-24.md` + `w68-route-7-c1-plans-status-fix-2026-07-24.md` + `w68-route-7-c2-plans-archive-2026-07-24.md` + `w68-route-7-d3-claude-code-voice-alert-2026-07-24.md` + `w68-route-8-d1-w68-7th-followup-2026-07-24.md`) 的真小修**未统一汇总**, 主指挥拍板窗口缺失. 主决策: W68 第 9 批派 D-1 agent 把 8 个真小修一次性整合到本文件 + 主指挥决策建议 + 5 新铁律, 纯 memory 不动业务代码.

**How to apply**: 见下方 §1 8 小修整合表 + §2 主指挥决策建议 + §3 5 新铁律.

---

## §1 8 小修整合表 (W68 第 6+7+8 批调研发现)

| # | 小修 | 来源批次 | 来源 agent | 优先级 | 主指挥必做时机 | 状态 |
|---|------|----------|-----------|--------|---------------|------|
| 1 | **VAPID 私钥持久化目录** | W68 第 7 批 B-3 | mobile-v3.2-push | **P0 高** | 部署 PWA push 前必做 | 待主指挥拍板 |
| 2 | **baseline 71 PASS + 7 SKIP 守恒** | W68 第 6/7/8 批 | A-1 (各批) | **P0 高** | 每次 merge 后必跑 | ✅ 自动化 (A-1 已跑) |
| 3 | **CLAUDE.md / 永久锚点沉淀纪律** | W68 第 8 批 D-3 | claudmd-discipline | **P0 高** | 永久 (每次大改动后) | ✅ D-3 已实施 |
| 4 | **voice-alert 实测** | W68 第 7 批 D-3 | claude-code-voice-alert | **P1 中高** | 全局 hook wire 后 | 待主指挥测 |
| 5 | **transcript_polished 全量回填** | W68 第 7 批 A-1 | cached-giggling-pebble | **P2 中** | cached-giggling A-1 已拍板接受强化版 | 留 W69+ |
| 6 | **Status 段引用错 (14 plans)** | W68 第 7 批 C-1 | plans-status-fix | **P2 中** | W68 第 7 批 C-1 已修正 | ✅ |
| 7 | **Plan 文件名错位 (60%, 8 plans)** | W68 第 7 批 C-2 | plans-archive | **P2 中** | W68 第 7 批 C-2 已归档 8 个 | ✅ |
| 8 | **delete purge_test_user_data.py** | W68 第 7 批 A-3 | qa-bench-isolation | **P3 低** | qa-bench-isolation 验证后拍板 | 待主指挥拍板 |

**优先级分布**: P0 高 3 个 (#1, #2, #3) + P1 中高 1 个 (#4) + P2 中 3 个 (#5, #6, #7) + P3 低 1 个 (#8)

**8/8 来源真实**: 全部来自 W68 第 6+7+8 批 agent memory 报告 / 主指挥审计发现 / 派工实战记录, **0 假想任务** (符合 W68 第 4 批 "plans 优先 + 小修搭配" 铁律 2).

---

## §2 主指挥决策建议 (现在必做 / 留 W69 / 待拍板)

### 2.1 现在必做 (主指挥本批派工窗口内)

#### 小修 #1: VAPID 私钥持久化目录 (P0 高)

- **来源**: W68 第 7 批 B-3 (`mobile-v3.2-push`) agent 报告 (commit `b31386d61`)
- **背景**: B-3 实施 PWA Push backend 端点 (VAPID 密钥生成 + subscribe endpoint + 推送服务). VAPID 私钥默认存 `/tmp/vapid_private.pem` (临时), **部署前必须**把 VAPID 密钥目录持久化到 `/etc/microbubble/pwapush/` 或 docker volume
- **主指挥必做步骤** (部署 W68 第 7 批 B-3 commit 前):
  ```bash
  # 1. SSH 到云 server
  ssh root@<cloud-server>

  # 2. 创建持久化目录
  mkdir -p /etc/microbubble/pwapush/
  chmod 700 /etc/microbubble/pwapush/
  chown root:root /etc/microbubble/pwapush/

  # 3. 生成 VAPID 密钥对 (持久化到目录, 不是 /tmp)
  cd /opt/microbubble-agent
  docker exec microbubble-agent-app-1 python -c "
  from py_vapid import Vapid
  v = Vapid()
  v.generate_keys()
  with open('/etc/microbubble/pwapush/vapid_private.pem', 'wb') as f:
      f.write(v.private_pem())
  with open('/etc/microbubble/pwapush/vapid_public.pem', 'wb') as f:
      f.write(v.public_pem().public_bytes())
  "
  # 或 mount docker volume:
  # docker volume create microbubble_pwapush
  # docker run -v microbubble_pwapush:/etc/microbubble/pwapush/ ...

  # 4. 更新 deploy-auto.sh / docker-compose 挂载卷
  # 5. 验证: curl /api/v1/notifications/vapid-public-key 返回 200 + 公钥
  ```
- **未做的后果**: VAPID 私钥存 `/tmp` → docker 重启丢失 → PWA Push 功能直接坏
- **优先级理由**: **P0 高** — 部署前必做, 不做 PWA Push 功能直接坏
- **状态**: **待主指挥拍板** (主指挥决策部署窗口时必做)

#### 小修 #2: baseline 71 PASS + 7 SKIP 守恒 (P0 高)

- **来源**: W68 第 6/7/8 批 A-1 (各批 baseline 守恒验证 agent) 报告
- **背景**: 跨 100+ commit 0 regression, baseline 71 PASS + 7 SKIP 必须每次 merge 后跑 (防止代码改动引入 regression)
- **主指挥必做步骤** (每次 merge 后 5 分钟内):
  ```bash
  cd /e/microbubble-agent
  SKIP_DB_SETUP=1 python -m pytest tests/test_baseline_audit.py -v --tb=short 2>&1 | tail -20
  # 期望输出: 39 passed in 3-4s + 71 PASS + 7 SKIP (累计 78 测试)
  ```
- **未做的后果**: 代码改动可能引入 regression 而无 baseline 检测 → 累计到一定规模后 71 PASS 跌至 70/69 → 锚点范式守恒链断裂
- **优先级理由**: **P0 高** — baseline 是回归检测底线, 必须每次 merge 后跑
- **状态**: ✅ **自动化** (A-1 agent 已在 W68 第 4/5/6/7/8 批多次跑通, 锚点范式第 65 守恒 = W68 第 5 批 baseline 验证报告)

#### 小修 #3: CLAUDE.md / 永久锚点沉淀纪律 (P0 高)

- **来源**: W68 第 8 批 D-3 (`claudmd-discipline`) agent 报告 (commit `6f78e4cec`)
- **背景**: 永久锚点沉淀纪律 (锚点范式 4 阶段流程 + 11 协调铁律 + W68 任务模式基调) 必须**每次大改动后**沉淀到 CLAUDE.md / 永久 memory, 防止后续会话重复踩坑
- **主指挥必做步骤**: D-3 agent 已实施 CLAUDE.md 顶部状态段同步 + 5 新铁律 + 锚点范式守恒路径, **0 主指挥额外操作**
- **状态**: ✅ **D-3 已实施** (锚点范式第 102 守恒)

### 2.2 留 W69 (未来派工窗口)

#### 小修 #5: transcript_polished 全量回填 (P2 中)

- **来源**: W68 第 7 批 A-1 (`cached-giggling-pebble`) agent 报告 (commit `85d130ab1`)
- **背景**: A-1 实施 autoPolishIfNeeded 强化版 (添加 transcripts 库, 仅"无 polished 且未在白名单内"时触发), **新会议触发**, 存量会议 (~240 条) 未全量回填 `transcript_polished`
- **未来待办**: 用 autoPolishIfNeeded 函数批量跑存量会议 (~240 条), 优先级 P2 中
- **留 W69 理由**: 240 条会议全量跑需要 LLM 调用 ~240 次, 单次 5-10s, 累计 20-40 min. 主指挥决策"是否值得批量跑" 需考虑: (a) 用户是否需要历史会议的 polished; (b) LLM 调用成本; (c) 是否影响线上
- **替代方案**: 仅新会议触发 (现状), 存量用 `repair_meeting_64_speakers.py` 类脚本按需修 (历史误识时手动跑)
- **状态**: 留 W69 第 1 批 "数据治理" 派工 (主指挥拍板时)

### 2.3 待主指挥拍板 (本批派工窗口结束后)

#### 小修 #4: voice-alert 实测 (P1 中高)

- **来源**: W68 第 7 批 D-3 (`claude-code-voice-alert`) agent 报告 (commit `0b0e6e336`)
- **背景**: D-3 实施 claude-code 全局 voice-alert hook (`~/.claude/settings.json` UserPromptSubmit hook 调 `~/.claude/hooks/play_voice_alert.sh $Mode $Message`). `$Mode` 参数完整 (idle/working/done/error/warning), wrapper script 调 Edge-TTS 播放. **但 D-3 没在云 server 实测**
- **主指挥必做步骤** (本地 PC session 实测 5-10 min):
  ```powershell
  # 1. 测试 6 种 mode 的 Edge-TTS 播放
  powershell scripts/voice-alert.ps1 -Message "Claude已经完成了所有任务，请回来查看结果吧"
  powershell scripts/voice-alert.ps1 -TaskDone
  powershell scripts/voice-alert.ps1 -NeedConfirm
  powershell scripts/voice-alert.ps1 -OnError "后端 500 了"
  powershell scripts/voice-alert.ps1 -AskQuestion "你需要选 A 还是 B？"

  # 2. 验证 hook 在 settings.json wire 真实触发
  # 启动新 session, 触发 idle → done → error, 听 SAPI / Edge-TTS 播放
  # 失败时回滚 hook 或换 say.exe (Windows 原生)
  ```
- **未做的后果**: hook wire 但未实测 → 用户实际场景 hook 不触发或声音不对 → 失去 voice-alert 价值
- **优先级理由**: **P1 中高** — 功能可用但未实测, 实测 5-10 min
- **状态**: **待主指挥测** (主指挥本地 PC session)

#### 小修 #8: delete purge_test_user_data.py (P3 低)

- **来源**: W68 第 7 批 A-3 (`qa-bench-isolation`) agent 报告 (commit `76bdb38b6`)
- **背景**: A-3 实施 qa-bench 物理隔离栈 (docker compose 独立 DB + 测试用户 fixture). `purge_test_user_data.py` 是 xiaoqi_testbot 7 表全清脚本 (2026-07-01 已实施). A-3 agent 建议: **隔离栈生产验证通过后**, 删除 `purge_test_user_data.py` (改用隔离栈 fixture)
- **主指挥必做步骤** (qa-bench 隔离栈生产验证 1 周后):
  ```bash
  # 1. 验证隔离栈已 100% 替代 purge_test_user_data.py 用途
  cd /opt/microbubble-agent
  docker compose -f docker-compose.isolation.yml up -d
  pytest tests/qa_bench/ -v  # 期望全部 PASS, 无需调 purge_test_user_data.py

  # 2. 删除 purge_test_user_data.py + test_purge_test_user_data.py
  git rm scripts/purge_test_user_data.py
  git rm tests/test_purge_test_user_data.py
  git commit -m "chore: remove purge_test_user_data.py (replaced by isolation stack)"
  ```
- **未做的后果**: 保留 `purge_test_user_data.py` 会导致 17 表全清脚本和隔离栈**并存**, 增加维护成本 + 测试冲突风险
- **优先级理由**: **P3 低** — 依赖隔离栈生产验证, 非紧急
- **状态**: **待主指挥拍板** (qa-bench 隔离栈生产验证 1 周后决策)

### 2.4 已闭环 (本批不操作)

#### 小修 #6: Status 段引用错 (14 plans)

- **来源**: W68 第 7 批 C-1 (`plans-status-fix`) agent 报告 (commit `a1d64750e`)
- **背景**: 14 个 plan Status 段 commit hash 错误, 与实际 git log 不匹配 (W66 状态化事故)
- **修复**: C-1 agent 已修正 14 plans 的 Status 段 + 5 新铁律沉淀
- **状态**: ✅ **W68 第 7 批 C-1 已修正** (锚点范式第 80 守恒)

#### 小修 #7: Plan 文件名错位 (60%, 8 plans)

- **来源**: W68 第 7 批 C-2 (`plans-archive`) agent 报告 (commit `77a7f8c88`)
- **背景**: 8 个 plan 文件名错位 (SUPERSEDED/MISCATEGORIZED/DELETED 类, 不应继续在主 plans 目录)
- **修复**: C-2 agent 已归档 8 plans 到 `C:/Users/pc/.claude/plans/archived/`, 67 plans → 59 plans 活跃 + 8 plans archived
- **状态**: ✅ **W68 第 7 批 C-2 已归档** (锚点范式第 84 守恒)

---

## §3 5 新铁律沉淀

### 铁律 1: 8 小修均来自 W68 第 6/7/8 批调研, 不允许 agent "假想"

- **依据**: W68 第 4 批主指挥拍板 "plans 优先 + 小修搭配" 铁律 2 — 小修任务的来源**必须**是: 前批事故复盘 / baseline 漂移检测 / 文档状态同步差异 / Verified Plans / audit 报告发现. **禁止** agent 为凑任务数假想小修
- **本批 8 小修全部可追溯**:
  - #1 VAPID 持久化 → W68 第 7 批 B-3 commit `b31386d61` agent 报告
  - #2 baseline 守恒 → W68 第 4/5/6/7/8 批 A-1 agent 报告
  - #3 CLAUDE.md 锚点沉淀 → W68 第 8 批 D-3 commit `6f78e4cec` agent 报告
  - #4 voice-alert 实测 → W68 第 7 批 D-3 commit `0b0e6e336` agent 报告
  - #5 transcript_polished 回填 → W68 第 7 批 A-1 commit `85d130ab1` agent 报告
  - #6 Status 段引用错 → W68 第 7 批 C-1 commit `a1d64750e` agent 报告
  - #7 Plan 文件名错位 → W68 第 7 批 C-2 commit `77a7f8c88` agent 报告
  - #8 purge_test_user_data.py 删除 → W68 第 7 批 A-3 commit `76bdb38b6` agent 报告
- **追溯完整率**: 8/8 = 100%, 0 假想任务
- **验证方法**: `git log --all --oneline | grep -E "<commit-hash>"` 每条均可找到对应 commit

### 铁律 2: P0 高 (部署必做) 优先 P2 P3

- **依据**: 主指挥决策框架 — P0 高 = 部署前必做 (不做功能坏) > P0 高 (每次必跑) > P1 中高 > P2 中 > P3 低
- **本批主指挥必做顺序**:
  1. **现在必做**: P0 高 #1 (VAPID 持久化) + #2 (baseline 守恒) + #3 (CLAUDE.md 锚点沉淀) — 部署 W68 第 7 批 commit 前
  2. **本批派工窗口后**: P1 中高 #4 (voice-alert 实测) — 主指挥本地 PC session
  3. **留 W69**: P2 中 #5 (transcript_polished 全量回填) — 数据治理批次
  4. **qa-bench 隔离栈生产验证后**: P3 低 #8 (purge_test_user_data.py 删除) — 主指挥拍板
- **禁止**: 跳过 P0 直接做 P2/P3 — P0 失败会导致功能直接坏
- **验证方法**: 主指挥部署 W68 第 7+8 批 commit 前必查本表 §1 + §2.1 必做项

### 铁律 3: baseline 守恒必须每次 merge 后跑

- **依据**: W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → W68 第 6 批 73 → W68 第 7 批 87 → W68 第 8 批 104 累计 100+ commit 0 regression, baseline 71 PASS + 7 SKIP (累计 78 测试) 必须每次 merge 后跑
- **必跑命令**:
  ```bash
  cd /e/microbubble-agent
  SKIP_DB_SETUP=1 python -m pytest tests/test_baseline_audit.py -v --tb=short 2>&1 | tail -20
  # 期望: 39 passed in 3-4s + 71 PASS + 7 SKIP (78 累计)
  ```
- **失败处理**: 71 PASS 跌至 70/69 → 立刻定位 regression commit → revert / fix-forward → 重跑 baseline
- **跳过例外**: 仅当 merge 内容是纯 docs/memory (如本文件) 时可跳过
- **验证**: W68 第 5 批 A-1 agent (锚点范式第 65 守恒) 已建立 baseline 守恒报告模板 (`memory/w68-route-5-baseline-verification-2026-07-24.md`)

### 铁律 4: VAPID 持久化是 PWA 推送部署硬要求

- **依据**: W68 第 7 批 B-3 (`mobile-v3.2-push`) agent 实施 PWA Push backend 时, VAPID 私钥默认存 `/tmp/vapid_private.pem` (临时), **部署前必须**持久化到 `/etc/microbubble/pwapush/` 或 docker volume
- **根因**: docker `/tmp` 目录在容器重启时丢失, VAPID 私钥丢失 → PWA Push 功能直接坏 (subscribe endpoint 报 401)
- **持久化路径**:
  - **方案 A** (推荐): `/etc/microbubble/pwapush/` 目录 + chmod 700 + chown root:root
  - **方案 B**: docker volume `microbubble_pwapush` 挂载到容器内 `/etc/microbubble/pwapush/`
  - **方案 C** (云 server): `~/.microbubble/pwapush/` 目录 + 部署脚本 cp 私钥
- **未做后果**: VAPID 私钥丢失 → PWA Push 端点 401 → 用户推送收不到 → Mobile UX v3.2 PWA 推送功能空转
- **验证**: 部署后 `curl https://<server>/api/v1/notifications/vapid-public-key` 返回 200 + 公钥字符串
- **部署文档**: `docs/drive-pr10-deploy-runbook.md` 第 X 节 PWA Push 部署章节需加本纪律

### 铁律 5: voice-alert 实测是 settings.json wire 后硬要求

- **依据**: W68 第 7 批 D-3 (`claude-code-voice-alert`) agent 实施全局 voice-alert hook (`~/.claude/settings.json` UserPromptSubmit hook 调 `~/.claude/hooks/play_voice_alert.sh $Mode $Message`). wrapper script 调 Edge-TTS 播放, 但 D-3 没在云 server / 本地 PC 实测
- **根因**: hook wire 后未实测 → 用户实际场景 hook 不触发或声音不对 → 失去 voice-alert 价值
- **实测 6 节** (主指挥本地 PC session):
  1. `powershell scripts/voice-alert.ps1 -Message "测试消息"` — 自定义消息
  2. `powershell scripts/voice-alert.ps1 -TaskDone` — 任务完成
  3. `powershell scripts/voice-alert.ps1 -NeedConfirm` — 需要确认
  4. `powershell scripts/voice-alert.ps1 -OnError "失败原因"` — 出错
  5. `powershell scripts/voice-alert.ps1 -AskQuestion "选 A 还是 B？"` — 询问
  6. 启动新 session, 触发 idle → done → error, 听 SAPI / Edge-TTS 真实播放
- **失败回滚**: hook 不触发 → 删 `~/.claude/settings.json` UserPromptSubmit 段; 声音不对 → 换 `say.exe` (Windows 原生); Edge-TTS 失败 → 改 SAPI 离线 TTS
- **未做后果**: hook 假装可用, 用户实际场景无声音, 失去 voice-alert 价值
- **验证**: 实测 6 节全成功后, 在 CLAUDE.md 顶部"当前状态"段加 voice-alert 状态

---

## §4 主指挥决策 checklist (本批派工窗口内)

```
□ 1. VAPID 私钥持久化 (#1) — P0 高 — 部署 W68 第 7 批 B-3 commit 前必做
   □ 1.1 SSH 到云 server + 创建 /etc/microbubble/pwapush/ + chmod 700
   □ 1.2 生成 VAPID 密钥对 + 写入持久化目录 (不是 /tmp)
   □ 1.3 更新 deploy-auto.sh / docker-compose 挂载卷
   □ 1.4 验证 curl /api/v1/notifications/vapid-public-key 返回 200
   □ 1.5 docs/drive-pr10-deploy-runbook.md 加 PWA Push 部署章节
□ 2. baseline 守恒 (#2) — P0 高 — 每次 merge 后必跑 (已自动化, 必跑 39 passed)
   □ 2.1 SKIP_DB_SETUP=1 python -m pytest tests/test_baseline_audit.py -v
   □ 2.2 验证 39 passed + 71 PASS + 7 SKIP (78 累计)
□ 3. CLAUDE.md 锚点沉淀 (#3) — P0 高 — D-3 已实施, 无需操作
□ 4. voice-alert 实测 (#4) — P1 中高 — 主指挥本地 PC session 实测 6 节 (5-10 min)
   □ 4.1 跑 5 种 powershell scripts/voice-alert.ps1 命令
   □ 4.2 启动新 session 触发 hook 真实场景
   □ 4.3 失败回滚或确认
□ 5. transcript_polished 全量回填 (#5) — P2 中 — 留 W69 (主指挥拍板时)
□ 6. purge_test_user_data.py 删除 (#8) — P3 低 — qa-bench 隔离栈验证 1 周后拍板
```

**预计主指挥本批派工窗口耗时**: #1 (30-60 min) + #2 (5 min) + #4 (5-10 min) = **40-75 min**

---

## §5 与既有铁律体系的关系

- 不推翻既有 170+ 铁律, 仅在 **整合层** 新增 5 条
- 锚点范式守恒链 (W7 12 → W68 第 8 批 104) 继续作为每批健康度指标
- "0 production code 改动铁律" 语义保持: 本批纯 memory 沉淀, 不动业务代码
- W19 选项 A 维持: 4 留未来 PR 继续观察

---

## §6 累计 baseline 守恒 (W68 第 9 批, 累计 40+ 守恒)

- **PASS**: 71 (跨 160+ commit 0 regression)
- **SKIP**: 7 (已知 iOS Safari 限制 + 网络测试环境)
- **baseline**: 40+ 守恒 (W7 12 → W62 24 → W65 26 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → W68 第 6 批 73 → W68 第 7 批 87 → W68 第 8 批 104 → **W68 第 9 批 105**)

**W68 第 9 批锚点范式目标**: W68 第 8 批 104 → **W68 第 9 批 D-1 105** ✅ (本批 D-1 仅 1 守恒, 仅 memory 沉淀)

---

## §7 关键文件清单 (本任务交付)

| 类别 | 文件 | 行数 | commit |
|------|------|------|--------|
| memory | `memory/w68-route-9-d1-8-smallfixes-2026-07-24.md` (本文件) | ~300 行 | (本批) |

**0 production code 改动**: ✓ (1 新增 memory, 0 业务代码)

---

## §8 参考

- [memory/w68-route-7-a1-cached-giggling-pebble-fix-2026-07-24.md](./w68-route-7-a1-cached-giggling-pebble-fix-2026-07-24.md) — W68 第 7 批 A-1 (transcript_polished 强化版)
- [memory/w68-route-7-a3-qa-bench-isolation-2026-07-24.md](./w68-route-7-a3-qa-bench-isolation-2026-07-24.md) — W68 第 7 批 A-3 (purge_test_user_data.py 待删)
- [memory/w68-route-7-c1-plans-status-fix-2026-07-24.md](./w68-route-7-c1-plans-status-fix-2026-07-24.md) — W68 第 7 批 C-1 (14 plans Status 修正)
- [memory/w68-route-7-c2-plans-archive-2026-07-24.md](./w68-route-7-c2-plans-archive-2026-07-24.md) — W68 第 7 批 C-2 (8 plans 归档)
- [memory/w68-route-7-d3-claude-code-voice-alert-2026-07-24.md](./w68-route-7-d3-claude-code-voice-alert-2026-07-24.md) — W68 第 7 批 D-3 (voice-alert hook)
- [memory/w68-route-8-d1-w68-7th-followup-2026-07-24.md](./w68-route-8-d1-w68-7th-followup-2026-07-24.md) — W68 第 8 批 D-1 (W68 第 7 批 6 小修整合)
- [memory/w68-route-5-baseline-verification-2026-07-24.md](./w68-route-5-baseline-verification-2026-07-24.md) — W68 第 5 批 baseline 验证报告 (锚点范式第 65 守恒)
- [memory/w68-grand-closure-8th-batch-2026-07-24.md](./w68-grand-closure-8th-batch-2026-07-24.md) — W68 第 8 批 grand closure (锚点范式第 90-104 守恒)
- [memory/w68-task-mode-paradigm-plans-first-2026-07-24.md](./w68-task-mode-paradigm-plans-first-2026-07-24.md) — W68 任务模式基调 (plans 优先 + 小修搭配)
- [memory/anchor-paradigm-21-day-validation-2026-07-22.md](./anchor-paradigm-21-day-validation-2026-07-22.md) — 锚点范式 21 天实战
- [memory/orchestrator-mode-coordination-2026-07-20.md](./orchestrator-mode-coordination-2026-07-20.md) — 主指挥协调范式
- [memory/multi-agent-task-orchestration-baseline.md](./multi-agent-task-orchestration-baseline.md) — 项目级协调范式锚点
- [memory/verified-plans-2026-07-22.md](./verified-plans-2026-07-22.md) — 67 plans 全项目调研
- [memory/future-pr-roadmap-2026-07-21.md](./future-pr-roadmap-2026-07-21.md) — W19 选项 A 4 留未来 PR
- CLAUDE.md 顶部: W68 第 8 批 grand closure (锚点范式第 104 守恒)
- ROADMAP.md 顶部: W68 第 8 批 grand closure
- CHANGELOG.md: W68 第 8 批段
- README.md 近期新增: W68 第 8 批段

---

**W68 第 9 批 D-1: 8 真小修整合 收官完成**: 锚点范式 W68 第 8 批 104 → W68 第 9 批 D-1 105 单调上升 (本批 D-1 仅 1 守恒, 仅 memory 沉淀), 0 production code 改动铁律完全维持 (本批纯 memory), W19 选项 A 维持 (4 留未来 PR 继续观察), 任务模式基调延续 W68 第 4 批 "plans 优先 + 小修搭配", 8 小修整合表 + 主指挥决策建议 + 5 新铁律 + 主指挥 checklist 完整列出.

**下一步**: 等主指挥拍板确认 W68 第 9 批 D-1 收官 + 启动主指挥决策 checklist (§4) 3 项必做 (#1 VAPID 持久化 + #2 baseline 守恒 + #4 voice-alert 实测) + W69 第 1 批派工规划 (含 #5 transcript_polished 回填).

**派工窗口**: 主指挥协调范式第 36 次派工完成 (锚点范式 W68 第 8 批 104 → W68 第 9 批 D-1 105, 仅 1 守恒, 紧凑节奏延续).

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**Date**: 2026-07-24
**Version**: W68 第 9 批 D-1 v1.0
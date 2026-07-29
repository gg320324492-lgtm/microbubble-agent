# W86 第 1 批 C-1: Trivy 镜像漏洞扫描 + Dockerfile base image 钉死 (2026-07-29)

> **锚点范式**: 320 → 321 (+1 实施)
> **分支**: `claude/w86-1st-batch-c1-trivy` (base `9564f2dc9`)
> **0 production code 改动铁律**: 例外 1 已批 (仅限 Dockerfile `FROM` 行 + compose `image:` 行,
> 未动任何 `RUN` / `COPY` / `CMD` / service 配置 / volume / network / 端口)

## 1. 交付物

| 文件 | 类型 | 说明 |
|------|------|------|
| `Dockerfile` / `.db` / `.funasr` / `.mcp` / `.voice-pipeline` / `.whisper` | 改 | 只改 `FROM` 行 + 头注释 |
| `web/Dockerfile` / `docker/Dockerfile.commercial` | 改 | 同上 (各 2 个 FROM) |
| `docker-compose.yml` | 改 | 5 个 `image:` 行 + 注释 |
| `.github/workflows/image-scan.yml` | 新 | 8 矩阵 trivy 扫描 (PR advisory + 周一 gate) |
| `scripts/install-trivy.md` | 新 | 3 平台安装说明 (**本机未装**) |
| `scripts/trivy/scan-images.sh` | 新 | 一次性扫 8 Dockerfile + 本地镜像 |
| `scripts/trivy/scan-all.sh` | 新 | 全量扫 + sarif 输出 + deploy gate 用法 |
| `tests/trivy/test_dockerfile_pinning.py` | 新 | 钉死硬门禁 (含正/负向自检) |
| `tests/trivy/test_workflow_exists.py` | 新 | workflow 存在 + 关键配置断言 |

## 2. 9 个 Dockerfile + compose 钉死前后对比表

| # | 文件:行 | 钉死前 (浮动) | 钉死后 | 验证 |
|---|---------|--------------|--------|------|
| 1 | `Dockerfile:2` | `python:3.11-slim-bookworm` | `python:3.11.15-slim-bookworm` | 200 |
| 2 | `Dockerfile.db:2` | `postgres:16-alpine` | `postgres:16.14-alpine` | 200 |
| 3 | `Dockerfile.funasr:2` | `python:3.11-slim-bookworm` | `python:3.11.15-slim-bookworm` | 200 |
| 4 | `Dockerfile.mcp:3` | `python:3.11-slim` | `python:3.11.15-slim` | 200 |
| 5 | `Dockerfile.voice-pipeline:3` | `nvidia/cuda:12.1-runtime-ubuntu22.04` | `nvidia/cuda:12.1.1-runtime-ubuntu22.04` | 200 |
| 6 | `Dockerfile.whisper:2` | `python:3.11-slim-bookworm` | `python:3.11.15-slim-bookworm` | 200 |
| 7 | `web/Dockerfile:2` | `node:20-alpine` | `node:20.19.6-alpine` | 200 |
| 8 | `web/Dockerfile:12` | `nginx:alpine` | `nginx:1.31.2-alpine` | 200 |
| 9 | `docker/Dockerfile.commercial:14` | `python:3.11-slim` (builder) | `python:3.11.15-slim` | 200 |
| 10 | `docker/Dockerfile.commercial:36` | `python:3.11-slim` (runtime) | `python:3.11.15-slim` | 200 |
| 11 | `docker-compose.yml:5` | `nginx:alpine` | `nginx:1.31.2-alpine` | 200 |
| 12 | `docker-compose.yml:93` | `redis:7-alpine` | `redis:7.4.9-alpine` | 200 |
| 13 | `docker-compose.yml:107` | `neo4j:5-community` | `neo4j:5.26.27-community` | 200 |
| 14 | `docker-compose.yml:129` | `minio/minio` (裸, 隐式 latest) | `minio/minio:RELEASE.2025-09-07T16-13-09Z` | 200 |
| 15 | `docker-compose.yml:185` | `ollama/ollama:latest` | `ollama/ollama:0.31.1` | 200 |

**15/15 全部钉死, 0 浮动 tag 残留.**

## 3. 派工 brief 建议版本与实测不符 — 据实上报 (类 20 实战)

派工 brief 段"钉死策略"给的示例版本**全部过时**, 未照抄, 改为按**本机实测**钉死:

| 镜像 | brief 建议 | 实测真值 | 差异 |
|------|-----------|---------|------|
| python | `3.11.13-slim-bookworm` | `3.11.15` | brief 落后 2 个 patch; `3.11.16` 探测 403 (不存在) |
| postgres | `16.4-alpine` | `16.14` | brief 落后 10 个 patch; `16.15` 403 |
| redis | `7.4-alpine` | `7.4.9` | brief 只给 major.minor (仍浮动) |
| nginx | `1.27.5-alpine` | `1.31.2` | brief 落后 4 个 minor |
| node | `20.19-alpine` | `20.19.6` | brief 只给 major.minor |
| minio | `RELEASE.2024-10-29T16-01-44Z` | `RELEASE.2025-09-07T16-13-09Z` | brief 落后约 1 年 |
| ollama | `0.4.4` | `0.31.1` | brief 落后大量版本 |
| neo4j | `5.26-community` | `5.26.27` | brief 只给 major.minor |
| nvidia/cuda | `12.1.1-runtime-ubuntu22.04` | `12.1.1` ✅ | 唯一命中 |

**取值方法 (不猜, 双重验证)**:
1. **本地镜像缓存读真值** — 现役浮动 tag 已 pull 到本机, `docker inspect` 读内部版本号:
   `PG_VERSION=16.14` / `REDIS_VERSION=7.4.9` / `NGINX_VERSION=1.31.2` /
   `PYTHON_VERSION=3.11.15` / `NEO4J_TARBALL=neo4j-community-5.26.27` /
   minio label `release=RELEASE.2025-09-07T16-13-09Z` / `ollama --version → 0.31.1`
2. **mirror registry manifest 探测存在性** — 逐个 tag 探 HTTP code (200=存在, 403=不存在)

**钉死语义 = 冻结当前已验证运行的版本**, 不是顺手升级到未测过的新版.
`redis:7.4.10` / `nginx:1.31.3` 探测存在但**故意不用** — 升级属另一议题, 需回归验证.

## 4. 网络环境实战 (本机 shell 出网被拦)

- `trivy --version` → `command not found` (**未安装**, 仅写文档, 遵守 brief"不要真装")
- `docker manifest inspect` **全部超时** — 该命令直连 `registry-1.docker.io`, **不走** 加速器
- `curl hub.docker.com` / `auth.docker.io` → 超时 / exit 28; WebFetch → 域名被安全策略拦
- `docker pull` **可用** — 走 daocloud/ustc/aliyun 加速器 (`docker info` 确认 5 个 mirror)
- **绕过方案**: 用加速器的 registry v2 API 探测 manifest, 而非 `docker pull` 拉几 GB 镜像:
  1. `GET https://m.daocloud.io/auth/token?service=docker.m.daocloud.io&scope=repository:<repo>:pull`
  2. `GET https://docker.m.daocloud.io/v2/<repo>/manifests/<tag>` + Bearer + Accept manifest 类型
  3. **200 = tag 存在, 403 = 不存在** (对照实验: `redis:7.4.999-alpine` → 403 确认判别有效)
- **mirror `tags/list` 被禁用** — 返回 `{"name":"disable-list-tags","tags":[]}` (HTTP 200 但空),
  故**无法枚举** tag, 只能逐个探测。曾因此产生"全部候选为空"的假结果, 查 raw 响应才发现。

## 5. e2e 验证结果

```
SKIP_DB_SETUP=1 python -m pytest tests/trivy/ -q
→ 47 passed in 0.05s
```

- `test_dockerfile_pinning.py` — 34 test: 15 参数化钉死断言 + 11 负向自检 + 10 正向自检 + 结构断言
- `test_workflow_exists.py` — 8 test: workflow 存在 / trivy-action / 触发器 / severity / sarif / 矩阵 / advisory / 脚本齐备
- 附加: `bash -n` 两脚本语法 PASS; workflow + compose YAML `yaml.safe_load` PASS

### 5.1 负向对照实验抓出门禁自身的 bug (关键教训)

首版 `_is_pinned()` 用 `re.search(r"\d+\.\d+", tag)` 判钉死。
把 `Dockerfile.mcp` 改回 `python:3.11-slim` 做**负向对照**, 结果 **26/26 仍 PASS = 假绿**:
`"3.11-slim"` 里的 `3.11` 被正则命中, 但 patch 号仍浮动。

**修正**: 改为要求 **3 段数字开头** (`^\d+\.\d+\.\d+`),
`postgres` 例外白名单 (上游 major.minor 即完整版本, 无第三段)。
修正后同一注入立即 FAIL (`Dockerfile.mcp:3 使用浮动 tag`), 恢复真 pin 后 47/47 PASS。
并把 11 条负向 + 10 条正向断言**固化进测试**, 让这类假绿由 suite 自身拦截, 不依赖人工对照。

## 6. `SKIP_DB_SETUP=1` 必须带 (踩坑)

首次直接 `pytest tests/trivy/` → **26 errors `ConnectionRefusedError`**:
`tests/conftest.py:151` 的 `setup_db` 是 **autouse function-scope** fixture, 会连 PG。
本任务测试是纯文件读取, 不需要 DB。用仓库既有逃逸口 `SKIP_DB_SETUP=1`
(`conftest.py:145` 分支切同步空 fixture), **未改动共享 conftest**。
→ CI/本地跑本目录测试**必须** `SKIP_DB_SETUP=1`。

## 7. 已知历史严重 CVE (留口, 待 trivy 真扫)

本机 trivy 未安装 + 出网受限 → **本批未产出任何真实 CVE 清单**, 不编造。
留待以下任一途径补齐:
- CI 侧 `.github/workflows/image-scan.yml` 首次 schedule 跑 (周一 05:00 UTC) 出 sarif
- 有网环境 `bash scripts/trivy/scan-all.sh` → `logs/trivy-report-all.txt`

**预判高风险面** (依据钉死过程观察, 非扫描结论):
1. `nvidia/cuda:12.1.1-runtime-ubuntu22.04` — ubuntu 22.04 + CUDA 12.1 (2023 版), 基底最老, 预计 HIGH 最多
2. `python:3.11.15-slim-bookworm` — 3 个服务共用, 一个 CVE 面放大 3 倍
3. `minio/minio` 原为**裸 latest** — 此前完全无法追踪 CVE, 本批首次可追踪
4. `ollama/ollama` 原为 `latest` — 同上

## 8. 待主指挥

1. **`deploy-auto.sh` gate 集成** — 脚本已备 (`scripts/trivy/scan-all.sh` 顶部注释含用法),
   遵守 brief **未改** `deploy-auto.sh`, 留主指挥合。
2. **真 CVE 清单** — 待 trivy 首扫产出后回填本文件第 7 节。
3. **镜像升级议题** — `redis:7.4.10` / `nginx:1.31.3` 已确认存在, 是否升级需独立回归, 本批只冻结现状。
4. **`.gitignore` 未改** — 第 30 行既有 `logs/` 已完全覆盖 `logs/trivy-*`,
   加冗余规则无意义, 故据实跳过 (brief 允许改但无必要)。

## 9. 新铁律 (5 条)

1. **钉死 = 冻结实测运行版本, 不是照抄派工 brief 示例** — brief 9 个建议版本 8 个过时
   (ollama 差 `0.4.4` vs `0.31.1`, minio 差约 1 年)。照抄 = 静默降级到未测版本, 比浮动 tag 更危险。
2. **`docker manifest inspect` 不走加速器** — 直连 `registry-1.docker.io`, 受限网络必超时。
   验证 tag 存在性用 mirror 的 registry v2 API + Bearer token 探 manifest (200/403 判别)。
3. **major.minor 不算钉死** — `python:3.11-slim` / `redis:7.4-alpine` 的 patch 仍浮动。
   门禁判定须要求 3 段数字 (`postgres` 等上游只有 2 段的镜像走白名单例外)。
4. **门禁必须做负向对照** — 注入一个已知违规再跑, 确认由 PASS 变 FAIL。
   本批正是靠此发现 `\d+\.\d+` 误判导致的假绿; 并把正/负向断言固化进 suite 防回归。
5. **`tags/list` 被 mirror 禁用时不可当"无此版本"** — 返回 HTTP 200 + 空数组 (`disable-list-tags`),
   易误读为"候选全不存在"。空结果必查 raw 响应体再下结论 (派工范式 v6 §1.2 必真验证)。

# MicroBubble Agent - dist build runbook (2026-08-04)

> **目的**: 统一 `web/dist/` 构建产物从本地 build → git commit → 服务器 pull → 容器重启的完整流程, 避免 dist 漏 commit / 服务器白屏 / 容器不重启三类常见事故.
> **适用范围**: 任何前端改动 (`web/src/*.vue` / `*.js` / `*.css`) 或后端代码改动 (需 `web/dist/` hash 同步刷新) 都走本流程.
> **沉淀来源**: W99 DEPLOY-AUTO + W100 +49~+61 chat 收口 + 类 20.150 docker compose v2 永久铁律.

---

## 何时需要 rebuild dist

| 改动类型 | 是否 rebuild dist | 说明 |
|---------|-----------------|------|
| 前端 `web/src/*.vue` / `*.js` / `*.css` | **必须** | 用户浏览器加载的是 `web/dist/assets/index-<hash>.js`, src 改动必须重新 build |
| 后端 `app/services/*.py` / `alembic/versions/*.py` | **必须** | 路由/接口签名变化, 前端 chunk graph 会跟着变, 必须 `npm run build` 重新生成 manifest |
| 后端 `app/main.py` / `app/core/*.py` | **必须** | 同上, 启动参数 / CORS / 异常处理变化 |
| 纯 `docs/` / `memory/` / `scripts/` / `tests/` | **不必** | dist 不引用这些, 无需 rebuild |
| `docker-compose.yml` (只改 env 不改 service 拓扑) | **不必** | dist 无引用 |
| alembic migration 文件 | **不必** | DB schema 变化不影响前端 chunk graph |

**判断依据**: `git diff --cached --name-only -- web/src/ app/ | head -3` — 任一非空就需要 rebuild.

---

## 完整流程 (5 步)

### Step 1: 本地 build

```bash
cd web
npm run build
# 输出: web/dist/assets/index-<8hex>.js + index-<8hex>.css + ... (若干新 hash 文件)
# 注意: `npm run build` 是唯一合法 build 命令, `vite build` 直跑会触发 PWA manifest 410 回归
#       (CLAUDE.md 2026-07-11 铁律, scripts/postbuild-fix-manifest.js 必经)
```

**健全性自检**:
```bash
ls web/dist/assets/index-*.js | head -3  # 应有新 hash
test -f web/dist/manifest.*.webmanifest  # PWA manifest 必须存在
```

### Step 2: git add + commit (含 dist)

```bash
cd <repo-root>
git add -f web/dist/  # 必须 -f, web/dist/ 在 .gitignore 第 50 行
git status --short | head -20  # 应见大量 web/dist/ staged 文件
git commit -m "build(dist): W100 +N <description>"
```

**自动拦截 (pre-commit hook)**: `scripts/check-dist-before-commit.sh` (W100 +75c 优化版) 检测 `web/src/` 改动 + 本地 `web/dist/` 新 hash 文件, 自动 `git add -f web/dist/`, 避免漏 commit 触发服务器 404.

### Step 3: push origin main

```bash
bash scripts/push-main.sh  # W100 +75d 新增, 带重试 + rev-list 验证 + force-with-lease
# 或手动:
git push origin main
git rev-list origin/main..HEAD --count  # 验证 ahead 数量, 必须 > 0
```

**常见假成功**: `Everything up-to-date` 但本地 packed-refs 掉了, ahead 实际 = 0 → 服务器没更新. push-main.sh 自动 detect + `force-with-lease` 修复.

### Step 4: 服务器 pull + nginx reload

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && git pull origin main && nginx -s reload"
```

**注意**: 服务器 webhook 不一定自动触发 (类 20.150 实战), 建议主拍手动 SSH 拉. 服务器**不跑**应用容器 (类 20.139 永久铁律), 只 nginx 静态 + reverse proxy.

### Step 5: 本地 PC 容器重启 (后端改时)

```bash
# 后端代码改动时 (app/*.py / alembic/versions/*.py):
docker cp <new-file.py> microbubble-agent-app-1:/app/app/<path>/<file.py>
docker exec microbubble-agent-app-1 rm -rf /app/app/<module>/__pycache__
docker stop microbubble-agent-app-1 microbubble-agent-celery-worker-1 microbubble-agent-celery-beat-1
docker start microbubble-agent-app-1 microbubble-agent-celery-worker-1 microbubble-agent-celery-beat-1

# alembic migration 改动时 (额外):
docker cp alembic/versions/<new>.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
```

**永久铁律 (类 20.150)**: Windows Docker Desktop 默认是 compose v1, `docker compose` (无横线) v2 CLI 不存在. **必须**用 `docker-compose` 或 `docker restart <name>` 单容器重启, 不可用 `docker compose up -d` (会报 "command not found").

---

## 验证 (3 步)

```bash
# 1. 服务器健康
curl -s https://agent.mnb-lab.cn/health
# 期望: {"status": "healthy", ...} (HTTP 200)

# 2. 服务器静态资源新 hash (确认 dist 已更新)
curl -s https://agent.mnb-lab.cn/index.html | grep -oE 'index-[a-f0-9]{8}\.js'
# 期望: index-<新 8 字符 hash>.js (与本地 web/dist/assets/ 一致)

# 3. 服务器 API 鉴权 (确认 nginx 转发 OK)
curl -s -o /dev/null -w "%{http_code}\n" https://agent.mnb-lab.cn/api/v1/tasks
# 期望: 401 (未鉴权) 或 200 (有 cookie), 绝不能 502 (类 20.139)
```

---

## 常见坑 (5 类)

### 坑 1: `git push` 显示 "Everything up-to-date" 假成功
- **根因**: 本地 main ref 偶尔会从 packed-refs 删除, push 时 ref 缺失 → git 判定 origin 已最新
- **修复**: `bash scripts/push-main.sh` (W100 +75d) 自动 `git rev-list` 验证 ahead + `force-with-lease` 补救
- **验证**: `git rev-list origin/main..HEAD --count` 期望 > 0

### 坑 2: 服务器 webhook 不自动触发
- **根因**: webhook.py:9001 端口偶尔被防火墙阻断 / nginx upstream 502
- **修复**: 主拍手动 SSH 拉, 见 Step 4
- **预防**: `scripts/deploy-auto.sh` (W99 DEPLOY-AUTO 沉淀) webhook + SSH 双保险

### 坑 3: docker compose v2 不存在
- **根因**: 类 20.150 永久铁律, Windows Docker Desktop 默认 compose v1
- **修复**: 用 `docker-compose` (有横线, Python 包) 或 `docker restart <name>` 单容器重启
- **示例**:
  ```bash
  # 错误: $ docker compose up -d
  # bash: docker: 'compose' is not a docker command
  # 正确: $ docker-compose up -d  # 或 $ docker restart <container-name>
  ```

### 坑 4: dist 漏 commit 服务器 404
- **根因**: `web/dist/` 在 `.gitignore` 第 50 行, `git add .` 默认跳过
- **修复**: 必须 `git add -f web/dist/` 或依赖 `scripts/check-dist-before-commit.sh` (W100 +75c 优化版) 自动 add
- **历史教训**: 2026-06-26 f6a2bc3d (v70 P2) 漏 add 95 个新 dist → `index-fc61064b.js` 404 → 整站白屏

### 坑 5: 容器重启后 alembic 不识别新 migration
- **根因**: 类 20.142 永久铁律, `microbubble-agent-app:latest` 镜像 build 时间早于当前 commit, 容器内 `alembic/versions/` 看不到新文件
- **修复**: `docker cp alembic/versions/<new>.py <container>:/app/alembic/versions/` + `rm -rf __pycache__` + `alembic upgrade head`
- **预防**: `scripts/auto-deploy.sh` 含完整 5 步 docker cp 流程

---

## 一键脚本 (主拍可选)

```bash
# W100 +75 收尾新增的 4 个脚本配合使用:
bash scripts/push-main.sh                        # Step 3
bash scripts/check-dist-before-commit.sh         # Step 2 pre-commit 自动拦截
# (Step 1/4/5 暂无一键, 沿用 W99 DEPLOY-AUTO)
```

---

## 关联沉淀

- `docs/deploy.md` 服务器迁移章节
- `scripts/auto-deploy.sh` (W99 DEPLOY-AUTO, 322 行完整链)
- `memory/w99-deploy-auto-closure-2026-08-02.md` (W99 DEPLOY-AUTO 沉淀)
- `memory/w99-fix-deploy-2026-08-02.md` (W99 +21 fix-deploy, 191 行)
- `CLAUDE.md` 类 20.142 (镜像 build 漂移) + 类 20.150 (docker compose v2) + 类 20.139 (服务器 502 = 本地 app)

---

## 5 件套守恒

1. **alembic**: rebuild dist 不改 migration, 1 head `097_meeting_processing_persistence` 守恒
2. **pytest**: rebuild dist 不涉及后端逻辑, 沿用基线 101+ PASS
3. **PWA build**: `cd web && npm run build` PASS (postbuild 自动 hash manifest)
4. **0 production code**: rebuild dist 是构建产物, 不算 production code
5. **锚点范式**: 本流程类 20.150 永久铁律已沉淀, 派工 v6 §13.3 沿用
# W73 hotfix commit message 模板

> **依据**: W72 第 2 批 E-1 commit `c29ca1663` 4 类 hot-fix 链预案 + CLAUDE.md §2.4 hot-fix 纪律 + 派工 v6 段 5 反馈循环实战 (W73 第 1 批 B-2 派工)
>
> **生效日期**: 2026-07-27 W73 第 1 批
>
> **维护者**: 主指挥 + 各 hot-fix 实施 agent

## 1. 模板结构 (4 段必含)

```bash
# hotfix commit message 必含 4 段:
# 1. <type>(<scope>): hotfix-<short-desc> (<short-bug-id>)
# 2. body 段 1: root cause (1-3 段, 含 commit 引用 + 行号)
# 3. body 段 2: 修复 (1-3 段, 含具体改法)
# 4. body 段 3: 验证 (1-2 段, 含 curl/pytest/手动步骤)
# 5. footer: 引用永久锚点 (CLAUDE.md 章节 + memory 沉淀)
```

## 2. 完整模板

```bash
<type>(<scope>): hotfix-<short-desc> (<short-bug-id>)

<root cause 段>
- 症状: <用户可见的具体现象 (含截图/curl 输出/console log)>
- 根因: <1-2 句定位 + 引用历史事故 commit hash>
- 触发链路: <3-5 步的因果链, 含文件:行号>

<修复 段>
- 改法 1: <具体改的命令/代码, 含文件:行号>
- 改法 2: <如有第二处改动>
- 部署: <cp / docker exec / git push 等具体步骤>

<验证 段>
- 自动: <curl / pytest / alembic heads 等具体命令 + 期望输出>
- 手动: <用户浏览器/管理员后台等手动验证步骤>
- 回归: <防 regression 检查命令>

引用:
- CLAUDE.md: <章节名> (永久锚点)
- memory: <memory 文件路径>
- 历史事故: <commit hash> → <修复 commit hash>
- 派工 v6 段 5 反馈: <#1/#2/#3 实战>

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

## 3. 4 类 hotfix commit 实战示例

### 3.1 hotfix alembic 双头

```bash
fix(alembic): hotfix-alembic-double-head (W73-B-2-#1)

症状:
  $ docker exec app-1 alembic upgrade head
  FAILED: Multiple head revisions are present for given argument 'head'

根因:
- 并行派多个 alembic migration agent, 派工 prompt 没明确 down_revision 接续关系
- 两个 agent 都声明 down_revision="077_xxx", merge 后分叉
- 历史事故: W68 第 3 批 F-1 (062) + F-2 (063) 双头, commit 1852468a6 修复

修复:
- 改 alembic/versions/079_xxx.py:
    down_revision: Union[str, None] = "078_xxx"  # 改
- docker cp + clear __pycache__:
    docker exec -e SKIP_DB_SETUP=1 app-1 rm -rf /app/alembic/versions/__pycache__

验证:
- docker exec app-1 alembic heads  # 期望 ['079_xxx']
- bash scripts/monitor-alembic-heads.sh  # 期望 exit 0
- CI migrate-check workflow PASS

引用:
- CLAUDE.md: §2026-07-24 alembic 并行 agent 串单链纪律
- CLAUDE.md: §W68 第 3 批 5 守恒
- memory: w68-alembic-chain-discipline-2026-07-24.md
- 派工 v6 段 5 反馈 #1 实战

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

### 3.2 hotfix PWA manifest 410

```bash
fix(pwa): hotfix-pwa-manifest-410 (W73-B-2-#2)

症状:
- 浏览器 DevTools Console:
    Manifest fetch failed, code: 410 (Gone)
    Bad Resource: manifest.webmanifest
- PWA install 按钮消失

根因:
- vite build 绕过 npm run build 的 postbuild (scripts/postbuild-fix-manifest.js)
- vite-plugin-pwa 生成 unhashed manifest.webmanifest
- nginx location = /manifest.webmanifest { return 410; } 拦截 (防护保留)
- 历史事故: commit 59187ce8 → 5d2bcdfd 修复

修复:
- cd web && npm run build  # 走 postbuild, 自动改 hashed URL
- git add -f web/dist/manifest.{hash}.webmanifest  # 新增文件 .gitignore 拦了必须 -f
- commit + push + 等 webhook 30s

验证:
- curl -sk -o /dev/null -w "%{http_code}\n" https://xiaoqi.studio/manifest.webmanifest
    期望: 410
- curl -sk -o /dev/null -w "%{http_code}\n" https://xiaoqi.studio/manifest.{hash}.webmanifest
    期望: 200
- bash scripts/monitor-pwa-manifest.sh  # 期望 exit 0
- 浏览器 DevTools → Application → Manifest → 解析成功

引用:
- CLAUDE.md: §2026-07-11 PWA manifest 410 回归
- memory: pwa-manifest-410-regression-2026-07-11.md
- 派工 v6 段 5 反馈 #2 实战

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

### 3.3 hotfix 整站 octet-stream

```bash
fix(nginx): hotfix-nginx-octet-stream (W73-B-2-#3)

症状:
- 浏览器打开 dashboard → 下载名为 "dashboard" 的文件
- curl -I https://xiaoqi.studio/:
    Content-Type: application/octet-stream

根因:
- server { } block 内加 types { } 块
- Nginx types 指令在 server context 是"完全覆盖"语义
- http context mime.types 整个被丢弃, .html 找不到 text/html
- fallback default_type application/octet-stream
- 历史事故: commit 08f440f → f148d96 + 5c24442 修复

修复:
- 编辑 nginx/conf.d/tunnel.conf + http-only.conf
- 删 server block 里的所有 types { } block
- 保留 http context 的 include /etc/nginx/mime.types;
- bash scripts/deploy-auto.sh (注入 webmanifest MIME + sed -i + grep 验证)
- docker exec nginx-1 nginx -t && nginx -s reload

验证:
- 6 点 curl Content-Type:
    for path in /index.html / /dashboard /sw.js /pwa-192.png /manifest.{hash}.webmanifest; do
      curl -sk -o /dev/null -w "$path %{content_type}\n" "https://xiaoqi.studio$path"
    done
    期望: text/html + text/html + text/html + application/javascript + image/png + application/manifest+json
- bash scripts/monitor-nginx-mime.sh  # 期望 exit 0
- 浏览器打开 dashboard 正常渲染

引用:
- CLAUDE.md: §2026-06-13 Nginx types 指令覆盖/合并行为差异
- memory: nginx-hsts-gzip-2026-06-29.md
- 派工 v6 段 5 反馈 #3 实战

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

### 3.4 hotfix SW 缓存污染

```bash
fix(sw): hotfix-sw-cache-poisoning (W73-B-2-#4)

症状:
- 服务器正常 (curl 一切 OK), 用户浏览器打开 dashboard 显示老版本
- DevTools → Application → Service Workers: 仍 activated 老 sw.js
- DevTools → Application → Cache Storage: documents cache 含老 octet-stream HTML

根因:
- 老 SW (NetworkFirst) 缓存了 octet-stream HTML 响应
- 服务器修复后 SW 仍可能返回缓存
- cleanupOutdatedCaches() 只清 precache, 不清 NetworkFirst/StaleWhileRevalidate runtime cache
- 历史事故: commit 08f440f → 747a735 SW 升级修复

修复:
- 编辑 web/src/sw.js:
    const SW_VERSION = 'v84-hotfix-sw-cache-purge-2026-07-27'  # BUMP
- activate 钩子加 caches.keys() + Promise.all(keys.map(caches.delete))
- 加 self.skipWaiting() + clients.claim() + postMessage SW_UPDATED
- web/src/main.js useRegisterSW onRegisteredSW 监听 SW_UPDATED → setTimeout reload 500ms
- cd web && npm run build + git add -f dist/sw.js + commit + push

验证:
- git diff --cached -- web/dist/sw.js | grep -qE '"url":\s*"manifest\.webmanifest"'
    期望: 退出码 1 (无 unhashed 引用)
- bash scripts/monitor-sw-cache.sh  # 期望 exit 0
- 浏览器 DevTools → Application → Service Workers → 看到新 SW_VERSION → activated
- 浏览器 DevTools → Application → Cache Storage → documents cache 已被清空
- 用户刷新页面 → 拿到新资源

引用:
- CLAUDE.md: §2026-06-13 SW 污染 cache 修复
- memory: sw-cache-poisoning-v79-bump-2026-07-08.md
- 派工 v6 段 5 反馈 #4 实战

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

## 4. 派工 v6 段 5 实战纪律 (永久锚点)

1. **hotfix commit 必单做, 不与 feature 合并** — 回滚粒度独立
2. **主指挥每次 session 启动必跑**:
   ```bash
   git log --oneline -30 | grep -i hotfix
   ```
3. **4 类常见 hotfix 必包含在 CLAUDE.md 永久锚点** (本模板固化)
4. **hotfix 监控 4 脚本必跑** (cron 1h/5min/10min/1h):
   ```bash
   bash scripts/monitor-alembic-heads.sh
   bash scripts/monitor-pwa-manifest.sh
   bash scripts/monitor-nginx-mime.sh
   bash scripts/monitor-sw-cache.sh
   ```
5. **防 59187ce8 regression** (本模板核心):
   ```bash
   # commit 前必跑
   git diff --cached -- web/dist/sw.js | grep -qE '"url":\s*"manifest\.webmanifest"'
   # 退出码 1 才是 PASS (无 unhashed 引用)
   ```
6. **commit message 4 段必含** (root cause + 修复 + 验证 + 引用), 不写"修了个 bug"这种空话
7. **修复路径必含 3 个具体步骤** (改法 + 部署 + 验证), 不写"按文档操作"
8. **历史事故 commit hash 必引用** (派工 v6 §6 段 6 实战: 引用 → 避坑)

## 5. 关联文件

- 4 监控脚本: `scripts/monitor-{alembic-heads,pwa-manifest,nginx-mime,sw-cache}.sh`
- 共用 webhook 库: `scripts/lib/webhook_payload.sh` (W75 第 1 批 B-3 新建, 5 函数, 6 件套监控共用)
- 4 测试: `tests/test_hotfix_monitor_e2e.py` (4 case 实战)
- 4 测试 (W75 B-3 新增): `tests/test_hotfix_webhook_e2e.py` (4 payload 验证 + retry + || true 删除)
- 4 类 hotfix 链预案: W72 第 2 批 E-1 commit `c29ca1663` (CLAUDE.md §2.4)
- 派工纪要 v6/v7/v8/v9/v10: `docs/w68-*-prompt-template-*.md` 系列
- 锚点范式: W72 第 2 批 235 → W73 第 1 批 B-2 240 守恒 (+1)
- 锚点范式: W73 第 1 批 249 → W75 第 1 批 B-3 255 守恒 (+1, 4 类 hot-fix 监控 P2 webhook 修复)

## 6. W75 B-3 webhook payload 格式升级 (W74 E-1 P2 实战)

**P2 缺陷** (W74 第 1 批 E-1 报告): 4 监控脚本原 webhook payload 缺右花括号 `{"text":"..."` + `|| true` 静默吞报警。

**修复纪律** (W75 第 1 批 B-3 实战, 派工 v6 段 5 反馈 #6):

### 6.1 webhook payload 5 字段必含

```json
{
  "severity": "critical|error|warn|info",
  "source": "<monitor-name>",
  "message": "<short summary>",
  "timestamp": "2026-07-27T16:00:00Z",
  "details": { ... 业务字段 ... }
}
```

### 6.2 监控必含业务字段

| 监控 | 必含业务字段 (details 内) |
|------|------------------------|
| monitor-alembic-heads | `heads`, `head_count`, `fix_ref` |
| monitor-pwa-manifest | `hashed_manifest_status`, `unhashed_manifest_status`, `detection_method` |
| monitor-nginx-mime | `endpoint`, `expected_content_type`, `actual_content_type`, `octet_stream_detected` |
| monitor-sw-cache | `sw_version`, `cache_keys_count`, `cache_purge_status` |

### 6.3 删 `|| true` 静默吞 + retry 策略

- **删 `|| true`** — 失败时主动告警 `exit 1` (派工 v6 段 5 反馈 #6 实战)
- **retry 策略** — 3 次重试, 间隔 5s (默认)
- **共用 webhook 库** `scripts/lib/webhook_payload.sh` — 5 函数 `validate_payload_json` / `send_webhook_with_retry` / `format_alert_payload` / `log_alert` / `notify_alert`

### 6.4 6 件套监控凑齐

W73 B-2 4 类 hot-fix (alembic + PWA + nginx + SW) + W74 D-1 多租户隔离 + W75 B-3 webhook 修复 = **6 件套监控共用 webhook 库**

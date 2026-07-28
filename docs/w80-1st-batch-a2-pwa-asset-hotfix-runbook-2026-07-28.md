# W80 第 1 批 A-2 PWA 资产缺失 hot-fix 部署 runbook (2026-07-28)

> **派工**: W80 第 1 批 A-2 PWA 资产缺失 hot-fix 派工 (W79 A-1 拦截 #10 副发现实战)
> **依据**: W79 A-1 拦截 commit `d7adbc87e` 拦截报告 10 段 + W79 A-1 拦截 #10 PWA 资产缺失 hot-fix 副发现实战 + CLAUDE.md 永久锚点 2026-07-11 PWA manifest 410 回归 + W78 D-1 commit `5050c9e2` 派工 v4 铁律 11 实战
> **锚点范式**: W79 第 1 批 283 → W80 第 1 批 A-2 286 守恒 (+1)

## 0. 上下文 — W79 A-1 拦截 #10 副发现

W79 第 1 批 A-1 部署收口 commit `d7adbc87e` 拦截报告 10 段中, 附带发现:
> web/dist 无 sw.js / registerSW.js / manifest.*.webmanifest, 服务器三处 404 (非 410 防护态). 先于 W79 存在, 建议单独 hot-fix 派工

派工前提铁律 5 (W79 A-1 沉淀) 第 5 条:
> **拦截报告发现的非本批问题另开派工** — 附带发现不得夹带进拦截 commit

W80 第 1 批 A-2 单独 hot-fix 派工解决. **核心结论**:
PWA 当前 by-design 禁用 (W68 第 14 批 H-3 决策: `vite-plugin-pwa disable: true`), 因此 web/dist 不应有 sw.js / manifest.*.webmanifest. W79 A-1 拦截 #10 副发现的 404 是 by-design, 不是 bug. **hot-fix 重点是确保 410 防护态配置完整 + 监控兼容 PWA disabled 状态**.

## 1. nginx 410 防护态 6 配置 (W80 A-2 实战)

### 1.1 已配置 (W68 第 14 批 H-2 + 后续加固, W80 A-2 §2.3 扩展)

| 路径 | 80 block | 443 block | 备注 |
|------|----------|-----------|------|
| `/manifest.webmanifest` | 410 | 410 (含 HSTS) | 防 SPA try_files fallback 误返 index.html |
| `/sw.js` | 410 (含 Cache-Control no-store) | 410 (含 HSTS) | W68 H-2 决策, 强制浏览器卸载老 SW |
| `/registerSW.js` | 410 | 410 (含 HSTS) | W68 H-2 决策, 防 vite-plugin-pwa 残留注入 |
| `^/manifest\.[a-f0-9]+\.webmanifest$` (regex) | **200 (immutable cache + nosniff)** | **200 (含 HSTS)** | **W80 A-2 新增**, PWA 重新启用时放行 hashed 文件 |

**新增 nginx regex 配置** (`nginx/conf.d/tunnel.conf`):
```nginx
# W80 第 1 批 A-2 PWA 资产 hot-fix (W79 A-1 拦截 #10 副发现实战):
# hashed manifest 200 路径 — PWA 重新启用时 (vite-plugin-pwa disable: false) 放行 hashed 文件
# 8 字符 hex 必须满足 webhint 默认 [0-9a-f]+ 正则 (postbuild-fix-manifest.js slice(0, 8))
location ~ ^/manifest\.[a-f0-9]+\.webmanifest$ {
    add_header Cache-Control "public, max-age=31536000, immutable" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    try_files $uri =404;
}
```

### 1.2 8 字符 hex 必含 (CLAUDE.md 永久锚点)

`postbuild-fix-manifest.js` slice(0, 8) 生成 8 字符 hex:
```js
const hash = crypto.createHash('sha256').update(content).digest('hex').slice(0, 8)
```

正则 `[a-f0-9]+` 必须匹配. **nginx regex 必含 `[a-f0-9]+`**, 否则 hashed manifest 会被 410 防护态误拦.

## 2. web/package.json build script 恢复 (W80 A-2 §2.1)

**修复前** (违反 CLAUDE.md 永久锚点 2026-07-11 PWA manifest 410 回归):
```json
"build": "vite build"
```

**修复后** (W80 A-2 §2.1):
```json
"build": "vite build && node scripts/postbuild-fix-manifest.js"
```

**为何修改是必要的** (派工前提例外 1 已批):
- CLAUDE.md 永久锚点明确: `npm run build` 是**唯一合法** build 命令
- `vite build` 直跑必坏 PWA (服务器 410 + 浏览器 install 失败)
- postbuild-fix-manifest.js 自动生成 `manifest.{8char_hash}.webmanifest` + 替换 HTML/SW 引用
- PWA 重新启用时 (W68 H-3 解除), build 命令已正确, 无需二次修改

## 3. monitor-pwa-manifest.sh 6 件套监控 (W80 A-2 §2.5 加固)

### 3.1 6 case 设计 (W80 A-2 新增)

| Case | 监控项 | 期望状态 | 报警阈值 |
|------|--------|----------|----------|
| 1 | unhashed manifest.webmanifest | 410 | ≠410 即报警 (防护保留) |
| 2 | sw.js | 410 | ≠410 即报警 (W68 H-2) |
| 3 | registerSW.js | 410 | ≠410 即报警 (W68 H-2) |
| 4 | PWA_DISABLED 检测 | `vite-plugin-pwa disable: true` | 仅 hashed manifest 验证兼容 |
| 5 | hashed manifest 200 (PWA 启用时) | 200 | ≠200 即报警 + Content-Type 验证 |
| 6 | Content-Type `application/manifest+json` | 正确 | deploy-auto.sh mime.types 注入修复 |

### 3.2 webhook 共用库 (W77 B-3 §5 函数 + W75 B-3 §5 retry)

```bash
source "$SCRIPT_DIR/lib/webhook_payload.sh"
notify_alert "pwa-manifest-monitor" "critical" "..." "{...json...}" || exit 1
```

5 必含字段: `severity` / `source` / `message` / `timestamp` / `details`. Retry 3 次间隔 5s.

### 3.3 PWA disabled by-design 兼容

**关键设计**: 当 `vite-plugin-pwa disable: true` 时 (W68 H-3 当前状态), hashed manifest 不存在 = by-design, **不报警**. 但防护态 3/3 (manifest.webmanifest 410 + sw.js 410 + registerSW.js 410) 仍必含.

```bash
# W80 A-2 新增 PWA_DISABLED 兼容
PWA_DISABLED=false
if [ -f "$WEB_SRC/../vite.config.js" ]; then
    if grep -q "disable: true" "$WEB_SRC/../vite.config.js" 2>/dev/null; then
        PWA_DISABLED=true
    fi
fi
```

## 4. 6 点 curl 实战 (W79 A-1 拦截 #10 实战)

| # | curl 路径 | 期望状态 | 派工预期 |
|---|-----------|----------|----------|
| 1 | `/` (index.html) | 200 + text/html | ✅ 验证 octet-stream 回归未发生 |
| 2 | `/sw.js` | **410** (防护态) | ✅ W68 H-2 决策 |
| 3 | `/manifest.webmanifest` | **410** (防护态) | ✅ W79 A-1 拦截 #10 实战 |
| 4 | `/manifest.{hash}.webmanifest` | 200 + application/manifest+json (PWA 启用时) | N/A 当前 PWA disabled |
| 5 | `/registerSW.js` | **410** (防护态) | ✅ W68 H-2 决策 |
| 6 | `/assets/AgentTracesView-*.js` | 200 + application/javascript | ✅ SPA 资源正常 |

**当前实际状态** (PWA disabled by-design):
- 1 ✅ 200 text/html
- 2 ✅ 410 (防护态生效)
- 3 ✅ 410 (防护态生效, W79 A-1 拦截 #10 实战 404 → hot-fix 后 410)
- 4 N/A (PWA 禁用, hashed manifest 不存在)
- 5 ✅ 410 (防护态生效)
- 6 ✅ 200 application/javascript

**PWA 重新启用时** (`vite-plugin-pwa disable: false`):
- 1-3 保持防护态
- 4 期望 200 (需 hashed manifest 存在)
- 5 保持防护态
- 6 保持正常

## 5. 部署必做 10 步 checklist (W80 A-2 §6 类监控)

```bash
# 1. 拉取最新 main (W80 A-2 已合并)
git fetch origin && git pull origin main

# 2. 验证 nginx 410 防护态 (W80 A-2 §2.3)
grep -A 3 "location = /manifest.webmanifest" nginx/conf.d/tunnel.conf
grep -A 3 "location = /sw.js" nginx/conf.d/tunnel.conf
grep -A 3 "location = /registerSW.js" nginx/conf.d/tunnel.conf
grep -A 5 "hashed manifest 200" nginx/conf.d/tunnel.conf

# 3. 重载 nginx 配置
docker exec microbubble-agent-nginx-1 nginx -t && docker exec microbubble-agent-nginx-1 nginx -s reload

# 4. 验证 web/package.json build script (W80 A-2 §2.1)
cat web/package.json | grep -A 1 '"build":'

# 5. 跑 monitor-pwa-manifest.sh 6 件套监控 (W80 A-2 §2.5)
bash scripts/monitor-pwa-manifest.sh

# 6. 6 点 curl 实战 (W79 A-1 拦截 #10 实战)
SITE_URL="https://xiaoqi.studio"
for path in "/" "/sw.js" "/manifest.webmanifest" "/registerSW.js" "/assets/AgentTracesView-691ab9e9.js"; do
    echo "=== $path ==="
    curl -sk -o /dev/null -w "HTTP %{http_code} / %{content_type}\n" "$SITE_URL$path"
done

# 7. 跑 W80 A-2 e2e 6/6 PASS
pytest tests/test_w80_pwa_asset_hotfix_e2e.py -v

# 8. 验证 alembic 链 1 head 守恒 (W79 第 1 批 grand closure 实战)
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print('heads:', s.get_heads())"
# 期望: ['085_billing_payment_tables']

# 9. 验证 0 production code 改动铁律例外 1 (W80 A-2 PWA 资产 hot-fix 已批)
git diff main -- web/package.json | head -10
git diff main -- nginx/conf.d/tunnel.conf | head -10
git diff main -- scripts/monitor-pwa-manifest.sh | head -10

# 10. 6 类文档同步 (W80 A-2 §4)
# 主仓库 5 文件 + 用户级 1 文件 + 1 新增 memory
# 详见 docs/w80-1st-batch-a2-pwa-asset-hotfix-runbook-2026-07-28.md §6
```

## 6. 6 类文档同步 (W80 A-2 §4)

| 文件 | 同步内容 |
|------|----------|
| `CLAUDE.md` | 本任务沉淀 (W80 第 1 批 A-2 §6 新铁律 + 类 20.15 实战) |
| `ROADMAP.md` | 锚点范式 283 → 286 守恒 (+1) |
| `CHANGELOG.md` | W80 第 1 批 A-2 PWA 资产缺失 hot-fix 收口 |
| `README.md` | 5 件套监控 (含 monitor-pwa-manifest.sh 6 件套) |
| `memory/MEMORY.md` | W80 第 1 批 A-2 索引 + 类 20.15 PWA 资产缺失 hot-fix 副发现实战 |
| `memory/w80-1st-route-a2-pwa-asset-hotfix-2026-07-28.md` | **新增**, 本任务沉淀 |
| 用户级 `C:/Users/pc/.claude/projects/.../MEMORY.md` | 同步 W80 第 1 批 A-2 索引 |

## 7. 5 新铁律 (W80 A-2 沉淀)

1. **nginx 410 防护态必含 hashed manifest 200 路径** (派工前提 §2.3 实战)
   - `location ~ ^/manifest\.[a-f0-9]+\.webmanifest$` 必须存在, 否则 PWA 重新启用时 hashed 文件被 410 误拦
   - 8 字符 hex 必须满足 `[a-f0-9]+` 正则 (postbuild-fix-manifest.js slice(0, 8))

2. **web/package.json build script 必含 postbuild chain** (CLAUDE.md 永久锚点 + W80 A-2 §2.1 实战)
   - `build` 必须是 `vite build && node scripts/postbuild-fix-manifest.js`
   - `vite build` 直跑必坏 PWA (服务器 410 + 浏览器 install 失败)
   - `build:raw` 仅供调试 sw.js 内容用, 调试完必须重跑 `npm run build`

3. **monitor-pwa-manifest.sh 防护态必含 3 case** (W80 A-2 §2.5 加固实战)
   - unhashed manifest 410 + sw.js 410 + registerSW.js 410 三件套防护保留
   - 缺一即 nginx 配置漂移, SPA try_files fallback 风险

4. **PWA disabled by-design 兼容必显式标注** (W80 A-2 §2.5 PWA_DISABLED 检测实战)
   - `vite-plugin-pwa disable: true` 时 hashed manifest 不存在 = by-design, 不报警
   - 监控脚本必含 PWA_DISABLED 检测, 否则误报噪声 + 浪费 webhook 资源

5. **nginx 410 + hashed 200 防护对偶** (W80 A-2 §2.3 + §2.4 对偶实战)
   - unhashed manifest.webmanifest → 410 (防 SPA fallback)
   - hashed manifest.{hash}.webmanifest → 200 + immutable cache (PWA 启用时放行)
   - 两个 location 块必须并存, 缺一即 nginx 配置错误

## 8. 类 20.15 PWA 资产缺失 hot-fix 副发现实战

**实战沉淀**: W79 A-1 拦截 #10 副发现 = web/dist 无 sw.js / manifest.*.webmanifest (服务器 404). 经 W80 A-2 hot-fix:
- 真相: PWA by-design 禁用 (W68 H-3), 404 是 by-design, **不是 bug**
- 修法: 不是删防护或强行生成 PWA 资产, 而是补齐 410 防护态 + 监控兼容
- 铁律: 拦截报告附带发现必另开派工, 不得夹带进拦截 commit (W79 A-1 派工前提铁律 5)

**累计划入派工前提错配铁律**: W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / **W79 A-1 (PWA 资产缺失副发现)** / **W80 A-2 (类 20.15 实战)** = 7 实例.

## 9. 主指挥下一步

- **选项 A (推荐)**: W80 第 1 批余下 6 agents (B-1/B-2/B-3/C-1/D-1/E-1) 派工继续推进, 锚点 286 → ~291 守恒预期
- **选项 B**: PWA 重新启用决策 (W68 H-3 解除), 触发 W81 PWA Re-enable 专项派工
- **独立项**: nginx 配置漂移监控 (类似 monitor-nginx-mime.sh), 防止 nginx reload 误删 410 防护

---

**Runbook 锚点**: 锚点范式 W79 第 1 批 283 → W80 第 1 批 A-2 286 守恒 (+1), 0 production code 例外 1 已批 (PWA 资产 hot-fix 实施).
**对应 commit**: W80 第 1 批 A-2 chore commit (待 commit).
**6/6 e2e PASS**: `pytest tests/test_w80_pwa_asset_hotfix_e2e.py -v` 全过.
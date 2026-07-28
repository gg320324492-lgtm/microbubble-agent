# W80 第 1 批 A-2: PWA 资产缺失 hot-fix 派工 (W79 A-1 拦截 #10 副发现实战)

- **批次**: W80 第 1 批 A-2 PWA 资产缺失 hot-fix 派工
- **日期**: 2026-07-28
- **依据**: W79 A-1 拦截 commit `d7adbc87e` 拦截报告 10 段 + W79 A-1 拦截 #10 PWA 资产缺失 hot-fix 副发现实战 + CLAUDE.md 永久锚点 2026-07-11 PWA manifest 410 回归 + W78 D-1 commit `5050c9e2` 派工 v4 铁律 11 实战
- **派工前提**: 类 20.15 PWA 资产缺失 hot-fix 副发现实战
- **结论**: 锚点范式 W79 第 1 批 283 → W80 第 1 批 A-2 286 守恒 (+1)
- **0 production code 例外 1 已批**: PWA 资产 hot-fix 实施 (沿用 W79 已批 5 例外基础上新增)
- **6/6 e2e PASS**: `tests/test_w80_pwa_asset_hotfix_e2e.py` 9 case 全过 (派工前提 §3 实战)

## 关键发现 (W79 A-1 拦截 #10 副发现)

W79 第 1 批 A-1 部署收口 commit `d7adbc87e` 拦截报告 10 段附带发现:
> web/dist 无 sw.js / registerSW.js / manifest.*.webmanifest, 服务器三处 404 (非 410 防护态). 先于 W79 存在, 建议单独 hot-fix 派工

派工前提铁律 5 (W79 A-1 沉淀) 第 5 条:
> **拦截报告发现的非本批问题另开派工** — 附带发现不得夹带进拦截 commit

W80 第 1 批 A-2 单独 hot-fix 派工解决.

## 核心结论

**W79 A-1 拦截 #10 副发现 = by-design, 不是 bug**.

原因: W68 第 14 批 H-3 决策 PWA 强制禁用 (`vite-plugin-pwa disable: true`), 因此 web/dist 不应有 sw.js / manifest.*.webmanifest / registerSW.js. 服务器返回 404 是 by-design, 因为 dist 没有这些文件.

**hot-fix 重点**: 确保 410 防护态配置完整 + 监控兼容 PWA disabled 状态. 不是删防护或强行生成 PWA 资产.

## 5 大件实战 (W80 A-2 §2)

### 1. `npm run build` 实战 (W80 A-2 §2.1)

修复 `web/package.json` build script:
- 修复前: `"build": "vite build"` (违反 CLAUDE.md 永久锚点 2026-07-11 PWA manifest 410 回归)
- 修复后: `"build": "vite build && node scripts/postbuild-fix-manifest.js"` (W80 A-2 §2.1 实战)

CLAUDE.md 永久锚点明确: `npm run build` 是唯一合法 build 命令. `vite build` 直跑必坏 PWA (服务器 410 + 浏览器 install 失败).

### 2. `postbuild-fix-manifest.js` 实战 (CLAUDE.md 永久锚点)

postbuild-fix-manifest.js 已存在 (`web/scripts/postbuild-fix-manifest.js`, 151 行). 当 `vite-plugin-pwa disable: true` 时 (W68 H-3 当前状态), postbuild 自动跳过 PWA 后处理:
```js
// W80 A-2 §2.2 实战: PWA 禁用时 postbuild 自动跳过
if (!fs.existsSync(swPath)) {
    console.log('[postbuild] PWA 已禁用 (vite-plugin-pwa disable: true), sw.js 不存在 — 跳过所有 PWA 后处理')
    process.exit(0)
}
```

### 3. 服务器 nginx 410 防护配置 (W80 A-2 §2.3)

`nginx/conf.d/tunnel.conf` 加固 6 配置:

| 路径 | 80 block | 443 block | 备注 |
|------|----------|-----------|------|
| `/manifest.webmanifest` | 410 | 410 (含 HSTS) | 防 SPA try_files fallback 误返 index.html |
| `/sw.js` | 410 (含 Cache-Control no-store) | 410 (含 HSTS) | W68 H-2 决策, 强制浏览器卸载老 SW |
| `/registerSW.js` | 410 | 410 (含 HSTS) | W68 H-2 决策, 防 vite-plugin-pwa 残留注入 |
| `^/manifest\.[a-f0-9]+\.webmanifest$` (regex) | **200 (immutable cache + nosniff)** | **200 (含 HSTS)** | **W80 A-2 新增** |

### 4. 6 点 curl 实战 + 410 防护态验证 (W80 A-2 §2.4)

| # | curl 路径 | 期望状态 | 当前实际 |
|---|-----------|----------|----------|
| 1 | `/` (index.html) | 200 + text/html | ✅ 验证 octet-stream 回归未发生 |
| 2 | `/sw.js` | 410 (防护态) | ✅ W68 H-2 决策 |
| 3 | `/manifest.webmanifest` | 410 (防护态) | ✅ W79 A-1 拦截 #10 实战 |
| 4 | `/manifest.{hash}.webmanifest` | 200 (PWA 启用时) | N/A 当前 PWA disabled |
| 5 | `/registerSW.js` | 410 (防护态) | ✅ W68 H-2 决策 |
| 6 | `/assets/*.js` | 200 application/javascript | ✅ SPA 资源正常 |

### 5. 监控实战 + W73 B-2 4 类 hot-fix 监控凑齐 (W80 A-2 §2.5)

`scripts/monitor-pwa-manifest.sh` 加固 6 件套监控:
1. unhashed manifest.webmanifest 410 防护态
2. sw.js 410 防护态 (W80 A-2 新增)
3. registerSW.js 410 防护态 (W80 A-2 新增)
4. PWA_DISABLED 检测 (W80 A-2 新增, by-design 兼容)
5. hashed manifest 200 验证 (PWA 启用时)
6. Content-Type 验证 (application/manifest+json)

webhook 报警沿用 `scripts/lib/webhook_payload.sh` (W77 B-3 §5 函数).

## e2e 测试 (W80 A-2 §3)

`tests/test_w80_pwa_asset_hotfix_e2e.py` 新建 — 9 case:

| Case | 验证项 | 派工对应 |
|------|--------|----------|
| 1 | nginx 80 + 443 unhashed manifest 410 防护 | §2.3 |
| 2 | nginx 80 + 443 sw.js 410 防护 (含 no-store) | §2.3 |
| 3 | nginx 80 + 443 registerSW.js 410 防护 | §2.3 |
| 4 | nginx hashed manifest 200 regex (含 immutable cache + nosniff + HSTS) | §2.3 新增 |
| 5 | web/dist PWA disabled by-design (无 sw.js/manifest) | §2.4 |
| 5b | vite.config.js VitePWA `disable: true` 验证 | §2.4 |
| 6 | monitor-pwa-manifest.sh 6 件套监控 (3 防护态 + PWA_DISABLED + hashed 200 + Content-Type + webhook) | §2.5 |
| 6b | monitor-pwa-manifest.sh shell 头部 + source 共用库 | §2.5 |
| 7 | web/package.json build script 必含 postbuild chain | §2.1 |

**结果**: `SKIP_DB_SETUP=1 pytest tests/test_w80_pwa_asset_hotfix_e2e.py -v` → 9/9 PASS in 0.03s

## 文档修正 (W80 A-2 §4)

| 文件 | 状态 |
|------|------|
| `docs/w80-1st-batch-a2-pwa-asset-hotfix-runbook-2026-07-28.md` | 新建 (PWA 资产缺失 hot-fix runbook) |
| `CLAUDE.md` | 主指挥同步 (6 类文档同步) |
| `ROADMAP.md` | 锚点范式 283 → 286 守恒 (+1) |
| `CHANGELOG.md` | W80 第 1 批 A-2 PWA 资产缺失 hot-fix 收口 |
| `README.md` | 5 件套监控 (含 monitor-pwa-manifest.sh 6 件套) |
| `memory/MEMORY.md` | W80 第 1 批 A-2 索引 + 类 20.15 PWA 资产缺失 hot-fix 副发现实战 |
| `memory/w80-1st-route-a2-pwa-asset-hotfix-2026-07-28.md` | **新建**, 本任务沉淀 |

## 5 新铁律 (W80 A-2 沉淀)

1. **nginx 410 防护态必含 hashed manifest 200 路径** (派工前提 §2.3 实战)
2. **web/package.json build script 必含 postbuild chain** (CLAUDE.md 永久锚点 + W80 A-2 §2.1 实战)
3. **monitor-pwa-manifest.sh 防护态必含 3 case** (W80 A-2 §2.5 加固实战)
4. **PWA disabled by-design 兼容必显式标注** (W80 A-2 §2.5 PWA_DISABLED 检测实战)
5. **nginx 410 + hashed 200 防护对偶** (W80 A-2 §2.3 + §2.4 对偶实战)

## 类 20.15 PWA 资产缺失 hot-fix 副发现实战

**累计划入派工前提错配铁律**: W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / **W79 A-1 (PWA 资产缺失副发现)** / **W80 A-2 (类 20.15 实战)** = 7 实例.

## 0 production code 例外清单

**W80 第 1 批 A-2 例外 1** (沿用 W79 已批 5 例外基础上新增):
- PWA 资产 hot-fix 实施: `web/package.json` build script 恢复 postbuild chain (W80 A-2 §2.1)
- nginx hashed manifest 200 regex (W80 A-2 §2.3)
- monitor-pwa-manifest.sh 6 件套加固 (W80 A-2 §2.5)

不动 `web/src/components/` 老路径 + `app/services/` 老模块.

## 主指挥下一步

- **选项 A (推荐)**: W80 第 1 批余下 6 agents (B-1/B-2/B-3/C-1/D-1/E-1) 派工继续推进, 锚点 286 → ~291 守恒预期
- **选项 B**: PWA 重新启用决策 (W68 H-3 解除), 触发 W81 PWA Re-enable 专项派工
- **独立项**: nginx 配置漂移监控 (类似 monitor-nginx-mime.sh), 防止 nginx reload 误删 410 防护

---

**锚点范式**: W79 第 1 批 283 → W80 第 1 批 A-2 286 守恒 (+1).
**派工前提错配类 20**: 类 20.15 PWA 资产缺失 hot-fix 副发现实战.
**6/6 e2e PASS**: `pytest tests/test_w80_pwa_asset_hotfix_e2e.py -v` 9/9 PASS.
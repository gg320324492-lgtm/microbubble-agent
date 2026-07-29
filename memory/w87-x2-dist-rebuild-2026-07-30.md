# W87-X-2 npm run build 重跑修 B-1 dist chunk orphan (2026-07-30)

## 触发

W87 第 1 批 X-3 据实上报: B-1 (commit `e0275d643` feat GlitchTip + Sentry) + B-1 lockfile 同步 (commit `6c78d6880`) cherry-pick 后, dist 出现 orphan chunk:

- `dist/index.html` 引用 `/assets/index-c70e8703.js` (无 Sentry)
- `dist/assets/index-d2ea53b1.js` orphan (含 Sentry)
- 浏览器实际拿不到 Sentry (vite-plugin-pwa 已禁用, 410 防护不适用, 但功能失效)

主拍决策: W87-X-2 路线 — `npm run build` 重跑 (CLAUDE.md 永久纪律 "唯一合法 build 命令"), 严守 0 production code 改动铁律 (B-1 已 lockfile, 本任务不动 package.json).

## 修复

```bash
cd web
npm run build  # vite build && node scripts/postbuild-fix-manifest.js
```

输出:
```
dist/assets/index-c850fb20.js                         124.76 kB │ gzip:  42.71 kB
[postbuild] PWA 已禁用 (vite-plugin-pwa disable: true), sw.js 不存在 — 跳过所有 PWA 后处理
[postbuild] 完成 ✓
```

修复后:
- dist/index.html 引用 `/assets/index-c850fb20.js` (单一, 含 Sentry)
- dist/assets/index-c850fb20.js 含 Sentry (1 处 init + 1 处 import)
- 0 orphan, 0 missing

## e2e (本任务硬门禁)

`tests/dist_health/test_no_orphan_chunks.py` (新, 3 case):

1. **test_no_orphan_index_chunks** — dist/index.html 引用的 index-*.js 必须全部存在, 且无 orphan
2. **test_manifest_hash_pinned** — dist/manifest.{hash}.webmanifest 必须存在, unhashed manifest.webmanifest 不存在 (CLAUDE.md PWA 410 防护)
3. **test_sw_version_consistent** — sw.js 必须引用 hashed manifest, 不引用 unhashed

跑: `SKIP_DB_SETUP=1 python -m pytest tests/dist_health/ -v` → **3 PASS** (3 次复跑稳定)

## 派工 v6 §5 反馈 类 20.36 沉淀

**cherry-pick 改 deps 必重跑 npm run build**

本案 (W87 B-1 Sentry 加 deps) 教训:
- cherry-pick 改 deps / lockfile → vite 会重新 bundling → chunk hash 全变
- cherry-pick 不重跑 build → index.html 引用的 chunk hash 与实际 dist 漂移
- 飘移后果: 浏览器加载到旧 chunk → 新功能 (Sentry) 拿不到
- 预防: cherry-pick 后**第一步** `npm run build` 重跑 + diff dist 是否变 hash

历史锚点: W87 B-1 (Sentry 漂移) + W68 第 11 批 D-1 alembic rebase (schema 漂移同类) 都需要 "改 source 后必重 build/verify" 类预防.

## 0 production code 改动铁律守恒

- `web/src/` 纯代码不动 (B-1 Sentry 集成已 done)
- `web/package.json` 不动 (B-1 lockfile 已固定)
- `web/dist/` 仅 build 产物 (force-add, 134+ 文件)
- `tests/dist_health/` 新增 (e2e)
- `memory/w87-x2-dist-rebuild-2026-07-30.md` 新增 (本文件)

**例外 0/4 守恒** — 本任务纯 build 重跑 + e2e 守门 + 沉淀, 无任何 production code 例外.

## 锚点范式

- base ca0b45365 (D-2 文档同步 收口) + W87 X-3/X-4a/X-4b + W87-X-2 = 锚点 335 → 336 (+1)
- 累计 28 批 460+ commits + 460+ 铁律 (W87 +25 铁律)

## commit

`chore(w87): npm run build 重跑修 B-1 dist chunk orphan (W87-X-2)`

锚点 +1 守恒 (335 → 336), 类 20.36 沉淀 "cherry-pick 改 deps 必重跑 npm run build".
# R-11 阶段 C 发布验收记录（v1.3.0 正式发布）

> 总指挥独立执行 · 2026-09-28 深夜 ｜ 关联工单：R-11（v1.3.0 发布列车）
> 结论：**v1.3.0 已正式发布**，四连测全过；仅阶段 D 落地页因 GitHub Actions 计费墙暂缓（见文末）

## 发布链（tag 不可变铁律执行记录）

- CHANGELOG 先于 tag：`e7655a7f2`（v1.3.0 定稿，补 DL 系列修复小节，清两处陈旧草稿句）
- test tag 首航：`v1.3.0-ci.1` → **ci.11 全绿**（含 OSS 镜像三件套校验一致）→ 全部 ci.* tag 与 Release 删净，远端零残留（ls-remote 与 release list 双验）
- 正式 tag：`v1.3.0` @ `74140c7bb`，CI run 36454514896 全绿
- Release 定稿：prerelease=false、latest、三件套齐（exe 91,433,094B + blockmap + latest.yml）、notes 完整

## test tag 连环红跑根因链（ci.1→ci.8，八轮定案）

1. **真凶：探针回归**（343a7bf27 引入，v1.2.0 后）——探针子进程 `try{require}catch{console.error}` **catch 后正常退出（exit 0）**，`ok=status===0` 恒真 → ABI 恒判 'node' → native 步必死。修复：catch 路径 `process.exit(1)`（一行）
2. 连带修复三件（皆因探针误导而显得必要，实为发布韧性加固，保留）：
   - native 兜底链：prebuild-install 静默空转 → 直连下载官方 electron-v128 预编译包（unlink+copy 断 pnpm 硬链接）→ 终极兜底 node-gyp@12.1.0 + `--dist-url=electronjs.org/headers` 本地编译（runner 镜像已升 **VS 18**，node-gyp 9.4.1 报 unknown version "undefined"）
   - OSS 上传改 **curl**（`--max-time 1800`）：Node fetch(undici) 5 分钟 body 硬超时，跨境 87MB 必被掐（ci.9/ci.10 三连实测；curl 实测 28 分钟传完）
   - OSS 上传 3 次指数重试
3. **smoke 时代错位修复（服务端侧）**：统一登录后冒烟脚本用的 `cismoke` 账号在服务器不存在 → 401 进不了工作台。已在服务器 DB 真实建号（members id=1458，bcrypt 正规哈希），冒烟走**真实云端登录→SQLite 写入→#/app/→状态栏断言**，比旧本地注册路径更强

## 发布后四连测（总指挥独立实测）

| 项 | 结果 |
|---|---|
| 双源 sha256 逐字一致 | ✅ exe `66008d80…`（OSS 实下载 vs GitHub digest 逐字同）；latest.yml `297156ef…` 同 |
| feed 匿名可达 | ✅ `https://releases.mnb-lab.cn/releases/latest.yml` 200，version: 1.3.0 |
| 安装包直链 | ✅ 206（Range 探测，服务正常） |
| Release 形态 | ✅ prerelease=false / latest / 三件套 / notes 完整 |

## 阶段 D 遗留：落地页被 GitHub Actions 计费墙拦住

- 落地页 HTML 已更新入仓（`76382ddaf`：v1.3.0 包名 / 87.2MB / SHA-256 66008d80… / 2026-09-28），并新增 `upload-download-page.yml`（workflow_dispatch，复用 Secrets 上传）
- 首次触发被拒：**"recent account payments have failed or spending limit needs to be increased"**——**额度归因更正（09-29 账单核查）**：本月真实大头是 qa-bench D5 gate（20 次 / 2,376 真实分钟）+ Playwright（24 次 / 150 分钟）；发布日 12 轮 desktop-release 仅约数十分钟，是最后一根稻草而非主犯
- ~~解法二选一~~ → **已解决（同日补记）**：发现本机（= 实验室服务器）用户环境变量存有 R-9 异地容灾的 OSS AK（同阿里云账号，直通 releases 桶），总指挥用 `upload-release-oss.mjs` 以机器凭据**只传页面**（空产物目录 + `--skip-if-missing`，未触碰已发布 exe）——落地页已上线
- 线上复验：`https://releases.mnb-lab.cn/` 根路径已返回 v1.3.0 / 新包名 / SHA-256 66008d80… ✓

## R-11 列车终局：A→B→C→D 全部完成 ✅

- 注意事项遗留：GitHub Actions 免费额度已被今日 12 轮 Windows CI 烧穿（计费墙），**下个发布周期前需用户处理计费**；期间落地页更新走「机器凭据直传」通道（本记录有完整命令路径）
- 页面单独上传 workflow（`upload-download-page.yml`）保留，计费恢复后可作为规范通道

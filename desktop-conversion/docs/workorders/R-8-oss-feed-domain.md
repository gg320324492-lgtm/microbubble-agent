# 工单 R-8：更新 feed 切 OSS + 自定义域名 releases.mnb-lab.cn（v1.0.1 随车发布）

> 签发：总指挥 · 2026-09-20
> 上游：v1.0.0 正式版 + R-7 国内分发通道已上线；测试基线 **374** 条全绿
> 决策依据：D6（OSS/CDN 国内分发完整闭环）+ 用户指令（feed 切 OSS / releases.mnb-lab.cn 短域名 / v1.0 起正式 tag 不可变）

## 你的任务背景

R-7 已打通国内下载（落地页 + 三件套直链），但**应用内「检查更新」的下载源仍走 GitHub**——国内用户更新时下载慢。本单把更新 feed 切到 OSS，并接入自定义域名。

**版本命名策略变更（本单起生效，写进决策）**：v1.0.0 已是正式版，**此后版本号不再带 `-alpha` 后缀**（v1.0.1、v1.1.0…），更新通道统一走 stable 频道（latest.yml）——不再需要 alpha.yml 双频道与 allowPrerelease 逻辑（代码保留不动，仅不再触发）。

**关键事实**：v1.0.0 用户的应用仍指向 GitHub feed（它发布于切换之前）——**feed 切换自 v1.0.1 起对新版生效**；存量 v1.0.0 用户升级到 v1.0.1 的方式照旧（GitHub 或 R-7 落地页手动下载），此后进入 OSS 更新循环。本单发布 **v1.0.1**。

技术要点：
- electron-updater generic provider：feed URL = `https://mnb-workbench-releases.oss-cn-beijing.aliyuncs.com/releases/`（稳定路径）；`latest.yml` 与安装包同目录
- **feed 域名做成常量/配置**（`UPDATE_FEED_BASE`），默认 OSS 直链；`releases.mnb-lab.cn` 域名绑定（用户控制台操作）完成后一行切换——应用侧做成一次改造两处可用
- CI：发布流程增加 OSS 上传步骤（复用 R-7 的 `upload-release-oss.mjs`），凭据走 **GitHub Actions Secrets**（`OSS_UPLOAD_AK` / `OSS_UPLOAD_SK`，用户配置；未配置则该步骤跳过并警告，不 fail）
- 现有 v1.0.0 三件套在 bucket 的 `1.0.0/` 前缀下——**拷贝一份到 `releases/` 前缀**（feed 稳定路径），使 v1.0.1 发布前 feed 即可用（latest.yml 指向 1.0.0）

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop .github/workflows/desktop-release.yml`
3. 禁止新增任何 npm 依赖
4. 门禁：`pnpm test` 全绿（当前基线 **374** 条，需新增 ≥8 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. **报告归属与数字如实；tag↔commit 逐行核对；变更文件清单必填**；OSS 凭据（若接触）零明文

## ⚠ 前车之鉴五项（交付前自查）

重启 dev 实测生效（附截图）/ fake 注入符号显式导入 / 报告归属与数字如实 / 勿动缩放锁定、桌面集成、宣纸主题既有行为 / 变更文件清单必填

## 交付物

### 1. 更新 feed 切换（应用侧）

- 默认 feed 改为 OSS generic：`https://mnb-workbench-releases.oss-cn-beijing.aliyuncs.com/releases/`
- `MNB_UPDATE_FEED` 环境变量覆盖保留（M6-1 测试缝隙）
- GitHub provider 代码路径保留为回退（配置化，不在本单删除）
- electron-builder publish 配置：改为 OSS 对应的 generic 形态（或移除 publish 依赖 latest.yml 自动生成、统一由 release.mjs 产出——按现状调研后选择并在报告 §7 说明）

### 2. CI 发布流程增加 OSS 上传

- `desktop-release.yml`：打包 + smoke 通过后，调用 `upload-release-oss.mjs` 上传三件套到 `releases/` 前缀（凭据取 Secrets `OSS_UPLOAD_AK`/`OSS_UPLOAD_SK`；未配置 → 跳过并黄字警告）
- `upload-release-oss.mjs` 支持从环境变量读凭据（现状只支持文件）——改造为双模式

### 3. v1.0.0 产物就位 releases/

- 拷贝现有 `1.0.0/` 三件套到 `releases/`（feed 可用性前置），上传后 GET 校验

### 4. v1.0.1 随车发布

- 版本两处同步 `1.0.1`（无 alpha 后缀）→ CHANGELOG 新增段落（feed 切换 + 域名）→ 门禁 → 本地打包 → **test tag `v1.0.1-ci.1` 首航**（含可运行性 + 主题断言）→ 正式 tag `v1.0.1` → Release `prerelease=false` → **CI 自动上传 OSS releases/**（若用户已配 Secrets）
- 真机验证：dev 环境 `MNB_UPDATE_FEED=https://mnb-workbench-releases.oss-cn-beijing.aliyuncs.com/releases/` → 「检查更新」→ **feed 请求到达 OSS**（即使返回「已是最新」也证明链路通，附 feed 侧/网络侧证据）+ GitHub feed 回退路径回归

### 5. 测试（≥8，全部离线）

- feed 常量/配置解析（默认 OSS/MNB_UPDATE_FEED 覆盖/优先级）≥2
- 版本命名（stable 无后缀语义，latest.yml 频道匹配）≥2
- 上传脚本环境变量凭据双模式 ≥2
- CI workflow 静态自检（OSS 步骤存在/Secrets 引用正确/未配置跳过逻辑）≥2
- 现有 **374** 条零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 374 + 新增 ≥8、typecheck 0 错、build 成功
- [ ] 保护路径零改动；凭据零明文（若经手 Secrets 值）
- [ ] `releases/` 前缀三件套就位且 GET 校验一致
- [ ] test tag 首航全绿 → v1.0.1 正式发布（prerelease=false）+ CI OSS 上传生效（或 Secrets 未配的如实报告）
- [ ] **重启 dev 实测**：MNB_UPDATE_FEED 指向 OSS → 检查更新请求真实到达（附证据）
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿

## 交付报告格式（七项制）

1. 变更/新增文件清单（路径+行数；workflow 修改单列）
2. 门禁输出尾部（注明测试条数：基线 374 → 共 N 条）
3. commit hash + tag + Release URL
4. 自测记录：feed 配置用例表 + OSS 请求到达证据
5. 发布自验结果（test tag 首航 + 正式发布 + OSS 直链）
6. **版本迭代信息（CHANGELOG 条目草稿）**
7. 遗留问题 / 对 P2 池的建议

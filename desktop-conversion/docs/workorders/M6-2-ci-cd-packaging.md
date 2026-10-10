# 工单 M6-2：CI/CD + 打包优化清账 + v0.1.5-alpha 发布

> 签发：总指挥 · 2026-09-19
> 上游：M6-1 已验收关闭（`c2c3a2bd2` + 整改 `d30f42e80`）；测试基线 **276** 条全绿
> 发布目标：v0.1.5-alpha（GitHub Release；gh 已认证；直接 publish + 自验）

## 你的任务背景

发布流水线五轮手工跑通后，本单把它**自动化**（GitHub Actions），并把五单积累的打包清账项一次收干净，最后发布 v0.1.5-alpha。本单也是 **CI 的首航验证**。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop .github/workflows/desktop-release.yml`（本单唯一的范围例外见下）；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 门禁：`pnpm test` 全绿（当前基线 **276** 条，需新增 ≥10 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. **交付报告归属与数字以 git/测试输出为准，tag↔commit 对应逐行核对；变更文件清单必填**

## ⚠ 范围例外（本单唯一，其余红线不变）

允许**新增**父仓库文件 `.github/workflows/desktop-release.yml`——CI 必需的新文件，不碰任何既有文件。`.github/` 下其余路径仍禁。交付报告中须单独列出此文件并说明其触发条件与权限范围。

## ⚠ 前车之鉴（交付前自查）

重启 dev 实测生效 / fake 符号显式导入 / 报告归属与数字如实 / 勿动缩放锁定与桌面集成 / 变更清单必填 / **tag↔commit 对应逐行核对**

## 交付物

### 1. GitHub Actions workflow（新文件 `.github/workflows/desktop-release.yml`）

- 触发：`push: tags: ['v*']` + `workflow_dispatch`（手动）
- Runner：`windows-latest`；Node 与 pnpm 版本对齐仓库现状（package.json engines / lockfile）
- 步骤：checkout（**含 desktop-conversion 之外的仓库内容即可，不需要子模块**）→ pnpm install `--frozen-lockfile` → 门禁三件套（test / typecheck / build）→ electron-builder 打包 → 生成 latest.yml（见清账①）→ 创建/更新 GitHub Release（tag 对应）并上传三件套
- 权限：`GITHUB_TOKEN`（Actions 内置，无需额外 secrets）
- **注意**：本仓库含 web/ 等非桌面内容——CI 只构建 `apps/desktop`，不要全仓构建；`pnpm test` 若有非桌面测试则限定 `--filter` 或目录

### 2. 打包清账五项（全部列自各单验收记录）

1. **latest.yml 自动化**：发布脚本内置生成（本地与 CI 同一脚本），字段含 version/path/sha512/size——消灭手工补
2. **托盘 .ico 资源化**：`build/icon.ico` 经 extraResources 落运行时可达路径，托盘优先用 .ico 多尺寸（PNG 回退保留）
3. **backup.exitPassword 迁移 safeStorage**：迁移逻辑（读旧明文 → safeStorage 加密 → 覆盖 → 清明文），兼容无旧值场景
4. **listObjects 分页**：continuation-token 循环（假 HTTP 多页响应测试；<1000 快照行为不变）
5. **out/ 清理批处理**：本地发布脚本的 out/ 分批删除（CI 无此问题，注明即可）

### 3. v0.1.5-alpha 发布

- 版本两处同步 → CHANGELOG 顶部新增（M6-1 更新通道 + M6-2 CI/CD 与清账条目，内容自拟但须覆盖：自动更新、CI、exitPassword 迁移、分页、托盘 .ico）
- 发布方式二选一并说明理由：**本地流水线发布**（已五轮跑通，稳）或 **CI 首航发布**（验证 automation，风险略高）。建议：本地发布 v0.1.5-alpha（稳），CI 用 test tag（如 `v0.1.5-ci.1`）首航验证后删除测试 tag 与其 Release
- 冒烟：`//S` 安装 → 状态栏 v0.1.5-alpha → 「检查更新」显示「已是最新版本」（真实 GitHub feed 上 v0.1.5 即最新——这也是 allowPrerelease + GitHub provider 的真机回归）→ 卸载清理

### 4. 测试（≥10，全部离线）

- listObjects 分页（两页/三页/末页空 continuation）≥2
- exitPassword safeStorage 迁移（有旧明文/无旧值/加密值不回显）≥2
- 托盘图标路径解析（.ico 存在用 .ico / 不存在回退 PNG）≥1
- 版本同步一致性检查脚本化（package.json ↔ constants.ts，防 R-1 类翻车复发）≥1
- CI workflow 的静态自检（如：yaml 存在性 + 触发器字段断言，用 node:fs 读文件做基本校验）≥1
- 其余按实现补足；现有 **276** 条零回归

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 276 + 新增 ≥10、typecheck 0 错、build 成功
- [ ] 保护路径零改动（workflow 新文件为例外并单独列示）
- [ ] CI 首航验证（test tag 触发 Actions 全绿 + 产物上传）或如实报告失败原因
- [ ] v0.1.5-alpha 已发布 + 三件套 + 公开可见自验
- [ ] **重启 dev 实测**：更新检查在真实 GitHub feed 下显示「已是最新版本」（0.1.5 即最新，且这次是「真的检查过了」）
- [ ] 交付报告第 6 项：CHANGELOG 条目草稿（v0.1.6 预留）

## 交付报告格式（七项制）

1. 变更/新增文件清单（路径+行数，workflow 单列）
2. 门禁输出尾部（注明测试条数：基线 276 → 共 N 条）
3. commit hash + tag + Release URL
4. 清账五项自测记录表
5. CI 首航记录（run URL / 结论）
6. **版本迭代信息（CHANGELOG 条目草稿）**
7. 遗留问题 / 对 M7（UI 换新）的建议

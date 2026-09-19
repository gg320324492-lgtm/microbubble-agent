# 发布审计清单（Release Audit Checklist）

> 自 v1.0.0 起，**正式 tag 不可变**：每次发布必须逐项打勾并留证，未通过项一律停止发布。
> 执行方式：`node scripts/release.mjs`（本地/CI 同一脚本）已自动覆盖第 1–6 项；
> 第 7–9 项需人工确认并在交付报告中贴出证据。

发布版本：`v______` 　发布人：`______` 　日期：`______`

---

## 一、发布前（门禁与一致性）

- [ ] **1. 版本两处一致**：`package.json` 与 `src/shared/constants.ts` 的 `APP_VERSION` 完全相同
      （发布脚本 `version` 步骤自动校验；不一致直接 fail）
      证据：`node scripts/release.mjs version` 输出 `版本同步 OK：<版本>`
- [ ] **2. 门禁三件套全过**：`pnpm test` 全绿（记录条数）/ `pnpm typecheck` 0 错 / `pnpm build` 成功
      证据：测试条数 `______`（基线对比：上一版 `______` → 本版 `______`）
- [ ] **3. 原生模块 ABI 对齐**：`better-sqlite3` 必须是 Electron ABI
      （发布脚本 `native` 步骤自动探测并拉取 Electron 预编译包；ABI 不对即拒绝发布）
      证据：`[release] 原生模块已对齐 Electron ABI` 或 `已是 Electron ABI，跳过`
- [ ] **4. CHANGELOG 已更新**：顶部新增本版段落，覆盖本版全部面向用户的变更
- [ ] **5. 保护路径零改动**：`app/` `web/` `alembic/` `nginx/` `docker-compose*` `.env`
      `desktop-conversion/` 均无改动
      证据：`git status --short` 输出（贴入报告）

## 二、产物（打包与可运行性）

- [ ] **6. 产物可运行性门禁通过**（`smoke` 步骤，CI 与本地同脚本）
      - [ ] 6a. **主题令牌断言**：`--el-color-primary` 级联生效值 = 品牌色 `#3e5c76`
            （不是 EP 默认蓝 `#409eff`）；`--color-bg-page` = `#f3eddf`
            证据：`[smoke] ✓ 主题令牌断言通过：--el-color-primary 生效值 = #3e5c76`
      - [ ] 6b. **启动即用**：静默启动打包产物 → 渲染进程挂载 `#app` → 走完首启注册
            （真实写入 SQLite）→ 进入工作台
      - [ ] 6c. **版本断言**：状态栏文本含 `v<版本>`
            证据：`[smoke] ✓ 产物可运行性门禁通过（状态栏含 v<版本>）`
      - [ ] 6d. 应用日志中**无** `NODE_MODULE_VERSION` / `compiled against` 字样

## 三、发布（不可变 tag）

- [ ] **7. test tag 首航**（仅大版本/流程变更时必做）：`v<版本>-ci.N` 触发 CI 全绿 +
      产物可运行性验证通过，**然后删除该 test tag 与其 Release**
      证据：run URL `______`　结论 `______`
- [ ] **8. 正式 tag 与 Release**
      - [ ] tag `v<版本>` 指向的 commit = 发布时 HEAD（逐行核对：`git rev-list -n1 v<版本>` 与 `git rev-parse HEAD` 相同）
      - [ ] Release 正文含本版说明 + 安装说明（覆盖安装数据延续 / 应用内「检查更新」可直升）
      - [ ] **正式版不得带 `--prerelease`**（alpha/beta 才带）
      - [ ] 三件套已上传：`*.exe` / `*.exe.blockmap` / `latest.yml`
- [ ] **9. 发布后自验**
      - [ ] 下载产物并比对 **sha256 与 Release asset digest 逐字一致**
            证据：`______`
      - [ ] 匿名访问（清空代理后 HEAD）：Release 页 / `latest.yml` / `exe` / `blockmap` 均 **200**，
            并用一个不存在的版本做 **404 反向对照**
      - [ ] 安装后真机抽查：状态栏版本正确 / 首启或登录正常 / 至少一个业务模块可用 /
            「检查更新」返回预期结果
      - [ ] 卸载后环境干净（无残留进程、无残留监听端口、安装目录为空）

---

## 附：常见打回原因（历史教训）

| 教训 | 表现 | 本清单对应项 |
|---|---|---|
| 版本两处不同步（R-1） | 界面版本与安装包版本不一致 | 1 |
| 原生模块 ABI 不匹配 | 装完启动即崩 `NODE_MODULE_VERSION 127 vs 128` | 3 / 6b / 6d |
| CSS 覆盖静默失效 | 写了品牌色但 EP 组件仍是默认蓝 | 6a |
| 产物与 Release 不一致 | 本地测的包 ≠ 线上包（NSIS 不可复现） | 9 |
| tag 指向错误 commit | Release 内容与 tag 代码不符 | 8 |

# 工单 R-12：v1.3.2 发布列车 —— 本阶段最终正式版

> 签发：总指挥 · 2026-09-30 ｜ 类型：**发布列车（tag 类）** ｜ 性质：**本阶段最终正式版**
> 基线：`v1.3.1`（已发布，exe sha256 `25ed0f7e…`）→ 目标 `v1.3.2`
> 上游验收：DL-7 ✅ / ZB-1 ✅（地基）/ ZB-2 ✅ / FIN-1 ✅ —— 四单全部验收通过，本列车无待验收项
> 执行方式：按 `docs/releases/RELEASE-CHECKLIST.md` 顺序铁律执行，**总指挥全程陪同 + 独立复核**

---

## 一、列车内容（13 笔，`v1.3.1..HEAD`，总指挥已核）

| 组 | commit | 内容 |
|---|---|---|
| **恢复演练三修复** | `d7b8a46f4` | ≤4MB 小文件上传改 multipart（此前**全废**） |
| | `7f0ebfed2` | requestWithAuth 首发与 401 重放均转发 contentType（multipart 被标 application/json 致 422） |
| | `49cab7627` | 备份附件段名带完整子目录层（此前子目录附件恢复**错位/同名覆盖**） |
| **应用身份** | `e102ff9ad` | setAppUserModelId 统一蓝色课题组 logo（dev/直启不再露 Electron 原子图标） |
| **DL-7 自动更新通知** | `ac2dc7c45` | 主交付：releaseNotes 注入 feed + 启动弹窗 + 备份失败落日志 |
| | `7ebea1ae7` | CRLF→LF 规范化 + CHANGELOG v1.3.2 草稿段 |
| | `8c09434b2` | setupTray 降级守卫（托盘失败不再拖垮启动自动检查） |
| **ZB-1 服务端地基** | `40b4b9883` | `backups/` 保留区复活 private + 11 处 private 写路径闸 + 迁移 140 |
| **ZB-2 双端堵漏** | `d357ad4b7` | 桌面端保留目录落 `backups/` + 服务端备份形态跳过抽取 + 移除 `private→team` + 迁移 141 |
| | `5e5d5d391` | 迁移 141 downgrade 补 `created_at/updated_at` |
| **FIN-1 收尾** | `a513a97c5` | 服务端：A1 备份形态禁公开分享（四路径）+ A2 任务引擎 URL 可注入 + C1 文档修正 |
| | `09b224ea5` | 桌面端：B1–B4 小修 + C2 CHANGELOG 备份隐私加固段 |
| （chore） | `df49cd7bd` | v1.3.1 落地页更新（上一版遗留） |

## 二、服务端状态（总指挥已直查，**本列车无需再动服务端逻辑**）

| 项 | 实测值 |
|---|---|
| `alembic_version` | **`141_zb2_backup_kb_purge`** ✅ 与代码同 head |
| ZB-2 安全终态 | kb 孪生 **0** / 备份形态 chunks **0** / 13 条备份行全部 `drive`+`private` ✅ |
| 容器代码 | `app` 含 FIN-1 A1（4 处标记）✅；`celery-worker` 含 ZB-2 ✅ |

> ⚠️ **前置门 G0（唯一的服务端动作）**：`celery-worker` / `celery-beat` / `celery-meeting-worker` 启动于 **23:55**，**早于 FIN-1（01:25）**。功能上无影响（worker 缺失的 A2 仅测试期 URL 注入，生产默认路径逐字不变），但**发布前应让运行代码与 tag 完全一致**——执行 `docker compose restart app celery-worker celery-beat celery-meeting-worker`，重启后确认四个容器均 `Up` 且 `celery inspect ping` 有节点应答。

## 三、前置门（推 tag 之前逐项确认）

- [ ] **G0** 四容器重启完成，worker ping 有应答（见上）
- [ ] **G1** 版本两处同步：`package.json` version 与 `src/shared/constants.ts` `APP_VERSION` **均为 `1.3.2`**
- [ ] **G2** `pnpm gate` 全绿，测试计数 **≥782**（基线 782；版本号改动若引发快照更新需注明）
- [ ] **G3** CHANGELOG `## v1.3.2` 段落**定稿**（DL-7 + FIN-1 已起草；`stepLatest` 会自动抽取该段落注入 `latest.yml`）
      - **若忘了写**：`stepLatest` 打 `[warn] CHANGELOG.md 未找到 v1.3.2 段落` 并**静默省略** releaseNotes —— 不炸但功能降级，四连测时必须盯这行日志
- [ ] **G4** 保护路径零改动（`git status --short` 自证）；`app/` `web/` `alembic/` `nginx/` `docker-compose*` `.env` 本列车**零改动**
- [ ] **G5** GitHub Secrets `OSS_UPLOAD_AK/SK` 有效（欠费/禁用会让 CI 在 OSS 镜像步红——自检已前置到上传前）
- [ ] **G6** 无新增依赖（`package.json` 除 version 外无改动）

## 四、顺序铁律（**照抄 `RELEASE-CHECKLIST.md`，不得跳步**）

1. **CHANGELOG 先于 tag**：G1–G3 完成并提交 → 才打 tag（R-9 曾 tag 后补 CHANGELOG，靠 Release notes 兜底，**不再允许**）
2. **test tag 首航**：`v1.3.2-ci.1` → CI **全绿含 OSS 镜像成功** → 删除 test tag 及其 Release（**远端零残留**）
3. **正式 tag**：`v1.3.2`，**不可变**；tag 后只允许文档类提交进 HEAD
4. **Release 定稿**：`prerelease=false` + notes 完整 + 三件套齐（exe / blockmap / latest.yml）
5. **四连测**（见第五节）
6. **落地页更新**（见第六节）

## 五、发布后四连测（总指挥独立执行，逐条贴证）

- [ ] **双源 sha256 逐字一致**：OSS 域名下载 vs GitHub Release digest
- [ ] **feed**：`https://releases.mnb-lab.cn/releases/latest.yml` 匿名 200 且 `version: 1.3.2`
      - **附加**：确认该 `latest.yml` **含 `releaseNotes` 块**且内容为 CHANGELOG v1.3.2 段（DL-7 功能是否真落地）
- [ ] **直链**：安装包 URL 200
- [ ] **Release 形态**：`prerelease=false`、notes 完整、三件套齐

## 六、落地页

- 用**机器凭据直传**通道（用户注册表 `HKCU\Environment` 的 R-9 AK，env 名必须是 `OSS_UPLOAD_AK/SK` + `OSS_BUCKET=mnb-workbench-releases`）：
  ```
  node scripts/upload-release-oss.mjs --dir <空目录> --skip-if-missing --page download-page.html
  ```
- 落地页版本号 / SHA-256 / 体积须与本次发布**逐字一致**
- ⚠️ **OSS 大文件上传必须 curl**（undici fetch 5 分钟 body 硬超时，跨境必死——脚本已改，勿绕过）

## 七、本版对外可见的能力变化（发版通知稿的事实依据）

1. **自动更新通知**（新）：启动自动检查（每日至多一次），发现新版本弹窗显示**版本号 + 更新日志**，一键下载安装并重启；更新日志经课题组 CDN 直达，**不依赖 GitHub**。组员从此不用盯落地页。
2. **云端附件恢复已修复**（此前残缺）：子目录附件恢复错位/同名覆盖、≤4MB 小文件上传全废。
3. **零感托管备份已加固**（安全）：备份容器与解密钥匙改为仅本人可见；备份文件不再进入知识库与语义检索；备份文件无法被分享成公开链接；历史密钥明文已从服务器清除。
4. **备份失败原因可见**（可观测性）：此前只弹通知不留痕。

> 措辞红线：安全项**只陈述本版实际覆盖的范围**，不得写成「已修复全部安全问题」。

## 八、发布后单独处置（不在本列车）

- 清理遗留物：`zb1probe` 账号（id=1459，**真实可登录**）、`backups/` 文件夹、3 个探针、zb1-open 文件夹
- 组员分发通知稿（双通道：落地页直装 + 应用内自动更新——**本版首次能吃到自动更新通知**）
- **备份密钥轮换：经核实不需要**，可从待办划掉（受影响的 22 行全部为 cismoke 演练账号数据，真实组员从未产生过备份，明文已由迁移 141 物理删除）

## 九、交付

- 报告须含：实际 HEAD、G1–G6 逐项证据、CI run 链接、test tag 删净证明、**四连测逐条真实响应**、落地页截图
- **回滚方案**：正式 tag 不可变 → 如需回滚，发新 patch 版本（v1.3.3）而非改 tag；`releases.mnb-lab.cn/releases/` 可手工替换 latest.yml 指向旧版实现客户端侧回退

# R-12 发布报告:v1.3.2 本阶段最终正式版(2026-09-30)

## 结论

**v1.3.2 已发布**。顺序铁律 1-6 逐步执行、零跳步;CI 三跑(首航红 → 修复 → ci.2 绿 → 正式绿);四连测全过(**双源 sha256 逐字一致**、feed 200 + version 1.3.2 + **releaseNotes 块确认**、直链 200、Release 定稿形态);落地页已更新并线上验证逐字一致。

- **正式 HEAD**:`6fcb8c364`(落地页更新,tag 后文档类提交,符合铁律 3);正式 tag **`v1.3.2`** 指向 `51fec58eb`(stepVerify 同源修复)
- **CI runs**:首航 `36608387444`(v1.3.2-ci.1,**红**,见下)/ 首航修复后 `36608949506`(ci.2,**绿**)/ 正式 `36609587227`(v1.3.2,**绿**)
- Release:https://github.com/gg320324492-lgtm/microbubble-agent/releases/tag/v1.3.2

## 前置门 G0–G6

| 门 | 证据 |
|---|---|
| G0 | 四容器重启(手工 `docker compose restart app celery-worker celery-beat celery-meeting-worker`),全 `Up (healthy)`,`celery inspect ping` 有节点应答(celery@…/meeting-worker@… OK pong) |
| G1 | `package.json` version=1.3.2 与 `constants.ts APP_VERSION='1.3.2'`(commit `2cd276f21`);版本同步测试在 gate 内通过 |
| G2 | `pnpm gate` 全绿:**782/782**(=基线,版本号改动未引发快照变化)+ typecheck 0 + build 0 |
| G3 | CHANGELOG `## v1.3.2` 段落定稿(commit `2cd276f21`,先于 tag ✓);CI 日志实证 **`更新日志命中:CHANGELOG v1.3.2 段落 1172 字符`**,无 [warn] 省略行 |
| G4 | `git status --short` 仅既有 untracked(`.env.bak-…`),零改动自证;G1–G3 提交仅触及 `apps/desktop/{package.json,src/shared/constants.ts,CHANGELOG.md}`;app/web/alembic/nginx/docker-compose/.env 在总指挥核验状态(§二)之后零新改动 |
| G5 | OSS 凭据有效性由两处实证:CI 镜像步自检通过(`[oss] ✓ 自检通过:凭据有效且具备 ListObjects 权限`) + 本机落地页直传同凭据自检通过 |
| G6 | `git diff v1.3.1..HEAD -- apps/desktop/package.json` 仅 version 行(1.3.1→1.3.2);零新增依赖 |

## 首航红 → 修复(透明度)

首航 `v1.3.2-ci.1` 在 **verify 步 FATAL**:`releaseNotes 应省略(expected 未提供更新日志)`。根因:DL-7 的 `verifyLatestYml` 两侧不对称守护(expected 未带而 yml 带判失败)+ `stepVerify` 未与 `stepLatest` 同源抽取 releaseNotes(独立 verify 步不知道 notes)。**这正是 test tag 首航存在的意义**——正式 tag 若无首航将直接红。修复:`stepVerify` 同源抽取传入(`51fec58eb`,对称守护语义不变);test tag 删净(远端 Release + tag 均删,`git ls-remote` 零 v1.3.2-ci 残留,仅历史 archive/* tag 含字面 ci)→ 重打 `v1.3.2-ci.2` 全绿。

## 四连测(逐条真实响应)

1. **双源 sha256 逐字一致**:OSS 域名全量下载(curl)92,238,850 bytes → SHA256 `1940ec0706c26850a5da772324e2b0e1a95785566e2dbcb6965f97bc610319f1` = GitHub Release asset digest `sha256:1940ec07…` **逐字一致** ✓
2. **feed**:`https://releases.mnb-lab.cn/releases/latest.yml` 匿名 **200**,`version: 1.3.2`;**含 `releaseNotes: |-` 块**且内容为 CHANGELOG v1.3.2 段(「备份隐私加固」×3 处命中;存档 `latest-132-feed.yml`)✓
3. **直链**:`releases/MicroBubbleWorkbench-1.3.2-setup.exe` HEAD **200**,Content-Length 92,238,850(全量下载亦成功)✓
4. **Release 形态**:`isPrerelease=false` / `isDraft=false` / title+notes 定稿(CHANGELOG v1.3.2 段 + 安装说明)/ 三件套齐(exe 92,238,850 + blockmap 97,203 + latest.yml 3,346,均有官方 digest)✓

## 落地页(铁律 6)

- 机器凭据直传:`OSS_UPLOAD_AK/SK`(注册表 HKCU\Environment R-9 AK 映射为工单指定 env 名)+ `OSS_BUCKET=mnb-workbench-releases`;`node scripts/upload-release-oss.mjs --version 1.3.2 --dir <空目录> --skip-if-missing --page scripts/download-page.html`(空目录 + skip = 三件套不重传,只部署落地页)
- 页面更新(逐字):v1.3.2 / exe 文件名 / GitHub tag 链接 / SHA-256 `1940ec07…` / 发布日期 2026-09-30 / 88.0 MB
- 线上验证:`download-page.html` 拉取比对 v1.3.2 ×3、新 exe 名 ×2、新 SHA ×1 全部命中
- ⚠️ 踩坑记录:Git Bash 将 `reg query /v` 参数路径化导致首次凭据提取为空;OSS 大文件走 curl(undici 5 分钟硬超时),均按工单告警规避

## 措辞红线自查

四连测与落地页措辞只陈述本版实际覆盖范围(自动更新通知/备份隐私加固/附件恢复修复/可观测性),CHANGELOG 保留「不声称覆盖产品其他面的安全问题」声明,无「已修复全部安全问题」类表述。

## 回滚方案(备案)

正式 tag 不可变 → 需回滚时发 v1.3.3 patch(不改 tag);客户端侧回退可手工替换 `releases.mnb-lab.cn/releases/latest.yml` 指向 v1.3.1 产物。

## 发布后单独处置(不在本列车,待办移交)

zb1probe 账号(1459)/ backups/ 文件夹 / 3 个探针 / zb1-open 文件夹清理;组员分发通知稿(双通道);备份密钥轮换**经核实不需要**(已从待办划掉)。

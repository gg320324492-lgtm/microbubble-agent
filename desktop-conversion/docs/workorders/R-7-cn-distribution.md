# 工单 R-7：国内分发通道 + 官网下载页（深夜极简·暗色）

> 签发：总指挥 · 2026-09-19
> 上游：v1.0.0 正式版已发布（Release 三件套 + 应用内更新通道已验证）
> 决策依据：D6（GitHub 存源码 + 阿里云 OSS/CDN 国内分发）+ 用户新增需求（父级网站下载页，UI 由用户选定：**B · 深夜极简（暗色）**）

## 你的任务背景

当前所有版本只在 GitHub Releases——国内用户不挂代理下载慢且不稳定。本单打通**国内直连下载**：把 v1.0.0 三件套上传到阿里云 OSS，做一个深夜极简风的暗色下载落地页（双源链接），并部署上线。

**已有资产（复用）**：
- M5-2 交付的 `src/main/services/backup/oss-sig.ts`（OSS V1 签名纯函数）与 `oss.client.ts`（注入式 HTTP 客户端）——本单的上传脚本**直接复用这套签名模式**写一个独立的发布上传脚本（放 `scripts/`，Node 直跑，不改业务代码）
- 设计基准：`docs/design/download-page-proposals.html` 的 **slate 主题（B · 深夜极简/暗色）**——用户从四方案中选定（本单第二个可读文件，第一个是本工单）

**前置条件（用户侧准备，执行前确认）**：
- 用户将创建公共读 bucket（如 `mnb-workbench-releases`，华北2·北京，与备份 bucket 分离）并创建/扩展 RAM 子账号授权（新 bucket 的 PutObject/GetObject/ListObjects）
- 用户把新 bucket 名 / endpoint / AK ID / Secret 交给总指挥，总指挥经安全渠道转交执行端（**Secret 不进对话与报告**，走临时凭据文件，用后删除）

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；**唯一例外：`desktop-conversion/docs/design/download-page-proposals.html` 允许读取（设计基准）**；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 除上传脚本外禁止新增任何 npm 依赖
4. 门禁：`pnpm test` 全绿（当前基线 **359** 条，需新增 ≥6 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. **凭据安全**：AK Secret 不落明文、不写日志、不出现在交付报告；上传脚本从临时凭据文件读取（用后删除）

## 交付物

### 1. 发布上传脚本（`scripts/upload-release-oss.mjs`）

- 复用 `oss-sig.ts` 签名模式（V1 HMAC-SHA1），独立脚本（node 直跑，不动业务代码）
- 输入：版本号 + 本地三件套路径 + OSS 配置（bucket/endpoint/AK，凭据从环境变量或临时文件读）
- 行为：上传三件套到 `releases bucket` 的 `<version>/` 前缀下 → 上传后 GET 校验字节数与 Content-MD5 → 输出三个国内直连 URL

### 2. 下载落地页（单文件 HTML，`download-page.html`）

- 以 `download-page-proposals.html` 的 **slate 主题**为基准（去掉主题切换器，固定暗色）
- 内容：Hero（应用名 + 暗色落地页 slogan + 主下载按钮「国内直连」+ 次「GitHub 下载」+ 版本/日期/大小）→ 六大功能模块卡片 → 三步开始使用 → 双源说明 → 页脚
- 主按钮直链 OSS 的 exe；GitHub 按钮直链 Release 页；两者内容一致提示保留
- 纯静态单文件（无构建、无外部依赖字体除外），移动端窄屏可用（响应式基础适配）

### 3. 部署

- **下载页**：OSS 同 bucket 开启「静态网站」功能（索引文档指向 download-page.html），或用户 ECS nginx 二选一（按用户提供的凭据/访问方式定，报告说明选择）
- **验证**：国内网络环境（无代理）下：落地页 200、exe 直链 200 且可完整下载（校验 sha256 与 Release 一致）

### 4. 真机验收指引（总指挥执行）

1. 无代理浏览器打开落地页 → 下载 exe（观察速度）→ 校验 sha256 → 安装启动
2. GitHub 源对照下载（速度对比记录进报告）

## 定义完成（全部满足才算完）

- [ ] 门禁全过：test 359 零回归（上传脚本若含可测纯函数则补单测）、typecheck 0 错、build 成功
- [ ] 保护路径零改动；Secret 无明文泄露
- [ ] 三件套已上传 OSS 且 GET 校验一致；国内直连 URL 输出
- [ ] 落地页已部署且国内网络可访问（用户协助验证）
- [ ] 交付报告七项制；**凭据零明文**；归属与数字如实

## 交付报告格式（六项制）

1. 变更/新增文件清单（路径+行数；上传脚本与落地页单列）
2. 门禁输出尾部（注明测试条数：基线 359 → 共 N 条）
3. commit hash + 提交信息
4. 上传校验记录（三件套 OSS 直链 + sha256 对照）+ 落地页部署地址
5. 遗留问题（如：CDN 域名绑定、GitHub feed 迁移等后续项）
6. 总指挥真机验收指引

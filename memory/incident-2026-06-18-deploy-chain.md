---
name: incident-2026-06-18-deploy-chain
description: 2026-06-18 三连环修复 + 部署链路事故复盘 — 本地 commit 后忘 push 误判 webhook 链断
metadata:
  type: project
---

# 2026-06-18 三连环修复 + 部署链路事故复盘

## 背景

用户在 1 天内报告 3 个独立 bug:
1. **桌面"正在听会"指示器点击不接进度** — 点击弹窗打开但不接听会
2. **浏览器 console 反复报 `/api/v1/auth/me 429`** — 即便前一次 commit 改成 read tier 200/min 仍不够
3. **MeetingRoomView 全屏页加载后 console 报 `Cannot read properties of null (reading 'value')`**

我交付 7 个 commit 修复,但中间有 1 次误判"webhook 链断",实际是本地 commit 后忘 push。

## 7 个 commit 时间线

| # | Commit | 内容 |
|---|---|---|
| 1 | `f8d27015` | EP useOrderedChildren.removeChild null guard (Vite plugin patch) |
| 2 | `f099e7e5` | MeetingRoomView 全屏页镜像移动端 |
| 3 | `a1fd8280` | /auth/me 限流 20/min → 200/min (read tier) — 不够 |
| 4 | `defb08e1` | 删 onMounted 重复 router.replace 防 URL 永远 /meetings |
| 5 | `9f11d97a` | MeetingRoomView 模板去掉 .value 防 null.value TypeError |
| 6 | `22f5a7d7` | /auth/me 完全豁免限流 (高频 polling 仍 429) |
| 7 | `38039d7c` | CLAUDE.md 沉淀 "高频只读端点完全豁免" 铁律 |

## 部署链路事故 — 真根因是本地忘 push

**用户报告**: 桌面端点击"正在听会"指示器不能继续之前的听会进度

**我的初判**: webhook 链又断了(CLAUDE.md 2026-06-17 教训复发)

**排查过程**:
1. 服务器 git log 显示 HEAD = `c1b969dd`(本地最新 commit)
2. 服务器 dist 无 MeetingRoomView chunk(预期要有的新文件)
3. 服务器 SSH 测 GitHub 通、webhook service 正常
4. 服务器 `git fetch origin main` + `git log origin/main -5` → **origin/main 也是 `c1b969dd` 之前**的 commit
5. **真根因**: 我本地 `git commit` 后忘 `git push`,GitHub 端一直停在 `c1b969dd`,服务器当然 deploy 不动

**修复**:
```bash
# 本地
git push origin main
# 服务器 webhook 5 秒内触发,HEAD 自动变 f099e7e5 + f8d27015
```

## 7 条新铁律(已沉淀到 CLAUDE.md)

### 铁律 1:`commit + push` 后必 verify push 真到 origin

```bash
git push origin main && \
git log --oneline origin/main -3  # 确认 HEAD 与本地一致
```

缺这步 = 服务器 deploy 永远拿不到新代码,与 webhook 链断的症状 100% 一样(dist mtime 不动、git log 不前进),浪费排查时间。

### 铁律 2:怀疑 webhook 断时第一步看 origin/main

```bash
ssh 服务器 "cd /opt/microbubble-agent && sudo git fetch origin main && git log --oneline origin/main -5"
```

- origin/main 与本地 HEAD 不一致 → 本地没 push 成功,不是 webhook 断
- origin/main 有新 commit 但服务器 HEAD 停在旧 commit → 真 webhook 断,走 2026-06-17 教训排查
- origin/main + 服务器 HEAD 都新 → 不是 deploy 问题,是浏览器侧 SW cache 污染

### 铁律 3:`/auth/` 路径必须按 path+method 细分限流

`if "/auth/" in path` 一刀切归 auth tier 20/min 是误伤:/auth/me 是高频只读(页面加载/Pinia 初始化/token 校验都会调),20/min ≈ 3秒/次根本不够。

修复模式 = 白名单敏感路径(login/refresh/change-password/reset-password/init-password)保留 20/min + 按方法分(POST/PUT/PATCH/DELETE → write 30/min,GET → read 200/min)+ fallback 仍归 auth tier(防 401 风暴)。

**铁律**:API 限流"按前缀"易误伤,必须"按 path 精确 + 按方法细分",否则高频只读端点会持续 429。

### 铁律 4:高频只读端点完全豁免限流

即便 200/min 也被 Vue reactive + WS 心跳 + 路由 prefetch 触发 429。

判断端点是否限流要看"是否会被高频轮询"而不是"是否敏感"。/auth/me 虽然挂在 /auth/ 前缀下但是只读 GET + JWT 鉴权,攻击成本高(没 token 401 直接拒),防护无意义。

```python
_AUTH_UNLIMITED_PATHS = frozenset({"/api/v1/auth/me"})

# middleware 看到 "unlimited" tier 直接 await call_next(request) 跳过
```

### 铁律 5:template 里 ref 永远不写 .value

Vue 3 `<script setup>` 硬规则:
- `<script setup>` 里:`ref.value`
- `<template>` 里:`ref`(裸用,Vue 自动 unwrap)

```vue
<!-- ❌ 反模式:Vue unwrap 后变成 null.value -->
<span v-if="recordingMeetingId.value && meetingId.value">

<!-- ✅ 正模式 -->
<span v-if="recordingMeetingId && meetingId">
```

复制桌面/移动组件时容易把 script 的 .value 习惯带进 template,必须逐个去掉。

### 铁律 6:router 操作一次只一个

`router.replace/push` 后不要再紧接第二个,后一行会覆盖前一行:

```js
// ❌ 旧代码 (commit f099e7e5 改 resumeRecording 后变 bug)
if (resumeId) {
  resumeRecording(Number(resumeId))          // router.replace('/meetings/room')
  router.replace({ path: '/meetings' })      // 覆盖!URL 永远 /meetings
}

// ✅ 修复 (commit defb08e1)
if (resumeId) {
  resumeRecording(Number(resumeId))  // 内部已 navigate 走
  // 不要在这里再 replace
}
```

一个 onMounted / 一个事件回调里最多 1 次 router 操作。

### 铁律 7:docker compose v1 (docker-compose) 与 v2 (docker compose) 服务器不互通

服务器 Docker 29.5.3 装的是 docker-compose v5.1.4 独立二进制,`docker compose` 命令不存在,必须 `sudo docker-compose`。

判断方法:
```bash
which docker-compose 2>&1  # 存在 = v1 (老独立二进制)
docker compose version 2>&1  # 存在 = v2 (Docker CLI plugin)
```

v1 警告 `Couldn't find env file: /opt/microbubble-agent/.env` 不影响 restart(只 restart 不重建容器,env 不需要重新解析)。

## 关键技术细节

### EP useOrderedChildren.removeChild null 崩溃

Element Plus `es/hooks/use-ordered-children/index.mjs` 的 `removeChild` 函数(对外暴露为 `unregisterPane`,被 tabs/tab-pane/table-column 复用)源码:

```js
const removeChild = (child) => {
    delete children.value[child.uid];
    triggerRef(children);
    const childNode = child.getVnode().el;
    const parentNode = childNode.parentNode;
    const childNodes = nodesMap.get(parentNode);  // parentNode 是 null 时返 undefined
    const index = childNodes.indexOf(childNode);  // ← BUG: childNodes undefined
    childNodes.splice(index, 1);
};
```

触发链:父组件先 unmount → parentNode 被 detach → childNode.parentNode 变 null → nodesMap.get(null) 返回 undefined → childNodes.indexOf(childNode) 爆。

修复:`web/vite.config.js` 新增 `epUnregisterPaneNullPatchPlugin`,Vite plugin transform 阶段 patch EP 源码:

```js
const EP_UNREGISTER_PANE_NULL_PATCH = '/* patch:ep-unregister-pane-null */ if (!childNodes) return;'
// pattern: const childNodes = nodesMap.get(parentNode);\nconst index = childNodes.indexOf(childNode)
```

验证:`npm run build` 后 `grep -boE 'if\(!a\)return;' element-plus-desktop-*.js` 找到 patch 注入位置(minifier 把 childNodes minify 成 a、nodesMap minify 成 i、removeChild minify 成 o,注释被剥但代码在)。

### MeetingRoomView 全屏页镜像 MobileMeetingRoom

新建 `web/src/views/MeetingRoomView.vue` (218 行),完全镜像 MobileMeetingRoom 但桌面化:
- el-page-header 顶栏(替代 PageHeader 移动组件)
- 右上角"正在听会 #N"橙色徽章让"继续听会"语义明确
- 帮助用 el-dialog(替代移动端底部 sheet)
- onMounted 调 checkActiveRecording() + 复用 recordingMeetingId

router fallback 改正: `/meetings/room` 桌面 fallback `MeetingView` → `MeetingRoomView`,与移动端各自专属 RoomView 镜像。

MeetingView.resumeRecording 改 navigate: 旧版 `liveCallMeeting = {id}` + `showLiveCallDialog = true` 开 dialog → 新版 `router.replace('/meetings/room')` 与 MobileMeetingView 镜像。

### /auth/me 限流 3 次进化

| 版本 | Commit | /auth/me tier | 实际触发频次 |
|---|---|---|---|
| 原始 | - | auth 20/min | 5-7 次就 429(每页面加载 + 路由切换) |
| 第一次改 | `a1fd8280` | read 200/min | 30-50 次仍 429(useUserStore 高频 polling) |
| 完全豁免 | `22f5a7d7` | unlimited | 200+ 次全 OK |

middleware 加 unlimited tier 处理:

```python
async def rate_limit_middleware(request, call_next):
    limit_type = _get_rate_limit_type(request)
    if limit_type == "unlimited":  # 新增
        return await call_next(request)  # 跳过限流直接通过
    limiter = _rate_limiters[limit_type]
    ...
```

## 部署必做(后端 Python 文件改动)

```bash
# 任何后端 Python 文件改动(app/ 任何路径)必跑:
sudo docker-compose restart app celery-worker
# volume 挂载只换文件不换模块缓存,新代码 import 必须靠重启进程
```

不 restart = 限流配置永远走旧逻辑。本次就是因为没及时 restart 看到 curl 还 429 一度怀疑修复无效。

## 服务器健康验证

```bash
# 1. 服务器 HEAD 含新 commit
ssh 服务器 "cd /opt/microbubble-agent && git log --oneline -3"
# 期望看到最新 commit (defb08e1 / 9f11d97a / 22f5a7d7)

# 2. 服务器 dist 含新 chunk
ssh 服务器 "ls /opt/microbubble-agent/web/dist/assets/MeetingRoomView-*.js"
# 期望至少 1 个新 hash

# 3. 验证 /auth/me 不再 429
ssh 服务器 "for i in \$(seq 1 30); do \
  curl -sk -o /dev/null -w '%{http_code} ' https://agent.mnb-lab.cn/api/v1/auth/me; \
done; echo"
# 期望 30 个 401(0 个 429)

# 4. 浏览器侧硬刷新
# F12 → Application → Service Workers → Unregister
# Ctrl+Shift+R
```

## 经验教训

1. **本地 commit 后必 push** — 缺 push 永远拿不到服务器 deploy,与 webhook 断症状一样,浪费排查时间
2. **怀疑 webhook 断先看 origin/main** — 区分"本地没 push"vs"webhook 链断"vs"浏览器 SW cache 污染"
3. **Vue 3 `<script setup>` 硬规则** — script 用 .value,template 裸用
4. **高频只读端点完全豁免** — Vue reactive + WS 心跳 + 路由 prefetch 远超产品逻辑假设
5. **API 限流按 path+method 细分** — 不要按前缀一刀切
6. **router 操作一次只一个** — 多个连续会被覆盖
7. **后端 Python 文件改动必 restart** — volume 挂载只换文件不换模块缓存
8. **docker compose v1/v2 服务器不互通** — 服务器装的是 docker-compose 独立二进制,必须 sudo docker-compose

## 相关文档

- [CHANGELOG.md](../CHANGELOG.md) - 项目更新日志
- [CLAUDE.md](../CLAUDE.md) - 项目上下文与铁律沉淀
- [ROADMAP.md](../ROADMAP.md) - 项目路线图
- [memory/docker-desktop-fix-2026-06-17.md](docker-desktop-fix-2026-06-17.md) - 部署与基础设施重建(类似事故链)
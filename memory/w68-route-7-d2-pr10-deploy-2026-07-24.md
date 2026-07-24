# W68 Route 7 D-2：PR10 部署守恒（2026-07-24）

本记录对应 `docs/drive-v2-pr10-deployment-runbook.md` 与 `scripts/verify_pr10_collab_ws.py`。本批保持 0 production code 改动，仅增加部署文档、验证脚本和 memory。

## 锚点范式第 86 守恒

PR10 部署材料把协同编辑的四条运行时边界写成可执行检查：WebSocket 握手、Redis pub/sub、Celery flush、pycrdt 二进制状态；同时把 Push/VAPID 与桌面/移动 PWA 验证纳入同一窗口。脚本默认 dry-run，只有显式 `--apply` 才发送 WS 帧，避免审计或 CI 意外修改线上数据。

## 三条新铁律

1. **WS 部署必跑连通测试。** HTTP 200 不代表 WebSocket Upgrade、鉴权和 Redis 广播可用；至少完成一次握手，并在两个客户端验证同文件广播及重连。
2. **pycrdt binary 兼容必须守住。** app 与 Celery worker 必须使用兼容版本；`ydoc_state` 只能按 pycrdt 约定读写，不得当作 UTF-8 文本拼接。升级前保留快照备份，升级后等待 flush 再检查长度和更新时间。
3. **Redis pub/sub channel 命名必须来自代码契约。** 部署、监控、回滚均使用同一前缀和文件维度；不得手工发明 channel。回滚只清理 PR10 临时 channel/key，不能误删其他业务 Redis 数据。

## Alembic 与回滚守恒

064 `drive_documents` 先于 065 push subscriptions，066、067 依次接续；合并后必须验证单 head。发生异常时先停止编辑和 flush，再按实际 revision 链反向降级，保留 `ydoc_state` 备份，不用 `upgrade heads` 掩盖分叉。

## 验证结果记录模板

- 部署 commit：
- Alembic heads：`067_push_subscriptions`（单 head）
- snapshot API：200 / 失败原因
- WS handshake：通过 / 失败原因
- VAPID 公钥：通过 / 失败原因
- push 测试：通过 / 失败原因
- 30 秒 flush：`ydoc_state` 长度、时间戳
- 基线：71 PASS + 7 SKIP
- 桌面/移动 PWA 与权限：
- 观察窗口与通知用户时间：

## 维护提示

`verify_pr10_collab_ws.py` 在无应用依赖的本地环境可能对模型、服务或路由给出 WARN；这不等同于线上成功。线上部署必须在容器内运行，并将 WARN 转化为人工证据。`--apply` 依赖 `websockets`，仅使用测试 token 和测试文件。

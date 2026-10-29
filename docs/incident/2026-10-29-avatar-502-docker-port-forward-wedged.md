# 2026-10-29 全站头像 502 —— Docker 宿主端口转发器卡死，隧道守卫全程显示 alive

> 事故档案（只增不改）。触发链路：**容器内一切正常** + **应用链路一切正常** +
> **宿主发布端口连接被接受却不给响应** —— 而被派去守这条链路的脚本
> **全程日志 `alive - no action`**，因为它只检查「ssh 进程在不在」。

## 现象

- 用户报前端控制台大量 `GET https://agent.mnb-lab.cn/minio/microbubble/avatars/<hash>.jpg 502 (Bad Gateway)`。
- 云端 nginx error.log：
  `upstream prematurely closed connection while reading response header from upstream, upstream: "http://127.0.0.1:9000/microbubble/avatars/..."`
- **第一次 502 出现在 2026-10-29 14:23:56**（当天 22 条，此前 0 条）⇒ 断了约 6.5 小时。

## 根因：Docker 的宿主端口转发器卡死（**不是** MinIO、**不是** 隧道、**不是** nginx）

分层实测（关键就在分清是哪一层）：

| 层 | 命令 | 实测 | 判定 |
|---|---|---|---|
| 容器内 | `docker exec minio curl 127.0.0.1:9000/minio/health/live` | **200** | MinIO 正常 |
| 应用链路 | app 容器 `GET http://minio:9000/microbubble/avatars/<hash>.jpg` | **200，846449 bytes** | 应用链路正常 |
| 宿主 → 容器发布端口 | `curl 127.0.0.1:9000/minio/health/live` | **Empty reply from server（curl exit 52）** | ← **真凶** |
| 宿主 → 同容器另一个发布口 | `curl 127.0.0.1:19000/minio/health/live` | 同样 Empty reply | ⇒ 坏的是**转发器**，不是单个端口 |
| 云端 → 隧道 | `ss -tlnp` 显示 sshd 在 8000/9000/2222 三口 LISTEN | 隧道**全程活着** | 隧道无责 |
| 云端 → 宿主 9000 | TCP 能连上 | 连得上但没有 HTTP 响应 | 与宿主侧症状一致 |

⇒ 宿主上 `127.0.0.1:9000` 的监听者是 **`com.docker.backend`**（Docker 的宿主端口转发），
它接受了 TCP 连接却转不出去 —— 于是 sshd 的反向转发拿到的是「连上即断」，
云端 nginx 报 `upstream prematurely closed connection`。

## 为什么没人发现：守护脚本信错了字段

`scripts/tunnel/guard-ssh-tunnel.ps1` 的判活口径是
「存在命令行含 `agent.mnb-lab.cn` 且带 `-R` 的 ssh.exe」⇒
断的 6.5 小时里，它每 5 分钟打一行 `alive (pid=39268) - no action`。
**类 20.220 的完整形态：状态字段（进程在）说谎，副作用（数据真能过去）没被验。**

## 处置

1. **现场修复**：`docker restart microbubble-agent-minio-1` ⇒ 重建端口转发 ⇒
   宿主 `127.0.0.1:9000` 与 `127.0.0.1:19000` 立即恢复 200。
   （数据在 volume 里，重启不丢；容器内数据与文件哈希未变。）
2. **守护升级**（`scripts/tunnel/guard-ssh-tunnel.ps1`）：判活口径从「进程在」改成
   **两级数据通路探针 + 定点自愈**：
   - `Local`：`http://127.0.0.1:9000/minio/health/live` 与 `http://127.0.0.1:8000/health`
     ⇒ 不通 = Docker 宿主端口转发器卡死 ⇒ `docker restart <容器>` 重建转发（实测可修）。
   - `E2E`：`https://agent.mnb-lab.cn/minio/minio/health/live` 与 `https://agent.mnb-lab.cn/health`
     ⇒ Local 通而 E2E 不通 = 隧道/云端侧 ⇒ **只记日志、不自动重启隧道**
     （2026-09-15 教训：两个监管者判活口径不一致会互相不认账）。
   - 探针带 `--noproxy '*'`（本机 `HTTP_PROXY=127.0.0.1:7897` 是 Clash，会劫持探针）。
   - 容器启动 < 120s 时探针失败**不重启**（防重启风暴）。
   - **app 通路也纳入** —— 同一转发器承载主站 API，失效面比头像大得多。

## 验证

| 判据 | 结果 |
|---|---|
| 宿主 `127.0.0.1:9000` / `127.0.0.1:19000` | HTTP 200 |
| 生产域名取 3 个头像 | HTTP 200，`content-type: image/jpeg`，23KB / 161KB / 846KB |
| 下载校验 | PIL 打开成功，`(2112, 2832) JPEG` |
| 生产 `/health` `/` `/drive` | HTTP 200 |
| 守卫脚本 | PS 5.1 解析 0 错；实跑 `alive` + 无告警（两条通路的 Local/E2E 全通） |
| 自愈分支（**隔离副本**验证，不碰真实服务） | 死端口 + 不存在的容器 ⇒ 依次打出 `DATA PATH BROKEN` → `ERROR: ... No such container` → `STILL BROKEN ... 需人工介入` |
| 探针正负两向 | 死端口 → False；live → True；E2E → True |
| `Get-ContainerUptimeSec` | minio 289s / app 150353s / 不存在的容器 → -1 |

## 定位路径（下次照抄）

```bash
# 1) 先分清是"服务坏了"还是"中间层坏了" —— 三层各打一遍
docker exec microbubble-agent-minio-1 curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9000/minio/health/live   # 容器内
docker exec microbubble-agent-app-1 python -c "import requests;print(requests.get('http://minio:9000/minio/health/live',timeout=8).status_code)"  # 应用链路
curl -sS -o /dev/null -w "%{http_code}\n" --noproxy '*' http://127.0.0.1:9000/minio/health/live                              # 宿主发布端口
# 2) 同容器的另一个发布口也坏 ⇒ 是转发器 (com.docker.backend) 坏了, 不是单个端口
curl -sS -o /dev/null -w "%{http_code}\n" --noproxy '*' http://127.0.0.1:19000/minio/health/live
# 3) 修: 重建转发 (数据不丢)
docker restart microbubble-agent-minio-1
# 4) 云端侧对照
ssh -i ~/.ssh/id_ed25519 root@agent.mnb-lab.cn "grep -m1 'minio/microbubble' /var/log/nginx/error.log | cut -c1-140"
```

## 沉淀

见 CLAUDE.md **类 20.240**（守护判活必须验端到端数据通路；"连得上但没响应"往中间层查；
探针必须 `--noproxy`；自愈防重启风暴；app 通路同样要探）。

# scripts/tunnel/ — SSH 隧道**守护器**

> **目录边界（结构重构批次 6，2026-10-10 补）**：本目录是**守护器**（guard / install / uninstall），
> **隧道本体在 [`../../tunnel/`](../../tunnel/)**（建隧道的那一侧）。
> **职责互补，不是重复 —— 勿合并。**

## 内容清单

| 文件 | 作用 |
|---|---|
| `guard-ssh-tunnel.ps1` | 守护逻辑本体：判活 ssh 反向隧道，断了就重拉；日志写 `logs/tunnel-guard.log` |
| `guard-ssh-tunnel.bat` | 计划任务的**实际 Action 入口**，转调上面的 `.ps1` |
| `install-tunnel-guard.bat` | 注册计划任务 `MicroBubble-SSH-Tunnel-Guard`（每 5 分钟） |
| `uninstall-tunnel-guard.bat` | 删除该计划任务 |

## 与 `tunnel/` 的分工

| | `tunnel/` | `scripts/tunnel/`（本目录） |
|---|---|---|
| 角色 | **隧道本体**（建隧道） | **隧道守护器**（守隧道） |
| 触发 | 人工 / 开机任务 `MicroBubble-SSH-Tunnel` | 计划任务 **`MicroBubble-SSH-Tunnel-Guard`**，每 5 分钟 |
| 判活 | 内置 30s 看门狗（进程内） | 独立进程幂等判活（跨进程） |

跨目录调用是**已知且刻意的**：`guard-ssh-tunnel.ps1` 会回调
`../../tunnel/start-ssh-tunnel.ps1` 重新拉隧道。**守护器引用本体是设计，不是层级错乱。**

两者的判活口径必须一致 —— 2026-09-15 曾因口径不一致（本体不带 `-R 0.0.0.0:9000`
字面量，守护器却要求它）导致两个监管者"互不认账"，5 分钟一轮反复抢端口，
当天 `ssh-tunnel.log` 出现 115 次 `SSH exited immediately (code: 255)`，断续约 70 分钟。
详见 [`../../tunnel/README.md`](../../tunnel/README.md) 与
`guard-ssh-tunnel.ps1` 文件头注释。**改判活逻辑必须两个目录一起看。**

---

## ⚠️ 本目录被 Windows 开机自启计划任务引用 —— 勿改名、勿移动

计划任务 **`MicroBubble-SSH-Tunnel-Guard`** 每 5 分钟执行
`E:\microbubble-agent\scripts\tunnel\guard-ssh-tunnel.bat`
（由 `install-tunnel-guard.bat` 注册，注册时用**绝对路径**写死 `Execute`）。

### ⚠️ 类 20.212：看着像残留，实为生产接线

本目录（连同顶层 `tunnel/`）**不是**"用不到的旧脚本"，是**活的生产链路**。
判据不是目录名或年龄，而是**是否被生产链路引用** —— 这里被开机计划任务引用着。

### ⚠️ 改名的三重风险

任何改名 / 移动都必须**同步重注册计划任务**，否则：

1. **守护静默失效** —— 隧道断掉后没人重拉，裸进程 `ssh.exe` 一死，
   云端 nginx `proxy_pass 127.0.0.1:8000` 立刻 502，全站不可用（类 20.214）；
2. **`LastTaskResult` 可能仍报 0** —— 调度器认为任务"成功"，
   但脚本根本没跑（类 20.220 的同款陷阱：状态字段会说谎）。**不能信任务状态，
   要查副作用产物**。

### 改完之后怎么验（类 20.220）

```powershell
# 1. 回读任务实际指向（长度 + 无控制字符, 类 20.216)
Get-ScheduledTask -TaskName "MicroBubble-SSH-Tunnel-Guard" | % Actions[0].Execute

# 2. 手动触发一次
Start-ScheduledTask -TaskName "MicroBubble-SSH-Tunnel-Guard"

# 3. 验副作用真的发生 —— 看日志有没有新增行, 不要只看 LastTaskResult
Get-Content E:\microbubble-agent\logs\tunnel-guard.log -Tail 20
```

> **类 20.216**：`install-tunnel-guard.bat` 的文件头留着一句
> "原文件里 `scripts\tunnel` 曾被 heredoc 写坏成 TAB，重装即复发"。
> 用脚本 / ps1 / heredoc 写任何含反斜杠路径的 `/TR` 或 `Execute` 时，
> `\r` `\t` 会被吞成控制字符 —— 任务永远 exit 1 且**日志一行不写**（进程根本没启动）。
> 改完注册**必须回读比对**。

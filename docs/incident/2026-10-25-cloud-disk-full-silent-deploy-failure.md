# 2026-10-25 云端磁盘 100% 满 ⇒ 部署静默中止 10 天

> 事故档案（只增不改）。触发链路：一次**看起来完全成功**的 push + 一次**全绿的 CI**
> + 一个**200 的健康检查**，三者同时成立，而**生产跑的是旧版本**，长达 10 天没人发现。

## 现象

- 2026-10-25 推送后，**新 dist 的资源在生产 404**，生产首页仍引用旧 chunk 指纹。
- `git push` 返回 0；GitHub CI **8 个 workflow 全绿**；生产 `https://agent.mnb-lab.cn/health` **200**。
- ⇒ 三个信号全对，但线上没更新。

## 根因链（四层，每层都伪装成正常）

1. **pm2 无限重启刷爆日志**：`admin` 用户的 pm2 托管着一个 **staging** 实例
   （`/srv/lab-miniapp-mvp-staging/backend/src/app.js`），它缺 `JWT_ACCESS_SECRET`
   → 启动即崩 → pm2 不停重启 → **同一段堆栈被反复写入**
   `/home/admin/.pm2/logs/lab-miniapp-backend-staging-error.log`，涨到 **18 GB**。
   （实测该文件前 20 万行去重后**仅 7 行** ⇒ 100% 重复，零信息量。）
2. **根分区被占满**：云端 `/` 40G，**Avail=0、Use%=100**。
3. **部署脚本的磁盘检查拦下每一次部署**：`scripts/deploy-auto.sh` 检测到空间不足 ⇒
   「ERROR: 磁盘空间不足，部署中止」⇒ **自 2026-10-15 起的 6+ 次 push 全部静默失败**。
   （脚本的拦截是**正确的防御** —— 它阻止了在磁盘满时写坏文件；问题在于**没人看它的日志**。）
4. **push 事件彻底丢失**：磁盘满 ⇒ webhook 服务连日志都写不进去 ⇒
   `/var/log/webhook-deploy.log` 的 mtime 停在最后一次失败那天 ⇒
   连「收到过 push」这件事都没有记录。

## 定位路径（下次照抄）

```bash
ssh -o BatchMode=yes -i ~/.ssh/id_ed25519 root@agent.mnb-lab.cn \
  'df -h /; du -sh /home/admin/.pm2 /var/log; tail -40 /var/log/webhook-deploy.log'
```
- **部署日志在云端**（成功末行 =「部署成功 ✓」，失败 =「磁盘空间不足，部署中止」）。
- GitHub 侧投递记录：`gh api repos/<owner>/<repo>/hooks/<id>/deliveries`
  ⇒ 实测出现过 **status=502 且请求根本没到 nginx**（云端 access.log 无记录）⇒ **两边都要看**。

## 处置

- `truncate -s 0` 掉那个 18 GB 日志（**保 inode**，pm2 仍可写；清之前先 `tail -50000` 留尾部备份）
  ⇒ 磁盘 **100%（0 可用）→ 32%（26G 可用）**；随后 push 即部署成功。
- 顺带纠正 `scripts/deploy-auto.sh` 两处「在云端 `docker ps` 找 db 容器」的死逻辑
  （容器名还是已废弃的 `microbubble-agent-app-revived`）⇒ 改成「云端不跑容器(预期) ⇒
  请在本地 PC 执行：<可复制命令>」；并修掉「**部署脚本执行中改写自己 ⇒ bash 按旧字节偏移
  执行半新半旧内容**」（类 20.236）。
- 手动补部署：`bash scripts/redeploy-cloud.sh`（判据 = **云端 HEAD == 本地 HEAD**）。

## 遗留（属 lab-miniapp 项目，未擅自处置）

staging 实例仍缺 `JWT_ACCESS_SECRET`，**一旦被 pm2 重新托管就会再次刷爆磁盘**。
建议二选一：补上环境变量，或给 pm2 配日志上限（`pm2-logrotate` 的 `max_size`），或停掉该实例。

## 沉淀的永久铁律

- **类 20.238**（push 成功 ≠ 部署成功，唯一硬判据是资源指纹比对）
- **类 20.236**（部署脚本执行中改写自己 ⇒ bash 按旧字节偏移执行）
- **类 20.214 ⑥**（云端不跑 MicroBubble 容器，Docker 全在本地 PC）

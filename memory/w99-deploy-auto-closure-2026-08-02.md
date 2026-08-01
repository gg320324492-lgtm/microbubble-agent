# W99 DEPLOY-AUTO 收口 (2026-08-02, 主拍自动部署固化)

## 任务背景
用户原始问题: "之前部署是可以自动执行的, 你看一下, 并把这个自动部署的命令写入相关文件, 以后自动执行"

## 自动部署现状 (实测梳理)
- **服务器端** ✅ 已自动化:
  - `scripts/webhook.py` (端口 9001): GitHub push webhook 监听
  - `scripts/webhook.service` (systemd): webhook 自启动
  - `scripts/deploy-auto.sh` (服务器跑): git fetch + reset --hard + 健全性检查 + Nginx reload + stats.json + changelog.json
- **本地 PC** ❌ 部署链最后一段空白:
  - web/dist 没自动 build + force-add
  - 后端代码改了没自动 docker cp + restart
  - deploy-auto.sh:106-123 **只 log 提醒, 不自动重启**

## 填补方案
**新增 `scripts/auto-deploy.sh`**: 5 步自动部署链, 可手动跑或 Claude Code PostToolUse hook 调

| 步骤 | 命令 | 目的 |
|---|---|---|
| 1. web/build | `cd web && npm run build` | 生成 PWA dist, 含 postbuild-fix-manifest.js hash 化 |
| 2. alembic check | `python -m alembic heads` | 守恒 1 head (CLAUDE.md 2026-07-24 串单链纪律) |
| 3. git add -f + commit | `git add -f -A web/dist/ && git commit -m "[DEPLOY-BUILD] ..."` | web/dist 整个目录被 .gitignore 拦, 必须 force-add |
| 4. git push | `git push origin main` | 触发服务器 webhook → 自动 deploy-auto.sh |
| 5. docker restart | `docker cp app/. + find __pycache__ -delete + docker restart` | 后端代码在本地 PC Docker 生效 (服务器 git pull 后 disk 新, Python 进程未 reload) |

## 脚本设计要点
- `--dry-run`: 默认演练模式, 仅打印计划 (类 20.117 沉淀)
- `--skip-build / --skip-push / --skip-restart`: 细粒度控制, 复用步骤
- 自动检测后端改动 (`git diff HEAD@{1} HEAD app/ alembic/`): 仅在有改动才跑 docker restart
- 自动检测本地领先 (`git rev-list origin/main..HEAD`): 仅领先才 push
- 部署后 `curl /health` 验证 + 输出后续命令清单

## 关联铁律
- CLAUDE.md 2026-06-13 PWA manifest 410 回归: `npm run build` 是**唯一**合法 build 命令
- CLAUDE.md 2026-07-14 deploy-auto.sh git clean 排除 web/dist: 服务器依赖 git 已 force-add 的 dist
- CLAUDE.md 2026-07-24 alembic 串单链纪律: 必须 1 head 才允许部署
- CLAUDE.md 752 行铁律: "docker cp + __pycache__ clear + docker restart"

## 实际部署结果 (W99 S-series + DEPLOY-AUTO)
**8 commits 全在 main 上, 已推 origin/main**:
1. `ab0a57ff4` W99-S1 /voice/tts 真 streaming
2. `8b052f79c` W99-S2 /ws/voice TTS 逐 chunk
3. `2d0631de6` W99-S3 compose embedding 对齐
4. `6dbe88713` W99-S4 ASR 评估
5. `88d8f63e6` W99-S-GC grand closure
6. `5d3b74f6e` W99-DEPLOY-AUTO auto-deploy.sh 创建
7. `9b9c1567c` DEPLOY-BUILD web/dist build (273 assets 改名 + index.html)
8. `f3e9ac8b3` W99-DEPLOY-AUTO force-add 修复

**服务器**: webhook 自动跑 deploy-auto.sh (git pull + Nginx reload + 健全性检查全过)
**本地 PC**: docker cp app/ + __pycache__ clear + restart app/celery-worker → `/health` 200 healthy

## 类 20 沉淀 (W99 DEPLOY-AUTO 新增)
- **类 20.117 实战**: 自动部署脚本必须含 --dry-run 演练模式 + 幂等检查
- **类 20.118 实战**: force-add 整个目录必须 `git add -f -A <dir>/`, 不能 `git add <dir>/` (gitignore 静默吞)
- **类 20.119 实战**: docker exec 后路径走 `C:/Program Files/Git/<path>` 错位, 必须 `docker exec <container> bash -c '<cmd>'` 才能在容器内解析
- **类 20.120 实战 (新增 - 部署链分段独立触发)**: webhook 服务端链 (push 触发) + 本地 PC 链 (git cp + restart) 是两段独立链, push 触发后服务端自动但本地必须手动; 原因是 frps 在云服务器 + docker 在本地 PC, 中间靠 SSH/FRP 隧道跨网络, server 端没法触发本地 PC 重启

## 累计 commits / 铁律延续
- 累计 W98-W99: 91 commits + 595+ 铁律
- W99 S-series + DEPLOY-AUTO + 4 新铁律 (类 20.117/118/119/120)
- 累计类 20 实战: 120 实例

## 未来改进 (留口)
1. **PostToolUse hook**: 在 .claude/settings.json 配置 git merge 完成后自动调 auto-deploy.sh (待用户决定是否开启)
2. **本地 PC auto-restart daemon**: 监听 git pull 完成事件自动 docker restart (彻底填空白, 类 20.120 衍生)
3. **健康检查主动报警**: webhook 服务端跑完后给本地 PC 发 webhook 让它 restart

详见 `scripts/auto-deploy.sh` (5 步链) + `docs/w99-deploy-auto-grand-closure-2026-08-02.md` (runbook)。
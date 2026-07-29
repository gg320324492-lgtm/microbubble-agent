# k6 装机说明 (W87-E-1)

> **目的**: k6 长连接压测脚本装机步骤 (SSE / WebSocket)。
> **本任务不真装 k6 binary**, 本文档供后续主指挥 / CI 在真实环境部署时参考。
> **参考**: <https://k6.io/docs/getting-started/installation/>

## macOS

```bash
brew install k6
```

## Linux (Debian/Ubuntu)

```bash
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69 \
  && echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list \
  && sudo apt-get update \
  && sudo apt-get install k6
```

## Linux (RHEL/CentOS/Fedora)

```bash
sudo dnf config-manager --add-repo https://dl.k6.io/rpm/repo.rpm \
  && sudo dnf install k6
```

## Windows

```powershell
# winget (推荐)
winget install k6 --source winget

# 或者从 release 下载 zip 解压:
# https://github.com/grafana/k6/releases
# 解压后 k6.exe 加入 PATH
```

## Docker

```bash
docker pull grafana/k6

# 单文件跑 (推荐 CI):
docker run --rm -i grafana/k6 run - <scripts/k6/chat_stream.js

# 挂载方式 (推荐本地):
docker run --rm -v "$PWD/scripts/k6:/scripts" grafana/k6 run /scripts/chat_stream.js
```

## 验证

```bash
k6 version
# k6 v0.49.0 (或更新)
```

## 本仓库脚本

```bash
# SSE 长连接 (chat)
npm --prefix web run load:chat

# WebSocket 通知
npm --prefix web run load:ws

# WebSocket 网盘协同
npm --prefix web run load:drive
```

## 目标 URL 配置

```bash
# 默认 http://localhost:3000 (本地 dev server)
K6_BASE_URL=https://prod.example.com npm --prefix web run load:chat

# 必须带认证 token (压测租户 test user, 不是生产账号!)
K6_AUTH_TOKEN=eyJhbGciOiJIUzI1NiIs... npm --prefix web run load:chat
```

## CI 集成 (W88+ 计划)

GitHub Actions 集成:

```yaml
- name: k6 load test (chat SSE)
  run: |
    docker run --rm -i grafana/k6 run \
      --vus 10 --duration 30s \
      -e BASE_URL=http://app:8000 \
      -e AUTH_TOKEN=${{ secrets.K6_TEST_TOKEN }} \
      - <scripts/k6/chat_stream.js
```

详见 `memory/w87-1st-batch-e1-k6-2026-07-29.md` 派工 v6 §5 反馈 #类 20.26 沉淀。

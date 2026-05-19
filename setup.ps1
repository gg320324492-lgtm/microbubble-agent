# MicroBubble Agent - Windows 一键初始化脚本
# 用法: 右键 -> 使用 PowerShell 运行，或在终端执行: powershell -ExecutionPolicy Bypass -File setup.ps1

param(
    [switch]$SkipFrontend,   # 跳过前端构建（已有 dist 时使用）
    [switch]$NoGPU,          # 无 GPU 模式
    [switch]$SkipFRP,        # 跳过 FRP 启动
    [switch]$Migrate         # 数据迁移模式（从旧电脑复制 data/ 目录后使用）
)

$ErrorActionPreference = "Stop"
$PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

# ---- 颜色工具 ----
function Write-Step  { param($n, $total, $msg) Write-Host "`n[$n/$total] $msg" -ForegroundColor Cyan }
function Write-OK    { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "  [!] $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "  [X] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " MicroBubble Agent - 一键初始化" -ForegroundColor Cyan
Write-Host " 项目目录: $PROJECT_DIR" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$TOTAL_STEPS = 7

# ============================================
# Step 1: 检查 Docker
# ============================================
Write-Step 1 $TOTAL_STEPS "检查 Docker"

try {
    $dockerVer = docker version --format '{{.Server.Version}}' 2>$null
    Write-OK "Docker $dockerVer 已安装"
} catch {
    Write-Err "Docker 未安装或未启动"
    Write-Host ""
    Write-Host "请先安装 Docker Desktop:" -ForegroundColor Yellow
    Write-Host "  https://www.docker.com/products/docker-desktop/" -ForegroundColor White
    Write-Host ""
    Write-Host "安装后启动 Docker Desktop，等待右下角鲸鱼图标变绿，然后重新运行此脚本。" -ForegroundColor Yellow
    Read-Host "按 Enter 退出"
    exit 1
}

# 检查 Docker Compose
try {
    docker compose version | Out-Null
    Write-OK "Docker Compose 可用"
} catch {
    Write-Err "Docker Compose 不可用，请更新 Docker Desktop"
    Read-Host "按 Enter 退出"
    exit 1
}

# ============================================
# Step 2: 检查 GPU
# ============================================
Write-Step 2 $TOTAL_STEPS "检查 GPU"

$hasGPU = $false
if ($NoGPU) {
    Write-Warn "已指定无 GPU 模式"
} else {
    try {
        $gpuInfo = nvidia-smi --query-gpu=name --format=csv,noheader 2>$null
        if ($gpuInfo) {
            Write-OK "检测到 NVIDIA GPU: $gpuInfo"
            $hasGPU = $true
        }
    } catch {
        Write-Warn "未检测到 NVIDIA GPU，Whisper 将使用 CPU 模式"
    }
}

# ============================================
# Step 3: 配置 .env
# ============================================
Write-Step 3 $TOTAL_STEPS "配置环境变量"

Set-Location $PROJECT_DIR

if (-not (Test-Path ".env")) {
    Write-Host "  首次运行，从 .env.example 创建 .env..." -ForegroundColor Gray
    Copy-Item ".env.example" ".env"

    # 生成随机 SECRET_KEY
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $secretKey = [BitConverter]::ToString($bytes) -replace '-', '' | ForEach-Object { $_.ToLower() }

    (Get-Content ".env") -replace 'change-this-to-a-random-string', $secretKey | Set-Content ".env"
    Write-OK "已生成随机 SECRET_KEY"

    # 配置 GPU/CPU 模式
    if (-not $hasGPU -or $NoGPU) {
        (Get-Content ".env") -replace 'WHISPER_MODEL_SIZE=large-v3', 'WHISPER_MODEL_SIZE=base' |
            ForEach-Object { $_ -replace 'WHISPER_DEVICE=cuda', 'WHISPER_DEVICE=cpu' } |
            Set-Content ".env"
        Write-OK "已配置 Whisper 为 CPU 模式"
    }

    Write-Host ""
    Write-Warn "请编辑 .env 文件，确认以下配置正确："
    Write-Host ""
    Write-Host "  必填配置：" -ForegroundColor White
    Write-Host "    CLAUDE_API_KEY          = 你的 Claude API Key" -ForegroundColor White
    Write-Host "    CLAUDE_BASE_URL         = Claude API 代理地址" -ForegroundColor White
    Write-Host ""
    Write-Host "  企业微信配置（已部署则必填）：" -ForegroundColor White
    Write-Host "    WECHAT_CORP_ID          = 企业 ID" -ForegroundColor White
    Write-Host "    WECHAT_AGENT_ID         = 应用 AgentId" -ForegroundColor White
    Write-Host "    WECHAT_SECRET           = 应用 Secret" -ForegroundColor White
    Write-Host "    WECHAT_CALLBACK_TOKEN   = 回调 Token（企业微信后台设置）" -ForegroundColor White
    Write-Host "    WECHAT_ENCODING_AES_KEY = 回调 EncodingAESKey" -ForegroundColor White
    Write-Host "    WECHAT_EXTERNAL_SENDER  = 外部联系人发送者 userid" -ForegroundColor White
    Write-Host ""
    Write-Host "  腾讯会议配置（已部署则必填）：" -ForegroundColor White
    Write-Host "    TENCENT_MEETING_SDK_ID  = SDK ID" -ForegroundColor White
    Write-Host "    TENCENT_MEETING_SDK_KEY = SDK Key" -ForegroundColor White
    Write-Host "    TENCENT_MEETING_USERID  = 主持人企业用户 ID" -ForegroundColor White
    Write-Host ""
    Write-Host "  注意：域名不变，企业微信/腾讯会议后台的回调 URL 无需修改" -ForegroundColor Gray
    Write-Host ""

    # 自动用记事本打开
    Start-Process notepad ".env" -Wait
    Write-OK ".env 已保存"
} else {
    Write-OK ".env 已存在，跳过配置"

    # 检查 GPU 模式是否匹配
    $envContent = Get-Content ".env" -Raw
    if (-not $hasGPU -and $envContent -match 'WHISPER_DEVICE=cuda') {
        Write-Warn "检测到 .env 中 Whisper 设置为 CUDA，但当前无 GPU"
        $answer = Read-Host "  是否切换为 CPU 模式？(Y/n)"
        if ($answer -ne 'n') {
            (Get-Content ".env") -replace 'WHISPER_MODEL_SIZE=large-v3', 'WHISPER_MODEL_SIZE=base' |
                ForEach-Object { $_ -replace 'WHISPER_DEVICE=cuda', 'WHISPER_DEVICE=cpu' } |
                Set-Content ".env"
            Write-OK "已切换为 CPU 模式"
        }
    }
}

# ============================================
# Step 4: 创建必要目录 & Docker Compose Override
# ============================================
Write-Step 4 $TOTAL_STEPS "初始化项目结构"

$dirs = @("data\postgres", "data\redis", "data\minio", "logs", "models")
foreach ($d in $dirs) {
    $fullPath = Join-Path $PROJECT_DIR $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}
Write-OK "数据目录已创建"

# 本地部署禁用 nginx（nginx 在云服务器上）
$overrideContent = @"
version: '3.8'
# 本地部署：禁用 nginx（nginx 在云服务器上运行）
services:
  nginx:
    profiles:
      - disabled
"@
Set-Content -Path (Join-Path $PROJECT_DIR "docker-compose.override.yml") -Value $overrideContent
Write-OK "已创建 docker-compose.override.yml（禁用本地 nginx）"

# ============================================
# Step 5: 构建前端
# ============================================
Write-Step 5 $TOTAL_STEPS "构建前端"

$distPath = Join-Path $PROJECT_DIR "web\dist"

if ($SkipFrontend -and (Test-Path $distPath)) {
    Write-OK "跳过前端构建（使用已有 dist）"
} else {
    # 检查 Node.js
    try {
        $nodeVer = node --version 2>$null
        Write-OK "Node.js $nodeVer 已安装"
    } catch {
        Write-Err "Node.js 未安装"
        Write-Host ""
        Write-Host "请先安装 Node.js:" -ForegroundColor Yellow
        Write-Host "  https://nodejs.org/" -ForegroundColor White
        Write-Host ""
        $answer = Read-Host "是否跳过前端构建继续？(需要手动构建, y/N)"
        if ($answer -eq 'y') {
            Write-Warn "跳过前端构建，稍后需手动执行: cd web && npm install && npm run build"
        } else {
            Read-Host "按 Enter 退出"
            exit 1
        }
    }

    Set-Location (Join-Path $PROJECT_DIR "web")

    if (-not (Test-Path "node_modules")) {
        Write-Host "  安装前端依赖（npm install）..." -ForegroundColor Gray
        npm install --legacy-peer-deps
        Write-OK "前端依赖已安装"
    }

    Write-Host "  构建前端（npm run build）..." -ForegroundColor Gray
    npm run build
    Write-OK "前端构建完成"

    Set-Location $PROJECT_DIR
}

# ============================================
# Step 6: 启动 Docker 服务
# ============================================
Write-Step 6 $TOTAL_STEPS "启动 Docker 服务"

Set-Location $PROJECT_DIR

Write-Host "  构建 Docker 镜像（首次约 10-15 分钟）..." -ForegroundColor Gray
docker compose build
Write-OK "镜像构建完成"

Write-Host "  启动服务..." -ForegroundColor Gray
docker compose up -d
Write-OK "服务已启动"

Write-Host "  等待数据库就绪..." -ForegroundColor Gray
$maxWait = 60
$waited = 0
while ($waited -lt $maxWait) {
    $healthy = docker inspect --format='{{.State.Health.Status}}' microbubble-agent-db-1 2>$null
    if ($healthy -eq "healthy") { break }
    Start-Sleep -Seconds 2
    $waited += 2
    Write-Host "." -NoNewline -ForegroundColor Gray
}
Write-Host ""

if ($waited -ge $maxWait) {
    Write-Warn "数据库启动超时，请手动检查: docker compose logs db"
} else {
    Write-OK "数据库就绪"
}

# 初始化数据库
if ($Migrate) {
    Write-Host "  迁移模式：检测到已有 data/ 数据，跳过初始化..." -ForegroundColor Gray
    Write-Host "  运行数据库迁移（确保表结构最新）..." -ForegroundColor Gray
    try {
        docker compose exec -T app alembic upgrade head 2>$null
        Write-OK "数据库迁移完成"
    } catch {
        Write-Warn "迁移可能已执行"
    }
} else {
    Write-Host "  初始化数据库表..." -ForegroundColor Gray
    try {
        docker compose exec -T app python scripts/init_db.py 2>$null
        Write-OK "数据库初始化完成"
    } catch {
        Write-Warn "数据库可能已初始化（如报错请检查日志）"
    }

    Write-Host "  运行数据库迁移..." -ForegroundColor Gray
    try {
        docker compose exec -T app alembic upgrade head 2>$null
        Write-OK "数据库迁移完成"
    } catch {
        Write-Warn "迁移可能已执行"
    }
}

# ============================================
# Step 7: 启动 FRP
# ============================================
Write-Step 7 $TOTAL_STEPS "启动 FRP 隧道"

if ($SkipFRP) {
    Write-Warn "跳过 FRP 启动"
} else {
    $frpExe = Join-Path $PROJECT_DIR "frp\frpc.exe"
    $frpToml = Join-Path $PROJECT_DIR "frp\frpc.toml"

    if (-not (Test-Path $frpExe)) {
        Write-Warn "frpc.exe 未找到"
        Write-Host "  请从 https://github.com/fatedier/frp/releases 下载" -ForegroundColor Gray
        Write-Host "  解压 frpc.exe 到 frp\ 目录" -ForegroundColor Gray
    } else {
        # 检查是否已在运行
        $existing = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
        if ($existing) {
            Write-OK "FRP 客户端已在运行 (PID: $($existing.Id))"
        } else {
            Start-Process -FilePath $frpExe -ArgumentList "-c", $frpToml -WindowStyle Hidden
            Start-Sleep -Seconds 2
            $proc = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
            if ($proc) {
                Write-OK "FRP 客户端已启动 (PID: $($proc.Id))"
            } else {
                Write-Warn "FRP 启动失败，请手动运行: frp\frpc.exe -c frp\frpc.toml"
            }
        }
    }
}

# ============================================
# 完成
# ============================================
Set-Location $PROJECT_DIR

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " 部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  访问地址: https://agent.mnb-lab.cn" -ForegroundColor White
Write-Host ""
Write-Host "  服务状态:" -ForegroundColor White
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>$null
Write-Host ""
Write-Host "  常用命令:" -ForegroundColor White
Write-Host "    查看日志:    docker compose logs -f app" -ForegroundColor Gray
Write-Host "    停止服务:    docker compose down" -ForegroundColor Gray
Write-Host "    重启服务:    docker compose restart" -ForegroundColor Gray
Write-Host "    查看 FRP:    Get-Process frpc" -ForegroundColor Gray

# ============================================
# 迁移检查清单（域名不变时）
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host " 迁移检查清单" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "  以下项目需要在新电脑上确认：" -ForegroundColor White
Write-Host ""

Write-Host "  [1] 旧电脑 FRP 客户端" -ForegroundColor White
Write-Host "      确保旧电脑的 frpc 已关闭，否则两端会冲突" -ForegroundColor Gray
Write-Host "      旧电脑执行: Stop-Process frpc -ErrorAction SilentlyContinue" -ForegroundColor Gray
Write-Host ""

Write-Host "  [2] 企业微信回调 URL（无需修改）" -ForegroundColor White
Write-Host "      回调地址: https://agent.mnb-lab.cn/api/v1/wechat/callback" -ForegroundColor Gray
Write-Host "      域名不变，企业微信后台无需任何改动" -ForegroundColor Gray
Write-Host "      只需确认 .env 中以下配置正确：" -ForegroundColor Gray
Write-Host "        WECHAT_CORP_ID         企业 ID" -ForegroundColor DarkGray
Write-Host "        WECHAT_AGENT_ID        应用 AgentId" -ForegroundColor DarkGray
Write-Host "        WECHAT_SECRET           应用 Secret" -ForegroundColor DarkGray
Write-Host "        WECHAT_CALLBACK_TOKEN   回调 Token" -ForegroundColor DarkGray
Write-Host "        WECHAT_ENCODING_AES_KEY 回调 EncodingAESKey" -ForegroundColor DarkGray
Write-Host "        WECHAT_EXTERNAL_SENDER  外部联系人发送者 userid" -ForegroundColor DarkGray
Write-Host ""

Write-Host "  [3] 腾讯会议 Webhook URL（无需修改）" -ForegroundColor White
Write-Host "      回调地址: https://agent.mnb-lab.cn/api/v1/tencent-meeting/webhook" -ForegroundColor Gray
Write-Host "      域名不变，腾讯会议后台无需任何改动" -ForegroundColor Gray
Write-Host "      只需确认 .env 中以下配置正确：" -ForegroundColor Gray
Write-Host "        TENCENT_MEETING_SDK_ID   SDK ID" -ForegroundColor DarkGray
Write-Host "        TENCENT_MEETING_SDK_KEY  SDK Key" -ForegroundColor DarkGray
Write-Host "        TENCENT_MEETING_USERID   主持人企业用户 ID" -ForegroundColor DarkGray
Write-Host ""

Write-Host "  [4] 数据迁移（可选）" -ForegroundColor White
Write-Host "      如需保留旧数据，将旧电脑的 data/ 目录复制到新电脑" -ForegroundColor Gray
Write-Host "      包含: PostgreSQL 数据库 + Redis 缓存 + MinIO 文件" -ForegroundColor Gray
Write-Host "      复制后重新运行: powershell -ExecutionPolicy Bypass -File setup.ps1 -Migrate" -ForegroundColor Gray
Write-Host ""

Write-Host "  [5] 云服务器 Nginx + FRP 服务端（无需修改）" -ForegroundColor White
Write-Host "      云服务器配置不变，新电脑 FRP 客户端会自动连接" -ForegroundColor Gray
Write-Host "      确认云服务器防火墙已开放: 80, 443, 7000 端口" -ForegroundColor Gray
Write-Host ""

Write-Host "  [6] 前端 dist（已包含在项目中）" -ForegroundColor White
Write-Host "      如果复制时包含了 web/dist/，可使用 -SkipFrontend 跳过构建" -ForegroundColor Gray
Write-Host ""

Read-Host "按 Enter 退出"

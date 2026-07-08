# MicroBubble SSH Key 一键生成辅助脚本
# 2026-07-08 P1-10: 新成员 onboard 用
#
# 用法: powershell -ExecutionPolicy Bypass -File tunnel\setup-ssh-key.ps1
#
# 功能:
# 1. 检测 ~/.ssh/id_ed25519 是否存在 (有就跳过, 不覆盖)
# 2. 生成新的 ed25519 key
# 3. 打印公钥到屏幕 (给 admin 加到 cloud ~/.ssh/authorized_keys)
# 4. 打印下一步操作提示

$ErrorActionPreference = "Continue"
$SSH_DIR = Join-Path $env:USERPROFILE ".ssh"
$KEY_PATH = Join-Path $SSH_DIR "id_ed25519"
$PUB_PATH = Join-Path $SSH_DIR "id_ed25519.pub"

Write-Host "========================================"
Write-Host " MicroBubble SSH Key 一键生成"
Write-Host "========================================"
Write-Host ""

# 检查现有 key
if (Test-Path $KEY_PATH) {
    Write-Host "SSH key 已存在: $KEY_PATH" -ForegroundColor Yellow
    Write-Host "如需重新生成, 请手动删除该文件后再跑此脚本"
    Write-Host ""
    Write-Host "现有公钥 (复制发给 admin):"
    Write-Host "----------------------------------------"
    Get-Content $PUB_PATH
    Write-Host "----------------------------------------"
    exit 0
}

Write-Host "未找到 SSH key, 开始生成 ed25519..." -ForegroundColor Cyan
Write-Host ""

# 创建 ~/.ssh 目录
if (-not (Test-Path $SSH_DIR)) {
    New-Item -ItemType Directory -Path $SSH_DIR -Force | Out-Null
    Write-Host "创建目录: $SSH_DIR"
}

# 用 ssh-keygen 生成 (Windows OpenSSH 自带)
try {
    $output = & ssh-keygen -t ed25519 -f $KEY_PATH -N '""' -C "microbubble-agent-local-$(whoami)@$(hostname)" 2>&1
    Write-Host $output
} catch {
    Write-Host "ERROR: ssh-keygen 失败: $_" -ForegroundColor Red
    Write-Host "请确认 Windows OpenSSH 已启用 (Settings > Apps > Optional Features > OpenSSH Client)"
    exit 1
}

if (-not (Test-Path $KEY_PATH)) {
    Write-Host "ERROR: 私钥生成失败" -ForegroundColor Red
    exit 2
}

# 限制权限 (NTFS + Windows SSH 通常要求)
icacls $KEY_PATH /inheritance:r | Out-Null
icacls $KEY_PATH /grant:r "$($env:USERNAME):(R)" | Out-Null
icacls $PUB_PATH /inheritance:r | Out-Null
icacls $PUB_PATH /grant:r "$($env:USERNAME):(R)" | Out-Null
icacls $SSH_DIR /inheritance:r | Out-Null

Write-Host ""
Write-Host "========================================"
Write-Host " 生成成功!"
Write-Host "========================================"
Write-Host ""
Write-Host "私钥: $KEY_PATH (KEEP SECRET)" -ForegroundColor Yellow
Write-Host "公钥: $PUB_PATH"
Write-Host ""
Write-Host "请把下面公钥发给 admin, admin 加到 cloud 的 ~/.ssh/authorized_keys 后,"
Write-Host "你就可以跑 tunnel\start-ssh-tunnel.ps1 启用反向隧道了."
Write-Host ""
Write-Host "公钥内容 (发给 admin):"
Write-Host "----------------------------------------"
Get-Content $PUB_PATH
Write-Host "----------------------------------------"
Write-Host ""
Write-Host "下一步 (admin 操作):"
Write-Host "  1. 你把上面公钥发给 admin"
Write-Host "  2. admin 在 cloud server 跑:"
Write-Host "     echo '<上面公钥>' >> ~/.ssh/authorized_keys"
Write-Host "  3. admin 测试: ssh -i ~/.ssh/id_ed25519 root@localhost  (本机) 或 ssh root@localhost (cloud)"
Write-Host ""
Write-Host "下一步 (你操作):"
Write-Host "  4. 测试隧道:  powershell tunnel\start-ssh-tunnel.ps1"
Write-Host "  5. 注册开机启动: schtasks /Create /TN MicroBubble-SSH-Tunnel /TR ..."
Write-Host "     (详见 tunnel\README.md)"
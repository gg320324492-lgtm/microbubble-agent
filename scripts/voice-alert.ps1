# MicroBubble Voice Alert — Agent/任务完成 / 需要确认时手动触发的语音提醒
#
# 用法（PowerShell 推荐）：
#   powershell scripts/voice-alert.ps1 -Message "Claude已经完成了所有任务，请回来查看结果吧"
#   powershell scripts/voice-alert.ps1 -TaskDone
#   powershell scripts/voice-alert.ps1 -NeedConfirm
#   powershell scripts/voice-alert.ps1 -OnError "后端 500 了"
#   powershell scripts/voice-alert.ps1 -AskQuestion "你需要选 A 还是 B？"
#   powershell scripts/voice-alert.ps1 -TaskDone -ShowToast      # 戴耳机时开启视觉通知
#
# 也支持 .bat 包装（更省事）：
#   scripts\voice-alert -TaskDone              # 默认：仅 TTS，2 秒完成
#   scripts\voice-alert -TaskDone -ShowToast   # 戴耳机场景：TTS + 通知
#   scripts\voice-alert -OnError "失败原因"
#
# 依赖：
#   - Windows SAPI（System.Speech，所有 Windows 10/11 自带，离线 TTS，无网络依赖）
#   - -ShowToast 时按需用 BurntToast / WinRT / NotifyIcon BalloonTip（3 层 fallback）
#
# 设计：
#   - 离线 SAPI TTS，零网络延迟，失败时优雅降级到 console 提示音
#   - 中文声音按优先级回退：Microsoft Huihui Desktop → Microsoft Zira → 系统默认
#     （部分 Win11 镜像不带 Huihui，Zira 是英文但 fallback 一定可用）
#   - 视觉通知默认关闭（Win11 托盘折叠 + BurntToast 在 PS 5.1 broken，可见性弱）；加 -ShowToast 显式开启
#   - 写结构化日志到 logs\voice-alert\voice-alert-YYYYMMDD.log
#
# 部署：脚本不需要任何安装，直接 powershell 执行即可。
# 如需在 schtasks / Agent hook 里调用，见 CLAUDE.md "schtasks 弹窗" 教训：
#   PowerShell 直接 schtasks 调会闪控制台窗口，建议用 run-hidden.vbs 包装。

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false, Position = 0)]
    [string]$Message,

    [switch]$TaskDone,
    [switch]$NeedConfirm,
    [switch]$OnError,           # 注意：不用 $Error，PowerShell 内置 $Error 是只读全局变量
    [switch]$AskQuestion,

    [int]$Rate = -2,        # SAPI rate (-10 ~ 10)，-2 略慢更清晰（edge-tts 用 +0% rate）
    [int]$Volume = 100,     # 0~100
    [string]$Voice = "zh-CN-XiaoxiaoNeural",  # edge-tts 女声（XiaoxiaoNeural=晓晓甜美 / XiaomengNeural=晓梦儿童 / XiaoyiNeural=晓伊温柔 / XiaoyouNeural=晓悠童声 / XiaoxuanNeural=晓萱活泼）
    [switch]$ShowToast,     # 显式开启 Windows 通知（默认关闭，因 Win11 托盘折叠可见性弱；戴耳机时启用）
    [switch]$Quiet          # 静默模式：只写日志，不发声（用于 watchdog 集成）
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot "logs\voice-alert"
$LogFile = Join-Path $LogDir ("voice-alert-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

# ---------- 日志 ----------
function Write-Log {
    param([string]$Level, [string]$MessageText, [hashtable]$Extra)
    if ($Extra -eq $null) { $Extra = @{} }
    $entry = [ordered]@{
        timestamp = (Get-Date).ToString("o")
        level     = $Level
        script    = "voice-alert"
        message   = $MessageText
    }
    # 受保护字段：hashtable 里同名 key 不覆盖（防止 call site 误传 `message` 覆盖 log message）
    $protected = @("timestamp", "level", "script", "message")
    foreach ($k in $Extra.Keys) {
        if ($protected -notcontains $k) { $entry[$k] = $Extra[$k] }
    }
    $json = $entry | ConvertTo-Json -Compress
    try { Add-Content -Path $LogFile -Value $json -Encoding UTF8 } catch {}
}

# ---------- 预设消息 ----------
# 中文 SAPI 默认 rate=-2 听起来比较自然，rate=0 偏快
$PresetTaskDone   = "Claude 已经完成了所有任务，请回来查看结果吧"
$PresetNeedConfirm = "任务需要你手动确认，请回来查看"
$PresetAskQuestion = "Claude 在等你回答问题，请回来查看"
$PresetError       = "出现错误，请回来查看"

$finalMessage = ""
$presetName   = "custom"

if ($TaskDone)    { $finalMessage = $PresetTaskDone;     $presetName = "task-done" }
elseif ($NeedConfirm) { $finalMessage = $PresetNeedConfirm; $presetName = "need-confirm" }
elseif ($AskQuestion) { $finalMessage = $PresetAskQuestion; $presetName = "ask-question" }
elseif ($OnError)   {
    if ([string]::IsNullOrWhiteSpace($Message)) {
        $finalMessage = $PresetError
    } else {
        $finalMessage = "错误：$Message"
    }
    $presetName = "error"
}
elseif (-not [string]::IsNullOrWhiteSpace($Message)) {
    $finalMessage = $Message
}
else {
    # 默认：任务完成提示（用户最常用的场景）
    $finalMessage = $PresetTaskDone
    $presetName = "task-done-default"
}

Write-Log "INFO" "voice-alert triggered" @{
    preset     = $presetName
    message    = $finalMessage
    rate       = $Rate
    volume     = $Volume
    show_toast = $ShowToast.IsPresent
    quiet      = $Quiet.IsPresent
}

if ($Quiet) {
    # 静默模式：只写日志，不发声（watchdog/Agent 集成用）
    exit 0
}

# ---------- TTS ----------
# 3 层 fallback：ChatTTS（离线）→ edge-tts（在线高质量）→ SAPI（保底）
# ChatTTS 跑在容器内，本地推理 0 网络依赖；edge-tts 走 Azure 短文本偶发 rate limit；SAPI 是 100% 保底

# 容器内 ChatTTS 合成（base64 传 text 避免 quoting + 中文问题）
# 关键：本地缓存 — 同一段文字只合成一次
function Invoke-ChatTTS {
    param([string]$Text)

    $container = "microbubble-agent-app-1"
    $chattsScript = "/app/app/chatts_synth.py"

    # 缓存路径：$env:LOCALAPPDATA\voice-alert-cache\<hash>.wav
    $cacheDir = Join-Path $env:LOCALAPPDATA "voice-alert-cache"
    if (-not (Test-Path $cacheDir)) { New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null }

    # Cache key 包含 prompt+seed：任何风格变化都生成新缓存
    $chattsPrompt = "[oral_2][laugh_0][speed_5]用甜美、温柔的女性声音说话，语气亲切自然，略带活泼"
    $chattsSeed = 42
    $cacheKey = [BitConverter]::ToString([System.Security.Cryptography.MD5]::Create().ComputeHash(
        [Text.Encoding]::UTF8.GetBytes("chatts|$chattsSeed|$chattsPrompt|$Text")
    )).Replace("-", "").Substring(0, 16)
    $wavCached = Join-Path $cacheDir "$cacheKey.wav"

    # 命中缓存：直接播
    if (Test-Path $wavCached) {
        try {
            Add-Type -AssemblyName PresentationCore -ErrorAction Stop
            $player = New-Object System.Windows.Media.MediaPlayer
            $player.Open($wavCached)
            $player.Play()
            $estimatedSec = [Math]::Max(3, [int]($Text.Length / 4.0) + 1)
            Start-Sleep -Seconds $estimatedSec
            $player.Close()
            Write-Log "DEBUG" "chatts cache hit" @{ key = $cacheKey }
            return $true
        }
        catch {
            Write-Log "DEBUG" "cached WAV playback failed" @{ error = $_.Exception.Message }
        }
    }

    # 缓存未命中：调 docker 合成 → 落容器 → cp 出来 → 缓存
    $wavContainer = "/tmp/chatts-$cacheKey.wav"
    $textB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Text))

    $env:MSYS2_ARG_CONV_EXCL = '*'
    $dockerOut = docker exec $container python $chattsScript "$textB64" $wavContainer --seed $chattsSeed --prompt "$chattsPrompt" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "DEBUG" "chatts docker exec failed" @{ error = ($dockerOut -join "`n") }
        return $false
    }

    # cp WAV 到本机缓存
    $cpOut = docker cp "${container}:${wavContainer}" $wavCached 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "DEBUG" "docker cp (chatts) failed" @{ error = ($cpOut -join "`n") }
        return $false
    }

    # 播放缓存的 WAV
    try {
        Add-Type -AssemblyName PresentationCore -ErrorAction Stop
        $player = New-Object System.Windows.Media.MediaPlayer
        $player.Open($wavCached)
        $player.Play()
        Write-Log "DEBUG" "chatts voice playing (cached)" @{ key = $cacheKey }
        $estimatedSec = [Math]::Max(3, [int]($Text.Length / 4.0) + 1)
        Start-Sleep -Seconds $estimatedSec
        $player.Close()
        return $true
    }
    catch {
        Write-Log "DEBUG" "WAV playback failed" @{ error = $_.Exception.Message }
        return $false
    }
}

# 容器内 edge-tts 合成（base64 传 text 避免 quoting + 中文问题）
# 关键：本地缓存 — 同一段文字只合成一次，避免 Microsoft Azure rate limit（短时间多次请求会触发 NoAudioReceived）
function Invoke-EdgeTTS {
    param([string]$Text, [string]$Voice = "zh-CN-XiaoxiaoNeural")

    $container = "microbubble-agent-app-1"

    # 缓存路径：$env:LOCALAPPDATA\voice-alert-cache\<hash>.mp3（hash 来自 text + voice）
    $cacheDir = Join-Path $env:LOCALAPPDATA "voice-alert-cache"
    if (-not (Test-Path $cacheDir)) { New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null }

    $cacheKey = [BitConverter]::ToString([System.Security.Cryptography.MD5]::Create().ComputeHash(
        [Text.Encoding]::UTF8.GetBytes("edge-tts|$Voice|$Text")
    )).Replace("-", "").Substring(0, 16)
    $mp3Cached = Join-Path $cacheDir "$cacheKey.mp3"

    # 命中缓存：直接播，跳过 docker 调用
    if (Test-Path $mp3Cached) {
        try {
            Add-Type -AssemblyName PresentationCore -ErrorAction Stop
            $player = New-Object System.Windows.Media.MediaPlayer
            $player.Open($mp3Cached)
            $player.Play()
            $estimatedSec = [Math]::Max(3, [int]($Text.Length / 4.0) + 1)
            Start-Sleep -Seconds $estimatedSec
            $player.Close()
            Write-Log "DEBUG" "edge-tts cache hit" @{ voice = $Voice; key = $cacheKey }
            return $true
        }
        catch {
            Write-Log "DEBUG" "cached MP3 playback failed" @{ error = $_.Exception.Message }
        }
    }

    # 缓存未命中：调 docker 合成 → 落容器 → cp 出来 → 缓存
    $mp3Container = "/tmp/voice-alert-edge-$cacheKey.mp3"
    $textB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Text))

    $env:MSYS2_ARG_CONV_EXCL = '*'
    $pyCmd = "import base64,asyncio,edge_tts; t=base64.b64decode('$textB64').decode('utf-8'); asyncio.run(edge_tts.Communicate(t,voice='$Voice').save('$mp3Container'))"
    $dockerOut = docker exec $container python -c $pyCmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "DEBUG" "edge-tts docker exec failed" @{ error = ($dockerOut -join "`n") }
        return $false
    }

    # cp MP3 到本机缓存
    $cpOut = docker cp "${container}:${mp3Container}" $mp3Cached 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "DEBUG" "docker cp failed" @{ error = ($cpOut -join "`n") }
        return $false
    }

    # 播放缓存的 MP3
    try {
        Add-Type -AssemblyName PresentationCore -ErrorAction Stop
        $player = New-Object System.Windows.Media.MediaPlayer
        $player.Open($mp3Cached)
        $player.Play()
        Write-Log "DEBUG" "edge-tts voice playing (cached)" @{ voice = $Voice; key = $cacheKey }
        $estimatedSec = [Math]::Max(3, [int]($Text.Length / 4.0) + 1)
        Start-Sleep -Seconds $estimatedSec
        $player.Close()
        return $true
    }
    catch {
        Write-Log "DEBUG" "MP3 playback failed" @{ error = $_.Exception.Message }
        return $false
    }
}

function Invoke-TTS {
    param([string]$Text)

    # 主路径 1：edge-tts（XiaoxiaoNeural 甜美女声，缓存命中后完全离线）
    if (Invoke-EdgeTTS -Text $Text -Voice $Voice) {
        Write-Log "INFO" "tts via edge-tts" @{ voice = $Voice }
        return $true
    }

    # 主路径 2：ChatTTS（离线推理，男声但 100% 离线保底）
    if (Invoke-ChatTTS -Text $Text) {
        Write-Log "INFO" "tts via chatts (offline)" @{}
        return $true
    }

    # Fallback：SAPI（离线 Microsoft Huihui Desktop 中文女声，机械感强但 100% 可用）
    try {
        Add-Type -AssemblyName System.Speech -ErrorAction Stop
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

        # 中文声音优先级：Huihui Desktop (zh-CN) > Zira (en-US, 一定可用) > 系统默认
        $preferredVoices = @(
            "Microsoft Huihui Desktop",
            "Microsoft Zira Desktop",
            "Microsoft David Desktop"
        )
        $voiceSelected = $false
        foreach ($v in $preferredVoices) {
            try {
                $synth.SelectVoice($v)
                $voiceSelected = $true
                Write-Log "DEBUG" "SAPI voice selected" @{ voice = $v }
                break
            } catch {}
        }
        if (-not $voiceSelected) {
            Write-Log "WARN" "no preferred SAPI voice found, using system default" @{}
        }

        $synth.Volume = [Math]::Max(0, [Math]::Min(100, $Volume))
        $synth.Rate   = [Math]::Max(-10, [Math]::Min(10, $Rate))

        $synth.Speak($Text)
        $synth.Dispose()
        Write-Log "INFO" "tts via SAPI fallback" @{}
        return $true
    }
    catch {
        Write-Log "ERROR" "TTS failed (all 3 paths)" @{ error = $_.Exception.Message }
        return $false
    }
}

# ---------- Windows 通知（3 层 fallback） ----------
# 方案 1: BurntToast 0.8.5+ （PS 7+ 可用，PS 5.1 上 WinRT activation 失败 → 跳到方案 2）
# 方案 2: WinRT 原生 ToastNotificationManager（PS 7+ 可用，PS 5.1 同样限制 → 跳到方案 3）
# 方案 3: System.Windows.Forms.NotifyIcon BalloonTip（.NET Framework 内置，PS 5.1/PS 7 都可用，最终兜底）
# TTS 永远是主通道，notification 仅是视觉补充，戴耳机/离开座位也能看见通知

# BurntToast 可用性缓存（避免每次都尝试 Import + New）
# PS 5.1 上 WinRT activation context 必然失败，跳过探测直接 false（节省 5-6s）
# PS 7+ 才走正常探测
$script:BurntToastUsable = if ($PSVersionTable.PSVersion.Major -lt 7) { $false } else { $null }

function Test-BurntToast {
    if ($null -ne $script:BurntToastUsable) { return $script:BurntToastUsable }
    try {
        if (-not (Get-Module -ListAvailable -Name BurntToast)) {
            $script:BurntToastUsable = $false
            return $false
        }
        Import-Module BurntToast -ErrorAction Stop
        # PS 7+ 上 New-BurntToastNotification 应该正常返回，探针一次确认
        $probe = New-BurntToastNotification -Text "probe", "probe" -ErrorAction Stop
        $script:BurntToastUsable = ($null -ne $probe)
    } catch {
        $script:BurntToastUsable = $false
    }
    return $script:BurntToastUsable
}

function Send-Toast {
    param([string]$Title, [string]$Body)

    if (-not $ShowToast) { return }

    # 方案 1: BurntToast
    if (Test-BurntToast) {
        try {
            $n = New-BurntToastNotification -Text $Title, $Body -ErrorAction Stop
            Submit-BTNotification -Content $n -ErrorAction Stop
            Write-Log "DEBUG" "toast shown via BurntToast" @{ title = $Title }
            return
        } catch {
            $script:BurntToastUsable = $false
            Write-Log "DEBUG" "BurntToast submit failed (will fall back)" @{ error = $_.Exception.Message }
        }
    }

    # 方案 2: WinRT 原生（PS 7+ 可用，PS 5.1 因 WinRT activation context 限制失败）
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
            [Windows.UI.Notifications.ToastTemplateType]::ToastText02
        )

        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode($Title)) | Out-Null
        $textNodes.Item(1).AppendChild($template.CreateTextNode($Body))   | Out-Null

        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("MicroBubble Voice Alert")
        $notifier.Show($toast)
        Write-Log "DEBUG" "toast shown via WinRT" @{ title = $Title }
        return
    }
    catch {
        Write-Log "DEBUG" "WinRT toast failed (will fall back to NotifyIcon)" @{ error = $_.Exception.Message }
    }

    # 方案 3: NotifyIcon BalloonTip（最终兜底，PS 5.1/7 都可用）
    # 系统托盘右下角弹气泡 5 秒，Win11 上 UX 略弱（系统托盘默认折叠）但 100% 可靠
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        Add-Type -AssemblyName System.Drawing -ErrorAction Stop

        $ni = New-Object System.Windows.Forms.NotifyIcon
        $ni.Icon = [System.Drawing.SystemIcons]::Information
        $ni.BalloonTipTitle = $Title
        $ni.BalloonTipText  = $Body
        $ni.BalloonTipIcon  = [System.Windows.Forms.ToolTipIcon]::Info
        $ni.Visible = $true
        $ni.ShowBalloonTip(5000)
        # 等气球显示完再 dispose，否则会被立即关掉
        Start-Sleep -Milliseconds 5500
        $ni.Dispose()
        Write-Log "DEBUG" "toast shown via NotifyIcon BalloonTip" @{ title = $Title }
    }
    catch {
        Write-Log "WARN" "all toast backends failed (TTS still active)" @{ error = $_.Exception.Message }
    }
}

# ---------- 主流程 ----------
$ok = Invoke-TTS -Text $finalMessage
Send-Toast -Title "MicroBubble" -Body $finalMessage

if (-not $ok) {
    # TTS 失败时给个 console 提示音，让用户至少看到脚本跑了
    try { [Console]::Beep(800, 300) } catch {}
    Write-Log "WARN" "fell back to console beep (TTS unavailable)" @{}
    exit 2
}

Write-Log "INFO" "voice-alert completed" @{}
exit 0
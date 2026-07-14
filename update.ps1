# Update-App-Elegant.ps1
param (
    [Parameter(Mandatory=$true)][string]$AppName,
    [Parameter(Mandatory=$true)][string]$SourceDir,
    [Parameter(Mandatory=$true)][string]$TargetDir,
    [int]$WaitTime = 5
)

# 0. 参数清理
$AppName = $AppName.Trim("'").Trim('"')
$SourceDir = $SourceDir.Trim("'").Trim('"')
$TargetDir = $TargetDir.Trim("'").Trim('"')

# 1. 智能权限判断
function Test-RequiresAdmin {
    param([string]$Path)
    $isSystemDrive = $Path.StartsWith("C:", [System.StringComparison]::OrdinalIgnoreCase)
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return ($isSystemDrive -and !$currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
}

if (Test-RequiresAdmin -Path $TargetDir) {
    $scriptPath = $MyInvocation.MyCommand.Path
    $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$scriptPath`"", "-AppName", "`"$AppName`"", "-SourceDir", "`"$SourceDir`"", "-TargetDir", "`"$TargetDir`"", "-WaitTime", "$WaitTime")
    Start-Process powershell.exe -ArgumentList $argList -Verb RunAs
    exit
}

# --- 美化工具函数 ---
function Write-Header {
    param([string]$Text)
    Write-Host "`n─── $Text ───" -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Step, [string]$Msg)
    Write-Host "[$Step] " -NoNewline -ForegroundColor Gray
    Write-Host $Msg -ForegroundColor White
}

function Write-Success { param([string]$Msg) Write-Host "  ✔ $Msg" -ForegroundColor Green }
function Write-Info    { param([string]$Msg) Write-Host "  ℹ $Msg" -ForegroundColor Blue }
function Write-Warning { param([string]$Msg) Write-Host "  ⚠ $Msg" -ForegroundColor Yellow }

# --- 界面初始化 ---
Clear-Host
Write-Host @"
┌────────────────────────────────────────────────────────┐
│             🚀  BM-Scripts-Box 自动更新程序            │
└────────────────────────────────────────────────────────┘
"@ -ForegroundColor Cyan

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$adminStatus = if ($currentPrincipal.IsInRole(64)) { "Administrator" } else { "User" }
Write-Info "运行权限: $adminStatus"
Write-Info "目标路径: $TargetDir"
Write-Header "准备阶段"

# 2. 倒计时美化
Write-Step "1/4" "等待应用进程关闭..."
for ($i = $WaitTime; $i -gt 0; $i--) {
    $pct = [int](($WaitTime - $i + 1) / $WaitTime * 100)
    Write-Host "`r  进度: [" -NoNewline -ForegroundColor Gray
    Write-Host ("#" * ($pct/5)) -NoNewline -ForegroundColor Cyan
    Write-Host ("." * (20 - $pct/5)) -NoNewline -ForegroundColor Gray
    Write-Host "] $i 秒 " -NoNewline -ForegroundColor White
    Start-Sleep -Seconds 1
}
Write-Host "`n"

# 进程清理
$retryCount = 0
while ($retryCount -lt 5) {
    $processes = Get-Process -Name $AppName -ErrorAction SilentlyContinue
    if (!$processes) { break }
    Write-Warning "进程 '$AppName' 仍在运行，尝试强制关闭 ($($retryCount + 1)/5)..."
    $processes | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $retryCount++
}

# 3. 备份阶段
Write-Header "更新阶段"
Write-Step "2/4" "创建系统快照 (备份)..."
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $env:TEMP "$($AppName)_backup_$timestamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Write-Success "临时备份点: $backupDir"

# 4. 执行更新
Write-Step "3/4" "正在部署新版本文件..."
try {
    $fullSource = (Get-Item -Path $SourceDir).FullName
    $files = Get-ChildItem -Path $fullSource -Recurse | Where-Object { !$_.PSIsContainer }
    $totalFiles = $files.Count
    $currentFile = 0

    foreach ($file in $files) {
        $currentFile++
        $relativePath = $file.FullName.Substring($fullSource.Length + 1)
        $targetPath = Join-Path $TargetDir $relativePath
        $targetFileDir = Split-Path $targetPath

        # 备份旧文件
        if (Test-Path $targetPath) {
            $null = New-Item -ItemType Directory -Path (Split-Path (Join-Path $backupDir $relativePath)) -Force
            Copy-Item -Path $targetPath -Destination (Join-Path $backupDir $relativePath) -Force
        }
        
        # 确保目录存在
        if (!(Test-Path $targetFileDir)) { New-Item -ItemType Directory -Path $targetFileDir -Force | Out-Null }

        # 更新操作（带重试机制）
        $moveSuccess = $false
        try {
            Move-Item -Path $file.FullName -Destination $targetPath -Force -ErrorAction Stop
            $moveSuccess = $true
            Write-Host "  → [$currentFile/$totalFiles] " -NoNewline -ForegroundColor Gray
            Write-Host $relativePath -ForegroundColor Green
        }
        catch {
            Write-Warning "文件锁定，正在等待重试..."
            Start-Sleep -Seconds 1
            Move-Item -Path $file.FullName -Destination $targetPath -Force
            Write-Success $relativePath
        }
    }
}
catch {
    Write-Host "`n❌ 部署失败!" -ForegroundColor Red -BackgroundColor Black
    Write-Warning "详情: $($_.Exception.Message)"
    if (Test-Path $backupDir) {
        Write-Info "正在执行回滚程序..."
        Copy-Item -Path "$backupDir\*" -Destination $TargetDir -Recurse -Force
        Write-Success "系统已恢复至更新前状态。"
    }
    Write-Host "`n按任意键退出..."
    $null = [Console]::ReadKey()
    exit 1
}

# 5. 启动与收尾
Write-Header "启动阶段"
Write-Step "4/4" "正在启动核心程序 (静默模式)..."


$exePath = Join-Path $TargetDir "runtime\$AppName.exe"
$scriptPath = "main.py"

if (Test-Path $exePath) {
    Start-Process -FilePath $exePath -ArgumentList "`"$scriptPath`"" -WorkingDirectory $TargetDir -WindowStyle Hidden
    Write-Success "程序已在后台成功启动。"
}
else {
    Write-Warning "可执行文件不存在: $exePath"
}

Write-Host "`n✨ 自动更新已完成！" -ForegroundColor Cyan
Write-Host "────────────────────────────────────────────────────────" -ForegroundColor Cyan
Start-Sleep -Seconds 2
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


# 0.1 系统版本检查（1.5.0 起需要 Windows 10 1809+）
if ([System.Environment]::OSVersion.Version.Build -lt 17763) {
    Write-Host "当前系统版本过低：1.5.0 起需要 Windows 10 1809 或更高版本" -ForegroundColor Yellow
    Write-Host "按任意键退出..." -ForegroundColor Gray
    try { $null = [Console]::ReadKey() } catch { }
    exit 1
}

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

# 3. 备份阶段（放在安装目录内，避免 %TEMP% 被清理后无法回滚）
Write-Header "更新阶段"
Write-Step "2/4" "创建系统快照 (备份)..."
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $TargetDir "BmLogs\update\$timestamp"
try {
    New-Item -ItemType Directory -Path $backupDir -Force -ErrorAction Stop | Out-Null
} catch {
    # 安装目录不可写时回退到用户目录
    $backupDir = Join-Path $env:LOCALAPPDATA "BmScriptsBox\update_backup\$timestamp"
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}
Write-Success "备份目录: $backupDir"

# 4. 执行更新
Write-Step "3/4" "正在部署新版本文件..."
try {
    $fullSource = (Get-Item -Path $SourceDir).FullName

    # 运行时整包替换（archives/runtime.zip）
    $runtimeArchive = Join-Path $fullSource "archives\runtime.zip"
    if (Test-Path $runtimeArchive) {
        Write-Step "3/4" "正在替换运行时..."
        $runtimeDir = Join-Path $TargetDir "runtime"
        $runtimeNew = Join-Path $TargetDir "runtime.new"
        $runtimeOld = Join-Path $TargetDir "runtime.old"
        if (Test-Path $runtimeNew) { Remove-Item -Path $runtimeNew -Recurse -Force }
        if (Test-Path $runtimeOld) { Remove-Item -Path $runtimeOld -Recurse -Force }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($runtimeArchive, $runtimeNew)
        if (!(Test-Path (Join-Path $runtimeNew "BmScriptsBox.exe"))) {
            throw "运行时包校验失败：缺少 BmScriptsBox.exe"
        }
        if (Test-Path $runtimeDir) {
            Rename-Item -Path $runtimeDir -NewName "runtime.old" -Force
        }
        Rename-Item -Path $runtimeNew -NewName "runtime" -Force
        Write-Success "运行时已替换"
    }

    # removed.json 是给下面的删除步骤用的控制文件，不能复制到安装目录
    $removedFile = Join-Path $fullSource "removed.json"
    $files = Get-ChildItem -Path $fullSource -Recurse | Where-Object {
        !$_.PSIsContainer -and $_.FullName -notmatch '\\archives\\' -and $_.FullName -ne $removedFile
    }
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

        # 更新操作：用 Copy 而不是 Move，保留下载目录作为回滚源
        try {
            Copy-Item -Path $file.FullName -Destination $targetPath -Force -ErrorAction Stop
            Write-Host "  → [$currentFile/$totalFiles] " -NoNewline -ForegroundColor Gray
            Write-Host $relativePath -ForegroundColor Green
        }
        catch {
            Write-Warning "文件锁定，正在等待重试..."
            Start-Sleep -Seconds 1
            Copy-Item -Path $file.FullName -Destination $targetPath -Force
            Write-Success $relativePath
        }
    }

    # 5. 执行删除清单（removed.json）：只删清单内、且位于安装目录内的路径
    if (Test-Path $removedFile) {
        Write-Info "清理旧版本文件..."
        $removedItems = @()
        try {
            $raw = Get-Content -Path $removedFile -Raw -Encoding UTF8
            $parsed = $raw | ConvertFrom-Json
            if ($null -ne $parsed) { $removedItems = @($parsed) }
        } catch {
            Write-Warning "删除清单解析失败，跳过: $($_.Exception.Message)"
        }

        $protectedDirs = @('bmdata', 'bmscripts', 'bmpackages', 'bmlogs', 'bmcache', 'bmcontext')
        $targetNorm = [System.IO.Path]::GetFullPath($TargetDir)
        $removedCount = 0
        foreach ($rel in $removedItems) {
            if ($rel -isnot [string]) { continue }
            $clean = ($rel -replace '/', '\').Trim()
            if ([string]::IsNullOrWhiteSpace($clean)) { continue }
            if ([System.IO.Path]::IsPathRooted($clean) -or $clean -match '\.\.') {
                Write-Warning "跳过非法删除项: $rel"
                continue
            }
            $first = ($clean -split '\\')[0].ToLower()
            if ($protectedDirs -contains $first) {
                Write-Warning "跳过受保护删除项: $rel"
                continue
            }
            $fullPath = [System.IO.Path]::GetFullPath((Join-Path $TargetDir $clean))
            if (-not $fullPath.StartsWith($targetNorm, [System.StringComparison]::OrdinalIgnoreCase)) {
                Write-Warning "跳过越界删除项: $rel"
                continue
            }
            if (-not (Test-Path $fullPath)) { continue }
            try {
                $backupPath = Join-Path $backupDir $clean
                New-Item -ItemType Directory -Path (Split-Path $backupPath) -Force | Out-Null
                Copy-Item -Path $fullPath -Destination $backupPath -Recurse -Force
                Remove-Item -Path $fullPath -Recurse -Force
                $removedCount++
                Write-Host "  - $rel" -ForegroundColor DarkYellow
            } catch {
                Write-Warning "删除失败 $rel : $($_.Exception.Message)"
            }
        }
        Write-Success "已清理 $removedCount 个旧文件/目录"
    }
}
catch {
    Write-Host "`n❌ 部署失败!" -ForegroundColor Red -BackgroundColor Black
    Write-Warning "详情: $($_.Exception.Message)"
    $runtimeDir = Join-Path $TargetDir "runtime"
    $runtimeOld = Join-Path $TargetDir "runtime.old"
    if (!(Test-Path $runtimeDir) -and (Test-Path $runtimeOld)) {
        Rename-Item -Path $runtimeOld -NewName "runtime" -Force
        Write-Success "运行时已回滚到更新前状态"
    }
    if (Test-Path $backupDir) {
        Write-Info "正在执行回滚程序..."
        Copy-Item -Path "$backupDir\*" -Destination $TargetDir -Recurse -Force
        Write-Success "系统已恢复至更新前状态。"
    }
    Write-Host "`n按任意键退出..."
    try { $null = [Console]::ReadKey() } catch { }
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

$runtimeOld = Join-Path $TargetDir "runtime.old"
if (Test-Path $runtimeOld) { Remove-Item -Path $runtimeOld -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host "`n✨ 自动更新已完成！" -ForegroundColor Cyan
Write-Host "────────────────────────────────────────────────────────" -ForegroundColor Cyan
Start-Sleep -Seconds 2
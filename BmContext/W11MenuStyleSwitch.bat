@echo off
chcp 65001 >nul

:: 检查管理员权限
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if %errorlevel% NEQ 0 (
    goto UACPrompt
) else ( 
    goto gotAdmin 
)

:UACPrompt
echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
"%temp%\getadmin.vbs"
exit /B

:gotAdmin
if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )

:: 主菜单
cls
echo ============================================= 
echo          Win11 右键菜单切换工具
echo ============================================= 
echo.
echo   [1] 切换到 Win10 经典右键菜单
echo   [2] 恢复到 Win11 新版右键菜单
echo   [3] 退出
echo.
echo ============================================= 
echo.

:select
set /p opt=请选择操作 (1/2/3)： 

if "%opt%"=="1" (
    echo.
    echo 正在切换到 Win10 经典右键菜单...
    reg add "HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32" /f /ve >nul 2>&1
    echo 设置完成！
    goto restart
)

if "%opt%"=="2" (
    echo.
    echo 正在恢复到 Win11 新版右键菜单...
    reg delete "HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}" /f >nul 2>&1
    echo 恢复完成！
    goto restart
)

if "%opt%"=="3" (
    exit
)

:: 输入无效
echo.
echo 输入无效，请重新选择！
timeout /t 2 >nul
cls
goto :select

:restart
echo.
echo 正在重启资源管理器以应用更改...
taskkill /f /im explorer.exe >nul 2>&1
start explorer.exe
echo.
echo 操作完成！右键菜单已切换。
echo 3秒后自动退出...
timeout /t 3 >nul
exit
@echo off

cd /d %~dp0

echo 检查dll
set dllfile=BmScriptsBoxContextMenu.dll
if not exist %dllfile% (
    echo %dllfile% is not exist!
	pause>nul 
	exit
)
".\RegAsm.exe"  /codebase %dllfile% /u

echo 重启资源管理器
taskkill /f /im explorer.exe & start explorer.exe



exit
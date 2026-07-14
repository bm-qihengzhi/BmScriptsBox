@echo off

cd /d %~dp0

echo ¼ì²édll
set dllfile=BmScriptsBoxContextMenu.dll
if not exist %dllfile% (
    echo %dllfile% is not exist!
	pause>nul 
	exit
)
".\RegAsm.exe"  /codebase %dllfile%



exit
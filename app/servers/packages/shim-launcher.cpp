#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

static HANDLE g_childProcess = NULL;

BOOL WINAPI ConsoleCtrlHandler(DWORD dwCtrlType) {
    if (g_childProcess) {
        TerminateProcess(g_childProcess, 1);
        WaitForSingleObject(g_childProcess, 5000);
    }
    return TRUE;
}

int main() {
    wchar_t selfPath[MAX_PATH];
    DWORD len = GetModuleFileNameW(NULL, selfPath, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) return -1;

    wchar_t targetPath[MAX_PATH];
    wcscpy_s(targetPath, selfPath);
    wchar_t* dot = wcsrchr(targetPath, L'.');
    if (!dot) return -1;
    wcscpy_s(dot, MAX_PATH - (dot - targetPath), L".target");

    HANDLE hFile = CreateFileW(targetPath, GENERIC_READ, FILE_SHARE_READ, NULL,
                                OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) {
        MessageBoxW(NULL, L"无法找到 .target 配置文件", L"Shim Launcher Error", MB_OK | MB_ICONERROR);
        return -1;
    }

    char targetBuf[MAX_PATH];
    DWORD bytesRead = 0;
    if (!ReadFile(hFile, targetBuf, MAX_PATH - 1, &bytesRead, NULL)) {
        CloseHandle(hFile);
        return -1;
    }
    CloseHandle(hFile);
    targetBuf[bytesRead] = '\0';

    while (bytesRead > 0 && (targetBuf[bytesRead-1] == '\r' || targetBuf[bytesRead-1] == '\n' ||
                              targetBuf[bytesRead-1] == ' ' || targetBuf[bytesRead-1] == '\t'))
        targetBuf[--bytesRead] = '\0';

    wchar_t targetWide[MAX_PATH];
    MultiByteToWideChar(CP_UTF8, 0, targetBuf, -1, targetWide, MAX_PATH);

    wchar_t* cmdLine = GetCommandLineW();
    wchar_t* args = cmdLine;

    if (*args == L'"') {
        args++;
        while (*args && *args != L'"') args++;
        if (*args == L'"') args++;
    } else {
        while (*args && *args != L' ') args++;
    }
    while (*args == L' ') args++;

    SetConsoleCtrlHandler(ConsoleCtrlHandler, TRUE);

    wchar_t cmdTarget[32768];
    swprintf_s(cmdTarget, L"\"%s\" %s", targetWide, args);

    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi;

    if (!CreateProcessW(targetWide, cmdTarget, NULL, NULL, TRUE,
                        CREATE_DEFAULT_ERROR_MODE, NULL, NULL, &si, &pi)) {
        DWORD err = GetLastError();
        wchar_t errMsg[256];
        swprintf_s(errMsg, L"启动目标程序失败，错误码: %lu\n目标: %s", err, targetWide);
        MessageBoxW(NULL, errMsg, L"Shim Launcher Error", MB_OK | MB_ICONERROR);
        return -1;
    }

    CloseHandle(pi.hThread);
    g_childProcess = pi.hProcess;

    WaitForSingleObject(pi.hProcess, INFINITE);

    DWORD exitCode = 0;
    GetExitCodeProcess(pi.hProcess, &exitCode);
    CloseHandle(pi.hProcess);

    return (int)exitCode;
}

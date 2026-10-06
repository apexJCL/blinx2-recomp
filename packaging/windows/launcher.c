/*
 * BLiNX2.exe - the Windows launcher the installer's shortcuts point at.
 *
 * It builds the environment cat_recomp.exe reads through recomp_env, then
 * starts it. A shortcut cannot set environment variables, a .cmd would
 * flash a console, and a user-wide HKCU\Environment entry would leak into
 * every other recomp build on the machine, hence a small program. It is
 * packaging code, not the game, so it reads and sets variables directly.
 *
 *   The user-data root is %LOCALAPPDATA%\BLiNX2, or BLINX2_DATA_DIR when set.
 *   <exe dir>\launch.env.default, then %LOCALAPPDATA%\BLiNX2\config\launch.env
 *       KEY=value lines, '#' comments, later wins
 *   RECOMP_GAME_FILES      <exe dir>\game_files
 *   RECOMP_HDD_DIR         %LOCALAPPDATA%\BLiNX2\hdd      (saves; never touched
 *                                                          by install or uninstall)
 *   RECOMP_ENHANCE_CONFIG  %LOCALAPPDATA%\BLiNX2\config\enhance.toml, copied
 *                          from enhance.toml.default when absent; the .default
 *                          beside it is refreshed on every launch
 *   RECOMP_STDIO_LOG       %LOCALAPPDATA%\BLiNX2\logs\game-<stamp>.log, the
 *                          newest LOG_KEEP (10) kept
 *
 * The game starts with logs\ as its working directory (xbox_kernel.log goes
 * there), and the launcher returns its exit code.
 *
 * Build: x86_64-w64-mingw32-clang -municode -mwindows -O2 '-DBLINX2_NAME=L"BLiNX 2"' \
 *            launcher.c BLiNX2.res.o -o BLiNX2.exe -lshell32 -lole32 -luuid
 *        (uuid: FOLDERID_LocalAppData; BLiNX2.res.o: the icon, from BLiNX2.rc)
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>
#include <wchar.h>
#include <stdio.h>
#include <stdlib.h>

/* The product name, from package_lib.PRODUCT_NAME (blinx2 package passes
 * -DBLINX2_NAME=L"..."), so it is written in one place. */
#ifndef BLINX2_NAME
#error "build with -DBLINX2_NAME=L\"<product name>\" (blinx2 package does)"
#endif

#define PATH_CHARS 2048

static wchar_t g_exe_dir[PATH_CHARS];
static wchar_t g_data[PATH_CHARS];

static void fail(const wchar_t *msg)
{
    MessageBoxW(NULL, msg, BLINX2_NAME, MB_ICONERROR);
    ExitProcess(1);
}

/* KEY=value lines, in UTF-8; returns quietly when the file is absent. */
static void load_env(const wchar_t *path)
{
    FILE *f = _wfopen(path, L"rb");
    char line[4096];
    if (!f)
        return;
    while (fgets(line, sizeof(line), f)) {
        char *p = line, *eq, *end;
        wchar_t key[512], val[3584];
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == '\r' || *p == '\n' || !*p)
            continue;
        end = p + strlen(p);
        while (end > p && (end[-1] == '\r' || end[-1] == '\n')) *--end = 0;
        eq = strchr(p, '=');
        if (!eq || eq == p)
            continue;
        *eq = 0;
        if (!MultiByteToWideChar(CP_UTF8, 0, p, -1, key, 512) ||
            !MultiByteToWideChar(CP_UTF8, 0, eq + 1, -1, val, 3584))
            continue;
        SetEnvironmentVariableW(key, val);
    }
    fclose(f);
}

static int file_exists(const wchar_t *p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

/* True when a and b differ (or b is missing). */
static int files_differ(const wchar_t *a, const wchar_t *b)
{
    FILE *fa = _wfopen(a, L"rb"), *fb = _wfopen(b, L"rb");
    int differ = 1;
    if (fa && fb) {
        int ca, cb;
        do {
            ca = fgetc(fa);
            cb = fgetc(fb);
        } while (ca == cb && ca != EOF);
        differ = ca != cb;
    }
    if (fa) fclose(fa);
    if (fb) fclose(fb);
    return differ;
}

/* Keep the newest `keep` game-*.log files (names sort by time). */
static void rotate_logs(const wchar_t *logs, int keep)
{
    wchar_t pattern[PATH_CHARS], (*names)[MAX_PATH] = NULL;
    WIN32_FIND_DATAW fd;
    HANDLE h;
    int n = 0, cap = 0, i;
    swprintf(pattern, PATH_CHARS, L"%ls\\game-*.log", logs);
    h = FindFirstFileW(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE)
        return;
    do {
        if (n == cap) {
            cap = cap ? cap * 2 : 64;
            names = realloc(names, (size_t)cap * sizeof(*names));
            if (!names) { FindClose(h); return; }
        }
        wcsncpy(names[n++], fd.cFileName, MAX_PATH - 1);
        names[n - 1][MAX_PATH - 1] = 0;
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    qsort(names, (size_t)n, sizeof(*names), (int (*)(const void *, const void *))wcscmp);
    for (i = 0; i < n - keep; i++) {
        wchar_t p[PATH_CHARS];
        swprintf(p, PATH_CHARS, L"%ls\\%ls", logs, names[i]);
        DeleteFileW(p);
    }
    free(names);
}

/* The user-data root: BLINX2_DATA_DIR when set (tests point it at a scratch
 * folder so they never touch the player's saves or launch.env), else
 * %LOCALAPPDATA%\BLiNX2. */
static void data_dir(void)
{
    PWSTR appdata = NULL;
    DWORD n = GetEnvironmentVariableW(L"BLINX2_DATA_DIR", g_data, PATH_CHARS);
    if (n > 0 && n < PATH_CHARS)
        return;
    if (FAILED(SHGetKnownFolderPath(&FOLDERID_LocalAppData, 0, NULL, &appdata)))
        fail(L"Cannot find %LOCALAPPDATA%.");
    swprintf(g_data, PATH_CHARS, L"%ls\\BLiNX2", appdata);
    CoTaskMemFree(appdata);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmdline, int show)
{
    wchar_t p[PATH_CHARS], q[PATH_CHARS], logs[PATH_CHARS], log[PATH_CHARS];
    wchar_t exe[PATH_CHARS], *cmd, *slash, keep_s[32];
    STARTUPINFOW si = { 0 };
    PROCESS_INFORMATION pi;
    SYSTEMTIME t;
    DWORD code = 1;
    size_t len;
    int keep;
    (void)inst; (void)prev; (void)show;
    si.cb = sizeof(si);

    if (!GetModuleFileNameW(NULL, g_exe_dir, PATH_CHARS))
        fail(L"Cannot find the launcher's own folder.");
    slash = wcsrchr(g_exe_dir, L'\\');
    if (slash) *slash = 0;
    data_dir();

    swprintf(p, PATH_CHARS, L"%ls\\game_files\\default.xbe", g_exe_dir);
    if (!file_exists(p))
        fail(L"The game files are missing (game_files\\default.xbe beside BLiNX2.exe). "
             L"Run the setup program again from its folder.");

    swprintf(p, PATH_CHARS, L"%ls\\launch.env.default", g_exe_dir);
    load_env(p);
    swprintf(p, PATH_CHARS, L"%ls\\config\\launch.env", g_data);
    load_env(p);

    swprintf(p, PATH_CHARS, L"%ls\\config", g_data);
    SHCreateDirectoryExW(NULL, p, NULL);
    swprintf(logs, PATH_CHARS, L"%ls\\logs", g_data);
    SHCreateDirectoryExW(NULL, logs, NULL);
    swprintf(p, PATH_CHARS, L"%ls\\hdd", g_data);
    SetEnvironmentVariableW(L"RECOMP_HDD_DIR", p);
    swprintf(p, PATH_CHARS, L"%ls\\game_files", g_exe_dir);
    SetEnvironmentVariableW(L"RECOMP_GAME_FILES", p);

    /* enhance.toml: the user's copy is made once and never touched again;
     * the .default beside it follows the installed version. */
    swprintf(p, PATH_CHARS, L"%ls\\enhance.toml.default", g_exe_dir);
    swprintf(q, PATH_CHARS, L"%ls\\config\\enhance.toml", g_data);
    if (!file_exists(q))
        CopyFileW(p, q, TRUE);
    swprintf(q, PATH_CHARS, L"%ls\\config\\enhance.toml.default", g_data);
    if (files_differ(p, q))
        CopyFileW(p, q, FALSE);
    swprintf(q, PATH_CHARS, L"%ls\\config\\enhance.toml", g_data);
    SetEnvironmentVariableW(L"RECOMP_ENHANCE_CONFIG", q);

    keep = 10;
    if (GetEnvironmentVariableW(L"LOG_KEEP", keep_s, 32) && _wtoi(keep_s) > 0)
        keep = _wtoi(keep_s);
    rotate_logs(logs, keep - 1);
    GetLocalTime(&t);
    swprintf(log, PATH_CHARS, L"%ls\\game-%04u%02u%02u-%02u%02u%02u.log", logs,
             t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond);
    SetEnvironmentVariableW(L"RECOMP_STDIO_LOG", log);

    swprintf(exe, PATH_CHARS, L"%ls\\cat_recomp.exe", g_exe_dir);
    len = wcslen(exe) + wcslen(cmdline) + 8;
    cmd = malloc(len * sizeof(wchar_t));
    if (!cmd)
        fail(L"Out of memory.");
    swprintf(cmd, len, L"\"%ls\"%ls%ls", exe, *cmdline ? L" " : L"", cmdline);
    if (!CreateProcessW(exe, cmd, NULL, NULL, FALSE, 0, NULL, logs, &si, &pi)) {
        swprintf(p, PATH_CHARS, L"Cannot start %ls (error %lu).", exe, GetLastError());
        fail(p);
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    free(cmd);
    return (int)code;
}

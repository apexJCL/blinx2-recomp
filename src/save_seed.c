/**
 * RECOMP_SAVE_SEED=<dir>: copy a save tree into RECOMP_SAVE_DIR before the
 * game starts (input-real-devices 7.2, design.md D11).
 *
 * <dir> holds UDATA/ (and TDATA/ if any) as the title's save root does, e.g.
 * a locally kept story save; it is never committed. Every file under it is
 * copied over the same path in RECOMP_SAVE_DIR, so the run sees the seed
 * even when the save dir is reused; files that are only in the save dir are
 * left alone (use a fresh RECOMP_SAVE_DIR per run, which the game may
 * overwrite). Both variables must be set, and RECOMP_SAVE_DIR must be a host
 * path. If the seed is missing, empty or only partly copied, the process
 * logs it and exits with status 2 instead of booting.
 */

#include <stdio.h>
#include "recomp_env.h"
#include <stdlib.h>
#include <string.h>

static int s_files, s_errors;

#ifdef _WIN32
#include <windows.h>

/* Wide paths, so a seed or save dir with non-ASCII names still works. */
static void copy_tree(const wchar_t *from, const wchar_t *to)
{
    WIN32_FIND_DATAW fd;
    HANDLE h;
    wchar_t pat[MAX_PATH], a[MAX_PATH], b[MAX_PATH];

    if (_snwprintf(pat, MAX_PATH, L"%ls\\*", from) < 0) {
        fprintf(stderr, "[SAVE] seed: path too long: %ls\n", from);
        s_errors++;
        return;
    }
    pat[MAX_PATH - 1] = 0;
    h = FindFirstFileW(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "[SAVE] seed: cannot open %ls (err %lu)\n", from, GetLastError());
        s_errors++;
        return;
    }
    if (!CreateDirectoryW(to, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        fprintf(stderr, "[SAVE] seed: cannot create %ls (err %lu)\n", to, GetLastError());
        s_errors++;
        FindClose(h);
        return;
    }
    do {
        int na, nb;
        if (!wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..")) continue;
        na = _snwprintf(a, MAX_PATH, L"%ls\\%ls", from, fd.cFileName);
        nb = _snwprintf(b, MAX_PATH, L"%ls\\%ls", to, fd.cFileName);
        if (na < 0 || na >= MAX_PATH || nb < 0 || nb >= MAX_PATH) {
            fprintf(stderr, "[SAVE] seed: path too long under %ls\n", from);
            s_errors++;
            continue;
        }
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) copy_tree(a, b);
        else if (CopyFileW(a, b, FALSE)) s_files++;
        else {
            fprintf(stderr, "[SAVE] seed: cannot copy %ls -> %ls (err %lu)\n", a, b, GetLastError());
            s_errors++;
        }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
}

static int seed_is_dir(const char *seed)
{
    DWORD at = GetFileAttributesA(seed);
    return at != INVALID_FILE_ATTRIBUTES && (at & FILE_ATTRIBUTE_DIRECTORY);
}
#else
#include <dirent.h>
#include <errno.h>
#include <sys/stat.h>

static void copy_file(const char *from, const char *to)
{
    FILE *in = fopen(from, "rb"), *out = in ? fopen(to, "wb") : NULL;
    char buf[65536];
    size_t n;

    if (!in || !out) {
        fprintf(stderr, "[SAVE] seed: cannot copy %s -> %s\n", from, to);
        s_errors++;
    } else {
        while ((n = fread(buf, 1, sizeof buf, in)) > 0)
            if (fwrite(buf, 1, n, out) != n) { s_errors++; break; }
        s_files++;
    }
    if (in) fclose(in);
    if (out) fclose(out);
}

static void copy_tree(const char *from, const char *to)
{
    DIR *d = opendir(from);
    struct dirent *e;
    struct stat st;
    char a[4096], b[4096];

    if (!d) { fprintf(stderr, "[SAVE] seed: cannot open %s\n", from); s_errors++; return; }
    if (mkdir(to, 0755) && errno != EEXIST) {
        fprintf(stderr, "[SAVE] seed: cannot create %s\n", to);
        s_errors++;
        closedir(d);
        return;
    }
    while ((e = readdir(d))) {
        int na, nb;
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        na = snprintf(a, sizeof a, "%s/%s", from, e->d_name);
        nb = snprintf(b, sizeof b, "%s/%s", to, e->d_name);
        if (na < 0 || na >= (int)sizeof a || nb < 0 || nb >= (int)sizeof b) {
            fprintf(stderr, "[SAVE] seed: path too long under %s\n", from);
            s_errors++;
            continue;
        }
        if (stat(a, &st)) { fprintf(stderr, "[SAVE] seed: cannot stat %s\n", a); s_errors++; continue; }
        if (S_ISDIR(st.st_mode)) copy_tree(a, b);
        else if (S_ISREG(st.st_mode)) copy_file(a, b);
    }
    closedir(d);
}

static int seed_is_dir(const char *seed)
{
    struct stat st;
    return !stat(seed, &st) && S_ISDIR(st.st_mode);
}
#endif

/* A run that asked for a seed and did not get all of it must not boot: it
 * would silently test the wrong save. */
void cat_save_seed(void)
{
    const char *seed = recomp_env(RENV_SAVE_SEED);
    const char *dir = recomp_env(RENV_SAVE_DIR);

    if (!seed || !*seed) return;
    if (!dir || !*dir) {
        fprintf(stderr, "[SAVE] RECOMP_SAVE_SEED needs RECOMP_SAVE_DIR; exiting\n");
        exit(2);
    }
    if (!seed_is_dir(seed)) {
        fprintf(stderr, "[SAVE] seed %s is not a readable directory; exiting\n", seed);
        exit(2);
    }
#ifdef _WIN32
    {
        wchar_t ws[MAX_PATH], wd[MAX_PATH];
        if (!MultiByteToWideChar(CP_UTF8, 0, seed, -1, ws, MAX_PATH) ||
            !MultiByteToWideChar(CP_UTF8, 0, dir, -1, wd, MAX_PATH)) {
            fprintf(stderr, "[SAVE] seed: path too long; exiting\n");
            exit(2);
        }
        copy_tree(ws, wd);
    }
#else
    copy_tree(seed, dir);
#endif
    fprintf(stderr, "[SAVE] seed %s -> %s: %d files%s\n", seed, dir, s_files,
            s_errors ? ", with errors" : "");
    if (s_errors || !s_files) {
        fprintf(stderr, "[SAVE] seed copy incomplete; exiting\n");
        exit(2);
    }
}

#!/usr/bin/env python3
"""Suffix recovered function names that would clash with a host C library.

merge_names.py already keeps ISO C names (memcpy, fopen...) out of the
generated code, but not POSIX ones. A title's CRT really does have routines
called read, write, close, lseek and isatty, and on macOS/Linux a global
function by that name in the executable replaces libc's for every caller in
the binary -- toolkit file I/O and the crash handler included. Windows never
noticed because the MSVC CRT spells them _read, _write...

The generated C is shared between hosts (it is produced here and synced to
the Windows/Proton bench), so the reserved set is the union of the host libc
and the Windows target's CRT and system import libraries: under MinGW, names
like fpclass, onexit or control87 collide with <math.h>/<stdlib.h>
declarations and fail the compile outright.

Any applied name in that set is renamed to <name>_<ADDR>, the same convention
merge_names.py uses for its own reserved words.

usage: host_reserved_names.py <functions.json>
"""
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Always reserved, whatever the host: the POSIX I/O and process surface most
# likely to appear among recovered CRT names.
POSIX_BASELINE = set("""
read write open close lseek isatty dup dup2 pipe unlink access chdir getcwd
stat fstat lstat creat fcntl ioctl mkdir rmdir chmod umask sleep usleep
fork execv execve getpid kill exit _exit environ tell eof sopen chsize
""".split())


def host_libc_exports():
    """Exported symbol names of the host C library (without leading '_')."""
    names = set()
    if sys.platform == "darwin":
        try:
            sdk = subprocess.run(["xcrun", "--show-sdk-path"], capture_output=True,
                                 text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return names
        for tbd in Path(sdk, "usr/lib/system").glob("*.tbd"):
            names.update(re.findall(r"\b_([A-Za-z][A-Za-z0-9_]*)\b", tbd.read_text(errors="ignore")))
    elif sys.platform.startswith("linux"):
        for lib in ("/lib/x86_64-linux-gnu/libc.so.6", "/lib/aarch64-linux-gnu/libc.so.6"):
            if Path(lib).exists():
                out = subprocess.run(["nm", "-D", "--defined-only", lib],
                                     capture_output=True, text=True).stdout
                names.update(l.split()[-1].split("@")[0] for l in out.splitlines() if l.strip())
    return names


# Windows CRT names that collide even without a MinGW toolchain to read them
# from (the leading underscore is dropped: Ghidra names are often bare).
WINDOWS_BASELINE = set("""
callnewh control87 controlfp flushall fpclass fpreset get_osfhandle
open_osfhandle lock_file unlock_file onexit CxxFrameHandler
DestructExceptionObject purecall setjmp longjmp exit atexit
""".split())

# Import libraries whose exports the generated code or the toolkit can see.
WINDOWS_LIBS = ("ucrt", "mingwex", "mingw32", "kernel32", "user32", "winmm",
                "d3d11", "dbghelp", "xinput", "ole32")


def windows_target_exports():
    """Exports of the llvm-mingw CRT/system import libs, if a toolchain is found
    (LLVM_MINGW_ROOT, or third_party/llvm-mingw-* next to this script's project)."""
    roots = [os.environ.get("LLVM_MINGW_ROOT", "")]
    roots += sorted(glob.glob(str(Path(__file__).resolve().parent.parent
                                  / "third_party" / "llvm-mingw-*")))
    for root in filter(None, roots):
        nm = Path(root, "bin", "llvm-nm")
        lib = Path(root, "x86_64-w64-mingw32", "lib")
        if not nm.exists() or not lib.is_dir():
            continue
        libs = [str(lib / ("lib%s.a" % n)) for n in WINDOWS_LIBS
                if (lib / ("lib%s.a" % n)).exists()]
        out = subprocess.run([str(nm), "--defined-only", "-j"] + libs,
                             capture_output=True, text=True).stdout
        names = set()
        for line in out.split():
            if line.endswith(":") or line.startswith(("__imp_", ".")):
                continue
            names.add(line)
            names.add(line.lstrip("_"))
        return names
    return set()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    funcs = json.loads(path.read_text())
    reserved = (POSIX_BASELINE | host_libc_exports()
                | WINDOWS_BASELINE | windows_target_exports())

    renamed = []
    for f in funcs:
        name = f.get("name", "")
        if name and not name.startswith("sub_") and name in reserved:
            new = "%s_%08X" % (name, int(f["start"], 16))
            renamed.append((name, new))
            f["name"] = new

    if renamed:
        path.write_text(json.dumps(funcs, indent=2))
    print("host_reserved_names: %d name(s) clashing with a host or target C library renamed%s"
          % (len(renamed), ": " + ", ".join("%s->%s" % r for r in renamed) if renamed else ""))


if __name__ == "__main__":
    main()

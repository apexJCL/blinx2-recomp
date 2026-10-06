#!/usr/bin/env python3
"""Packaging helpers for `blinx2 package` (blinx2.py imports this module):
version, manifest, sums, XBE title check, the staged-tree checks, the macOS
dylib plan and the NSIS file lists. Standard library only, Python 3.9 or
newer. The subcommands below expose the same functions for debugging.

  package_lib.py version   --cat DIR --toolkit DIR --gen DIR --exe FILE
  package_lib.py check-cache CMakeCache.txt [--allow-debug] [--allow-nonstock]
  package_lib.py xbe-title FILE [--expect 0x4D530065]
  package_lib.py stage-game-files SRC DST         (clone or copy, minus exclusions)
  package_lib.py manifest  --root DIR --target T --version V --cat DIR
                           --toolkit DIR --gen DIR --cache FILE
                           [--override NAME]... [--extra JSON] [--files-under SUB]
  package_lib.py dylibs    EXE [--companion NAME=PATH]...   (prints a JSON plan)
  package_lib.py nsis-files DIR                   (prints !define-able blocks)

Nothing here writes outside the paths it is given, and the manifest never
holds a host name or an absolute path: bundles live on the user's machines
only, but their metadata should not say whose machines those are.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import textwrap

PRODUCT = "blinx2-recomp"
# The name the player sees: installer, app, shortcuts, README, messages.
# The one place it is written; blinx2.py renders it into every template.
PRODUCT_NAME = "BLiNX 2"
TITLE_ID = 0x4D530065
SCHEMA = 1
DATA_LAYOUT = 1

# game_files/ entries that are not the dump: the pipeline's XBE analysis and
# any save tree a dev run left there.
GAME_FILES_EXCLUDE = ("default_analysis.json", "UDATA", "TDATA", ".DS_Store")

TARGETS = ("windows-x86_64", "steamos-x86_64-proton", "macos-arm64")


def die(msg):
    print("package_lib: " + msg, file=sys.stderr)
    sys.exit(1)


def sha256_file(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def git(tree, *args):
    return subprocess.run(["git", "-C", tree] + list(args), check=True,
                          stdout=subprocess.PIPE).stdout


# ── version ──────────────────────────────────────────────────────────────

def tree_state(tree):
    """commit, branch, the dirty-path count and a digest of the dirt
    (tracked diff plus untracked, non-ignored files with their contents)."""
    commit = git(tree, "rev-parse", "HEAD").decode().strip()
    branch = git(tree, "rev-parse", "--abbrev-ref", "HEAD").decode().strip()
    porcelain = [l for l in git(tree, "status", "--porcelain").decode().splitlines() if l]
    h = hashlib.sha256()
    if porcelain:
        h.update(git(tree, "diff", "HEAD", "--binary"))
        others = git(tree, "ls-files", "--others", "--exclude-standard", "-z")
        for name in sorted(n for n in others.decode().split("\0") if n):
            h.update(b"\0" + name.encode() + b"\0")
            p = os.path.join(tree, name)
            if os.path.isfile(p) and not os.path.islink(p):
                h.update(sha256_file(p).encode())
    return {"commit": commit, "branch": branch, "dirty": bool(porcelain),
            "dirty_paths": len(porcelain), "_dirt": h.hexdigest() if porcelain else ""}


def gen_digest(gen_dir):
    """The digest bench.sh computes (gen_digest_local): sha256 of the
    `shasum -a 256 -- *` listing, sorted by name. Dotfiles are not in *."""
    names = sorted((n for n in os.listdir(gen_dir)
                    if not n.startswith(".") and os.path.isfile(os.path.join(gen_dir, n))),
                   key=lambda n: n.encode())
    listing = "".join("%s  %s\n" % (sha256_file(os.path.join(gen_dir, n)), n) for n in names)
    return hashlib.sha256(listing.encode()).hexdigest(), len(names)


def format_version(built_utc, cat, toolkit, gen_sha):
    v = "%s-c%s-t%s-g%s" % (built_utc.strftime("%Y%m%d.%H%M"), cat["commit"][:7],
                            toolkit["commit"][:7], gen_sha[:8])
    if cat["dirty"] or toolkit["dirty"]:
        dirt = hashlib.sha256((cat["_dirt"] + ":" + toolkit["_dirt"]).encode()).hexdigest()
        v += "-dirty" + dirt[:8]
    return v


def exe_time(exe):
    return datetime.datetime.fromtimestamp(int(os.stat(exe).st_mtime), datetime.timezone.utc)


def compute_version(cat_dir, tk_dir, gen_dir, exe):
    cat, tk = tree_state(cat_dir), tree_state(tk_dir)
    gsha, _ = gen_digest(gen_dir)
    return format_version(exe_time(exe), cat, tk, gsha)


# ── CMake cache: a packaged build is the stock Release configuration ─────

def read_cache(path):
    vals = {}
    with open(path, errors="replace") as f:
        for line in f:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):[A-Z]+=(.*)$", line.rstrip("\n"))
            if m:
                vals[m.group(1)] = m.group(2)
    return vals


def cache_problems(vals):
    """(debug, nonstock) lists of human-readable reasons."""
    debug, nonstock = [], []
    if vals.get("CMAKE_BUILD_TYPE", "") != "Release":
        debug.append("CMAKE_BUILD_TYPE=%s (want Release)" % vals.get("CMAKE_BUILD_TYPE", ""))
    if vals.get("CAT_GEN_OPT", ""):
        nonstock.append("CAT_GEN_OPT=%s (want empty)" % vals["CAT_GEN_OPT"])
    if vals.get("XBOXRECOMP_ENHANCE", "ON").upper() in ("OFF", "0", "FALSE", "NO"):
        nonstock.append("XBOXRECOMP_ENHANCE=%s (want ON)" % vals["XBOXRECOMP_ENHANCE"])
    return debug, nonstock


def compiler_line(vals, build_dir=None):
    """The compiler's first --version line. A toolchain file's compiler is
    not in the cache, only in CMakeFiles/<cmake version>/CMakeCCompiler.cmake."""
    cc = vals.get("CMAKE_C_COMPILER", "")
    if not cc and build_dir:
        import glob
        for f in sorted(glob.glob(os.path.join(build_dir, "CMakeFiles", "*", "CMakeCCompiler.cmake"))):
            with open(f, errors="replace") as fh:
                m = re.search(r'^set\(CMAKE_C_COMPILER "([^"]+)"\)', fh.read(), re.M)
            if m:
                cc = m.group(1)
    try:
        out = subprocess.run([cc, "--version"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, check=True).stdout.decode()
        return out.splitlines()[0].strip()
    except (OSError, subprocess.CalledProcessError, IndexError):
        return "unknown"


# ── XBE ──────────────────────────────────────────────────────────────────

def xbe_title_id(data):
    """The certificate's title ID. Header: 'XBEH', base address at 0x104,
    certificate VA at 0x118; the certificate is size, time, then title ID."""
    if len(data) < 0x11C or data[:4] != b"XBEH":
        raise ValueError("not an XBE (no XBEH magic)")
    base, = struct.unpack_from("<I", data, 0x104)
    cert, = struct.unpack_from("<I", data, 0x118)
    off = cert - base
    if off < 0 or off + 12 > len(data):
        raise ValueError("certificate address 0x%X outside the header" % cert)
    tid, = struct.unpack_from("<I", data, off + 8)
    return tid


# The XBE builds its media paths from templates ("adx\\%s.adx",
# "voice\\%s.adx", "movie\\%s.sfd") and names kept elsewhere in the image,
# so there is no list of files to compare against. A dump made from a damaged
# or partial copy of the disc lacks some of them and the game plays on in
# silence (missing songs, missing voice lines), which looks like a recomp bug.
MEDIA_DIRS = ("adx", "voice", "movie")


def _name_shape(name):
    """'VC_cd1-1a_QRST_P' -> 'a_a0-0a_a_a': digit runs -> 0, letter runs -> a."""
    return re.sub(r"[A-Za-z]+", "a", re.sub(r"[0-9]+", "0", name))


def _name_family(name):
    return name.split("_", 1)[0].lower()


def xbe_strings(data, lo=3, hi=64):
    """The NUL-terminated name-like strings in an XBE image."""
    pat = rb"(?<=\x00)([A-Za-z0-9_\-!]{%d,%d})\x00" % (lo, hi)
    return sorted({m.group(1).decode("ascii") for m in re.finditer(pat, data)})


def missing_media(xbe_data, game_dir, dirs=MEDIA_DIRS):
    """{dir: [names]} the XBE mentions but the dump lacks. A string counts as
    a file name for dir D when it belongs to a name family (the part before
    the first '_') with at least two files in D, and has the same shape as
    one of them; that keeps format strings, texture and model names out. The
    match is case-insensitive, as on the Xbox. A heuristic: it only warns."""
    strings = xbe_strings(xbe_data)
    out = {}
    for d in dirs:
        path = os.path.join(game_dir, d)
        if not os.path.isdir(path):
            continue
        names = [os.path.splitext(f)[0] for f in os.listdir(path)
                 if not f.startswith(".")]
        have = {n.lower() for n in names}
        shapes = {}
        for n in names:
            if "_" in n:
                shapes.setdefault(_name_family(n), []).append(_name_shape(n))
        fams = {f: set(v) for f, v in shapes.items() if len(v) >= 2}
        miss = [s for s in strings
                if "_" in s and s.lower() not in have
                and _name_shape(s) in fams.get(_name_family(s), ())]
        if miss:
            out[d] = miss
    return out


def missing_media_text(missing):
    """The warning for missing_media's result, or '' when nothing is missing."""
    if not missing:
        return ""
    n = sum(len(v) for v in missing.values())
    lines = ["the dump looks incomplete: the XBE names %d media file%s that "
             "game_files/ lacks" % (n, "" if n == 1 else "s")]
    for d, names in sorted(missing.items()):
        lines.extend(textwrap.wrap(", ".join(names), 76,
                                   initial_indent="  %s/ (%d): " % (d, len(names)),
                                   subsequent_indent="    "))
    lines.append("The game runs, but those songs, voice lines or movies stay silent")
    lines.append("or blank. Extract the disc again (all of it) into game_files/.")
    return "\n".join(lines)


# ── game files ───────────────────────────────────────────────────────────

def game_file_excluded(rel):
    first = rel.replace("\\", "/").split("/")[0]
    return first in GAME_FILES_EXCLUDE or os.path.basename(rel) == ".DS_Store"


def _clonefile():
    """macOS clonefile(2) through ctypes, or None: on APFS a clone takes no
    space, which matters for a dump of several GB."""
    if sys.platform != "darwin":
        return None
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        f = libc.clonefile
        f.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32)
        return f
    except (OSError, AttributeError):
        return None


def copy_file(src, dst, clone=None):
    """Clone where the filesystem can, else a plain copy (other volumes,
    other hosts)."""
    if clone is not None and clone(os.fsencode(src), os.fsencode(dst), 0) == 0:
        return
    shutil.copy2(src, dst)


def stage_game_files(src, dst):
    """Copy the dump without the pipeline's and dev runs' leftovers."""
    src = os.path.realpath(src)
    clone = _clonefile()
    os.makedirs(dst, exist_ok=True)
    n = 0
    for name in sorted(os.listdir(src)):
        if game_file_excluded(name):
            continue
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, copy_function=lambda a, b: copy_file(a, b, clone),
                            ignore=shutil.ignore_patterns(".DS_Store"))
        else:
            copy_file(s, d, clone)
        n += 1
    return n


# ── staged-tree checks ───────────────────────────────────────────────────

# Names Windows cannot create (any extension), and characters it refuses.
# The steamos tar is unpacked on Linux, but the same payload is built on
# Windows hosts too, so every target gets the same rules.
RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9¹²³]|lpt[0-9¹²³])(\..*)?$", re.I)
BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
# Files a POSIX shell or Python reads: a CR breaks `#!/bin/sh\r` and KEY=value.
LF_ONLY = re.compile(r"(\.(sh|py|default|in|toml|env)$|^launch\.env\.default$|^BLiNX2$)")


def name_problem(name):
    """Why Windows cannot hold a file or directory called name, or None."""
    if RESERVED.match(name):
        return "reserved name on Windows"
    if name.endswith((".", " ")):
        return "trailing dot or space"
    if BAD_CHARS.search(name):
        return "character Windows refuses"
    return None


# The icon files game_icon.py writes (the game's title image). The .ico is
# compiled into the exes, never shipped loose; the others belong next to
# the launcher or in the app, never among the game files.
ICON_FILES = ("icon.png", "BLiNX2.icns", "BLiNX2.ico")


def staged_problems(root):
    """Reasons a staged payload must not be packaged."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        for n in dirnames + filenames:
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if os.path.islink(p):
                out.append("%s: symlink" % rel)
            if n in filenames and n in ICON_FILES and (
                    n.endswith(".ico") or rel.startswith("game_files/")):
                out.append("%s: icon file out of place" % rel)
            why = name_problem(n)
            if why:
                out.append("%s: %s" % (rel, why))
            if n in filenames and not rel.startswith("game_files/") and LF_ONLY.search(n):
                with open(p, "rb") as f:
                    if b"\r\n" in f.read():
                        out.append("%s: CRLF line endings" % rel)
    return out


# ── manifest and sums ────────────────────────────────────────────────────

def list_files(root, under=None):
    """Every regular file under root (or root/under), as sorted relative
    POSIX paths."""
    base = os.path.join(root, under) if under else root
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for f in filenames:
            p = os.path.join(dirpath, f)
            if os.path.isfile(p):
                out.append(os.path.relpath(p, root).replace(os.sep, "/"))
    return sorted(out)


def build_manifest(root, target, version, cat, toolkit, gen_sha, gen_files, cache,
                   compiler, overrides=(), extra=None, under=None, built=None):
    files = []
    for rel in list_files(root, under):
        if rel in ("manifest.json", "SHA256SUMS"):
            continue
        p = os.path.join(root, rel)
        files.append({"path": rel, "sha256": sha256_file(p), "size": os.path.getsize(p)})
    m = {
        "schema": SCHEMA,
        "product": PRODUCT,
        "name": PRODUCT_NAME,
        "version": version,
        "target": target,
        "built": (built or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {k: {x: v[x] for x in ("commit", "branch", "dirty", "dirty_paths")}
                    for k, v in (("cat", cat), ("toolkit", toolkit))},
        "gen": {"sha256": gen_sha, "files": gen_files},
        "build": {"type": cache.get("CMAKE_BUILD_TYPE", ""),
                  "enhance": cache.get("XBOXRECOMP_ENHANCE", "ON").upper() not in ("OFF", "0", "FALSE", "NO"),
                  "gen_opt": cache.get("CAT_GEN_OPT", ""),
                  "compiler": compiler,
                  "overrides": list(overrides)},
        "data_layout": DATA_LAYOUT,
        "files": files,
        "notice": "personal use only: contains your own copy of the game and code generated from it; never share it",
    }
    if extra:
        m.update(extra)
    return m


def sums_text(manifest):
    return "".join("%s  %s\n" % (f["sha256"], f["path"]) for f in manifest["files"])


def private_leaks(text, home=None, host=None):
    """Strings a manifest must never carry: absolute paths, $HOME, host name."""
    leaks = []
    home = home if home is not None else os.path.expanduser("~")
    host = host if host is not None else os.uname().nodename.split(".")[0]
    if home and home != "/" and home in text:
        leaks.append("home directory")
    if host and len(host) > 2 and re.search(r"\b%s\b" % re.escape(host), text, re.I):
        leaks.append("host name")
    if re.search(r'"(/Users/|/home/|/var/home/|[A-Za-z]:\\\\)', text):
        leaks.append("absolute path")
    return leaks


# ── macOS dylibs ─────────────────────────────────────────────────────────

SYSTEM_PREFIXES = ("/usr/lib/", "/System/")


def parse_otool(text):
    """otool -L output -> list of install names (the first line names the
    file itself and is skipped)."""
    names = []
    for line in text.splitlines()[1:]:
        m = re.match(r"^\s+(\S.*?) \(compatibility version", line)
        if m:
            names.append(m.group(1))
    return names


def otool_runner(path):
    return subprocess.run(["otool", "-L", path], check=True,
                          stdout=subprocess.PIPE).stdout.decode()


def dylib_plan(exe, companions=(), run=otool_runner, realpath=os.path.realpath):
    """The libraries to bundle: every non-system install name reachable
    from exe, plus companions (libraries loaded with dlopen, NAME=PATH, such
    as sdl2-compat's libSDL3), with their own dependencies. Returns
    {"libs": [{"name", "src"}], "changes": [{"file", "old", "new"}]}, file
    being "@exe" or a bundled lib name."""
    libs = {}            # name -> src realpath
    changes = []
    queue = [("@exe", exe)]
    for spec in companions:
        name, _, path = spec.partition("=")
        if name not in libs:
            libs[name] = realpath(path)
            queue.append((name, path))
    seen = set()
    while queue:
        who, path = queue.pop(0)
        if who in seen:
            continue
        seen.add(who)
        deps = parse_otool(run(path))
        if who != "@exe" and deps:
            deps = deps[1:]   # a dylib lists its own id first
        for dep in deps:
            if dep.startswith(SYSTEM_PREFIXES) or dep.startswith("@"):
                continue
            name = os.path.basename(dep)
            changes.append({"file": who, "old": dep, "new": "@rpath/" + name})
            if name not in libs:
                libs[name] = realpath(dep)
                queue.append((name, dep))
    return {"libs": [{"name": n, "src": s} for n, s in sorted(libs.items())],
            "changes": changes}


# ── NSIS ─────────────────────────────────────────────────────────────────

def nsis_lists(root):
    """The program files (everything but game_files/) as NSIS File and
    Delete lines, so the uninstaller removes exactly what was installed."""
    files = [r for r in list_files(root) if not r.startswith("game_files/")]
    nested = [r for r in files if "/" in r]
    if nested:
        # The installer copies top-level files only; a subdirectory would be
        # silently missing from the install.
        raise ValueError("unexpected payload subdirectory: %s" % ", ".join(nested))
    names = files
    install = "".join('  File "%s"\n' % os.path.join(root, n).replace("$", "$$") for n in names)
    uninstall = "".join('  Delete "$INSTDIR\\%s"\n' % n for n in names)
    return names, install, uninstall


# ── CLI ──────────────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("version")
    for k in ("cat", "toolkit", "gen", "exe"):
        v.add_argument("--" + k, required=True)

    c = sub.add_parser("check-cache")
    c.add_argument("cache")
    c.add_argument("--allow-debug", action="store_true")
    c.add_argument("--allow-nonstock", action="store_true")

    x = sub.add_parser("xbe-title")
    x.add_argument("xbe")
    x.add_argument("--expect", default="0x%08X" % TITLE_ID)

    g = sub.add_parser("stage-game-files")
    g.add_argument("src")
    g.add_argument("dst")

    m = sub.add_parser("manifest")
    for k in ("root", "target", "version", "cat", "toolkit", "gen", "cache"):
        m.add_argument("--" + k, required=True)
    m.add_argument("--override", action="append", default=[])
    m.add_argument("--extra", default=None, help="JSON object merged into the manifest")
    m.add_argument("--files-under", default=None)

    d = sub.add_parser("dylibs")
    d.add_argument("exe")
    d.add_argument("--companion", action="append", default=[])

    n = sub.add_parser("nsis-files")
    n.add_argument("root")
    n.add_argument("--out-install", required=True)
    n.add_argument("--out-uninstall", required=True)

    a = ap.parse_args(argv)

    if a.cmd == "version":
        print(compute_version(a.cat, a.toolkit, a.gen, a.exe))
    elif a.cmd == "check-cache":
        debug, nonstock = cache_problems(read_cache(a.cache))
        bad = ([] if a.allow_debug else debug) + ([] if a.allow_nonstock else nonstock)
        if bad:
            die("not a stock Release build: " + "; ".join(bad)
                + " (--allow-debug / --allow-nonstock to package anyway)")
        for r in (debug if a.allow_debug else []) + (nonstock if a.allow_nonstock else []):
            print(r)
    elif a.cmd == "xbe-title":
        try:
            with open(a.xbe, "rb") as f:
                tid = xbe_title_id(f.read(0x10000))
        except (OSError, ValueError) as e:
            die("%s: %s" % (a.xbe, e))
        print("0x%08X" % tid)
        if tid != int(a.expect, 16):
            die("%s: title ID 0x%08X is not %s (%s)" % (a.xbe, tid, PRODUCT_NAME, a.expect))
    elif a.cmd == "stage-game-files":
        print(stage_game_files(a.src, a.dst))
    elif a.cmd == "manifest":
        if a.target not in TARGETS:
            die("unknown target %s" % a.target)
        cat, tk = tree_state(a.cat), tree_state(a.toolkit)
        gsha, gn = gen_digest(a.gen)
        cache = read_cache(a.cache)
        extra = json.loads(a.extra) if a.extra else None
        man = build_manifest(a.root, a.target, a.version, cat, tk, gsha, gn, cache,
                             compiler_line(cache), a.override, extra, a.files_under)
        text = json.dumps(man, indent=2) + "\n"
        leaks = private_leaks(text)
        if leaks:
            die("manifest would carry private data: " + ", ".join(leaks))
        with open(os.path.join(a.root, "manifest.json"), "w") as f:
            f.write(text)
        with open(os.path.join(a.root, "SHA256SUMS"), "w") as f:
            f.write(sums_text(man))
        print("%d files" % len(man["files"]))
    elif a.cmd == "dylibs":
        print(json.dumps(dylib_plan(a.exe, a.companion), indent=1))
    elif a.cmd == "nsis-files":
        names, inst, uninst = nsis_lists(a.root)
        with open(a.out_install, "w") as f:
            f.write(inst)
        with open(a.out_uninstall, "w") as f:
            f.write(uninst)
        print("\n".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())

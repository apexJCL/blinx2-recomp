#!/usr/bin/env python3
"""blinx2: set up, generate, build and package BLiNX 2 on this host.

Commands:
  blinx2                                package for this computer (macos on a
                                        Mac, steamos on Linux, windows on
                                        Windows): sets up, generates and builds
                                        whatever is missing or out of date
  blinx2 package windows|steamos|macos  the same, for a given target: dist/
  blinx2 doctor                         what this host has, and what it can package
  blinx2 setup [--dev] [--no-toolkit]   fetch the pinned toolchain into this tree

Developer commands:
  blinx2 analyze | recomp | all         the pipeline (parse disasm funcid abi names
                                        recomp; ghidra is optional)
  blinx2 build [windows|macos]          compile build-win/ or build/
  blinx2 pins refresh                   maintainers: re-pin the downloads

`blinx2 <command> --help` for the options. Windows: `blinx2.cmd`, or
`py -3 blinx2.py`. Docs: docs/packaging.md.

Standard library only, Python 3.9 or newer. Every host-specific step goes
through Python (hashlib, shutil, urllib, tarfile, zipfile, platform), so the
same commands work on Windows, Linux and macOS; only the macOS target uses
Apple's tools (otool, install_name_tool, codesign, hdiutil).
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(ROOT, "src", "recomp", "gen")
REGEN_MARKER = os.path.join(ROOT, "src", "recomp", ".gen-regenerating")
VENV = os.path.join(ROOT, ".venv")
THIRD_PARTY = os.path.join(ROOT, "third_party")
CLT = "/Library/Developer/CommandLineTools"


class CliError(Exception):
    pass


COMMANDS = []   # (name, help, configure(parser), func(args)), in --help order


def command(name, help, configure=None):
    def wrap(func):
        COMMANDS.append((name, help, configure, func))
        return func
    return wrap


# The progress view (scripts/progress.py) while `package` runs, else None:
# say, step and run go through it, and child output goes to build-logs/.
VIEW = None
LOGS = os.path.join(ROOT, "build-logs")


def say(msg=""):
    if VIEW:
        VIEW.say(msg)
    else:
        print(msg, flush=True)


def step(msg):
    if VIEW:
        VIEW.begin(msg)
        return
    say()
    say("== %s ==" % msg)


def mark(name):
    """The plan step now running: '[3/4] build' at the head of the view."""
    if VIEW and name in VIEW.plan:
        VIEW.set_stage("[%d/%d] %s" % (VIEW.plan.index(name) + 1, len(VIEW.plan), name))


def progress_lib():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import progress
    return progress


# ── host ─────────────────────────────────────────────────────────────────

def host_os(system=None):
    s = (system or platform.system()).lower()
    if s.startswith("win") or s.startswith("cygwin") or s.startswith("msys"):
        return "windows"
    if s == "darwin":
        return "macos"
    if s == "linux":
        return "linux"
    return s


def host_arch(machine=None):
    m = (machine or platform.machine()).lower()
    if m in ("x86_64", "amd64", "x64"):
        return "x86_64"
    if m in ("arm64", "aarch64", "armv8", "armv8l"):
        return "aarch64"
    return m


def exe_suffix(os_name=None):
    return ".exe" if (os_name or host_os()) == "windows" else ""


# ── paths ────────────────────────────────────────────────────────────────

def toolkit_dir(env=None):
    """$XBOXRECOMP_DIR, else external/xboxrecomp, else ../xboxrecomp: the
    order README.md, CMakeLists.txt and bench.sh use."""
    env = os.environ if env is None else env
    if env.get("XBOXRECOMP_DIR"):
        return os.path.abspath(env["XBOXRECOMP_DIR"])
    ext = os.path.join(ROOT, "external", "xboxrecomp")
    if os.path.isdir(ext):
        return ext
    return os.path.abspath(os.path.join(ROOT, "..", "xboxrecomp"))


def venv_bin(venv=None, os_name=None):
    return os.path.join(venv or VENV, "Scripts" if (os_name or host_os()) == "windows" else "bin")


def venv_python(venv=None, os_name=None):
    return os.path.join(venv_bin(venv, os_name), "python" + exe_suffix(os_name))


def tool_python(env=None):
    """The interpreter that runs the toolkit's tools: XBOXRECOMP_PYTHON,
    else this project's venv (made by setup), else a toolkit venv a
    developer already has (tools/macos/setup.sh)."""
    env = os.environ if env is None else env
    if env.get("XBOXRECOMP_PYTHON"):
        return env["XBOXRECOMP_PYTHON"]
    for cand in (venv_python(), venv_python(os.path.join(toolkit_dir(env), ".venv"))):
        if os.path.isfile(cand):
            return cand
    raise CliError("no Python environment for the toolkit's tools: run 'blinx2 setup' "
                   "(or set XBOXRECOMP_PYTHON)")


def build_env(env=None, os_name=None):
    """The environment for CMake and the compilers: the venv's tools first
    on PATH, and on macOS the Command Line Tools as the developer dir
    (the selected Xcode's linker may not read the newer SDK)."""
    e = dict(os.environ if env is None else env)
    e.setdefault("NINJA_STATUS", "[%f/%t] ")    # what the progress view parses
    b = venv_bin(os_name=os_name)
    if os.path.isdir(b):
        e["PATH"] = b + os.pathsep + e.get("PATH", "")
    if (os_name or host_os()) == "macos" and not e.get("DEVELOPER_DIR") and os.path.isdir(CLT):
        e["DEVELOPER_DIR"] = CLT
    return e


def run(cmd, cwd=None, env=None, check=True, parser=None):
    """Argument lists only, never a shell string: paths with spaces stay
    one argument on every host. Under the progress view the output goes to
    the step's log and the parser (by default chosen from the command)."""
    if VIEW:
        rc = progress_lib().run_step(VIEW, cmd, cwd, env, parser, VIEW.verbose)
    else:
        rc = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env).returncode
    if check and rc != 0:
        raise CliError("%s failed (exit %d)" % (os.path.basename(str(cmd[0])), rc))
    return rc


def require(path, stage):
    if not os.path.exists(path):
        raise CliError("missing %s: run the '%s' stage first" % (os.path.relpath(path, ROOT), stage))


def refuse_while_regenerating():
    if os.path.exists(REGEN_MARKER):
        raise CliError("gen/ is being regenerated (or the last recomp failed): wait, "
                       "or run 'blinx2 recomp' again")


# ── build ────────────────────────────────────────────────────────────────

def read_env_file(path):
    """KEY=value lines of a tracked .env file (config/toolchain.env)."""
    vals = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


def mingw_tag(env=None):
    env = os.environ if env is None else env
    return env.get("LLVM_MINGW_TAG") or read_env_file(
        os.path.join(ROOT, "config", "toolchain.env"))["LLVM_MINGW_TAG"]


def mingw_root(env=None):
    """LLVM_MINGW_ROOT, else the pinned tag under third_party/, else ''
    (the toolchain file then searches PATH)."""
    env = os.environ if env is None else env
    if env.get("LLVM_MINGW_ROOT"):
        return os.path.abspath(env["LLVM_MINGW_ROOT"])
    prefix = "llvm-mingw-%s-" % mingw_tag(env)
    if os.path.isdir(THIRD_PARTY):
        cands = sorted(d for d in os.listdir(THIRD_PARTY)
                       if d.startswith(prefix) and not d.endswith(".partial")
                       and os.path.isdir(os.path.join(THIRD_PARTY, d)))
        if cands:
            return os.path.join(THIRD_PARTY, cands[-1])
    if shutil.which("x86_64-w64-mingw32-clang"):
        return ""
    raise CliError("no llvm-mingw: run 'blinx2 setup' (or set LLVM_MINGW_ROOT)")


def build_tools(system_tools, os_name=None):
    """(cmake, ninja or None): the venv's pip wheels, or with --system-tools
    the host's. Ninja is required on Windows (no make there, and CMake's
    default generator would be Visual Studio)."""
    os_name = os_name or host_os()
    if system_tools:
        cmake, ninja = shutil.which("cmake"), shutil.which("ninja")
        if not cmake:
            raise CliError("--system-tools: no cmake on PATH")
    else:
        b = venv_bin(os_name=os_name)
        cmake = os.path.join(b, "cmake" + exe_suffix(os_name))
        ninja = os.path.join(b, "ninja" + exe_suffix(os_name))
        if not os.path.isfile(cmake):
            raise CliError("no CMake in .venv: run 'blinx2 setup' (or pass --system-tools)")
        ninja = ninja if os.path.isfile(ninja) else None
    if not ninja and os_name == "windows":
        raise CliError("Ninja is required on Windows: run 'blinx2 setup'")
    return cmake, ninja


def default_build_target(os_name=None):
    return "macos" if (os_name or host_os()) == "macos" else "windows"


def check_build_target(target, os_name=None):
    os_name = os_name or host_os()
    if target == "macos" and os_name != "macos":
        raise CliError("the macos target needs a macOS host (Apple clang, codesign, "
                       "hdiutil); this host can build: windows (and package windows, steamos)")


def build_dir(target):
    return os.path.join(ROOT, "build-win" if target == "windows" else "build")


def pkg_build_dir(target):
    """package's own build tree: a developer's build/ and build-win/ (with
    whatever options they keep there) are never read or changed by it."""
    return os.path.join(ROOT, "build-pkg-win" if target == "windows" else "build-pkg-macos")


# The stock options, passed on every packaging configure so a cache can not
# keep a non-stock value from an earlier run (CAT_GEN_OPT's default is empty).
STOCK_CMAKE_ARGS = ("-DCMAKE_BUILD_TYPE=Release", "-DXBOXRECOMP_ENHANCE=ON", "-UCAT_GEN_OPT")


def build(target, cmake_args=(), system_tools=False, bdir=None, stock=False,
          reconfigure=False):
    """Configure once (the generator is fixed by the first configure; an
    existing tree keeps its own), then build incrementally. stock (package's
    own tree): configure on every run with STOCK_CMAKE_ARGS; reconfigure
    starts that tree's cache afresh."""
    check_build_target(target)
    require(os.path.join(GEN, "recomp_funcs.h"), "recomp")
    refuse_while_regenerating()
    cmake, ninja = build_tools(system_tools)
    env = build_env()
    bdir = bdir or build_dir(target)
    tk = toolkit_dir()
    if not os.path.isfile(os.path.join(tk, "CMakeLists.txt")):
        raise CliError("no toolkit at %s: run 'blinx2 setup' or set XBOXRECOMP_DIR" % tk)
    if reconfigure:
        if os.path.isfile(os.path.join(bdir, "CMakeCache.txt")):
            os.remove(os.path.join(bdir, "CMakeCache.txt"))
        shutil.rmtree(os.path.join(bdir, "CMakeFiles"), ignore_errors=True)
    if stock:
        cmake_args = list(STOCK_CMAKE_ARGS) + list(cmake_args)
    if stock or not os.path.isfile(os.path.join(bdir, "CMakeCache.txt")):
        cfg = [cmake, "-S", ROOT, "-B", bdir, "-DCMAKE_BUILD_TYPE=Release",
               "-DXBOXRECOMP_DIR=" + tk]
        if ninja:
            cfg += ["-G", "Ninja", "-DCMAKE_MAKE_PROGRAM=" + ninja]
        if target == "windows":
            cfg += ["-DCMAKE_TOOLCHAIN_FILE=" + os.path.join(ROOT, "cmake", "llvm-mingw-x86_64.cmake"),
                    "-DLLVM_MINGW_ROOT=" + mingw_root()]
        run(cfg + list(cmake_args), env=env)
    elif cmake_args:
        run([cmake, "-B", bdir] + list(cmake_args), env=env)
    run([cmake, "--build", bdir, "--config", "Release", "-j", str(os.cpu_count() or 4)], env=env)
    exe = os.path.join(bdir, "cat_recomp.exe" if target == "windows" else "cat_recomp")
    if not os.path.isfile(exe):
        raise CliError("the build finished but %s is missing" % exe)
    return exe


def _cfg_build(p):
    p.add_argument("target", nargs="?", choices=("windows", "macos"),
                   help="default: macos on a macOS host, windows elsewhere")
    p.add_argument("--system-tools", action="store_true",
                   help="use the host's cmake and ninja instead of the venv's")
    p.set_defaults(passthrough="extra CMake arguments, e.g. -DCAT_GEN_OPT=-O1")


@command("build", "compile the executable: build-win/ (windows) or build/ (macos)", _cfg_build)
def cmd_build(a):
    target = a.target or default_build_target()
    args = [x for x in a.extra if x != "--"]
    step("build %s" % target)
    say("built %s" % build(target, args, a.system_tools))


# ── pipeline stages (were scripts/pipeline.sh) ───────────────────────────
#
# Every intermediate lives in this project, not in the toolkit clone, whose
# tools otherwise default to paths under xboxrecomp/tools/*/output. The
# stages and their order follow the toolkit's docs/GETTING_STARTED.md,
# Steps 2-7.

GAME_FILES = os.path.join(ROOT, "game_files")
XBE = os.path.join(GAME_FILES, "default.xbe")
ANALYSIS_JSON = os.path.join(ROOT, "game_files", "default_analysis.json")
OUT = os.path.join(ROOT, "analysis")
SEEDS = os.path.join(ROOT, "config", "seed_functions.json")
ICALL_SEEDS = os.path.join(OUT, "icall_seeds.json")
GAME_NAME = os.path.basename(ROOT)
# Code outside .text: the XDK library sections. --text-only stays, because
# the XBE also flags ~60 model/motion data sections (DOLBY onwards)
# executable and sweeping those yields phantom functions. See openspec
# change recomp-coverage.
DISASM_EXTRA_SECTIONS = "D3D,D3DX,XGRPH,DSOUND,PSFD_I,PSFD_B,PSFD_P,PSFD00,SRCADV,SRCED,SRCAC,XPP"


def split_size():
    return os.environ.get("SPLIT", "250")   # functions per generated file


def tool_cmd(name, *args):
    """One toolkit tool run, as data: ("tool", module, args). The stage
    functions below return lists of these so the generation key can hash
    exactly what a stage would run (gen_key) and run_cmds can run it."""
    return ("tool", name, [str(x) for x in args])


def py_cmd(script, *args):
    """A script run with the tools' Python: ("py", script, args)."""
    return ("py", script, [str(x) for x in args])


def run_cmds(cmds):
    tk = toolkit_dir()
    if not os.path.isdir(os.path.join(tk, "tools")):
        raise CliError("no toolkit at %s: run 'blinx2 setup' or set XBOXRECOMP_DIR" % tk)
    for kind, what, args in cmds:
        if kind == "tool":
            run([tool_python(), "-m", "tools." + what] + args, cwd=tk)
        else:
            run([tool_python(), what] + args)


def icall_db():
    """The toolkit's icall_feedback database (gitignored there), or ICALL_DB."""
    return os.environ.get("ICALL_DB") or os.path.join(
        toolkit_dir(), "tools", "recomp", "output", "icall_targets.json")


def parse_cmds(extra=()):
    return [tool_cmd("xbe_parser", XBE, "--json", ANALYSIS_JSON, *extra)]


def disasm_cmds(extra=()):
    """Indirect-call targets measured at runtime: the hand-kept list, plus
    the toolkit's icall_feedback database once one exists. The database is
    never seeded directly: it holds targets that are not function starts,
    and seeding those split real functions (toolkit
    docs/technical/indirect-calls.md). The filtered seed file is
    regenerated from it on every disasm, decoding each target against the
    XBE."""
    cmds = []
    seeds = ["--seed-functions", SEEDS]
    if os.path.isfile(icall_db()):
        cmds.append(tool_cmd("recomp.icall_feedback", "--db", icall_db(), "seeds",
                             "--out", ICALL_SEEDS, "--xbe", XBE))
        seeds += ["--seed-functions", ICALL_SEEDS]
    cmds.append(tool_cmd("disasm", XBE, "--analysis-json", ANALYSIS_JSON,
                         "-o", os.path.join(OUT, "disasm"), "--text-only",
                         "--extra-sections", DISASM_EXTRA_SECTIONS, *(seeds + ["-v"] + list(extra))))
    return cmds


def funcid_cmds(extra=()):
    d = os.path.join(OUT, "disasm")
    return [tool_cmd("func_id", XBE, "--functions", os.path.join(d, "functions.json"),
                     "--strings", os.path.join(d, "strings.json"),
                     "--xrefs", os.path.join(d, "xrefs.json"),
                     "-o", os.path.join(OUT, "func_id"), "-v", *extra)]


def abi_cmds(extra=()):
    return [tool_cmd("abi_analysis", XBE, "--disasm-dir", os.path.join(OUT, "disasm"),
                     "--func-id-dir", os.path.join(OUT, "func_id"),
                     "--output-dir", os.path.join(OUT, "abi"), "-v", *extra)]


GHIDRA_EXPORT = os.path.join(OUT, "ghidra", "export", "functions.json")
HOST_RESERVED = os.path.join(ROOT, "scripts", "host_reserved_names.py")
RECOMP_MANUAL = os.path.join(ROOT, "src", "recomp_manual.c")


def names_cmds(extra=()):
    funcs = os.path.join(OUT, "disasm", "functions.json")
    # merge_names only reserves ISO C names; a recovered "read" or "write"
    # would replace libc's for the whole executable off Windows.
    return [py_cmd(os.path.join(toolkit_dir(), "tools", "ghidra_naming", "merge_names.py"),
                   "--export-dir", os.path.dirname(GHIDRA_EXPORT),
                   "--out", os.path.join(OUT, "ghidra", "ghidra_names.json"),
                   "--functions-json", funcs, "--apply", *extra),
            py_cmd(HOST_RESERVED, funcs)]


def recomp_cmds(extra=()):
    # --exclude-manual: functions src/recomp_manual.c defines by hand are
    # declared in gen/, not emitted.
    return [tool_cmd("recomp", XBE, "--all", "--split", split_size(), "--gen-dir", GEN,
                     "--exclude-manual", RECOMP_MANUAL,
                     "--game-name", GAME_NAME, "--disasm-dir", os.path.join(OUT, "disasm"),
                     "--func-id-dir", os.path.join(OUT, "func_id"),
                     "--abi-dir", os.path.join(OUT, "abi"),
                     "-o", os.path.join(OUT, "recomp"), *extra)]


def stage_parse(extra=()):
    step("parse")
    begin_stage("parse", extra)
    require(XBE, "(dump the disc into game_files/)")
    run_cmds(parse_cmds(extra))


def stage_disasm(extra=()):
    step("disasm")
    begin_stage("disasm", extra)
    require(ANALYSIS_JSON, "parse")
    if os.path.isfile(icall_db()):
        os.makedirs(OUT, exist_ok=True)
    run_cmds(disasm_cmds(extra))


def stage_funcid(extra=()):
    step("funcid")
    begin_stage("funcid", extra)
    require(os.path.join(OUT, "disasm", "functions.json"), "disasm")
    run_cmds(funcid_cmds(extra))


def stage_abi(extra=()):
    step("abi")
    begin_stage("abi", extra)
    require(os.path.join(OUT, "func_id"), "funcid")
    run_cmds(abi_cmds(extra))


def ghidra_home():
    if os.environ.get("GHIDRA_HOME"):
        return os.environ["GHIDRA_HOME"]
    if host_os() == "macos" and shutil.which("brew"):
        r = subprocess.run(["brew", "--prefix", "ghidra"], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            return os.path.join(r.stdout.decode().strip(), "libexec")
    return ""


def stage_ghidra(extra=()):
    """Optional: better function names. Ghidra 12 ships no Jython, so the
    toolkit's export script runs under PyGhidra, from a Python 3.13 venv at
    .venv-ghidra (JPype has no 3.14 wheels yet)."""
    step("ghidra")
    # Its extras are not recorded: the export they shape is hashed into the
    # key as an input, so recording them too would keep the key stale forever.
    begin_stage("ghidra")
    require(XBE, "(dump the disc into game_files/)")
    home = ghidra_home()
    headless = os.path.join(home, "support", "analyzeHeadless")
    if not home or not os.path.exists(headless):
        raise CliError("no Ghidra at %r: set GHIDRA_HOME (the ghidra stage is optional)" % home)
    gpy = venv_python(os.path.join(ROOT, ".venv-ghidra"))
    if not os.path.isfile(gpy):
        raise CliError("no %s: see README (PyGhidra venv)" % gpy)
    g = os.path.join(OUT, "ghidra")
    src = os.path.join(toolkit_dir(), "tools", "ghidra_naming")
    for d in ("work", "project", "export", "scripts"):
        os.makedirs(os.path.join(g, d), exist_ok=True)
    # Same scripts as upstream; only the runtime tag changes.
    shutil.copy2(os.path.join(src, "ghidra_scripts", "SetAnalysisOptions.java"),
                 os.path.join(g, "scripts"))
    with open(os.path.join(src, "ghidra_scripts", "ExportXbeNames.py")) as f:
        text = f.read()
    text = "\n".join("# @runtime PyGhidra" if l == "# @runtime Jython" else l
                     for l in text.split("\n"))
    with open(os.path.join(g, "scripts", "ExportXbeNames.py"), "w", newline="\n") as f:
        f.write(text)
    run([tool_python(), os.path.join(src, "extract_for_ghidra.py"), XBE,
         "--out-dir", os.path.join(g, "work")])
    # Flags mirror tools/ghidra_naming/run_ghidra.sh, which only drives the
    # Windows .bat. No -analysisTimeoutPerFile: 0 there means zero seconds.
    run([gpy, os.path.join(home, "Ghidra", "Features", "PyGhidra", "support", "pyghidra_launcher.py"),
         home, "-H", os.path.join(g, "project"), GAME_NAME,
         "-import", os.path.join(g, "work", "xbe_flat.bin"), "-overwrite",
         "-loader", "BinaryLoader", "-loader-baseAddr", "0x10000",
         "-processor", "x86:LE:32:default", "-cspec", "windows",
         "-scriptPath", os.path.join(g, "scripts"),
         "-preScript", "SetAnalysisOptions.java",
         "-postScript", "ExportXbeNames.py", os.path.join(g, "export"), "nodecompile"] + list(extra))
    stage_names()


def stage_names(extra=()):
    step("names")
    begin_stage("names", extra)
    require(GHIDRA_EXPORT, "ghidra")
    require(os.path.join(OUT, "disasm", "functions.json"), "disasm")
    run_cmds(names_cmds(extra))


def maybe_names():
    if os.path.isfile(GHIDRA_EXPORT):
        stage_names()


def stage_recomp(extra=()):
    """gen/ is half-written while this runs; bench.sh sync and the build
    refuse while the marker exists. It is removed only on success, so a
    failed run stays locked. The generation key is written last."""
    step("recomp")
    begin_stage("recomp", extra)
    # recomp only warns when this is missing, then guesses cdecl for everything.
    require(os.path.join(OUT, "abi", "abi_functions.json"), "abi")
    os.makedirs(os.path.dirname(REGEN_MARKER), exist_ok=True)
    open(REGEN_MARKER, "a").close()
    run_cmds(recomp_cmds(extra))
    os.remove(REGEN_MARKER)
    write_gen_key()


# ── generation key ───────────────────────────────────────────────────────
#
# What gen/ was generated from, so `package` regenerates only when needed:
# the XBE, the toolkit's tools, every project file a stage reads, and the
# exact commands the stages run (with ROOT and the toolkit as placeholders,
# so a stage change stales gen/ without a constant to bump). Every stage
# deletes the key before it runs and records its extra arguments; recomp
# writes the key on success. A developer who reruns a stage with other
# arguments has therefore always invalidated it.

GEN_KEY = os.path.join(ROOT, "src", "recomp", "gen.key.json")
STAGE_EXTRAS = os.path.join(OUT, "stage-extras.json")
GEN_KEY_VERSION = 1


def _load_json(path, default):
    import json
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, obj):
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="\n") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def begin_stage(name, extra=()):
    """Invalidate the key and record this stage's extra arguments."""
    if os.path.exists(GEN_KEY):
        os.remove(GEN_KEY)
    extras = _load_json(STAGE_EXTRAS, {})
    if list(extra):
        extras[name] = [str(x) for x in extra]
    else:
        extras.pop(name, None)
    if extras or os.path.exists(STAGE_EXTRAS):
        _write_json(STAGE_EXTRAS, extras)


def reset_stage_extras():
    """Forget the extras of earlier hand-run stages. The package regenerate
    runs every stage plain, so what they recorded no longer describes gen/."""
    if os.path.exists(STAGE_EXTRAS):
        os.remove(STAGE_EXTRAS)


def _placeholders(text):
    for path, tag in ((toolkit_dir(), "$TK"), (ROOT, "$ROOT")):
        text = text.replace(path, tag)
    return text.replace("\\", "/")


def gen_inputs():
    """{path with placeholders: sha256 | 'absent'}: every file outside gen/
    the stages read that the pipeline does not produce itself."""
    files = [SEEDS, icall_db(), RECOMP_MANUAL, HOST_RESERVED, GHIDRA_EXPORT]
    return {_placeholders(p): (sha256_path(p) if os.path.isfile(p) else "absent") for p in files}


def stage_argv():
    """The commands a fresh `analyze` + `recomp` runs, with placeholders."""
    import json
    cmds = parse_cmds() + disasm_cmds() + funcid_cmds() + abi_cmds()
    if os.path.isfile(GHIDRA_EXPORT):
        cmds += names_cmds()
    cmds += recomp_cmds()
    return _placeholders(json.dumps(cmds))


def toolkit_state():
    """The toolkit commit, plus a hash of uncommitted and untracked changes
    under tools/ (runtime-only toolkit edits do not stale gen/)."""
    import hashlib
    tk = toolkit_dir()

    def git(*args):
        r = subprocess.run(["git", "-C", tk] + list(args), stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL)
        return r.stdout if r.returncode == 0 else b""
    head = git("rev-parse", "HEAD").decode().strip() or "unknown"
    h = hashlib.sha256(git("diff", "HEAD", "--", "tools"))
    for rel in sorted(git("ls-files", "--others", "--exclude-standard", "--", "tools")
                      .decode().splitlines()):
        p = os.path.join(tk, rel)
        if os.path.isfile(p):
            h.update(rel.encode() + b"\0" + sha256_path(p).encode())
    dirty = h.hexdigest()
    empty = hashlib.sha256(b"").hexdigest()
    return head if dirty == empty else "%s-dirty%s" % (head, dirty[:12])


def gen_key(extra=None):
    import hashlib
    return {"version": GEN_KEY_VERSION,
            "xbe_sha256": sha256_path(XBE) if os.path.isfile(XBE) else "absent",
            "toolkit": toolkit_state(),
            "inputs": gen_inputs(),
            "argv": hashlib.sha256(stage_argv().encode()).hexdigest(),
            "extra": _load_json(STAGE_EXTRAS, {}) if extra is None else extra,
            "ghidra": os.path.isfile(GHIDRA_EXPORT)}


def write_gen_key():
    _write_json(GEN_KEY, gen_key())


GEN_KEY_FIELD_NAMES = {"version": "key format changed", "xbe_sha256": "the XBE changed",
                       "toolkit": "toolkit changed", "argv": "stage commands changed",
                       "extra": "a stage ran with extra arguments",
                       "ghidra": "Ghidra export appeared or went"}


def gen_stale_reasons():
    """[] when gen/ is fresh for packaging, else why not, field by field."""
    if os.path.exists(REGEN_MARKER):
        return ["the last recomp did not finish"]
    if not os.path.isfile(os.path.join(GEN, "recomp_funcs.h")):
        return ["no gen/"]
    rec = _load_json(GEN_KEY, None)
    if not isinstance(rec, dict):
        return ["no key"]
    now = gen_key(extra={})
    why = []
    for k, v in now.items():
        if k == "inputs":
            old = rec.get("inputs") or {}
            why += ["%s changed" % p.replace("$ROOT/", "").replace("$TK/", "toolkit:")
                    for p in sorted(set(v) | set(old)) if v.get(p) != old.get(p)]
        elif rec.get(k) != v:
            why.append(GEN_KEY_FIELD_NAMES.get(k, k))
    return why


STAGES = (("parse", stage_parse, "XBE headers, sections, kernel imports -> game_files/default_analysis.json"),
          ("disasm", stage_disasm, "find functions, build xrefs -> analysis/disasm/"),
          ("funcid", stage_funcid, "classify CRT / XDK / game functions -> analysis/func_id/"),
          ("abi", stage_abi, "recover calling conventions -> analysis/abi/"),
          ("ghidra", stage_ghidra, "optional: headless Ghidra names (slow, cached) -> analysis/ghidra/"),
          ("names", stage_names, "write Ghidra's names into functions.json"),
          ("recomp", stage_recomp, "lift x86 to C -> src/recomp/gen/"))


def _stage_cmd(fn):
    def cmd(a):
        fn(a.extra)
    return cmd


def _cfg_stage(p):
    p.set_defaults(passthrough="extra arguments for the stage's tool")


for _name, _fn, _help in STAGES:
    command(_name, _help, _cfg_stage)(_stage_cmd(_fn))


def _cfg_all(p):
    p.add_argument("--system-tools", action="store_true",
                   help="all: use the host's cmake and ninja instead of the venv's")


@command("analyze", "parse, disasm, funcid, abi, then names if a Ghidra export exists")
def cmd_analyze(a):
    stage_parse(); stage_disasm(); stage_funcid(); stage_abi(); maybe_names()


@command("all", "analyze, recomp, then build for this host's default target", _cfg_all)
def cmd_all(a):
    cmd_analyze(a)
    stage_recomp()
    step("build")
    build(default_build_target(), (), a.system_tools)


# ── setup, doctor and pins ───────────────────────────────────────────────

PINS = os.path.join(ROOT, "config", "setup-pins.json")
REQS = os.path.join(ROOT, "config", "requirements-setup.txt")
REQS_DEV = os.path.join(ROOT, "config", "requirements-dev.txt")
TOOLKIT_PIN_MARK = ".blinx2-pin"

# The llvm-mingw asset for each host, by OS and arch.
MINGW_ASSETS = {
    ("windows", "x86_64"): "llvm-mingw-{tag}-ucrt-x86_64.zip",
    ("windows", "aarch64"): "llvm-mingw-{tag}-ucrt-aarch64.zip",
    ("linux", "x86_64"): "llvm-mingw-{tag}-ucrt-ubuntu-22.04-x86_64.tar.xz",
    ("linux", "aarch64"): "llvm-mingw-{tag}-ucrt-ubuntu-22.04-aarch64.tar.xz",
    ("macos", "x86_64"): "llvm-mingw-{tag}-ucrt-macos-universal.tar.xz",
    ("macos", "aarch64"): "llvm-mingw-{tag}-ucrt-macos-universal.tar.xz",
}

MAKENSIS_HINT = {
    "macos": "brew install makensis",
    "debian": "sudo apt install nsis",
    "fedora": "sudo dnf install mingw32-nsis",
    "arch": "sudo pacman -S nsis   (or the AUR package)",
    "immutable": ("in a toolbox or distrobox: distrobox create -n blinx2-build -i fedora:42, "
                  "then distrobox enter blinx2-build -- sudo dnf install -y mingw32-nsis, "
                  "and run 'blinx2 package windows' inside the box"),
}


def load_pins(path=PINS):
    import json
    with open(path) as f:
        return json.load(f)


def mingw_asset_name(tag, os_name=None, arch=None):
    key = (os_name or host_os(), arch or host_arch())
    if key not in MINGW_ASSETS:
        raise CliError("no llvm-mingw build for %s %s" % key)
    return MINGW_ASSETS[key].format(tag=tag)


def mingw_dir_for(asset):
    """third_party/<asset without its archive extension>."""
    for ext in (".tar.xz", ".zip"):
        if asset.endswith(ext):
            return os.path.join(THIRD_PARTY, asset[:-len(ext)])
    raise CliError("unknown archive type: %s" % asset)


def sha256_path(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def download(url, dest, want_sha256, want_size=None):
    """Fetch to dest.part, check the pinned sha256, then rename. A mismatch
    deletes the download: nothing unpinned is ever unpacked or run."""
    import urllib.request
    part = dest + ".part"
    say("fetching %s" % url)
    req = urllib.request.Request(url, headers={"User-Agent": "blinx2-setup"})
    with urllib.request.urlopen(req) as r, open(part, "wb") as f:
        hdr = getattr(r, "headers", None)
        total = (int(hdr.get("Content-Length") or 0) if hdr else 0) or want_size or 0
        done = 0
        for chunk in iter(lambda: r.read(1 << 16), b""):
            f.write(chunk)
            done += len(chunk)
            if VIEW and total:
                VIEW.progress(done >> 20, max(1, total >> 20))    # MiB
    got = sha256_path(part)
    if got != want_sha256 or (want_size and os.path.getsize(part) != want_size):
        os.remove(part)
        raise CliError("%s: checksum mismatch (got %s, pinned %s); nothing was unpacked"
                       % (os.path.basename(dest), got, want_sha256))
    os.replace(part, dest)
    say("sha256 verified: %s" % got)


def _member_ok(name, linkname=None):
    """No absolute paths, no '..', no link leaving the tree (Python < 3.12
    has no tarfile extraction filter to do this for us)."""
    for n in (name,) + ((linkname,) if linkname else ()):
        n = n.replace("\\", "/")
        if n.startswith("/") or (len(n) > 1 and n[1] == ":"):
            return False
        if ".." in n.split("/"):
            return False
    return True


def check_archive_members(members):
    """members: (name, linkname or None, is_link_relative_to_member_dir)."""
    bad = [m[0] for m in members if not _member_ok(m[0], None)]
    for name, link, rel in members:
        if link is None:
            continue
        target = os.path.normpath(os.path.join(os.path.dirname(name), link)) if rel else link
        if not _member_ok(target.replace(os.sep, "/")):
            bad.append("%s -> %s" % (name, link))
    if bad:
        raise CliError("archive has unsafe members: %s" % ", ".join(bad[:5]))


def extract(archive, dest, strip=1):
    """Unpack into dest, dropping the archive's top folder (strip=1)."""
    import tarfile
    import zipfile
    os.makedirs(dest, exist_ok=True)
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            check_archive_members([(i.filename, None, False) for i in z.infolist()])
            for i in z.infolist():
                parts = i.filename.replace("\\", "/").split("/")[strip:]
                if not parts or parts == [""]:
                    continue
                out = os.path.join(dest, *parts)
                if i.is_dir():
                    os.makedirs(out, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with z.open(i) as src, open(out, "wb") as f:
                    shutil.copyfileobj(src, f, 1 << 20)
                mode = (i.external_attr >> 16) & 0o777
                if mode:
                    os.chmod(out, mode)
        return
    with tarfile.open(archive) as t:
        members = t.getmembers()
        check_archive_members([(m.name, m.linkname if (m.issym() or m.islnk()) else None, m.issym())
                               for m in members])
        for m in members:
            parts = m.name.split("/")[strip:]
            if not parts or parts == [""]:
                continue
            m.name = "/".join(parts)
            if m.islnk():
                m.linkname = "/".join(m.linkname.split("/")[strip:])
            if hasattr(tarfile, "data_filter"):
                # Python 3.12+ (and patched 3.9-3.11): the stdlib's own check
                # on top of ours (no device files, no setuid bits).
                t.extract(m, dest, filter="data")
            else:
                t.extract(m, dest)


def fetch_mingw(pins, force=False):
    tag = mingw_tag()
    asset = mingw_asset_name(tag)
    pin = pins["llvm_mingw"]["assets"].get(asset)
    if pins["llvm_mingw"]["tag"] != tag or not pin:
        raise CliError("config/setup-pins.json has no pin for %s (run 'blinx2 pins refresh')" % asset)
    dest = mingw_dir_for(asset)
    cc = os.path.join(dest, "bin", "x86_64-w64-mingw32-clang" + exe_suffix())
    if not force and os.path.isfile(cc) and _read(os.path.join(dest, ".tag")) == tag:
        say("llvm-mingw %s: already installed (%s)" % (tag, os.path.relpath(dest, ROOT)))
        return dest
    os.makedirs(THIRD_PARTY, exist_ok=True)
    arc = os.path.join(THIRD_PARTY, asset)
    download(pin["url"], arc, pin["sha256"], pin.get("size"))
    part = dest + ".partial"
    shutil.rmtree(part, ignore_errors=True)
    extract(arc, part)
    with open(os.path.join(part, ".tag"), "w") as f:
        f.write(tag + "\n")
    shutil.rmtree(dest, ignore_errors=True)
    os.rename(part, dest)
    os.remove(arc)
    say("llvm-mingw %s -> %s" % (tag, os.path.relpath(dest, ROOT)))
    return dest


def fetch_nsis(pins, force=False):
    """Windows hosts only: the portable NSIS zip (makensis.exe needs no
    install). Linux and macOS take makensis from the package manager."""
    pin = pins["nsis"]
    dest = os.path.join(THIRD_PARTY, "nsis-%s" % pin["version"])
    if not force and os.path.isfile(os.path.join(dest, "makensis.exe")):
        say("NSIS %s: already installed" % pin["version"])
        return dest
    os.makedirs(THIRD_PARTY, exist_ok=True)
    arc = os.path.join(THIRD_PARTY, "nsis-%s.zip" % pin["version"])
    download(pin["url"], arc, pin["sha256"], pin.get("size"))
    part = dest + ".partial"
    shutil.rmtree(part, ignore_errors=True)
    extract(arc, part)
    shutil.rmtree(dest, ignore_errors=True)
    os.rename(part, dest)
    os.remove(arc)
    return dest


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def make_venv(dev=False):
    py = venv_python()
    if not os.path.isfile(py):
        say("creating .venv (%s)" % sys.executable)
        r = subprocess.run([sys.executable, "-m", "venv", VENV])
        if r.returncode != 0:
            raise CliError("python -m venv failed; on Debian-like systems install python3-venv")
    if dev and sys.version_info < (3, 12):
        raise CliError("setup --dev needs Python 3.12 or newer (numpy); this is %s"
                       % platform.python_version())
    reqs = ["-r", REQS] + (["-r", REQS_DEV] if dev else [])
    run([py, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         "--require-hashes", "--only-binary", ":all:"] + reqs)


def exclude_pin_mark(tk):
    """Keep the pin mark out of `git status` in the toolkit clone: as an
    untracked file it made every packaged version '-dirty'."""
    if not os.path.isfile(os.path.join(tk, TOOLKIT_PIN_MARK)):
        return
    # Ask git where the exclude file lives: in a worktree (or a clone whose
    # .git is a file) it is under the common dir, not <tk>/.git/info.
    r = subprocess.run(["git", "-C", tk, "rev-parse", "--git-path", "info/exclude"],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if r.returncode != 0:
        return
    excl = os.path.join(tk, r.stdout.decode().strip())
    os.makedirs(os.path.dirname(excl), exist_ok=True)
    try:
        with open(excl) as f:
            if "/" + TOOLKIT_PIN_MARK in f.read().split():
                return
    except OSError:
        pass
    with open(excl, "a") as f:
        f.write("\n/%s\n" % TOOLKIT_PIN_MARK)


def clone_toolkit(pins):
    tk = toolkit_dir()
    if os.path.isdir(os.path.join(tk, "tools")):
        exclude_pin_mark(tk)
        say("toolkit: %s (left as it is)" % tk)
        return tk
    if not shutil.which("git"):
        raise CliError("git is needed to fetch the toolkit")
    pin = pins["toolkit"]
    dest = os.path.join(ROOT, "external", "xboxrecomp")
    say("toolkit: cloning %s %s into external/xboxrecomp" % (pin["url"], pin["commit"][:12]))
    run(["git", "clone", "--branch", pin["branch"], pin["url"], dest])
    run(["git", "-C", dest, "checkout", "--quiet", pin["commit"]])
    with open(os.path.join(dest, TOOLKIT_PIN_MARK), "w") as f:
        f.write(pin["commit"] + "\n")
    exclude_pin_mark(dest)
    return dest


def _cfg_setup(p):
    p.add_argument("--dev", action="store_true", help="also the toolkit's test dependencies")
    p.add_argument("--no-toolkit", action="store_true", help="do not clone the toolkit")
    p.add_argument("--force", action="store_true", help="fetch the toolchain again")


@command("setup", "fetch the pinned toolchain for this host (venv, llvm-mingw, NSIS on Windows)",
         _cfg_setup)
def cmd_setup(a):
    run_setup(a.dev, a.force, a.no_toolkit)
    return cmd_doctor(a)


def run_setup(dev=False, force=False, no_toolkit=False):
    """Every step skips what is already in place, so package can run it
    whenever something is missing."""
    pins = load_pins()
    step("setup: Python venv (.venv)")
    make_venv(dev)
    step("setup: llvm-mingw")
    fetch_mingw(pins, force)
    if host_os() == "windows":
        step("setup: NSIS")
        fetch_nsis(pins, force)
    if not no_toolkit:
        step("setup: toolkit")
        clone_toolkit(pins)


def setup_needs(target, system_tools=False):
    """What `setup` would fetch for this target: [] when nothing."""
    needs = []
    if not system_tools:
        for t in ("cmake", "ninja"):
            if not os.path.isfile(os.path.join(venv_bin(), t + exe_suffix())):
                needs.append("no %s" % t)
    try:
        tool_python()
    except CliError:
        needs.append("no tools Python")
    if not os.path.isdir(os.path.join(toolkit_dir(), "tools")):
        needs.append("no toolkit")
    if target in ("windows", "steamos"):
        try:
            mingw_root()
        except CliError:
            needs.append("no llvm-mingw")
    if target == "windows" and host_os() == "windows" and not makensis_path():
        needs.append("no NSIS")
    return needs


def host_blockers(target):
    """What stops this target on this host that setup cannot install, each
    with its one-line fix: [] when nothing."""
    out = []
    if not os.path.isfile(XBE):
        out.append("no game_files/default.xbe: dump the disc into game_files/")
    os_name = host_os()
    if target == "macos":
        if os_name != "macos":
            out.append("the macos target needs a macOS host (Apple clang, codesign, hdiutil)")
        elif not os.path.isdir(CLT):
            out.append("Command Line Tools: xcode-select --install")
        else:
            missing = brew_missing()
            if missing:
                out.append("Homebrew: brew install %s" % " ".join(missing))
    if target == "windows" and os_name != "windows" and not makensis_path():
        out.append("makensis: " + makensis_hint())
    return out


# doctor

def makensis_path():
    if host_os() == "windows":
        try:
            ver = load_pins()["nsis"]["version"]
        except (OSError, KeyError, ValueError):
            ver = None
        if ver:
            p = os.path.join(THIRD_PARTY, "nsis-%s" % ver, "makensis.exe")
            if os.path.isfile(p):
                return p
    return shutil.which("makensis")


def linux_flavour():
    try:
        with open("/etc/os-release") as f:
            info = dict(l.rstrip("\n").split("=", 1) for l in f if "=" in l)
    except OSError:
        return "debian"
    ids = (info.get("ID", "") + " " + info.get("ID_LIKE", "")).replace('"', "").lower()
    if os.path.exists("/run/ostree-booted") or "steamos" in ids:
        return "immutable"
    for k in ("fedora", "arch", "debian", "ubuntu"):
        if k in ids:
            return "debian" if k == "ubuntu" else k
    return "debian"


def makensis_hint():
    return MAKENSIS_HINT["macos" if host_os() == "macos" else linux_flavour()]


def brew_missing(pkgs=("sdl2", "sdl3", "openssl", "libepoxy")):
    if not shutil.which("brew"):
        return list(pkgs)
    missing = []
    for p in pkgs:
        r = subprocess.run(["brew", "--prefix", "--installed", p], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            missing.append(p)
    return missing


def quarantined(path):
    if host_os() != "macos" or not os.path.exists(path):
        return False
    r = subprocess.run(["xattr", "-p", "com.apple.quarantine", path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def windows_long_paths_enabled():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem")
        return winreg.QueryValueEx(k, "LongPathsEnabled")[0] == 1
    except (ImportError, OSError):
        return None


def windows_path_warnings(root=ROOT, long_paths=None):
    w = []
    if len(root) > 60:
        w.append("the checkout path is %d characters; the build nests deep, so use a short "
                 "path such as C:\\b2" % len(root))
    if long_paths is False:
        w.append("LongPathsEnabled is off; enable it, and run "
                 "'git config core.longpaths true'")
    return w


def doctor_report():
    """(lines, packageable targets, blocked {target: reason})."""
    os_name, arch = host_os(), host_arch()
    lines = ["host:       %s %s, Python %s" % (os_name, arch, platform.python_version())]
    blocked = {}
    problems = []
    # venv tools
    b = venv_bin()
    for t in ("cmake", "ninja"):
        p = os.path.join(b, t + exe_suffix())
        lines.append("%-11s %s" % (t + ":", p if os.path.isfile(p) else
                                    "missing in .venv (run 'blinx2 setup'); system: %s"
                                    % (shutil.which(t) or "none")))
        if not os.path.isfile(p):
            problems.append("no %s in .venv (blinx2 setup; or --system-tools)" % t)
    try:
        lines.append("tools py:   %s" % tool_python())
    except CliError as e:
        lines.append("tools py:   %s" % e)
        problems.append("no tools Python (blinx2 setup)")
    tk = toolkit_dir()
    if os.path.isdir(os.path.join(tk, "tools")):
        head = subprocess.run(["git", "-C", tk, "rev-parse", "HEAD"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL).stdout.decode().strip() or "?"
        note = ""
        mark = _read(os.path.join(tk, TOOLKIT_PIN_MARK))
        if mark:
            try:
                pin = load_pins()["toolkit"]["commit"]
                note = " (pinned)" if head == pin else " (differs from the pin %s)" % pin[:12]
            except (OSError, KeyError, ValueError):
                pass
        lines.append("toolkit:    %s @ %s%s" % (tk, head[:12], note))
    else:
        lines.append("toolkit:    missing at %s (run 'blinx2 setup')" % tk)
        problems.append("no toolkit (blinx2 setup)")
    try:
        root = mingw_root()
        cc = os.path.join(root, "bin", "x86_64-w64-mingw32-clang" + exe_suffix()) if root \
            else shutil.which("x86_64-w64-mingw32-clang")
        lines.append("llvm-mingw: %s" % (root or cc))
        if quarantined(cc or ""):
            lines.append("            quarantined: macOS will refuse it; clear with "
                         "xattr -dr com.apple.quarantine '%s'" % root)
            problems.append("llvm-mingw quarantined")
    except CliError as e:
        lines.append("llvm-mingw: %s" % e)
        problems.append("no llvm-mingw (blinx2 setup)")
    gen_ok = os.path.isfile(os.path.join(GEN, "recomp_funcs.h"))
    lines.append("game files: %s" % ("game_files/default.xbe" if os.path.isfile(XBE)
                                      else "MISSING: put your dump in game_files/"))
    lines.append("gen/:       %s" % ("present" if gen_ok else "not generated yet (blinx2 analyze, blinx2 recomp)"))
    if os_name == "macos":
        lines.append("DEVELOPER_DIR: %s" % build_env().get("DEVELOPER_DIR", "(Xcode default)"))
    if os_name == "windows":
        for w in windows_path_warnings(ROOT, windows_long_paths_enabled()):
            lines.append("warning:    " + w)
    if not os.path.isfile(XBE):
        problems.append("no game_files/default.xbe")
    media = media_warning()
    if media:
        lines.extend("warning:    " + l if i == 0 else "            " + l
                     for i, l in enumerate(media.splitlines()))
    ok = not problems
    why = "; ".join(problems)
    if not ok:
        blocked["steamos"] = why
    mk = makensis_path()
    lines.append("makensis:   %s" % (mk or "missing (windows target only): " + makensis_hint()))
    if not ok:
        blocked["windows"] = why
    elif not mk:
        blocked["windows"] = "makensis: " + makensis_hint()
    if os_name != "macos":
        blocked["macos"] = "needs a macOS host (Apple clang, codesign, hdiutil)"
    else:
        missing = brew_missing()
        clt = os.path.isdir(CLT)
        if not clt:
            blocked["macos"] = "Command Line Tools: xcode-select --install"
        elif missing:
            blocked["macos"] = "Homebrew: brew install %s" % " ".join(missing)
        elif not ok:
            blocked["macos"] = why
    targets = [t for t in ("windows", "steamos", "macos") if t not in blocked]
    return lines, targets, blocked


_MEDIA_CACHE = {}


def media_warning():
    """The incomplete-dump warning for game_files/, or '' (warn only: the
    game runs without those files, it just stays silent where they play).
    Cached per XBE state: doctor and the package payload both ask, and the
    scan reads the whole XBE."""
    try:
        st = os.stat(XBE)
    except OSError:
        return ""
    key = (XBE, GAME_FILES, st.st_size, st.st_mtime_ns)
    if key not in _MEDIA_CACHE:
        lib = plib()
        try:
            with open(XBE, "rb") as f:
                _MEDIA_CACHE[key] = lib.missing_media_text(lib.missing_media(f.read(), GAME_FILES))
        except OSError:
            return ""
    return _MEDIA_CACHE[key]


@command("doctor", "what this host has, and which targets it can package")
def cmd_doctor(a):
    lines, targets, blocked = doctor_report()
    step("doctor")
    for l in lines:
        say(l)
    say()
    say("can package: %s" % (", ".join(targets) or "nothing yet"))
    for t, why in blocked.items():
        say("  %s: %s" % (t, why))
    return 0 if "steamos" in targets else 1


# pins refresh (maintainers only)

# pip pins: (name, version or None for the newest, environment marker).
# capstone stays on the dev venv's version: the lifter decodes with it, so a
# different capstone could change the generated code. Hash mode needs every
# transitive dependency, so pytest's (with their markers) are listed too;
# `pins refresh` fails if any pinned package gains one that is not here.
# numpy 2.5 needs Python 3.12, so `setup --dev` does too.
PIP_SETUP = (("cmake", None, None), ("ninja", None, None),
             ("capstone", "5.0.9", None), ("pefile", "2024.8.26", None))
PIP_DEV = (("pytest", "9.1.1", None), ("iniconfig", "2.3.0", None), ("packaging", "26.3", None),
           ("pluggy", "1.6.0", None), ("pygments", None, None),
           ("colorama", None, 'sys_platform == "win32"'),
           ("exceptiongroup", None, 'python_version < "3.11"'),
           ("tomli", None, 'python_version < "3.11"'),
           ("typing-extensions", None, 'python_version < "3.11"'),
           ("numpy", "2.5.3", None))
TOOLKIT_FORK = ("https://github.com/apexJCL/xboxrecomp.git", "blinx2/portability")
NSIS_VERSION = "3.13"


def _get_json(url):
    import json
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "blinx2-pins",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def requires(requires_dist):
    """Runtime dependency names, minus extras and anything only for a Python
    older than this CLI's 3.9."""
    import re
    out = []
    for r in requires_dist or []:
        req, _, marker = r.partition(";")
        if "extra ==" in marker:
            continue
        m = re.search(r'python_version\s*<\s*"3\.(\d+)"', marker)
        if m and int(m.group(1)) <= 9:
            continue
        out.append(re.split(r"[<>=!~\[ (]", req.strip(), maxsplit=1)[0].lower().replace("_", "-"))
    return out


def pip_block(pins, all_pins):
    out = []
    for name, ver, marker in pins:
        d = _get_json("https://pypi.org/pypi/%s/%sjson" % (name, (ver + "/") if ver else ""))
        ver = d["info"]["version"]
        wheels = sorted(u["digests"]["sha256"] for u in d["urls"] if u["packagetype"] == "bdist_wheel")
        if not wheels:
            raise CliError("%s %s has no wheels on PyPI" % (name, ver))
        line = "%s==%s" % (name, ver) + ("; %s" % marker if marker else "")
        out.append(line + " \\\n" + " \\\n".join("    --hash=sha256:%s" % h for h in wheels))
        missing = set(requires(d["info"].get("requires_dist"))) - {n for n, _, _ in all_pins}
        if missing:
            raise CliError("%s %s needs %s: add them to PIP_SETUP or PIP_DEV"
                           % (name, ver, ", ".join(sorted(missing))))
    return "\n".join(out) + "\n"


def pins_refresh():
    import json
    header = ("# Generated by 'blinx2.py pins refresh'; do not edit. pip installs these with\n"
              "# --require-hashes --only-binary :all:, so nothing else can be installed.\n")
    with open(REQS, "w", newline="\n") as f:
        f.write(header + pip_block(PIP_SETUP, PIP_SETUP + PIP_DEV))
    with open(REQS_DEV, "w", newline="\n") as f:
        f.write(header + "# setup --dev: the toolkit's test dependencies (Python 3.12 or newer).\n"
                + pip_block(PIP_DEV, PIP_SETUP + PIP_DEV))
    tag = mingw_tag()
    rel = _get_json("https://api.github.com/repos/mstorsjo/llvm-mingw/releases/tags/%s" % tag)
    want = sorted(set(v.format(tag=tag) for v in MINGW_ASSETS.values()))
    assets = {}
    for a in rel["assets"]:
        if a["name"] in want:
            if not (a.get("digest") or "").startswith("sha256:"):
                raise CliError("%s has no sha256 digest in the release API" % a["name"])
            assets[a["name"]] = {"url": a["browser_download_url"],
                                 "sha256": a["digest"][len("sha256:"):], "size": a["size"]}
    missing = set(want) - set(assets)
    if missing:
        raise CliError("llvm-mingw %s lacks %s" % (tag, ", ".join(sorted(missing))))
    url, branch = TOOLKIT_FORK
    repo = url.split("github.com/")[1][:-len(".git")]
    head = _get_json("https://api.github.com/repos/%s/branches/%s" % (repo, branch))["commit"]["sha"]
    # SourceForge publishes no sha256: hash the download here, once, and
    # pin that (trust on first use by the maintainer; setup then checks it).
    nsis_url = ("https://sourceforge.net/projects/nsis/files/NSIS%%203/%s/nsis-%s.zip/download"
                % (NSIS_VERSION, NSIS_VERSION))
    import tempfile
    import urllib.request
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "nsis.zip")
        with urllib.request.urlopen(urllib.request.Request(nsis_url, headers={"User-Agent": "blinx2-pins"})) as r, \
                open(p, "wb") as f:
            shutil.copyfileobj(r, f)
        nsis = {"version": NSIS_VERSION, "url": nsis_url, "sha256": sha256_path(p),
                "size": os.path.getsize(p)}
    pins = {"_comment": "Generated by 'blinx2.py pins refresh'. setup checks every download against these.",
            "llvm_mingw": {"tag": tag, "assets": assets},
            "nsis": nsis,
            "toolkit": {"url": url, "branch": branch, "commit": head}}
    with open(PINS, "w", newline="\n") as f:
        json.dump(pins, f, indent=2, sort_keys=True)
        f.write("\n")
    say("wrote %s, %s, %s" % (os.path.relpath(PINS, ROOT), os.path.relpath(REQS, ROOT),
                              os.path.relpath(REQS_DEV, ROOT)))


def _cfg_pins(p):
    p.add_argument("action", choices=("refresh",))


@command("pins", "maintainers: rewrite config/setup-pins.json and the pip pins", _cfg_pins)
def cmd_pins(a):
    pins_refresh()


# ── package ──────────────────────────────────────────────────────────────

DIST = os.path.join(ROOT, "dist")
PKG = os.path.join(ROOT, "packaging")
NOTICE_TEXT = ("PRIVATE: this bundle contains your own copy of %s and code generated from it.\n"
               "It is for your own machines only. The game is not yours to redistribute:\n"
               "never share, upload or publish this bundle.")
TARGET_NAMES = {"windows": "windows-x86_64", "steamos": "steamos-x86_64-proton", "macos": "macos-arm64"}
DATA_PATHS = {
    "windows": "  %LOCALAPPDATA%\\BLiNX2\\   (hdd, config, logs)",
    "steamos": "  ~/Games/BLiNX2/   (hdd, config, logs; the program is in versions/)",
    "macos": "  ~/Library/Application Support/BLiNX2/   (hdd, config, logs)",
}


def plib():
    """scripts/package_lib.py, imported (it is also a CLI of its own)."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import package_lib
    return package_lib


def make_icon(bdir):
    """The icon set from the XBE's title image (or the generic one) in
    <packaging build dir>/icon: game data, never in the source tree."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import game_icon
    out = os.path.join(bdir, "icon")
    desc, rebuilt = game_icon.make_icons(XBE, out)
    say("icon: %s%s" % (desc, "" if rebuilt else " (cached)"))
    return out


def render(template, values, dst, mode=None):
    with open(template) as f:
        text = f.read()
    for k, v in values.items():
        text = text.replace("@%s@" % k, v)
    with open(dst, "w", newline="\n") as f:
        f.write(text)
    if mode:
        os.chmod(dst, mode)


def copy_lf(src, dst, mode=0o644):
    """A text file into a bundle with LF line endings, whatever the checkout
    did (a Windows clone without .gitattributes would have CRLF)."""
    with open(src, "rb") as f:
        data = f.read().replace(b"\r\n", b"\n")
    with open(dst, "wb") as f:
        f.write(data)
    os.chmod(dst, mode)


def ghidra_named():
    return os.path.isfile(os.path.join(OUT, "ghidra", "export", "functions.json"))


def readme(target, version, lib, dst):
    cat = lib.tree_state(ROOT)
    tk = lib.tree_state(toolkit_dir())
    values = {"NAME": lib.PRODUCT_NAME, "VERSION": version, "TARGET": TARGET_NAMES[target],
              "SOURCES": "cat %s, toolkit %s" % (cat["commit"][:7], tk["commit"][:7]),
              "DATA_PATHS": DATA_PATHS[target], "LOG_KEEP": "10"}
    render(os.path.join(PKG, "README.txt.in"), values, dst)
    with open(os.path.join(PKG, target, "README.part")) as f:
        part = f.read()
    with open(dst, "a", newline="\n") as f:
        f.write(part.replace("@VERSION@", version))


def mingw_tool(name):
    root = mingw_root()
    return os.path.join(root, "bin", "x86_64-w64-mingw32-" + name + exe_suffix()) if root \
        else shutil.which("x86_64-w64-mingw32-" + name)


def build_launcher_exe(dst, ico, work, name):
    """BLiNX2.exe with the icon compiled in (windres, from llvm-mingw); the
    .rc and its object stay in the work dir, out of the payload."""
    rc, res = os.path.join(work, "BLiNX2.rc"), os.path.join(work, "BLiNX2.res.o")
    render(os.path.join(PKG, "windows", "BLiNX2.rc.in"), {"ICON": ico.replace("\\", "/")}, rc)
    run([mingw_tool("windres"), "-O", "coff", "-o", res, rc], env=build_env())
    run([mingw_tool("clang"), "-municode", "-mwindows", "-O2", "-Wall", "-o", dst,
         '-DBLINX2_NAME=L"%s"' % name.replace("\\", "\\\\").replace('"', '\\"'),
         os.path.join(PKG, "windows", "launcher.c"), res, "-lshell32", "-lole32", "-luuid"],
        env=build_env())


def check_staged(root, lib):
    problems = lib.staged_problems(root)
    if problems:
        raise CliError("refusing to package:\n  " + "\n  ".join(problems))


def cli_name():
    return "blinx2" if host_os() == "windows" else "./blinx2"


def stock_refusal(target, bdir, bad):
    """The refusal for a non-stock packaging cache, with the exact fix."""
    rel = os.path.relpath(bdir, ROOT)
    return ("%s is not a stock build: %s\n"
            "  fix: %s package %s --reconfigure    (or delete %s/)\n"
            "  or package it as it is, recorded in the manifest: --allow-debug / --allow-nonstock"
            % (rel, "; ".join(bad), cli_name(), target, rel))


def stage_payload(target, a, lib):
    """Build, check, and stage the payload common to every target.
    Returns (stage dir, payload dir, version, overrides, exe)."""
    mark("build")
    host = host_os()
    if target == "macos" and host != "macos":
        raise CliError("package macos needs a macOS host (Apple clang, codesign, hdiutil); "
                       "this host can package: windows, steamos")
    require(XBE, "(dump the disc into game_files/)")
    with open(XBE, "rb") as f:
        try:
            tid = lib.xbe_title_id(f.read(0x10000))
        except ValueError as e:
            raise CliError("%s: %s" % (XBE, e))
    if tid != lib.TITLE_ID:
        raise CliError("%s: title ID 0x%08X is not %s (0x%08X)"
                       % (XBE, tid, lib.PRODUCT_NAME, lib.TITLE_ID))
    media = media_warning()
    if media:
        say("warning: " + media)
    btarget = "macos" if target == "macos" else "windows"
    bdir = pkg_build_dir(btarget)
    a.icon_dir = make_icon(bdir)
    # The taskbar shows the icon of the window's process: cat_recomp.exe.
    icon_args = ["-DCAT_APP_ICON=" + os.path.join(a.icon_dir, "BLiNX2.ico")] \
        if btarget == "windows" else []
    if a.no_build:
        refuse_while_regenerating()
        exe = os.path.join(bdir, "cat_recomp.exe" if btarget == "windows" else "cat_recomp")
        if not os.path.isfile(exe):
            raise CliError("--no-build: no %s yet; run '%s package %s' without it first"
                           % (os.path.relpath(exe, ROOT), cli_name(), target))
    else:
        step("build %s (%s)" % (btarget, os.path.basename(bdir)))
        exe = build(btarget, icon_args, a.system_tools, bdir=bdir, stock=True,
                    reconfigure=a.reconfigure)
    if not os.listdir(GEN):
        raise CliError("src/recomp/gen/ is empty: run 'blinx2 recomp'")
    cache = os.path.join(bdir, "CMakeCache.txt")
    debug, nonstock = lib.cache_problems(lib.read_cache(cache))
    bad = ([] if a.allow_debug else debug) + ([] if a.allow_nonstock else nonstock)
    if bad:
        raise CliError(stock_refusal(target, bdir, bad))
    overrides = (debug if a.allow_debug else []) + (nonstock if a.allow_nonstock else [])
    version = lib.compute_version(ROOT, toolkit_dir(), GEN, exe)
    mark("package")
    step("stage the files")
    say("version: %s" % version)
    stage = os.path.join(a.out, ".stage-%s" % target)
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    payload = os.path.join(stage, "BLiNX2-%s-%s" % (version, target))
    os.makedirs(payload)
    return stage, payload, version, overrides, exe


def write_common(payload, target, version, lib):
    fam = "macos" if target == "macos" else "windows"
    copy_lf(os.path.join(PKG, "launch.env.default." + fam), os.path.join(payload, "launch.env.default"))
    copy_lf(os.path.join(PKG, "enhance.toml.default"), os.path.join(payload, "enhance.toml.default"))
    for n in ("LICENSE", "NOTICE"):
        copy_lf(os.path.join(ROOT, n), os.path.join(payload, n))
    readme(target, version, lib, os.path.join(payload, "README.txt"))
    n = lib.stage_game_files(os.path.join(ROOT, "game_files"), os.path.join(payload, "game_files"))
    say("game files: %d entries staged" % n)


def write_manifest(root, target, version, overrides, lib, extra=None):
    cat, tk = lib.tree_state(ROOT), lib.tree_state(toolkit_dir())
    gsha, gn = lib.gen_digest(GEN)
    btarget = "macos" if target == "macos" else "windows"
    cache = lib.read_cache(os.path.join(pkg_build_dir(btarget), "CMakeCache.txt"))
    ex = {"host": {"os": host_os(), "arch": host_arch()}, "ghidra_names": ghidra_named()}
    ex.update(extra or {})
    man = lib.build_manifest(root, TARGET_NAMES[target], version, cat, tk, gsha, gn, cache,
                             lib.compiler_line(cache, pkg_build_dir(btarget)), overrides, ex)
    import json
    text = json.dumps(man, indent=2) + "\n"
    leaks = lib.private_leaks(text)
    if leaks:
        raise CliError("the manifest would carry private data: " + ", ".join(leaks))
    with open(os.path.join(root, "manifest.json"), "w", newline="\n") as f:
        f.write(text)
    with open(os.path.join(root, "SHA256SUMS"), "w", newline="\n") as f:
        f.write(lib.sums_text(man))
    return man


def wrap_steamos(payload, version, exe, out):
    """One tar, written by tarfile with explicit modes, uid/gid 0 and no
    owner names (no account name leaks), the exe's mtime on every member and
    no symlinks: the same file from any build host, NTFS included."""
    import tarfile
    dst = os.path.join(out, "BLiNX2-%s-steamos.tar" % version)
    part = dst + ".part"
    mtime = int(os.path.getmtime(exe))
    top = os.path.basename(payload)
    execs = {"install.sh", "launch.sh"}

    def info(arc, path, isdir):
        ti = tarfile.TarInfo(arc)
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = ""
        ti.mtime = mtime
        if isdir:
            ti.type, ti.mode = tarfile.DIRTYPE, 0o755
        else:
            ti.size = os.path.getsize(path)
            ti.mode = 0o755 if os.path.basename(arc) in execs and arc.count("/") == 1 else 0o644
        return ti

    with tarfile.open(part, "w", format=tarfile.PAX_FORMAT) as t:
        t.addfile(info(top, payload, True))
        for dirpath, dirnames, filenames in os.walk(payload):
            dirnames.sort()
            rel = os.path.relpath(dirpath, payload)
            for d in dirnames:
                p = os.path.join(dirpath, d)
                if os.path.islink(p):
                    raise CliError("symlink in the payload: %s" % p)
                t.addfile(info("/".join(x for x in (top, rel, d) if x != "."), p, True))
            for fn in sorted(filenames):
                p = os.path.join(dirpath, fn)
                if os.path.islink(p):
                    raise CliError("symlink in the payload: %s" % p)
                with open(p, "rb") as f:
                    t.addfile(info("/".join(x for x in (top, rel, fn) if x != "."), p, False), f)
    os.replace(part, dst)
    return dst


def nsis_escape(path):
    return path.replace("$", "$$")


def wrap_windows(stage, payload, version, out, lib, icon_dir):
    mk = makensis_path()
    if not mk:
        raise CliError("no makensis: %s" % (makensis_hint() if host_os() != "windows"
                                            else "run 'blinx2 setup'"))
    try:
        names, inst, uninst = lib.nsis_lists(payload)
    except ValueError as e:
        raise CliError(str(e))
    folder = os.path.join(out, "BLiNX2-%s-windows" % version)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    setup = os.path.join(folder, "BLiNX2-%s-setup.exe" % version)
    nsi = os.path.join(stage, "installer.nsi")
    render(os.path.join(PKG, "windows", "installer.nsi.in"),
           {"NAME": lib.PRODUCT_NAME, "VERSION": version, "OUTFILE": nsis_escape(setup),
            "STAGE": nsis_escape(payload),
            "ICON": nsis_escape(os.path.join(icon_dir, "BLiNX2.ico")),
            "INSTALL_FILES": inst.rstrip("\n"), "UNINSTALL_FILES": uninst.rstrip("\n")}, nsi)
    flag = "/" if host_os() == "windows" else "-"
    try:
        nfiles = len(names) + 4      # + the uninstaller and the registry/shortcut steps
        run([mk, flag + ("V3" if VIEW else "V2"), nsi],
            parser=progress_lib().MakensisParser(nfiles) if VIEW else None)
        if os.path.getsize(setup) >= 2 * 1024 ** 3:
            raise CliError("%s is over 2 GB" % setup)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)   # no half-made bundle in dist/
        raise
    os.rename(os.path.join(payload, "game_files"), os.path.join(folder, "game_files"))
    return folder


def _otool(path):
    return subprocess.run(["otool", "-L", path], stdout=subprocess.PIPE, check=True).stdout.decode()


def brew_origin(src):
    """Where a bundled dylib came from, without the host's paths: the
    Homebrew formula and version when it is a Cellar file."""
    parts = src.split("/")
    if "Cellar" in parts and len(parts) > parts.index("Cellar") + 2:
        i = parts.index("Cellar")
        return "%s %s" % (parts[i + 1], parts[i + 2])
    return os.path.basename(src)


def wrap_macos(stage, payload, version, exe, out, overrides, lib, icns):
    """BLiNX2.app with the game files and every non-system dylib inside,
    relinked to @rpath and signed ad hoc, then a DMG."""
    import json
    app = os.path.join(stage, "dmg", "BLiNX2.app")
    c = os.path.join(app, "Contents")
    for d in ("MacOS", "Frameworks", "Resources"):
        os.makedirs(os.path.join(c, d))
    for n in os.listdir(payload):
        shutil.move(os.path.join(payload, n), os.path.join(c, "Resources", n))
    build_sha = plib().sha256_file(exe)
    shutil.copy2(exe, os.path.join(c, "MacOS", "cat_recomp"))
    render(os.path.join(PKG, "macos", "BLiNX2.in"), {"NAME": lib.PRODUCT_NAME},
           os.path.join(c, "MacOS", "BLiNX2"), 0o755)
    shutil.copy2(icns, os.path.join(c, "Resources", "BLiNX2.icns"))
    short = version.split("-")[0]
    render(os.path.join(PKG, "macos", "Info.plist.in"), {"VERSION": version, "SHORT_VERSION": short, "NAME": lib.PRODUCT_NAME},
           os.path.join(c, "Info.plist"))
    comps = []
    sdl3 = brew_prefix_lib("sdl3", "libSDL3.dylib")
    if sdl3:
        comps.append("libSDL3.dylib=" + sdl3)
    plan = lib.dylib_plan(exe, comps)
    for l in plan["libs"]:
        dst = os.path.join(c, "Frameworks", l["name"])
        shutil.copy2(l["src"], dst)
        os.chmod(dst, 0o755)
        run(["install_name_tool", "-id", "@rpath/" + l["name"], dst])
    for ch in plan["changes"]:
        f = os.path.join(c, "MacOS", "cat_recomp") if ch["file"] == "@exe" \
            else os.path.join(c, "Frameworks", ch["file"])
        run(["install_name_tool", "-change", ch["old"], ch["new"], f])
    run(["install_name_tool", "-add_rpath", "@executable_path/../Frameworks",
         os.path.join(c, "MacOS", "cat_recomp")])
    leftovers = []
    for f in [os.path.join(c, "MacOS", "cat_recomp")] + \
            [os.path.join(c, "Frameworks", l["name"]) for l in plan["libs"]]:
        for dep in lib.parse_otool(_otool(f)):
            if not dep.startswith(lib.SYSTEM_PREFIXES) and not dep.startswith("@"):
                leftovers.append("%s -> %s" % (os.path.basename(f), dep))
    if leftovers:
        raise CliError("unbundled libraries remain: " + "; ".join(leftovers))
    write_manifest(os.path.join(c, "Resources"), "macos", version, overrides, lib,
                   {"program": {"build_sha256": build_sha, "sealed_by": "codesign"},
                    "host_deps": [{"name": l["name"], "from": brew_origin(l["src"])}
                                  for l in plan["libs"]]})
    for l in plan["libs"]:
        run(["codesign", "--force", "--sign", "-", os.path.join(c, "Frameworks", l["name"])])
    run(["codesign", "--force", "--sign", "-", os.path.join(c, "MacOS", "cat_recomp")])
    run(["codesign", "--force", "--sign", "-", app])
    run(["codesign", "--verify", "--deep", "--strict", app])
    os.symlink("/Applications", os.path.join(stage, "dmg", "Applications"))
    dmg = os.path.join(out, "BLiNX2-%s.dmg" % version)
    if os.path.exists(dmg):
        os.remove(dmg)
    run(["hdiutil", "create"] + (["-puppetstrings"] if VIEW else ["-quiet"]) +
        ["-srcfolder", os.path.join(stage, "dmg"),
         "-format", "UDZO", "-volname", "%s %s" % (lib.PRODUCT_NAME, version), dmg])
    return dmg


def brew_prefix_lib(formula, name):
    if not shutil.which("brew"):
        return None
    r = subprocess.run(["brew", "--prefix", formula], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p = os.path.join(r.stdout.decode().strip(), "lib", name)
    return p if r.returncode == 0 and os.path.isfile(p) else None


def _cfg_package(p):
    p.add_argument("target", choices=("windows", "steamos", "macos"))
    p.add_argument("--no-build", action="store_true", help="package the existing build as it is")
    p.add_argument("--allow-debug", action="store_true", help="package a non-Release build")
    p.add_argument("--allow-nonstock", action="store_true",
                   help="package with CAT_GEN_OPT or XBOXRECOMP_ENHANCE=OFF (recorded)")
    p.add_argument("--archive", action="store_true", help="windows: also a stored .zip of the folder")
    p.add_argument("--out", default=DIST, help="output directory (default dist/)")
    p.add_argument("--keep-stage", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--plain", action="store_true",
                   help="plain line output, no live progress (also when not a terminal, or CI=1)")
    p.add_argument("--verbose", action="store_true",
                   help="show every tool's output as it runs (implies --plain); "
                        "it always goes to build-logs/ too")
    p.add_argument("--no-setup", action="store_true",
                   help="never run setup, even when something is missing (own toolchain)")
    p.add_argument("--reconfigure", action="store_true",
                   help="configure the packaging build tree afresh")
    p.add_argument("--system-tools", action="store_true",
                   help="use the host's cmake and ninja instead of the venv's")


def package_plan(a):
    """[(step, why)] for this package run, before anything runs. Generation
    is judged again after setup (the key needs the toolkit)."""
    plan = []
    needs = [] if a.no_setup else setup_needs(a.target, a.system_tools)
    if needs:
        plan.append(("setup", ", ".join(needs)))
    if not a.no_build:
        if "no toolkit" in needs:
            plan.append(("generate", "checked after setup"))
        else:
            why = gen_stale_reasons()
            if why:
                plan.append(("generate", ", ".join(why)))
        plan.append(("build", os.path.basename(pkg_build_dir(
            "macos" if a.target == "macos" else "windows"))))
    plan.append(("package", a.target))
    return plan


def plan_line(plan):
    return "plan: " + ", ".join("%s (%s)" % (n, w) if w else n for n, w in plan)


def run_plan_prefix(a, plan):
    """The setup and generate steps of the plan; build and package follow."""
    names = [n for n, _ in plan]
    if "setup" in names:
        mark("setup")
        run_setup()
        still = setup_needs(a.target, a.system_tools)
        if still:
            raise CliError("setup finished but still: %s (run '%s doctor')"
                           % (", ".join(still), cli_name()))
    if "generate" in names:
        mark("generate")
        why = gen_stale_reasons()
        if why:
            say("generate: %s" % ", ".join(why))
            reset_stage_extras()
            stage_parse(); stage_disasm(); stage_funcid(); stage_abi(); maybe_names()
            stage_recomp()
        else:
            say("gen/ is current")


@command("package", "a private bundle for windows, steamos or macos in dist/; runs setup, "
         "generation and the build first when they are needed", _cfg_package)
def cmd_package(a):
    global VIEW
    prog = progress_lib()
    VIEW = prog.View(prog.choose_mode(a.plain or a.verbose), logs=LOGS)
    VIEW.verbose = a.verbose
    VIEW.plan = []
    try:
        package(a)
    finally:
        VIEW.close()
        prog.prune_logs(LOGS)
        VIEW = None


def package(a):
    lib = plib()
    a.out = os.path.abspath(a.out)
    blockers = host_blockers(a.target)
    if blockers:
        raise CliError("cannot package %s on this host:\n  %s"
                       % (a.target, "\n  ".join(blockers)))
    exclude_pin_mark(toolkit_dir())
    plan = package_plan(a)
    VIEW.plan = [n for n, _ in plan]
    say(plan_line(plan))
    run_plan_prefix(a, plan)
    os.makedirs(a.out, exist_ok=True)
    stage, payload, version, overrides, exe = stage_payload(a.target, a, lib)
    write_common(payload, a.target, version, lib)
    if a.target == "macos":
        check_staged(payload, lib)
        step("app and dmg")
        result = wrap_macos(stage, payload, version, exe, a.out, overrides, lib,
                            os.path.join(a.icon_dir, "BLiNX2.icns"))
    else:
        shutil.copy2(exe, os.path.join(payload, "cat_recomp.exe"))
        pdb = os.path.join(os.path.dirname(exe), "cat_recomp.pdb")
        if os.path.isfile(pdb):
            shutil.copy2(pdb, os.path.join(payload, "cat_recomp.pdb"))
        if a.target == "steamos":
            copy_lf(os.path.join(PKG, "steamos", "install.sh"), os.path.join(payload, "install.sh"), 0o755)
            render(os.path.join(PKG, "steamos", "launch.sh"), {"NAME": lib.PRODUCT_NAME},
                   os.path.join(payload, "launch.sh"), 0o755)
            copy_lf(os.path.join(PKG, "steamos", "install_lib.py"), os.path.join(payload, "install_lib.py"))
            copy_lf(os.path.join(ROOT, "scripts", "running_game.py"), os.path.join(payload, "running_game.py"))
            shutil.copy2(os.path.join(a.icon_dir, "icon.png"), os.path.join(payload, "icon.png"))
        else:
            build_launcher_exe(os.path.join(payload, "BLiNX2.exe"),
                               os.path.join(a.icon_dir, "BLiNX2.ico"), stage, lib.PRODUCT_NAME)
        check_staged(payload, lib)
        write_manifest(payload, a.target, version, overrides, lib)
        if a.target == "steamos":
            step("tar")
            result = wrap_steamos(payload, version, exe, a.out)
        else:
            step("installer")
            result = wrap_windows(stage, payload, version, a.out, lib, a.icon_dir)
            if a.archive:
                import zipfile
                z = result + ".zip"
                with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
                    for dirpath, _, files in os.walk(result):
                        for fn in files:
                            p = os.path.join(dirpath, fn)
                            zf.write(p, os.path.relpath(p, os.path.dirname(result)))
                say("archive: %s" % z)
    if not a.keep_stage:
        shutil.rmtree(stage, ignore_errors=True)
    VIEW.end(True)
    if "-dirty" in version:
        say("WARNING: built from uncommitted changes (%s)" % version)
    say()
    say("bundle: %s" % result)
    say()
    say(NOTICE_TEXT % lib.PRODUCT_NAME)


# ── CLI ──────────────────────────────────────────────────────────────────

def make_parser():
    ap = argparse.ArgumentParser(prog="blinx2", description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n\n", 1)[1].split("\n\nStandard")[0])
    sub = ap.add_subparsers(dest="cmd", metavar="command")
    sub.required = True
    for name, help_, configure, func in COMMANDS:
        # No help= on the sub-parsers: the epilog lists the commands, players'
        # first and the developers' apart.
        p = sub.add_parser(name, description=help_)
        if configure:
            configure(p)
        p.set_defaults(func=func)
    return ap, sub


def native_target(os_name=None):
    """What `blinx2` with no arguments packages: the bundle for this host."""
    return {"macos": "macos", "windows": "windows"}.get(os_name or host_os(), "steamos")


def main(argv=None):
    ap, sub = make_parser()
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help")):
        argv = ["package", native_target()] + argv
    a, extra = ap.parse_known_args(argv)
    if extra and not getattr(a, "passthrough", None):
        ap.error("unrecognized arguments: %s" % " ".join(extra))
    a.extra = extra
    try:
        return a.func(a) or 0
    except CliError as e:
        print("blinx2: %s" % e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())

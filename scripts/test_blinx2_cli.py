#!/usr/bin/env python3
"""Tests for blinx2.py's host logic, with fake downloads and mocked hosts:
no network, no toolchain, no build. Plain asserts; runs alone or under
pytest.

  python3 scripts/test_blinx2_cli.py
  python3 -m pytest scripts/test_blinx2_cli.py

Exit 0 when every test passes.
"""

import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import blinx2 as b  # noqa: E402

try:
    import pytest
except ImportError:
    pytest = None
if pytest is not None:
    @pytest.fixture
    def d(tmp_path):
        return str(tmp_path)


def raises(fn, *a, match=""):
    try:
        fn(*a)
    except b.CliError as e:
        assert match in str(e), (match, str(e))
        return str(e)
    raise AssertionError("no CliError from %s%r" % (fn.__name__, a))


def test_host_mapping():
    assert [b.host_os(s) for s in ("Windows", "Darwin", "Linux", "CYGWIN_NT-10.0", "MSYS_NT")] == \
        ["windows", "macos", "linux", "windows", "windows"]
    assert [b.host_arch(m) for m in ("AMD64", "x86_64", "arm64", "aarch64", "ARM64")] == \
        ["x86_64", "x86_64", "aarch64", "aarch64", "aarch64"]
    assert b.exe_suffix("windows") == ".exe" and b.exe_suffix("linux") == ""


def test_asset_selection():
    t = "20260922"
    want = {("windows", "x86_64"): "llvm-mingw-20260922-ucrt-x86_64.zip",
            ("windows", "aarch64"): "llvm-mingw-20260922-ucrt-aarch64.zip",
            ("linux", "x86_64"): "llvm-mingw-20260922-ucrt-ubuntu-22.04-x86_64.tar.xz",
            ("linux", "aarch64"): "llvm-mingw-20260922-ucrt-ubuntu-22.04-aarch64.tar.xz",
            ("macos", "x86_64"): "llvm-mingw-20260922-ucrt-macos-universal.tar.xz",
            ("macos", "aarch64"): "llvm-mingw-20260922-ucrt-macos-universal.tar.xz"}
    for (o, a), name in want.items():
        assert b.mingw_asset_name(t, o, a) == name
    raises(b.mingw_asset_name, t, "freebsd", "x86_64", match="no llvm-mingw build")
    assert b.mingw_dir_for(want[("windows", "x86_64")]).endswith(
        os.path.join("third_party", "llvm-mingw-20260922-ucrt-x86_64"))


def test_every_asset_pinned():
    pins = b.load_pins()
    tag = b.mingw_tag()
    assert pins["llvm_mingw"]["tag"] == tag
    names = {v.format(tag=tag) for v in b.MINGW_ASSETS.values()}
    assert names == set(pins["llvm_mingw"]["assets"]), names ^ set(pins["llvm_mingw"]["assets"])
    for a in pins["llvm_mingw"]["assets"].values():
        assert len(a["sha256"]) == 64 and a["size"] > 0 and a["url"].startswith("https://github.com/")
    assert pins["nsis"]["version"] == b.NSIS_VERSION and len(pins["nsis"]["sha256"]) == 64
    assert pins["toolkit"]["url"] == b.TOOLKIT_FORK[0] and len(pins["toolkit"]["commit"]) == 40


def test_requirements_hashed():
    for path in (b.REQS, b.REQS_DEV):
        with open(path) as f:
            text = f.read()
        reqs = [l for l in text.splitlines() if l and not l.startswith((" ", "#"))]
        assert reqs and all("==" in r for r in reqs), reqs
        assert text.count("--hash=sha256:") >= len(reqs)
    with open(b.REQS) as f:
        assert "capstone==5.0.9" in f.read()


def fake_urlopen(payload):
    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.close()
    return lambda req: R(payload)


def test_digest_mismatch_deletes(d):
    import urllib.request
    real = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen(b"evil bytes")
    try:
        dest = os.path.join(d, "x.zip")
        raises(b.download, "https://example.invalid/x.zip", dest, "0" * 64, match="checksum mismatch")
        assert os.listdir(d) == [], os.listdir(d)
        good = hashlib.sha256(b"evil bytes").hexdigest()
        raises(b.download, "https://example.invalid/x.zip", dest, good, 999, match="checksum mismatch")
        assert os.listdir(d) == []
        b.download("https://example.invalid/x.zip", dest, good, len(b"evil bytes"))
        assert os.listdir(d) == ["x.zip"]
    finally:
        urllib.request.urlopen = real


def test_fetch_mingw_mismatch_unpacks_nothing(d):
    import urllib.request
    real = (urllib.request.urlopen, b.THIRD_PARTY, b.mingw_tag)
    b.THIRD_PARTY = os.path.join(d, "third_party")
    b.mingw_tag = lambda: "t1"
    asset = b.mingw_asset_name("t1")
    pins = {"llvm_mingw": {"tag": "t1", "assets": {asset: {"url": "https://example.invalid/a",
                                                           "sha256": "1" * 64, "size": 3}}}}
    urllib.request.urlopen = fake_urlopen(b"abc")
    try:
        raises(b.fetch_mingw, pins, match="checksum mismatch")
        assert os.listdir(b.THIRD_PARTY) == []
    finally:
        urllib.request.urlopen, b.THIRD_PARTY, b.mingw_tag = real


def test_archive_member_checks(d):
    bad = [[("top/../../etc/x", None, False)], [("/abs", None, False)], [("C:\\x", None, False)],
           [("top/link", "../../outside", True)], [("top/hl", "/etc/passwd", False)]]
    for m in bad:
        raises(b.check_archive_members, m, match="unsafe")
    b.check_archive_members([("top/bin/clang", None, False), ("top/bin/cc", "clang", True),
                             ("top/lib/x", "../bin/clang", True)])
    # A good tar: strip=1, the in-tree symlink kept.
    tp = os.path.join(d, "a.tar.xz")
    with tarfile.open(tp, "w:xz") as t:
        data = b"#!/bin/sh\n"
        ti = tarfile.TarInfo("llvm-mingw-x/bin/clang")
        ti.size, ti.mode = len(data), 0o755
        t.addfile(ti, io.BytesIO(data))
        li = tarfile.TarInfo("llvm-mingw-x/bin/cc")
        li.type, li.linkname = tarfile.SYMTYPE, "clang"
        t.addfile(li)
    b.extract(tp, os.path.join(d, "out"))
    assert os.access(os.path.join(d, "out", "bin", "clang"), os.X_OK)
    assert os.readlink(os.path.join(d, "out", "bin", "cc")) == "clang"
    # A zip with a '..' member is refused before anything is written.
    zp = os.path.join(d, "a.zip")
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("top/ok", "1")
        z.writestr("top/../../evil", "2")
    raises(b.extract, zp, os.path.join(d, "zout"), match="unsafe")
    assert not os.path.exists(os.path.join(d, "zout", "ok"))


def test_venv_layout():
    assert b.venv_bin("/v", "windows") == os.path.join("/v", "Scripts")
    assert b.venv_bin("/v", "linux") == os.path.join("/v", "bin")
    assert b.venv_python("/v", "windows") == os.path.join("/v", "Scripts", "python.exe")
    assert b.venv_python("/v", "macos") == os.path.join("/v", "bin", "python")


def test_wrapper_line_endings():
    with open(os.path.join(ROOT, "blinx2.cmd"), "rb") as f:
        cmd = f.read()
    with open(os.path.join(ROOT, "blinx2"), "rb") as f:
        sh = f.read()
    assert b"\r\n" in cmd and cmd.count(b"\n") == cmd.count(b"\r\n"), "blinx2.cmd must be CRLF"
    assert b"\r" not in sh and sh.startswith(b"#!/bin/sh\n"), "blinx2 must be LF"
    assert os.access(os.path.join(ROOT, "blinx2"), os.X_OK)


def test_macos_target_refused():
    for host in ("linux", "windows"):
        msg = raises(b.check_build_target, "macos", host, match="needs a macOS host")
        assert "windows" in msg
    b.check_build_target("macos", "macos")
    b.check_build_target("windows", "linux")
    assert b.default_build_target("macos") == "macos"
    assert b.default_build_target("windows") == b.default_build_target("linux") == "windows"


def test_ninja_required_on_windows(d):
    real = b.VENV
    b.VENV = d
    try:
        os.makedirs(os.path.join(d, "Scripts"))
        open(os.path.join(d, "Scripts", "cmake.exe"), "w").close()
        raises(b.build_tools, False, "windows", match="Ninja is required")
        os.makedirs(os.path.join(d, "bin"))
        open(os.path.join(d, "bin", "cmake"), "w").close()
        assert b.build_tools(False, "linux") == (os.path.join(d, "bin", "cmake"), None)
    finally:
        b.VENV = real


def test_windows_path_warnings():
    assert b.windows_path_warnings("C:\\b2", True) == []
    w = b.windows_path_warnings("C:\\Users\\someone\\Documents\\projects\\games\\recomp\\blinx2-recomp-checkout", False)
    assert len(w) == 2 and "short" in w[0] and "LongPathsEnabled" in w[1], w
    assert b.windows_path_warnings("C:\\b2", None) == []


def test_reserved_names():
    import package_lib as pl
    for bad in ("CON", "nul.txt", "COM1", "LPT9.bin", "x.", "x ", "a?b"):
        assert pl.name_problem(bad), bad
    for ok in ("console", "default.xbe", "COM10", "media"):
        assert pl.name_problem(ok) is None, ok


def test_developer_dir(d):
    real = b.CLT
    try:
        b.CLT = d
        e = b.build_env({"PATH": "/usr/bin"}, "macos")
        assert e["DEVELOPER_DIR"] == d
        e = b.build_env({"PATH": "/usr/bin", "DEVELOPER_DIR": "/Applications/Xcode.app"}, "macos")
        assert e["DEVELOPER_DIR"] == "/Applications/Xcode.app"
        assert "DEVELOPER_DIR" not in b.build_env({"PATH": "/usr/bin"}, "linux")
        b.CLT = os.path.join(d, "absent")
        assert "DEVELOPER_DIR" not in b.build_env({"PATH": "/usr/bin"}, "macos")
    finally:
        b.CLT = real


def test_requires_parsing():
    got = b.requires(['colorama>=0.4; sys_platform == "win32"', 'pluggy<2,>=1.5',
                      'importlib-resources; python_version < "3.9"', 'attrs>=19.2; extra == "dev"',
                      'typing_extensions>=4.6.0; python_version < "3.13"', "iniconfig"])
    assert got == ["colorama", "pluggy", "typing-extensions", "iniconfig"], got


def test_cli_rejects_stray_args():
    import contextlib
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            b.main(["doctor", "--bogus"])
            raise AssertionError("accepted --bogus")
        except SystemExit as e:
            assert e.code == 2
    assert "unrecognized arguments" in err.getvalue()


# ── the one-liner: native target, generation key, plan, packaging build ──

import contextlib  # noqa: E402

TREE_ATTRS = ("ROOT", "GEN", "REGEN_MARKER", "GAME_FILES", "XBE", "ANALYSIS_JSON", "OUT",
              "SEEDS", "ICALL_SEEDS", "GEN_KEY", "STAGE_EXTRAS", "GHIDRA_EXPORT",
              "HOST_RESERVED", "RECOMP_MANUAL", "SPIN_WAITS", "VENV", "THIRD_PARTY")


@contextlib.contextmanager
def fake_tree(d):
    """blinx2's paths moved under d/cat, a fake toolkit at d/tk: nothing real
    is read or written."""
    saved = {k: getattr(b, k) for k in TREE_ATTRS}
    env_saved = {k: os.environ.get(k) for k in ("XBOXRECOMP_DIR", "ICALL_DB", "SPLIT",
                                                 "XBOXRECOMP_PYTHON", "LLVM_MINGW_ROOT")}
    root = os.path.join(d, "cat")
    tk = os.path.join(d, "tk")
    paths = {"ROOT": root, "GEN": os.path.join(root, "src", "recomp", "gen"),
             "REGEN_MARKER": os.path.join(root, "src", "recomp", ".gen-regenerating"),
             "GAME_FILES": os.path.join(root, "game_files"),
             "XBE": os.path.join(root, "game_files", "default.xbe"),
             "ANALYSIS_JSON": os.path.join(root, "game_files", "default_analysis.json"),
             "OUT": os.path.join(root, "analysis"),
             "SEEDS": os.path.join(root, "config", "seed_functions.json"),
             "ICALL_SEEDS": os.path.join(root, "analysis", "icall_seeds.json"),
             "GEN_KEY": os.path.join(root, "src", "recomp", "gen.key.json"),
             "STAGE_EXTRAS": os.path.join(root, "analysis", "stage-extras.json"),
             "GHIDRA_EXPORT": os.path.join(root, "analysis", "ghidra", "export", "functions.json"),
             "HOST_RESERVED": os.path.join(root, "scripts", "host_reserved_names.py"),
             "RECOMP_MANUAL": os.path.join(root, "src", "recomp_manual.c"),
             "SPIN_WAITS": os.path.join(root, "config", "spin_waits.json"),
             "VENV": os.path.join(root, ".venv"), "THIRD_PARTY": os.path.join(root, "third_party")}
    for p in ("GEN", "GAME_FILES", "OUT"):
        os.makedirs(paths[p], exist_ok=True)
    for p, text in (("XBE", "xbe"), ("SEEDS", "[]"), ("HOST_RESERVED", "#"),
                    ("RECOMP_MANUAL", "/* */"), ("SPIN_WAITS", "{}")):
        os.makedirs(os.path.dirname(paths[p]), exist_ok=True)
        with open(paths[p], "w") as f:
            f.write(text)
    open(os.path.join(paths["GEN"], "recomp_funcs.h"), "w").close()
    os.makedirs(os.path.join(tk, "tools", "recomp", "output"), exist_ok=True)
    for k, v in paths.items():
        setattr(b, k, v)
    os.environ["XBOXRECOMP_DIR"] = tk
    for k in ("ICALL_DB", "SPLIT"):
        os.environ.pop(k, None)
    try:
        yield root, tk
    finally:
        for k, v in saved.items():
            setattr(b, k, v)
        for k, v in env_saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def test_native_target():
    assert [b.native_target(o) for o in ("macos", "linux", "windows")] == \
        ["macos", "steamos", "windows"]
    seen = []
    real = b.cmd_package
    try:
        for i, (name, h, c, f) in enumerate(b.COMMANDS):
            if name == "package":
                b.COMMANDS[i] = (name, h, c, lambda a: seen.append(a.target))
        assert b.main([]) == 0
    finally:
        for i, (name, h, c, f) in enumerate(b.COMMANDS):
            if name == "package":
                b.COMMANDS[i] = (name, h, c, real)
    assert seen == [b.native_target()]


def test_command_table():
    funcs = {name: f.__name__ for name, _, _, f in b.COMMANDS}
    assert funcs["package"] == "cmd_package" and funcs["setup"] == "cmd_setup"
    assert funcs["doctor"] == "cmd_doctor" and funcs["build"] == "cmd_build"


def test_help_sections():
    ap, _ = b.make_parser()
    text = ap.format_help()
    cmds, dev = text.split("\nCommands:")[1].split("Developer commands:")
    for w in ("analyze", "recomp", "build [", "pins"):
        assert w not in cmds and w in dev, w
    assert "blinx2 package" in cmds and "blinx2 doctor" in cmds


def test_stage_argv_snapshot(d):
    with fake_tree(d):
        argv = json.loads(b.stage_argv())
    tm = "$TK/tools/ghidra_naming/merge_names.py"
    assert tm not in json.dumps(argv)    # no Ghidra export: no names stage
    assert argv == [
        ["tool", "xbe_parser", ["$ROOT/game_files/default.xbe", "--json",
                                "$ROOT/game_files/default_analysis.json"]],
        ["tool", "disasm", ["$ROOT/game_files/default.xbe", "--analysis-json",
                            "$ROOT/game_files/default_analysis.json", "-o", "$ROOT/analysis/disasm",
                            "--text-only", "--extra-sections", b.DISASM_EXTRA_SECTIONS,
                            "--seed-functions", "$ROOT/config/seed_functions.json", "-v"]],
        ["tool", "func_id", ["$ROOT/game_files/default.xbe", "--functions",
                             "$ROOT/analysis/disasm/functions.json", "--strings",
                             "$ROOT/analysis/disasm/strings.json", "--xrefs",
                             "$ROOT/analysis/disasm/xrefs.json", "-o", "$ROOT/analysis/func_id", "-v"]],
        ["tool", "abi_analysis", ["$ROOT/game_files/default.xbe", "--disasm-dir",
                                  "$ROOT/analysis/disasm", "--func-id-dir", "$ROOT/analysis/func_id",
                                  "--output-dir", "$ROOT/analysis/abi", "-v"]],
        ["tool", "recomp", ["$ROOT/game_files/default.xbe", "--all", "--split", "250",
                            "--gen-dir", "$ROOT/src/recomp/gen", "--exclude-manual",
                            "$ROOT/src/recomp_manual.c", "--game-name", b.GAME_NAME,
                            "--disasm-dir", "$ROOT/analysis/disasm", "--func-id-dir",
                            "$ROOT/analysis/func_id", "--abi-dir", "$ROOT/analysis/abi",
                            "--spin-waits", "$ROOT/config/spin_waits.json",
                            "-o", "$ROOT/analysis/recomp"]]], argv


def test_gen_key_inputs(d):
    with fake_tree(d) as (root, tk):
        inputs = b.gen_inputs()
        assert inputs["$ROOT/config/seed_functions.json"] != "absent"
        assert inputs["$ROOT/config/spin_waits.json"] != "absent"
        assert inputs["$TK/tools/recomp/output/icall_targets.json"] == "absent"
        assert inputs["$ROOT/analysis/ghidra/export/functions.json"] == "absent"
        for p in inputs:
            real = p.replace("$ROOT", root).replace("$TK", tk)
            assert os.path.isfile(real) == (inputs[p] != "absent"), p


def test_gen_key_staleness(d):
    with fake_tree(d) as (root, tk):
        assert b.gen_stale_reasons() == ["no key"]
        b.write_gen_key()
        assert b.gen_stale_reasons() == []
        cases = [
            (lambda: write(b.SEEDS, "[1]"), "config/seed_functions.json changed"),
            (lambda: write(b.XBE, "xbe2"), "the XBE changed"),
            (lambda: write(b.RECOMP_MANUAL, "/* 2 */"), "src/recomp_manual.c changed"),
            (lambda: write(b.SPIN_WAITS, '{"auto": true}'), "config/spin_waits.json changed"),
            # The gitignored feedback database appearing changes inputs and argv.
            (lambda: write(b.icall_db(), "{}"), "toolkit:tools/recomp/output/icall_targets.json changed"),
            (lambda: os.environ.__setitem__("SPLIT", "100"), "stage commands changed"),
            (lambda: write(b.GHIDRA_EXPORT, "{}"), "Ghidra export appeared or went"),
        ]
        for change, why in cases:
            change()
            got = b.gen_stale_reasons()
            assert why in got, (why, got)
            b.write_gen_key()
            assert b.gen_stale_reasons() == [], why
        # Any stage run invalidates the key; extra arguments keep it stale.
        b.begin_stage("disasm", ["--foo"])
        assert b.gen_stale_reasons() == ["no key"]
        b.write_gen_key()
        assert b.gen_stale_reasons() == ["a stage ran with extra arguments"]
        b.begin_stage("disasm", [])
        b.write_gen_key()
        assert b.gen_stale_reasons() == []
        # Extras from hand-run stages the package regenerate does not rerun
        # (names with arguments; ghidra records none, its export is an input)
        # are cleared by that regenerate, so the next package run is a no-op.
        b.begin_stage("ghidra", ["-max-cpu", "2"])
        b.begin_stage("names", ["--min-len", "3"])
        b.write_gen_key()
        assert b.gen_stale_reasons() == ["a stage ran with extra arguments"]
        saved = {n: getattr(b, n) for n in ("stage_parse", "stage_disasm", "stage_funcid",
                                            "stage_abi", "maybe_names", "stage_recomp")}
        try:
            for n in ("parse", "disasm", "funcid", "abi"):
                setattr(b, "stage_" + n, lambda n=n: b.begin_stage(n))
            b.maybe_names = lambda: b.begin_stage("names")
            b.stage_recomp = lambda: (b.begin_stage("recomp"), b.write_gen_key())
            b.run_plan_prefix(A(), [("generate", "stale")])
        finally:
            for n, f in saved.items():
                setattr(b, n, f)
        assert b.gen_stale_reasons() == []
        open(b.REGEN_MARKER, "w").close()
        assert b.gen_stale_reasons() == ["the last recomp did not finish"]


def test_recomp_verbose_not_hashed(d):
    """recomp runs with -v (progress lines for the view), but the key's argv
    leaves it out, so the flag never stales gen/; the game name is fixed."""
    with fake_tree(d) as (root, tk):
        os.makedirs(os.path.join(b.OUT, "abi"), exist_ok=True)
        write(os.path.join(b.OUT, "abi", "abi_functions.json"), "{}")
        ran = []
        real = b.run_cmds
        try:
            b.run_cmds = lambda cmds: ran.extend(cmds)
            b.stage_recomp()
        finally:
            b.run_cmds = real
        assert ran and ran[0][2][-1] == "-v", ran
        import json
        assert json.loads(b.stage_argv())[-1][2][-1] != "-v"
        assert b.gen_stale_reasons() == []
        assert b.GAME_NAME == "cat"


def test_exclude_pin_mark(d):
    """The pin mark stays out of `git status` in a plain clone and in a
    worktree, whose exclude file is under the main repo's .git."""
    import subprocess as sp

    def git(*args, cwd):
        return sp.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                      stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True, check=True).stdout
    main = os.path.join(d, "tk")
    os.makedirs(main)
    git("init", "-q", cwd=main)
    write(os.path.join(main, "f"), "x")
    git("add", "f", cwd=main)
    git("commit", "-qm", "f", cwd=main)
    wt = os.path.join(d, "tk-wt")
    git("worktree", "add", "-q", wt, cwd=main)
    for tk in (wt, main):        # the worktree first: the exclude file is shared
        write(os.path.join(tk, b.TOOLKIT_PIN_MARK), "pin")
        if tk == wt:
            assert git("status", "--porcelain", cwd=tk).strip(), tk
        b.exclude_pin_mark(tk)
        b.exclude_pin_mark(tk)       # once only
        assert git("status", "--porcelain", cwd=tk) == "", tk
    with open(os.path.join(main, ".git", "info", "exclude")) as f:
        assert f.read().count(b.TOOLKIT_PIN_MARK) == 1


class A:
    def __init__(self, **kw):
        self.__dict__.update(dict(target="macos", no_setup=False, no_build=False,
                                  system_tools=False, reconfigure=False))
        self.__dict__.update(kw)


def test_package_plan(d):
    with fake_tree(d) as (root, tk):
        real = b.setup_needs
        try:
            b.setup_needs = lambda t, s=False: []
            b.write_gen_key()
            assert [n for n, _ in b.package_plan(A())] == ["build", "package"]
            assert b.plan_line(b.package_plan(A(target="windows"))) == \
                "plan: build (build-pkg-win), package (windows)"
            write(b.SEEDS, "[2]")
            plan = b.package_plan(A())
            assert plan[0] == ("generate", "config/seed_functions.json changed"), plan
            assert [n for n, _ in b.package_plan(A(no_build=True))] == ["package"]
            b.setup_needs = lambda t, s=False: ["no llvm-mingw"]
            plan = b.package_plan(A(target="steamos"))
            assert plan[0] == ("setup", "no llvm-mingw") and plan[1][0] == "generate"
            assert b.package_plan(A(no_setup=True))[0][0] == "generate"
        finally:
            b.setup_needs = real


def test_setup_needs(d):
    with fake_tree(d) as (root, tk):
        os.environ["XBOXRECOMP_PYTHON"] = sys.executable
        os.environ["LLVM_MINGW_ROOT"] = os.path.join(d, "mingw")
        assert b.setup_needs("macos") == ["no cmake", "no ninja"]
        assert b.setup_needs("macos", True) == []
        import shutil
        shutil.rmtree(os.path.join(tk, "tools"))
        assert b.setup_needs("macos", True) == ["no toolkit"]
        # The windows and steamos targets need llvm-mingw as well.
        b.THIRD_PARTY = os.path.join(d, "none")
        os.environ.pop("LLVM_MINGW_ROOT")
        write(os.path.join(root, "config", "toolchain.env"), "LLVM_MINGW_TAG=1\n")
        path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.path.join(d, "empty")
        try:
            assert b.setup_needs("steamos", True) == ["no toolkit", "no llvm-mingw"]
        finally:
            os.environ["PATH"] = path


def fake_cmake(d):
    """A cmake that logs its argv and, on --build, creates the exe."""
    log = os.path.join(d, "cmake.log")
    path = os.path.join(d, "fakecmake.py")
    write(path, "import json, os, sys\n"
                "with open(%r, 'a') as f: f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                "a = sys.argv[1:]\n"
                "if a[0] == '--build':\n"
                "    open(os.path.join(a[1], 'cat_recomp'), 'w').close()\n"
                "else:\n"
                "    b = a[a.index('-B') + 1]\n"
                "    os.makedirs(b, exist_ok=True)\n"
                "    open(os.path.join(b, 'CMakeCache.txt'), 'a').close()\n" % log)
    return path, log


def test_packaging_build_dir(d):
    with fake_tree(d) as (root, tk):
        write(os.path.join(tk, "CMakeLists.txt"), "")
        # A developer's build/ with enhancements off stays as it is.
        dev_cache = os.path.join(root, "build", "CMakeCache.txt")
        write(dev_cache, "XBOXRECOMP_ENHANCE:BOOL=OFF\n")
        script, log = fake_cmake(d)
        real_tools, real_run = b.build_tools, b.run
        calls = []
        try:
            b.build_tools = lambda s, o=None: ("CMAKE", None)

            def run(cmd, cwd=None, env=None, check=True):
                calls.append(cmd)
                return real_run([sys.executable, script] + list(cmd[1:]), cwd=cwd, env=env)
            b.run = run
            bdir = b.pkg_build_dir("macos")
            for _ in range(2):
                exe = b.build("macos", (), False, bdir=bdir, stock=True)
            assert exe == os.path.join(root, "build-pkg-macos", "cat_recomp")
        finally:
            b.build_tools, b.run = real_tools, real_run
        configures = [c for c in calls if c[1] == "-S"]
        assert len(configures) == 2, calls        # configured on every run
        for c in configures:
            assert c[c.index("-B") + 1] == bdir
            for opt in b.STOCK_CMAKE_ARGS:
                assert opt in c, (opt, c)
        dev = os.path.join(root, "build")
        assert not any(str(x) == dev or str(x).startswith(dev + os.sep)
                       for c in calls for x in c), calls
        with open(dev_cache) as f:
            assert f.read() == "XBOXRECOMP_ENHANCE:BOOL=OFF\n"


def test_stock_refusal_text():
    msg = b.stock_refusal("macos", os.path.join(b.ROOT, "build-pkg-macos"),
                          ["XBOXRECOMP_ENHANCE=OFF (want ON)"])
    assert msg.startswith("build-pkg-macos is not a stock build: XBOXRECOMP_ENHANCE=OFF (want ON)")
    assert "package macos --reconfigure" in msg and "delete build-pkg-macos/" in msg


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        if t.__code__.co_argcount:
            with tempfile.TemporaryDirectory() as d:
                t(d)
        else:
            t()
        print("ok %s" % t.__name__)
    print("%d tests passed" % len(tests))


if __name__ == "__main__":
    main()

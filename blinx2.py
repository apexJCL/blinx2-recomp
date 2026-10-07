#!/usr/bin/env python3
"""The game's command: finds uv and the xboxrecomp-cli commit game.toml pins,
then runs it. A copy of xboxrecomp-cli's wrapper/game.py, named after the
game (`<this> wrapper --check` compares the two); standard library only,
Python 3.9 or newer, so a host with only the system Python still gets the
help and the uv hint. Docs: docs/packaging.md."""

import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SLUG = os.path.splitext(os.path.basename(__file__))[0]
UV_MIN = (0, 5, 31)  # xboxrecomp-cli's env.UV_MIN
UV_HINT = {
    "darwin": "brew install uv",
    "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh   (or your distribution's uv package)",
    "win32": "winget install --id=astral-sh.uv -e",
}
UV_DOCS = "https://docs.astral.sh/uv/getting-started/installation/"
MARK = ".xbr-pin"


def cli_table():
    """[cli] commit and url; game.toml keeps them plain one-line strings."""
    vals, cur = {}, None
    with open(os.path.join(ROOT, "game.toml"), encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("["):
                cur = line.strip("[]").strip()
            elif cur == "cli":
                m = re.match(r'^(commit|url)\s*=\s*"([^"\\]*)"\s*(#.*)?$', line)
                if m:
                    vals[m.group(1)] = m.group(2)
    return vals


def find_uv():
    uv = shutil.which("uv")
    if not uv:
        return None
    out = subprocess.run([uv, "--version"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    m = re.match(r"uv (\d+)\.(\d+)\.(\d+)", out.stdout.decode().strip())
    return uv if m and tuple(int(x) for x in m.groups()) >= UV_MIN else None


GET_CLI = "clone it beside this checkout, or set XBOXRECOMP_CLI_DIR"


class NoCli(Exception):
    """Why no CLI can run; main() prints it with the way to get one."""


def git(*args):
    """git's stdout, or NoCli with its message (no network, no such
    commit on the remote, no git)."""
    try:
        r = subprocess.run(["git"] + list(args), capture_output=True, check=True)
    except OSError as e:
        raise NoCli("git: %s" % e) from None
    except subprocess.CalledProcessError as e:
        why = (e.stderr or b"").decode(errors="replace").strip().splitlines()
        raise NoCli(
            "git %s failed%s"
            % (args[0] if args[0] != "-C" else args[2], ": " + why[-1] if why else "")
        ) from None
    return r.stdout.decode(errors="replace").strip()


def head(d):
    try:
        return git("-C", d, "rev-parse", "HEAD")
    except NoCli:
        return ""


def at_pin(d, pin):
    """external/xboxrecomp-cli is this script's: it runs only at the pin. A
    clone it made (MARK) at another commit is moved to the pin (the game
    moved it); any other checkout there is refused, never run unpinned."""
    h = head(d)
    if h == pin:
        return d
    if not os.path.isfile(os.path.join(d, MARK)):
        raise NoCli(
            "external/xboxrecomp-cli is at %s, not the pin %s, and this script did not "
            "clone it: delete it, or set XBOXRECOMP_CLI_DIR to use it as it is"
            % (h[:12] or "no commit", pin[:12])
        )
    print("%s: xboxrecomp-cli: the pin moved; checking out %s" % (SLUG, pin[:12]), file=sys.stderr)
    try:
        git("-C", d, "checkout", "--quiet", pin)
    except NoCli:
        git("-C", d, "fetch", "--quiet", "origin")
        git("-C", d, "checkout", "--quiet", pin)
    if head(d) != pin:
        raise NoCli("external/xboxrecomp-cli would not check out the pin %s" % pin[:12])
    with open(os.path.join(d, MARK), "w") as f:
        f.write(pin + "\n")
    return d


def clone(cli, dest):
    """A clone at the pin, made aside and moved into place only once HEAD is
    the pin: a failed clone or checkout leaves nothing behind."""
    if not cli.get("url") or not cli.get("commit"):
        raise NoCli("game.toml [cli] names no url to clone it from")
    if not shutil.which("git"):
        raise NoCli("no git on PATH to clone it with")
    pin = cli["commit"]
    tmp = dest + ".partial"
    shutil.rmtree(tmp, ignore_errors=True)
    print(
        "%s: cloning %s %s into external/xboxrecomp-cli" % (SLUG, cli["url"], pin[:12]),
        file=sys.stderr,
    )
    try:
        git("clone", "--quiet", "--no-checkout", cli["url"], tmp)
        git("-C", tmp, "checkout", "--quiet", pin)
        if head(tmp) != pin:
            raise NoCli("the clone is not at the pin %s" % pin[:12])
        excl = git("-C", tmp, "rev-parse", "--git-path", "info/exclude")
        with open(os.path.join(tmp, excl), "a") as f:
            f.write("\n/%s\n" % MARK)  # out of `git status`: no -dirty versions
        with open(os.path.join(tmp, MARK), "w") as f:
            f.write(pin + "\n")
        os.rename(tmp, dest)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return dest


def find_cli(cli, may_clone=True):
    """$XBOXRECOMP_CLI_DIR, else external/xboxrecomp-cli (at the pin), else
    ../xboxrecomp-cli (the toolkit's order), else a clone at the pin. A
    developer's checkout (the variable, or beside this one) runs as it is."""
    env = os.environ.get("XBOXRECOMP_CLI_DIR")
    if env:
        d = os.path.abspath(env)
        if not os.path.isfile(os.path.join(d, "pyproject.toml")):
            raise NoCli("XBOXRECOMP_CLI_DIR=%s is not an xboxrecomp-cli checkout" % env)
        return d
    dest = os.path.join(ROOT, "external", "xboxrecomp-cli")
    if os.path.isfile(os.path.join(dest, "pyproject.toml")):
        return at_pin(dest, cli.get("commit", "")) if may_clone else dest
    beside = os.path.join(ROOT, "..", "xboxrecomp-cli")
    if os.path.isfile(os.path.join(beside, "pyproject.toml")):
        return os.path.abspath(beside)
    if not may_clone:
        raise NoCli("no xboxrecomp-cli found")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    return clone(cli, dest)


def no_cli(why):
    print("%s: %s" % (SLUG, why), file=sys.stderr)
    print("%s: no xboxrecomp-cli: %s" % (SLUG, GET_CLI), file=sys.stderr)


def uv_hint():
    hint = UV_HINT.get(sys.platform, UV_HINT["linux"])
    print(
        "%s: no uv %s on PATH; install it with: %s   (other ways: %s)"
        % (SLUG, ".".join(map(str, UV_MIN)) + "+", hint, UV_DOCS),
        file=sys.stderr,
    )


def main(argv):
    cli = cli_table()
    uv = find_uv()
    if not uv:
        # No clone without uv: nothing could run it yet.
        try:
            d = find_cli(cli, may_clone=False)
        except NoCli as e:
            d = None
            if argv in (["-h"], ["--help"]):
                no_cli(e)
        if argv in (["-h"], ["--help"]) and d:
            helptext = os.path.join(d, "src", "xboxrecomp_cli", "helptext.py")
            return subprocess.run([sys.executable, helptext, ROOT, SLUG]).returncode
        uv_hint()
        return 1
    try:
        d = find_cli(cli)
    except NoCli as e:
        no_cli(e)
        return 1
    env = dict(os.environ)
    for k in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):  # the CLI's own .venv, not the shell's
        env.pop(k, None)
    cmd = [
        uv,
        "run",
        "--quiet",
        "--project",
        d,
        "--locked",
        "--no-dev",
        "xbr",
        "--game",
        ROOT,
        "--prog",
        SLUG,
    ] + argv
    if os.name == "nt":
        return subprocess.run(cmd, env=env).returncode
    os.execve(uv, cmd, env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

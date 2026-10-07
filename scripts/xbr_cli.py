"""For the tests that stay here while some packaging templates are still
the game's (test_launchers): the xboxrecomp-cli
modules, found as blinx2.py finds the CLI and loaded with this game's
game.toml. Python 3.12+ (the CLI's floor); None on an older Python or
when no CLI is found, and the tests skip.

  import xbr_cli
  cli = xbr_cli.load()     # cli.lib is package/lib.py, configured
  xbr_cli.game_name()      # game.toml's [game] name, on any Python
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def cli_dir():
    """XBOXRECOMP_CLI_DIR, else external/xboxrecomp-cli, else
    ../xboxrecomp-cli: blinx2.py's order (it clones only when it runs)."""
    if os.environ.get("XBOXRECOMP_CLI_DIR"):
        return os.path.abspath(os.environ["XBOXRECOMP_CLI_DIR"])
    for d in (
        os.path.join(ROOT, "external", "xboxrecomp-cli"),
        os.path.join(ROOT, "..", "xboxrecomp-cli"),
    ):
        if os.path.isfile(os.path.join(d, "pyproject.toml")):
            return os.path.abspath(d)
    return None


def game_name():
    """game.toml's [game] name, read as the bootstrap reads its lines
    (standard library, any Python 3)."""
    cur = None
    with open(os.path.join(ROOT, "game.toml"), encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("["):
                cur = line.strip("[]").strip()
            elif cur == "game":
                m = re.match(r'^name\s*=\s*"([^"\\]*)"', line)
                if m:
                    return m.group(1)
    return None


class Cli:
    pass


def load():
    if sys.version_info < (3, 12):
        return None
    d = cli_dir()
    if d is None:
        return None
    src = os.path.join(d, "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from xboxrecomp_cli import manifest, package
    from xboxrecomp_cli.package import steamos

    manifest.use(manifest.load(ROOT))
    c = Cli()
    c.dir = d
    c.lib = package.plib()
    c.steamos = steamos
    return c


SKIP = (
    "needs xboxrecomp-cli (beside this checkout, external/, or XBOXRECOMP_CLI_DIR) and Python 3.12+"
)

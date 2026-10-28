#!/usr/bin/env python3
"""golden.json's known_divergence entries name private tracker items, and
only a CLI that drops them on export keeps them out of the public repo. This
runs the pinned CLI's own export step (public.drop_known, at game.toml's
[cli] commit) over golden.json and greps what it would publish for the
key and the entries' items. An older pin leaves the entries in, so the
entries and the re-pin land in one squash. Other tracker refs in the notes
are the private rewrite rules' (and the export's !fail check's) to catch.

  python3 scripts/test_public_golden.py
  uv run pytest scripts/test_public_golden.py
"""

import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import xbr_cli  # noqa: E402

GOLDEN = os.path.join(ROOT, "analysis", "golden", "golden.json")


def known_items(v):
    """The item of every known_divergence entry in v."""
    out = set()
    if isinstance(v, dict):
        for k in v.get("known_divergence", []):
            out.add(k.get("item", ""))
        for x in v.values():
            out |= known_items(x)
    elif isinstance(v, list):
        for x in v:
            out |= known_items(x)
    return out


def cli_pin():
    import tomllib

    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        cli = tomllib.load(f)["cli"]
    # A bare-commit pin (no tag) is one the bootstrap runs too.
    return cli.get("tag") or cli["commit"][:12], cli["commit"]


def exported_golden(cli_src, text):
    """golden.json as the CLI at cli_src would export it, before the private
    rewrite rules: its drop_known, or the text unchanged when it has none."""
    code = (
        "import sys, types\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from xboxrecomp_cli import public\n"
        "if not hasattr(public, 'drop_known'):\n"
        "    sys.stdout.write(sys.stdin.read()); sys.exit(0)\n"
        "ctx = types.SimpleNamespace(game=types.SimpleNamespace(root=sys.argv[2],"
        " golden_json=sys.argv[3]))\n"
        "rel = public.golden_path(ctx)\n"
        "sys.stdout.write(public.drop_known(ctx, rel, sys.stdin.read()))\n"
    )
    r = subprocess.run(
        [sys.executable, "-I", "-c", code, cli_src, ROOT, GOLDEN],
        input=text,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_pinned_cli_drops_known_divergence():
    if sys.version_info < (3, 12):
        print("skip: the CLI needs Python 3.12+")
        return
    with open(GOLDEN, encoding="utf-8") as f:
        text = f.read()
    items = known_items(json.loads(text)) - {""}
    if not items and "known_divergence" not in text:
        return
    d = xbr_cli.cli_dir()
    tag, commit = cli_pin()
    have = (
        d
        and not subprocess.run(
            ["git", "-C", d, "cat-file", "-e", commit + "^{commit}"], capture_output=True
        ).returncode
    )
    if not have:
        print("skip: no xboxrecomp-cli checkout with the pinned commit %s" % commit[:12])
        return
    with tempfile.TemporaryDirectory() as tmp:
        tar = os.path.join(tmp, "cli.tar")
        subprocess.run(
            ["git", "-C", d, "archive", "-o", tar, commit, "src/xboxrecomp_cli"], check=True
        )
        with tarfile.open(tar) as t:
            t.extractall(tmp, filter="data")
        out = exported_golden(os.path.join(tmp, "src"), text)
    assert "known_divergence" not in out, (
        "golden.json has known_divergence entries, but the pinned CLI %s exports them:"
        " re-pin [cli] to a release that drops them, in the same squash" % tag
    )
    for item in items:
        hits = [x.strip() for x in out.splitlines() if re.search(r"\b%s\b" % re.escape(item), x)]
        assert not hits, (item, hits)
    json.loads(out)


def test_known_items_finds_nested_entries():
    k = [{"host": "windows", "item": "ITEM-1"}, {"host": "posix", "item": "ITEM-2"}]
    assert known_items({"s": {"frames": [{"name": "m", "known_divergence": k}]}}) == {
        "ITEM-1",
        "ITEM-2",
    }
    assert known_items({"s": {"frames": [{"name": "m"}]}, "x": ["known_divergence"]}) == set()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and isinstance(fn, types.FunctionType):
            fn()
            print("ok", name)

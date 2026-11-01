#!/usr/bin/env python3
"""Tests for the shader profile key (present.profile, openspec change
shader-profiles, task 6.1): the golden check knows its stock value, the
shipped defaults leave it commented out (stock), and docs/env.md and the
README list it.

  python3 scripts/test_shader_profile_keys.py
  uv run pytest scripts/test_shader_profile_keys.py
"""

import os
import sys

import pytest
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    # The toolkit logs "[ENHANCE] present.profile=<slug>" only when a
    # profile is chosen; a golden run must show none.
    assert stock.get("present.profile") == "none"


def test_defaults_leave_it_stock():
    text = read("packaging", "config.default.toml")
    present = tomllib.loads(text)["present"]
    # Shipped commented out: the key's own default, none, applies.
    assert "profile" not in present
    assert '# profile = "none"' in text
    # The commented row sits in [present], after the shader row.
    sec = text.index("[present]")
    assert sec < text.index("# shader = ") < text.index('# profile = "none"')
    nxt = text.find("\n[", sec + 1)
    assert nxt < 0 or text.index('# profile = "none"') < nxt


def test_env_doc_row():
    rows = [
        ln
        for ln in read("docs", "env.md").splitlines()
        if ln.startswith("| `RECOMP_PRESENT_PROFILE`")
    ]
    assert len(rows) == 1
    assert "`present.profile`" in rows[0] and "Golden runs leave it `none`" in rows[0]


def test_readme_row():
    rows = [ln for ln in read("README.md").splitlines() if "`RECOMP_PRESENT_PROFILE`" in ln]
    assert len(rows) == 1 and "`present.profile`" in rows[0]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

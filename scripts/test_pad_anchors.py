#!/usr/bin/env python3
"""Tests for BLiNX 2's pad_record defaults: anchors and the poll clock.

A pad_record step is timed by the walker's flip count, and a load takes as
many flips as the host makes it, so a record without anchors replays a
stage's steps early or late. src/env/recomp_env_game.h gives
RECOMP_DEBUG=pad_anchor a default; these checks hold it to the opens that
end a load or a movie, and keep it off the opens the player's own play
causes, which a replay that drifted would wait on for a minute.

It also defaults RECOMP_DEBUG=pad_clock to poll: a record timed by the
walker's flip handed a replayed poll its neighbour's stick whenever two polls
shared a flip, and the frame-exact 2-1 wall clip missed on every replay.

The matching is the toolkit's anchor_wanted (src/usb/usb_gamepad.c): a
successful open whose path holds one of the |-separated texts, in any case.

  python3 scripts/test_pad_anchors.py
  uv run pytest scripts/test_pad_anchors.py
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

# Successful opens of the 2-1 clip's session, in order, that must
# be anchors: the boot and title movies, the title's song, the stage load
# and the stage start.
LOAD_OPENS = [
    r"d:\media\logo_mgs.sfd",
    r"d:\media\blinx2_opening.sfd",
    r"d:\media\title_movie_1a.sfd",
    r"d:\adx\song_TITLE.adx",
    r"z:\lng_us\stg0201_tex_us.tmp",
    r"z:\lng_us\stg0201_infotex_us.tmp",
    r"z:\media\stg0201_se.tmp",
    r"d:\adx\jingle_stagestart.adx",
]

# Opens that must not be: the cache's records and archives at boot, the
# stage intro's camera, the stage's song and ambience (opened again on a
# death's restart), and the jingles the play itself starts (a rewind, a
# goal): a replay that went another way may never open them.
PLAY_OPENS = [
    r"t:\$u\contentmeta.xbx",
    r"z:\blinx2_000.rec",
    r"d:\media.iph",
    r"d:\lng_us.iph",
    r"d:\tank_tex.iph",
    r"d:\cam\EVCAMST0201_003.CAM",
    r"d:\adx\song_R2sw.adx",
    r"d:\adx\envse_r2_wind.adx",
    r"d:\adx\jingle_17rew.adx",
    r"d:\adx\jingle_12kenriseiritsu.adx",
]


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def _default(row="PAD_ANCHOR"):
    text = _read("src", "env", "recomp_env_game.h")
    m = re.search(r"D\(" + row + r',\s*"([^"]*)"\)', text)
    assert m, f"no {row} game default in recomp_env_game.h"
    return m.group(1)


def anchor_wanted(texts, path):
    """The toolkit's anchor_wanted: any text inside the path, in any case."""
    p = path.lower()
    return any(t and t.lower() in p for t in texts.split("|"))


def test_default_is_a_bar_list_without_commas():
    texts = _default()
    # RECOMP_DEBUG is a comma list and the anchor line a colon one.
    assert texts and not re.search(r"[,:#\s]", texts)
    assert all(texts.split("|")), "an empty text would match every open"


def test_load_ends_are_anchors():
    texts = _default()
    for path in LOAD_OPENS:
        assert anchor_wanted(texts, path), f"{path}: not an anchor"


def test_play_opens_are_not_anchors():
    texts = _default()
    for path in PLAY_OPENS:
        assert not anchor_wanted(texts, path), f"{path}: an anchor"


def test_env_doc_names_the_default():
    doc = _read("docs", "env.md")
    row = next(line for line in doc.splitlines() if line.startswith("| (none) | `pad_anchor` |"))
    assert _default().replace("|", "\\|") in row
    assert "ITEM" in row


def test_records_on_the_poll_clock():
    assert _default("PAD_CLOCK") == "poll"


def test_pad_defaults_wait_for_the_toolkit_rows():
    # The public build's toolkit pin may predate PAD_CLOCK: a default for a
    # row it lacks would not compile.
    text = _read("src", "env", "recomp_env_game.h")
    guard = text.index("#ifdef RECOMP_ENV_HAVE_PAD_CLOCK_ROW")
    end = text.index("#endif", guard)
    for row in ("PAD_CLOCK", "PAD_ANCHOR"):
        at = text.index(f"D({row},")
        assert guard < at < end, f"{row}: default outside the guard"


def test_env_doc_rows_for_clock_and_quit():
    doc = _read("docs", "env.md").splitlines()
    clock = next(line for line in doc if line.startswith("| (none) | `pad_clock` |"))
    assert "`poll`" in clock and "ITEM" in clock
    assert any(line.startswith("| (none) | `pad_quit` |") for line in doc)


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))

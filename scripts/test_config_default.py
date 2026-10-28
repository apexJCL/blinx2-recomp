#!/usr/bin/env python3
"""Tests for the host actions in packaging/config.default.toml.

The shipped default names menu.open, and the highest file that names an
action decides all of its bindings (the toolkit's docs/runtime/config.md,
"Host actions"). So the list must repeat the toolkit's own three defaults
and add the Back+L3 chord for hosts that never pass Guide on (the Xbox Game
Bar on Windows, Steam under Proton). The menu ships on (the user,
2026-10-27: closed, it changes no frame or input) and the stats strip off;
the goldens pin both off (analysis/golden/golden.json).

  python3 scripts/test_config_default.py
  uv run pytest scripts/test_config_default.py
"""

import json
import os
import re
import sys

import pytest
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DEFAULT = os.path.join(ROOT, "packaging", "config.default.toml")
ACTIONS_C = os.path.join("src", "enhance", "enhance_actions.c")

TOOLKIT_MENU_OPEN = ["F10", "guide+a", "paddle1"]
CHORD = "back+left_thumb@400"


def _load():
    with open(DEFAULT, "rb") as f:
        return tomllib.load(f)


def test_menu_open_carries_the_chord():
    actions = _load()["input"]["actions"]
    assert actions["menu"]["open"] == TOOLKIT_MENU_OPEN + [CHORD]


# Pad and host-only button names (config.md, "Host actions"); a binding
# made only of these is a pad binding, anything else names a key.
PAD_NAMES = {
    "a", "b", "x", "y", "white", "black", "left_trigger", "right_trigger", "start",
    "back", "left_thumb", "right_thumb", "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "guide", "misc1", "paddle1", "paddle2", "paddle3", "paddle4", "touchpad",
}  # fmt: skip
# A modifier in a key binding is held as either side's key.
MODIFIER_KEYS = {
    "ctrl": {"ctrl", "lctrl", "rctrl"},
    "shift": {"shift", "lshift", "rshift"},
    "alt": {"alt", "lalt", "ralt"},
}


def _keys_of(binding):
    """The keys a binding holds (its modifiers too), lower case; none for a pad one."""
    parts = binding.split("@", 1)[0].split("+")
    if all(p.lower() in PAD_NAMES for p in parts):
        return set()
    keys = {parts[-1].lower()}
    for mod in parts[:-1]:
        keys |= MODIFIER_KEYS.get(mod.lower(), {mod.lower()})
    return keys


def test_action_keys_are_not_the_games():
    # Rule 2: a key the game receives is refused for a host action, so an
    # action's key must not be a control's, the walk key, the release key or
    # a free-camera key (F5 to F8, taken by src/free_camera.c), nor F11,
    # which the toolkit keeps for the fullscreen hotkey (enhance_input.c
    # reserved_use).
    cfg = _load()
    inp = cfg["input"]
    used = {"f11": "the toolkit's fullscreen hotkey"}
    for name, v in cfg["camera"].items():
        if name.endswith(("_toggle", "_key")):
            used[v.lower()] = f"camera.{name}"
    for ctl, v in inp["bindings"].items():
        for k in [v] if isinstance(v, str) else v:
            used[k.lower()] = f"input.bindings.{ctl}"
    for name in ("walk_key", "mouse_release_key"):
        used[inp[name].lower()] = f"input.{name}"
    actions = inp["actions"]
    for name, v in (
        ("menu.open", actions["menu"]["open"]),
        ("overlay.stats", actions["overlay"]["stats"]),
    ):
        for binding in [v] if isinstance(v, str) else v:
            for key in _keys_of(binding):
                assert key not in used, f"{name} '{binding}' takes {used[key]}"


# Upstream's control names (the toolkit's src/input/input_map.c), the only
# ones [input.bindings] takes since the tracker item: an old name is an error there.
CONTROLS = {
    "dpad_up", "dpad_down", "dpad_left", "dpad_right", "start", "back",
    "left_thumb", "right_thumb", "a", "b", "x", "y", "black", "white",
    "left_trigger", "right_trigger", "left_stick_up", "left_stick_down",
    "left_stick_left", "left_stick_right", "right_stick_up", "right_stick_down",
    "right_stick_left", "right_stick_right",
}  # fmt: skip
# Key names the toolkit dropped with the tracker item, with no alias.
OLD_KEYS = re.compile(r"^(kp\w+|lbracket|rbracket|mouseleft|mouseright|mousemiddle)$")


def test_bindings_use_upstream_names():
    bindings = _load()["input"]["bindings"]
    assert set(bindings) <= CONTROLS, set(bindings) - CONTROLS
    for ctl, v in bindings.items():
        for k in [v] if isinstance(v, str) else v:
            assert not OLD_KEYS.match(k.lower()), f"{ctl}: '{k}' is an old key name"


def test_menu_ships_on_strip_off():
    # The one feature key the default sets: the menu arms the
    # actions; the strip stays off until F3 or the menu's Stats page.
    cfg = _load()
    assert cfg["menu"]["enabled"] is True
    assert cfg["overlay"]["stats"] is False


def test_goldens_pin_menu_and_strip_off():
    # RECOMP_CONFIG=none already skips this file; the pins keep the goldens
    # stock even if that pin goes or a player config turns the menu on.
    with open(os.path.join(ROOT, "analysis", "golden", "golden.json"), encoding="utf-8") as f:
        env = json.load(f)["env"]
    assert env["RECOMP_MENU"] == "0"
    assert env["RECOMP_OVERLAY_STATS"] == "0"
    assert env["RECOMP_CONFIG"] == "none"


def test_no_scenario_unpins_the_menu():
    # A scenario's env goes last and beats the shared one (golden.py
    # scenario_env), so none may set these.
    with open(os.path.join(ROOT, "analysis", "golden", "golden.json"), encoding="utf-8") as f:
        scenarios = json.load(f)["scenarios"]
    for name, scen in scenarios.items():
        env = scen.get("env", {})
        for key in ("RECOMP_MENU", "RECOMP_OVERLAY_STATS", "RECOMP_CONFIG"):
            assert key not in env, f"scenario {name} sets {key}"


def _toolkit():
    for d in (
        os.path.join(ROOT, "external", "xboxrecomp"),
        os.path.join(ROOT, "..", "xboxrecomp"),
    ):
        if os.path.exists(os.path.join(d, ACTIONS_C)):
            return d
    return None


def test_toolkit_defaults_are_kept():
    tk = _toolkit()
    if not tk:
        pytest.skip("no toolkit checkout beside the game")
    with open(os.path.join(tk, ACTIONS_C), encoding="utf-8") as f:
        m = re.search(r"menu_open\[\]\s*=\s*\{([^}]*)\}", f.read())
    assert m, "menu_open[] not found in enhance_actions.c"
    tk_defaults = re.findall(r'"([^"]+)"', m.group(1))
    assert tk_defaults == TOOLKIT_MENU_OPEN, "the toolkit's menu.open defaults changed"


def test_toolkit_reads_the_shipped_keys():
    # The keys the shipped file sets are the ones the toolkit arms the
    # actions hook with and registers; a renamed key would do nothing.
    tk = _toolkit()
    if not tk:
        pytest.skip("no toolkit checkout beside the game")
    with open(os.path.join(tk, ACTIONS_C), encoding="utf-8") as f:
        src = f.read()
    assert 'arm_key("menu.enabled"' in src
    assert 'arm_key("overlay.stats"' in src
    assert 'enhance_action_register("overlay.stats"' in src


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

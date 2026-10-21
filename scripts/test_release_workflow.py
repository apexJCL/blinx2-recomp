#!/usr/bin/env python3
"""Tests for .github/workflows/release-wizard.yml: its notes step takes the
tag's CHANGELOG.md section or stops the run. The step's `run:` block is
taken from the workflow and run by bash. The repository's own CHANGELOG.md
is checked too: every release section is dated and linked, and the newest
has notes. The workflow is the CLI's template (`blinx2 workflow --check`),
whose own tests cover the release step.

  python3 scripts/test_release_workflow.py
  python3 -m pytest scripts/test_release_workflow.py

Exit 0 when every test passes.
"""

import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "release-wizard.yml")
REPO_CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

CHANGELOG = """# Changelog

## [Unreleased]

## [2026.10.0-rc.2] - 2026-10-16

### Fixed
- A fix.

## [2026.10.0-rc.1] - 2026-10-15

### Added
- The first release.

[2026.10.0-rc.2]: https://example.invalid/compare/v2026.10.0-rc.1...v2026.10.0-rc.2
"""

_TMP = []


def tmpdir():
    d = tempfile.TemporaryDirectory()
    _TMP.append(d)
    return Path(d.name)


def step_script(name):
    """The `run: |` block of the step called NAME, as bash reads it."""
    with open(WORKFLOW, encoding="utf-8") as f:
        lines = f.read().splitlines()
    (start,) = [i for i, ln in enumerate(lines) if ln.strip() == "- name: " + name]
    i = start + 1
    while lines[i].strip() != "run: |":
        i += 1
    indent = len(lines[i]) - len(lines[i].lstrip())
    body = []
    for ln in lines[i + 1 :]:
        if ln.strip() and len(ln) - len(ln.lstrip()) <= indent:
            break
        body.append(ln)
    return textwrap.dedent("\n".join(body)) + "\n"


def run_notes(tmp_path, tag, changelog=CHANGELOG):
    if changelog is not None:
        (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    script = step_script("Take the tag's section of CHANGELOG.md")
    return subprocess.run(
        ["bash", "-e", "-c", script],
        cwd=tmp_path,
        env=dict(os.environ, TAG=tag),
        capture_output=True,
        text=True,
        check=False,
    )


def test_notes_are_the_tags_section():
    tmp_path = tmpdir()
    r = run_notes(tmp_path, "v2026.10.0-rc.2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "notes.md").read_text(encoding="utf-8") == "### Fixed\n- A fix.\n"


def test_the_last_section_leaves_out_the_links():
    tmp_path = tmpdir()
    r = run_notes(tmp_path, "v2026.10.0-rc.1")
    assert r.returncode == 0, r.stdout + r.stderr
    notes = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert notes == "### Added\n- The first release.\n"


def test_a_tag_without_notes_stops_the_run():
    for tag in ("v2026.10.0-rc.3", "v2026.10.0", "vUnreleased"):
        tmp_path = tmpdir()
        r = run_notes(tmp_path, tag)
        assert r.returncode != 0, tag
        assert "::error file=CHANGELOG.md::" in r.stdout and tag in r.stdout
        assert not (tmp_path / "notes.md").exists()


def test_no_changelog_stops_the_run():
    tmp_path = tmpdir()
    r = run_notes(tmp_path, "v1.0.0", changelog=None)
    assert r.returncode != 0
    assert "::error::v1.0.0 has no CHANGELOG.md" in r.stdout


def test_the_changelog_sections_are_dated_and_linked():
    with open(REPO_CHANGELOG, encoding="utf-8") as f:
        text = f.read()
    heads = re.findall(r"^## \[([^\]]+)\](.*)$", text, re.M)
    links = set(re.findall(r"^\[([^\]]+)\]: https://github.com/apexJCL/blinx2-recomp/", text, re.M))
    assert heads and heads[0] == ("Unreleased", "")
    for version, rest in heads[1:]:
        assert re.fullmatch(r"\d{4}\.\d{1,2}\.\d+(-rc\.\d+)?", version), version
        assert re.fullmatch(r" - \d{4}-\d{2}-\d{2}", rest), version
    assert [v for v, _ in heads if v not in links] == []


def test_the_newest_release_has_notes():
    with open(REPO_CHANGELOG, encoding="utf-8") as f:
        text = f.read()
    newest = re.findall(r"^## \[([^\]]+)\]", text, re.M)[1]
    r = run_notes(tmpdir(), "v" + newest, changelog=text)
    assert r.returncode == 0, r.stdout + r.stderr


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except AssertionError as e:
                fails += 1
                print("FAIL", name, e)
    sys.exit(1 if fails else 0)

#!/usr/bin/env python3
"""Tests for benchlog-retention.py on a temp-dir fixture: protection detection,
newest-N, age cutoff, dry run touches nothing, idempotency.

  python3 scripts/test_benchlog_retention.py

Covers suffixed runs, HHMMSS refs, openspec/notes/--refs sources, named and
scratch entries, symlinks, prune scope, verify-before-remove and orphan .tmp,
with compression run on both the zstd and gzip branches.
"""

import contextlib
import importlib.util
import io
import os
import tempfile
import time
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "retention", os.path.join(HERE, "benchlog-retention.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

MB = 1 << 20


_n = [0]


def stamp(days_ago):
    """Unique stamp `days_ago` days back (distinct time parts, so HHMMSS
    references in one test never protect another test run)."""
    _n[0] += 1
    t = time.time() - days_ago * 86400 - _n[0] * 4217
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(t))


def write(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class Fixture(unittest.TestCase):
    gz = ["--gzip"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.top = self.tmp.name
        self.root = os.path.join(self.top, "cat")
        self.store = os.path.join(self.root, "bench-logs")
        write(os.path.join(self.root, "analysis/golden/golden.json"), b"{}")
        write(os.path.join(self.root, "timeline/entries.json"), b"[]")
        self.stderr = io.StringIO()

    def tearDown(self):
        self.tmp.cleanup()

    def run_dir(self, name, steam=False):
        d = os.path.join(self.store, name)
        write(os.path.join(d, "frames/f0.png"), b"p" * 4096)
        write(os.path.join(d, "game-stdio.log"), b"l" * (MB + 10))
        write(os.path.join(d, "other.log"), b"o" * (MB + 10))
        write(os.path.join(d, "small.log"), b"s")
        if steam:
            write(os.path.join(d, "steam-default.log"), b"z" * 1000)
        return d

    def main(self, *args, keep=0):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(self.stderr):
            R.main(["--root", self.root, "--keep-newest", str(keep)] + self.gz + list(args))
        return buf.getvalue()

    def snapshot(self):
        out = {}
        for d, _, fs in os.walk(self.store):
            for f in fs:
                p = os.path.join(d, f)
                out[p] = os.path.getsize(p)
        return out

    def ex(self, *parts):
        return os.path.exists(os.path.join(self.store, *parts))


class TestProtection(Fixture):
    def test_detects_stamps_in_all_sources(self):
        names = [stamp(60 + i) for i in range(8)]
        write(os.path.join(self.root, "analysis/golden/golden.json"), names[0].encode())
        write(os.path.join(self.root, "analysis/golden/audio.json"), names[1].encode())
        write(os.path.join(self.root, "timeline/sub/e.json"), names[2].encode())
        write(os.path.join(self.root, "RESUME-x.md"), ("see " + names[3]).encode())
        write(os.path.join(self.root, "openspec/changes/a/archive/n.md"), names[4].encode())
        write(os.path.join(self.top, "notes/x/n.md"), names[5].encode())
        extra = os.path.join(self.top, "extra.txt")
        write(extra, names[6].encode())
        for n in names:
            self.run_dir(n)
        text = R.referenced_text(self.root, [extra])
        self.assertEqual(set(R.protection(text, names)), set(names[:7]))

    def test_suffixed_run_cited_by_bare_stamp(self):
        s = stamp(60)
        write(os.path.join(self.root, "TASKS.md"), s.encode())
        got = R.protection(R.referenced_text(self.root), [s + "-realpad-steam-ry"])
        self.assertEqual(got, {s + "-realpad-steam-ry": "referenced"})

    def test_hhmmss_only_reference(self):
        s = stamp(60)
        write(os.path.join(self.root, "analysis/golden/golden.json"),
              ("(%s)" % s[9:]).encode())
        other = "20200101-111111"
        got = R.protection(R.referenced_text(self.root), [s, other])
        self.assertEqual(set(got), {s})

    def test_stamp_boundaries(self):
        write(os.path.join(self.root, "TASKS.md"), b"x20261004050144x")
        got = R.protection(R.referenced_text(self.root), ["20261004-050144"])
        self.assertEqual(got, {})

    def test_named_protected_by_default_and_opt_out(self):
        write(os.path.join(self.root, "TASKS.md"), b"bench-logs/cited-a/ ")
        names = ["cited-a", "cpu-int-1"]
        text = R.referenced_text(self.root)
        self.assertEqual(set(R.protection(text, names)), set(names))
        self.assertEqual(set(R.protection(text, names, include_named=True)), {"cited-a"})

    def test_named_untouched_in_run(self):
        self.run_dir("cpu-int-1")
        os.utime(os.path.join(self.store, "cpu-int-1"), (1, 1))
        self.main("--apply")
        self.assertTrue(self.ex("cpu-int-1", "frames/f0.png"))
        self.main("--apply", "--include-named")
        self.assertFalse(self.ex("cpu-int-1", "frames/f0.png"))

    def test_scratch_excluded_unless_flag(self):
        self.run_dir("_wt")
        os.utime(os.path.join(self.store, "_wt"), (1, 1))
        self.main("--apply", "--include-named")
        self.assertTrue(self.ex("_wt", "frames/f0.png"))
        self.main("--apply", "--include-named", "--include-scratch")
        self.assertFalse(self.ex("_wt", "frames/f0.png"))

    def test_missing_sources_warn(self):
        self.run_dir(stamp(60))
        os.remove(os.path.join(self.root, "timeline/entries.json"))
        self.main()
        err = self.stderr.getvalue()
        self.assertIn("entries.json", err)
        self.assertIn("openspec", err)

    def test_refuses_without_golden_json(self):
        os.remove(os.path.join(self.root, "analysis/golden/golden.json"))
        self.run_dir(stamp(90))
        with self.assertRaises(SystemExit):
            self.main()


class Policy(object):
    def test_age_cutoff(self):
        old, new = stamp(30), stamp(2)
        self.run_dir(old)
        self.run_dir(new)
        self.main("--apply")
        self.assertFalse(self.ex(old, "frames/f0.png"))
        self.assertFalse(self.ex(old, "other.log"))
        self.assertTrue(self.ex(old, "small.log"))
        self.assertTrue(self.ex(new, "frames/f0.png"))
        self.assertTrue(self.ex(new, "other.log"))

    def test_game_stdio_never_compressed(self):
        old = stamp(30)
        self.run_dir(old)
        self.main("--apply")
        self.assertTrue(self.ex(old, "game-stdio.log"))

    def test_newest_n(self):
        names = [stamp(30 + i) for i in range(4)]  # names[0] newest
        for n in names:
            self.run_dir(n)
        self.main("--apply", keep=2)
        for n in names[:2]:
            self.assertTrue(self.ex(n, "frames/f0.png"))
        for n in names[2:]:
            self.assertFalse(self.ex(n, "frames/f0.png"))

    def test_protected_only_steam_log_and_only_when_old(self):
        old, young = stamp(60), stamp(2)
        write(os.path.join(self.root, "RESUME.md"), (old + " " + young).encode())
        self.run_dir(old, steam=True)
        self.run_dir(young, steam=True)
        self.main("--apply")
        self.assertTrue(self.ex(old, "frames/f0.png"))
        self.assertTrue(self.ex(old, "other.log"))
        self.assertFalse(self.ex(old, "steam-default.log"))
        self.assertTrue(any(f.startswith("steam-default.log.") for f in
                            os.listdir(os.path.join(self.store, old))))
        self.assertTrue(self.ex(young, "steam-default.log"))

    def test_prune_deletes_only_unprotected_old_dirs(self):
        keep, gone = stamp(60), stamp(61)
        write(os.path.join(self.root, "RESUME.md"), keep.encode())
        self.run_dir(keep)
        self.run_dir(gone)
        loose = os.path.join(self.store, stamp(70) + ".wav")
        write(loose, b"w" * 100)
        self.main("--apply", "--prune")
        self.assertTrue(os.path.isdir(os.path.join(self.store, keep)))
        self.assertFalse(self.ex(gone))
        # a loose old file is never deleted (it may be compressed instead)
        self.assertTrue(any(os.path.exists(loose + e) for e in ("", ".gz", ".zst")))

    def test_compress_without_prune_never_deletes(self):
        n = stamp(60)
        self.run_dir(n)
        self.main("--apply")
        self.assertTrue(os.path.isdir(os.path.join(self.store, n)))

    def test_symlinks_skipped_and_confined(self):
        outside = os.path.join(self.top, "outside")
        write(os.path.join(outside, "frames/f0.png"), b"p" * 4096)
        n = stamp(60)
        d = self.run_dir(n)
        os.symlink(os.path.join(outside, "frames/f0.png"), os.path.join(d, "link.png"))
        os.symlink(outside, os.path.join(d, "linkdir"))
        sl = stamp(61)
        os.symlink(outside, os.path.join(self.store, sl))
        self.main("--apply", "--prune")
        self.assertTrue(os.path.exists(os.path.join(outside, "frames/f0.png")))
        self.assertTrue(os.path.islink(os.path.join(self.store, sl)))
        self.assertFalse(self.ex(n, "frames/f0.png"))

    def test_orphan_tmp_cleaned(self):
        n = stamp(60)
        d = self.run_dir(n)
        write(os.path.join(d, "frames/f0.png.zst.tmp"), b"junk")
        write(os.path.join(d, "x.log.gz.tmp"), b"junk")
        self.main("--apply")
        self.assertFalse(self.ex(n, "frames/f0.png.zst.tmp"))
        self.assertFalse(self.ex(n, "x.log.gz.tmp"))

    def test_failed_verify_keeps_original_and_continues(self):
        n = stamp(60)
        self.run_dir(n)
        orig = R.verify_file
        calls = []

        def bad(path, use_zstd):
            calls.append(path)
            if len(calls) == 1:
                raise EOFError("corrupt")
            return orig(path, use_zstd)
        R.verify_file = bad
        try:
            self.main("--apply")
        finally:
            R.verify_file = orig
        self.assertIn("compress failed", self.stderr.getvalue())
        survivors = [f for f in ("frames/f0.png", "other.log") if self.ex(n, f)]
        self.assertEqual(len(survivors), 1)
        for dd, _, fs in os.walk(os.path.join(self.store, n)):
            self.assertFalse([f for f in fs if f.endswith(".tmp")])

    def test_dry_run_touches_nothing(self):
        self.run_dir(stamp(60))
        before = self.snapshot()
        out = self.main()
        self.assertEqual(before, self.snapshot())
        self.assertIn("DRY RUN", out)

    def test_idempotent(self):
        self.run_dir(stamp(60))
        self.run_dir(stamp(40), steam=True)
        self.main("--apply")
        once = self.snapshot()
        out = self.main("--apply")
        self.assertEqual(once, self.snapshot())
        self.assertIn("0 with action", out)


class TestPolicyGzip(Policy, Fixture):
    gz = ["--gzip"]


@unittest.skipUnless(shutil.which("zstd"), "zstd not installed")
class TestPolicyZstd(Policy, Fixture):
    gz = []

    def test_uses_zstd(self):
        n = stamp(60)
        self.run_dir(n)
        self.main("--apply")
        self.assertTrue(self.ex(n, "frames/f0.png.zst"))
        subprocess.run(["zstd", "-q", "-t", os.path.join(self.store, n, "frames/f0.png.zst")],
                       check=True)


if __name__ == "__main__":
    unittest.main()

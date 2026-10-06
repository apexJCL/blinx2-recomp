#!/usr/bin/env python3
"""Retention for the bench-logs store. Default is a DRY RUN; --apply acts.

  python3 scripts/benchlog-retention.py                 # dry run, table + totals
  python3 scripts/benchlog-retention.py --apply         # compress old raw files
  python3 scripts/benchlog-retention.py --apply --prune # delete old stamp dirs

Protected (never compressed or deleted), first match wins:
  - symlinked entries and `_*` scratch entries (--include-scratch lifts the latter)
  - runs referenced by a stamp YYYYMMDD-HHMMSS anywhere in: analysis/golden/
    golden.json, audio.json, timeline/**, RESUME*.md, TASKS.md, OPEN_QUESTIONS.md,
    openspec/**/*.md, ../notes/**/*.md and any --refs PATH. An entry whose name
    CONTAINS a referenced stamp counts (suffixed runs), and a bare 6-digit
    token (HHMMSS) protects every stamped run with that time part (may
    over-protect; that is intended).
  - non-stamp-named entries (agent evidence nobody cites); --include-named
    treats them like stamped runs, protected only when their name is cited
  - the newest N stamped runs (--keep-newest, default 30)
  - anything younger than D days (--days, default 14)

An unprotected run older than D days has *.png *.bmp *.raw *.wav and *.log over
1 MB compressed in place (zstd if on PATH, else gzip; --gzip forces gzip), each
file verified before the original is removed. With --prune the whole stamp-named
directory is deleted instead (loose files never are). Nothing is deleted without
--prune. game-stdio.log is never compressed (timeline/charts.py globs it).
steam-default.log is compressed in any run, protected or not, once older than D
days (bench.sh symbolize reads it for recent crashed runs). Re-running is a no-op.

Constraint: golden.py reads frames/*.png|bmp and game-stdio.log from the runs it
checks, so a run you may re-check with golden.py must be protected or younger
than D days. Stdlib only.
"""

import argparse
import datetime
import gzip
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)
STAMP_RE = re.compile(r"(?<!\d)(\d{8}-\d{6})(?!\d)")
SIX_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
RAW_EXT = (".png", ".bmp", ".raw", ".wav")
BIG_LOG = 1 << 20
COMPRESSED = (".zst", ".gz")
STD_FILES = ["analysis/golden/golden.json", "analysis/golden/audio.json",
             "TASKS.md", "OPEN_QUESTIONS.md"]


def warn(msg):
    print("WARNING: " + msg, file=sys.stderr)


def _walk_files(top, suffix=None):
    out = []
    for d, _, fs in os.walk(top, followlinks=False):
        for f in fs:
            p = os.path.join(d, f)
            if os.path.islink(p):
                continue
            if suffix is None or f.endswith(suffix):
                out.append(p)
    return out


def ref_paths(root, extra=()):
    """(paths, warnings) of every file that may name a run."""
    paths, warns = [], []
    for rel in STD_FILES:
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            paths.append(p)
        else:
            warns.append("ref source missing: %s" % p)
    res = [n for n in sorted(os.listdir(root)) if n.startswith("RESUME") and n.endswith(".md")]
    if not res:
        warns.append("ref source missing: %s/RESUME*.md" % root)
    paths += [os.path.join(root, n) for n in res]
    tl = os.path.join(root, "timeline")
    if os.path.isdir(tl):
        paths += _walk_files(tl)
    else:
        warns.append("ref source missing: %s" % tl)
    if not os.path.isfile(os.path.join(tl, "entries.json")):
        warns.append("LOUD: timeline/entries.json not found under %s; timeline "
                     "references are NOT protected" % root)
    for rel, suffix in (("openspec", ".md"), (os.path.join(os.pardir, "notes"), ".md")):
        d = os.path.join(root, rel)
        if os.path.isdir(d):
            paths += _walk_files(d, suffix)
        else:
            warns.append("ref source missing: %s" % os.path.normpath(d))
    for e in extra:
        if os.path.isdir(e):
            paths += _walk_files(e)
        elif os.path.isfile(e):
            paths.append(e)
        else:
            warns.append("--refs path missing: %s" % e)
    return paths, warns


def referenced_text(root, extra=(), warns=None):
    paths, w = ref_paths(root, extra)
    if warns is not None:
        warns.extend(w)
    out = []
    for p in paths:
        try:
            with open(p, errors="replace") as f:
                out.append(f.read())
        except OSError:
            pass
    return "\n".join(out)


def protection(text, names, include_named=False):
    """name -> reason for entries `text` protects by reference or by name."""
    stamps = set(STAMP_RE.findall(text))
    six = set(SIX_RE.findall(text))
    hit = {}
    for n in names:
        m = STAMP_RE.search(n)
        if m:
            st = m.group(1)
            if st in stamps:
                hit[n] = "referenced"
            elif st[9:] in six:
                hit[n] = "referenced (HHMMSS)"
        elif not include_named:
            hit[n] = "named evidence"
        elif re.search(r"(?<![\w.-])" + re.escape(n) + r"(?![\w-])", text):
            hit[n] = "referenced (name)"
    return hit


def tree_size(p):
    if os.path.islink(p):
        return 0
    if os.path.isfile(p):
        return os.lstat(p).st_size
    t = 0
    for f in _walk_files(p):
        try:
            t += os.lstat(f).st_size
        except OSError:
            pass
    return t


def run_time(path, name):
    """Run start time: from the stamp in the name, else mtime."""
    m = STAMP_RE.search(name)
    if m:
        try:
            return datetime.datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").timestamp()
        except ValueError:
            pass
    return os.stat(path).st_mtime


def compressible(path, protected, old):
    """Should this file be compressed? `old` = run older than --days."""
    base = os.path.basename(path)
    if base.endswith(COMPRESSED) or base == "game-stdio.log":
        return False
    if base == "steam-default.log":
        return old
    if protected or not old:
        return False
    if base.lower().endswith(RAW_EXT):
        return True
    return base.endswith(".log") and os.path.getsize(path) > BIG_LOG


def files_of(entry, store_real):
    cands = [entry] if os.path.isfile(entry) and not os.path.islink(entry) else _walk_files(entry)
    return [f for f in cands if os.path.realpath(f).startswith(store_real + os.sep)]


def verify_file(path, use_zstd):
    """Raise if the compressed file at `path` is not intact."""
    if use_zstd:
        subprocess.run(["zstd", "-q", "-t", path], check=True)
    else:
        with gzip.open(path, "rb") as g:
            while g.read(1 << 20):
                pass


def compress_file(path, use_zstd):
    """Compress to path.zst/.gz via a temp file, verify, keep mtime, remove original."""
    st = os.stat(path)
    dst = path + (".zst" if use_zstd else ".gz")
    tmp = dst + ".tmp"
    try:
        if use_zstd:
            subprocess.run(["zstd", "-q", "-f", "-o", tmp, path], check=True)
        else:
            with open(path, "rb") as fi, open(tmp, "wb") as fo:
                with gzip.GzipFile(fileobj=fo, mode="wb", compresslevel=6, mtime=0) as g:
                    shutil.copyfileobj(fi, g)
        verify_file(tmp, use_zstd)
        os.utime(tmp, (st.st_atime, st.st_mtime))
        os.replace(tmp, dst)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    os.remove(path)
    return dst


def clean_stale_tmp(store_real):
    n = 0
    for f in _walk_files(store_real):
        if f.endswith((".zst.tmp", ".gz.tmp")):
            os.remove(f)
            n += 1
    return n


def plan(store, text, keep_newest, days, prune, now, include_named=False,
         include_scratch=False):
    names = sorted(n for n in os.listdir(store) if not n.startswith("."))
    real = [n for n in names if not os.path.islink(os.path.join(store, n))]
    prot = protection(text, real, include_named)
    items = [(run_time(os.path.join(store, n), n), n) for n in real]
    stamped = sorted((t, n) for t, n in items if STAMP_RE.search(n))
    newest = {n for _, n in stamped[-keep_newest:]} if keep_newest > 0 else set()
    cutoff = now - days * 86400
    rows = []
    for n in names:
        path = os.path.join(store, n)
        row = dict(name=n, path=path, old=False, before=tree_size(path), protected=True)
        if n not in real:
            row["reason"] = "symlink, skipped"
        else:
            t = run_time(path, n)
            row["old"] = t < cutoff
            if n.startswith("_") and not include_scratch:
                row["reason"] = "scratch"
            elif n in prot:
                row["reason"] = prot[n]
            elif n in newest:
                row["reason"] = "newest %d" % keep_newest
            elif not row["old"]:
                row["reason"] = "younger than %dd" % days
            else:
                row["reason"], row["protected"] = "older than %dd, unreferenced" % days, False
        row["prune"] = (prune and not row["protected"] and os.path.isdir(path)
                        and bool(STAMP_RE.search(n)))
        rows.append(row)
    return rows


def fmt(n):
    for u in ("B", "K", "M", "G", "T"):
        if n < 1024 or u == "T":
            return "%d%s" % (n, u) if u == "B" else "%.1f%s" % (n, u)
        n /= 1024.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="cat checkout holding analysis/, timeline/, RESUME*.md")
    ap.add_argument("--store", help="bench-logs dir (default ROOT/bench-logs)")
    ap.add_argument("--days", type=float, default=14)
    ap.add_argument("--keep-newest", type=int, default=30)
    ap.add_argument("--refs", action="append", default=[], metavar="PATH",
                    help="extra file or dir whose text names runs (repeatable)")
    ap.add_argument("--include-named", action="store_true",
                    help="treat non-stamp-named entries like stamped runs")
    ap.add_argument("--include-scratch", action="store_true",
                    help="allow actions on _* scratch entries")
    ap.add_argument("--gzip", action="store_true", help="use gzip even if zstd exists")
    ap.add_argument("--apply", action="store_true", help="act (default: dry run)")
    ap.add_argument("--prune", action="store_true",
                    help="delete old unprotected stamp dirs instead of compressing")
    ap.add_argument("--quiet", action="store_true", help="totals only")
    a = ap.parse_args(argv)

    store = a.store or os.path.join(a.root, "bench-logs")
    if not os.path.isdir(store):
        sys.exit("store not found: %s" % store)
    store_real = os.path.realpath(store)
    if not os.path.isfile(os.path.join(a.root, "analysis/golden/golden.json")):
        sys.exit("no analysis/golden/golden.json under %s: refusing to guess "
                 "protected runs (worktrees lack the untracked analysis/; "
                 "pass --root <main cat checkout>)" % a.root)
    use_zstd = shutil.which("zstd") is not None and not a.gzip
    warns = []
    text = referenced_text(a.root, a.refs, warns)
    for w in warns:
        warn(w)
    if a.apply:
        clean_stale_tmp(store_real)
    rows = plan(store_real, text, a.keep_newest, a.days, a.prune, time.time(),
                a.include_named, a.include_scratch)

    tot_before = tot_after = 0
    n_act = failures = 0
    out = []
    reasons = {}
    for r in rows:
        key = r["reason"] if not r["reason"].startswith(("newest", "younger")) else r["reason"].split(" ")[0]
        reasons[key] = reasons.get(key, 0) + 1
        files = files_of(r["path"], store_real) if not os.path.islink(r["path"]) else []
        todo = [f for f in files if compressible(f, r["protected"], r["old"])]
        if r["prune"]:
            action = "delete"
        elif todo:
            action = "compress %d file(s)" % len(todo)
        else:
            action = "none"
        after = r["before"]
        if a.apply and action != "none":
            if r["prune"]:
                shutil.rmtree(r["path"])
                after = 0
            else:
                for f in todo:
                    try:
                        compress_file(f, use_zstd)
                    except (subprocess.CalledProcessError, OSError, EOFError) as e:
                        failures += 1
                        warn("compress failed, original kept: %s (%s)" % (f, e))
                after = tree_size(r["path"])
            n_act += 1
        elif action != "none":
            n_act += 1
            after = None
        tot_before += r["before"]
        tot_after += r["before"] if after is None else after
        out.append((r["name"], fmt(r["before"]), "-" if after is None else fmt(after),
                    action, r["reason"]))

    if not a.quiet:
        print("%-28s %9s %9s  %-20s %s" % ("run", "before", "after", "action", "reason"))
        for o in out:
            print("%-28s %9s %9s  %-20s %s" % o)
    n_prot = sum(1 for r in rows if r["protected"])
    print("\n%s: %d entries, %d protected, %d with action (%s)" % (
        "APPLIED" if a.apply else "DRY RUN", len(rows), n_prot, n_act,
        "prune" if a.prune else "compress, %s" % ("zstd" if use_zstd else "gzip")))
    print("by reason: " + ", ".join("%s=%d" % kv for kv in sorted(reasons.items())))
    if a.apply:
        print("total before %s, after %s; %d failure(s)" % (
            fmt(tot_before), fmt(tot_after), failures))
    else:
        print("total %s (after sizes unknown in a dry run; nothing touched)" % fmt(tot_before))
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

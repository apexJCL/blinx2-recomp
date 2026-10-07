#!/usr/bin/env python3
"""Compare two packaged bundles file by file: the gate that a change to the
packaging code (the move to xboxrecomp-cli) left every payload byte alone.
Standard library only, Python 3.9 or newer.

  compare-bundles.py list BUNDLE > listing.json
  compare-bundles.py diff A B          (each a bundle or a listing)

A bundle is what `blinx2 package` writes: the steamos .tar, the windows
folder (its game_files/ and installer) or a macOS .app; run package with
--keep-stage and pass the stage too (dist/.stage-windows/<payload>, the
payload as it was before the installer took it; dist/.stage-macos/dmg/
<app>.app for macos), since the installer and the DMG compress it.

The two bundles come from different commits or builds, so their version
strings differ (<time>-c<game sha>-...): every name and every text file is
compared with the bundle's version (from its manifest.json), its game
commit and its output folder replaced by placeholders (a bundle without a
manifest, the windows folder, takes the version from its name). A PE file
is also compared with its link timestamps (COFF header and debug
directory) and checksum zeroed. The diff lists each file that still
differs. These are reported apart:
- manifest.json and SHA256SUMS, which name the build time and the sources,
  with the manifest's fields that differ;
- the windows installer, which compresses the payload (compare the stage);
- a macOS signature (_CodeSignature/), when CodeResources differs only for
  files that differ for the version.
Exit 0 when nothing else differs, 1 otherwise.
"""

import base64
import hashlib
import json
import os
import plistlib
import struct
import sys
import tarfile

TEXT_MAX = 4 << 20
EXPECTED = ("manifest.json", "SHA256SUMS")
# The windows installer compresses the payload (manifest included): the
# stage beside it is what is compared.
INSTALLER = "-setup.exe"
# A macOS bundle's signature: CodeResources hashes every resource, the
# rest signs CodeResources. CodeResources is compared without the entries
# of the files that differ for the version; the rest then follows it.
SIG_DIR = "_CodeSignature/"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pe_normalised(data):
    """The bytes with the link timestamps and the checksum zeroed: the COFF
    TimeDateStamp, the optional header's CheckSum, and each debug directory
    entry's TimeDateStamp (lld writes the link time there too). None when
    data is not a PE image."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    (off,) = struct.unpack_from("<I", data, 0x3C)
    if off + 0x5C > len(data) or data[off : off + 4] != b"PE\0\0":
        return None
    b = bytearray(data)
    b[off + 8 : off + 12] = b"\0\0\0\0"  # TimeDateStamp
    b[off + 0x58 : off + 0x5C] = b"\0\0\0\0"  # CheckSum (PE32 and PE32+ alike)
    nsec, opt_size = struct.unpack_from("<H12xH", data, off + 6)
    opt = off + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dirs = opt + (96 if magic == 0x10B else 112)  # the data directories
    if dirs + 7 * 8 > opt + opt_size:
        return bytes(b)
    rva, size = struct.unpack_from("<II", data, dirs + 6 * 8)  # IMAGE_DIRECTORY_ENTRY_DEBUG
    sec = opt + opt_size
    for i in range(nsec):
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, sec + 40 * i + 8)
        if va <= rva < va + max(vsize, rawsize):
            pos = raw + rva - va
            for e in range(pos, pos + size - 27, 28):
                b[e + 4 : e + 8] = b"\0\0\0\0"  # IMAGE_DEBUG_DIRECTORY.TimeDateStamp
            break
    return bytes(b)


def entry(data, subs):
    e = {"sha256": sha(data), "size": len(data)}
    if len(data) <= TEXT_MAX:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is not None:
            for old, new in subs:
                if old:
                    text = text.replace(old, new)
            e["norm"] = sha(text.encode())
    pe = pe_normalised(data)
    if pe is not None:
        e["pe_norm"] = sha(pe)
    if data.startswith(b"<?xml") and b"<key>files2</key>" in data:
        try:
            pl = plistlib.loads(data)
        except Exception:
            pl = None
        if isinstance(pl, dict):
            # files2's per-file hashes, comparable entry by entry.
            e["sig_files"] = {
                k: base64.b64encode(
                    v["hash2"] if isinstance(v, dict) and "hash2" in v else b""
                ).decode()
                for k, v in pl.get("files2", {}).items()
            }
    return e


def walk(top):
    """(relative path, bytes reader, mode) for every file under top."""
    for d, dirs, files in os.walk(top):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(d, f)
            if os.path.islink(p):
                yield os.path.relpath(p, top), (lambda p=p: b"LINK:" + os.readlink(p).encode()), 0
                continue
            yield (
                os.path.relpath(p, top).replace(os.sep, "/"),
                (lambda p=p: open(p, "rb").read()),
                os.stat(p).st_mode & 0o777,
            )


def tar_items(path):
    with tarfile.open(path) as t:
        for m in t.getmembers():
            if m.isfile():
                data = t.extractfile(m).read()
                yield m.name, (lambda data=data: data), m.mode
            else:
                yield m.name + "/", (lambda: b""), m.mode


def find_manifest(items):
    for rel, read, _ in items:
        if rel.endswith("manifest.json"):
            return json.loads(read())
    return None


def listing(bundle):
    bundle = os.path.abspath(bundle.rstrip("/"))
    items = list(tar_items(bundle) if bundle.endswith(".tar") else walk(bundle))
    man = find_manifest(items) or {}
    # Without a manifest (the windows folder: it is in the installer), the
    # version is the bundle's name between <app>- and -<target>.
    version = man.get("version", "") or (
        os.path.basename(bundle).split("-", 1)[1].rsplit("-", 1)[0]
        if os.path.basename(bundle).count("-") >= 2
        else ""
    )
    game = next(iter(man.get("sources", {}).values()), {}).get("commit", "")
    out = os.path.dirname(bundle)
    if os.path.basename(out).startswith(".stage-"):
        out = os.path.dirname(out)
    subs = [(version, "@VERSION@"), (game[:7], "@GAMESHA@"), (out, "@OUT@")]
    files = {}
    for rel, read, mode in items:
        name = rel.replace(version, "@VERSION@") if version else rel
        e = entry(read(), subs)
        e["mode"] = oct(mode)
        files[name] = e
    return {"bundle": os.path.basename(bundle), "version": version, "manifest": man, "files": files}


def load(p):
    if p.endswith(".json") and os.path.isfile(p):
        with open(p) as f:
            return json.load(f)
    return listing(p)


def same(a, b):
    if a["sha256"] == b["sha256"]:
        return "equal"
    if a.get("norm") and a.get("norm") == b.get("norm"):
        return "equal but for the version"
    if a.get("pe_norm") and a.get("pe_norm") == b.get("pe_norm"):
        return "equal but for the PE timestamp"
    return None


def manifest_fields(a, b, prefix=""):
    out = []
    for k in sorted(set(a) | set(b)):
        if k == "files":
            continue
        x, y = a.get(k), b.get(k)
        if isinstance(x, dict) and isinstance(y, dict):
            out += manifest_fields(x, y, prefix + k + ".")
        elif x != y:
            out.append("%s%s: %r -> %r" % (prefix, k, x, y))
    return out


def signature_follows(fa, fb, name, versioned):
    """A CodeResources whose entries differ only for files that differ for
    the version."""
    a, b = fa[name].get("sig_files"), fb[name].get("sig_files")
    if a is None or b is None or set(a) != set(b):
        return False
    top = name[: -len(SIG_DIR + "CodeResources")]
    return all(a[k] == b[k] or top + k in versioned for k in a)


def diff(a, b):
    fa, fb = a["files"], b["files"]
    bad, notes = [], []
    versioned = {
        n for n in set(fa) & set(fb) if fa[n]["sha256"] != fb[n]["sha256"] and same(fa[n], fb[n])
    } | {n for n in set(fa) & set(fb) if n.rsplit("/", 1)[-1] in EXPECTED}
    sig_ok = {
        n.rsplit(SIG_DIR, 1)[0]
        for n in set(fa) & set(fb)
        if n.endswith(SIG_DIR + "CodeResources") and signature_follows(fa, fb, n, versioned)
    }
    for name in sorted(set(fa) | set(fb)):
        base = name.rsplit("/", 1)[-1]
        if (
            name.endswith(INSTALLER)
            and any(n.endswith(INSTALLER) for n in fa)
            and any(n.endswith(INSTALLER) for n in fb)
        ):
            notes.append("%s: the installer (compare its stage)" % name)
            continue
        if name not in fa or name not in fb:
            bad.append("%s: only in %s" % (name, "B" if name not in fa else "A"))
            continue
        how = same(fa[name], fb[name])
        if how is None and SIG_DIR in name and name.rsplit(SIG_DIR, 1)[0] in sig_ok:
            notes.append("%s: the signature over the files above" % name)
        elif base in EXPECTED:
            notes.append("%s: %s" % (name, how or "differs (expected: build time, sources)"))
        elif how is None:
            bad.append("%s: differs" % name)
        elif how != "equal":
            notes.append("%s: %s" % (name, how))
        if how and fa[name]["mode"] != fb[name]["mode"]:
            bad.append("%s: mode %s -> %s" % (name, fa[name]["mode"], fb[name]["mode"]))
    fields = manifest_fields(a.get("manifest") or {}, b.get("manifest") or {})
    return bad, notes, fields


def main(argv):
    if len(argv) == 2 and argv[0] == "list":
        json.dump(listing(argv[1]), sys.stdout, indent=1, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    if len(argv) == 3 and argv[0] == "diff":
        a, b = load(argv[1]), load(argv[2])
        bad, notes, fields = diff(a, b)
        print(
            "A: %s (%d files)\nB: %s (%d files)"
            % (a["bundle"], len(a["files"]), b["bundle"], len(b["files"]))
        )
        for n in notes:
            print("  note: " + n)
        for f in fields:
            print("  manifest: " + f)
        for x in bad:
            print("  DIFFERS: " + x)
        print("same payload" if not bad else "%d files differ" % len(bad))
        return 0 if not bad else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

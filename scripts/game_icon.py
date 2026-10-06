#!/usr/bin/env python3
"""The app icon from the game's own title image: the XBE's $$XTIMAGE
section (an XPR0 texture, DXT1 128x128 in BLiNX 2), decoded and written as
icon.png, BLiNX2.icns and BLiNX2.ico. Standard library only, Python 3.9 or
newer; used by `blinx2 package`, and as a CLI for debugging:

  game_icon.py XBE OUTDIR [--force]

The image is game data: OUTDIR must be a packaging build dir (build-*/),
dist/, or a folder outside this tree. Without a usable image the icon is a
generic one drawn here, with no game data in it. The files are rebuilt only
when the XBE (or this file's VERSION) changes: OUTDIR/icon.key.
"""

import argparse
import hashlib
import json
import math
import os
import struct
import sys
import zlib

VERSION = 1
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "BLiNX2"
OUTPUTS = ("icon.png", NAME + ".icns", NAME + ".ico")

# Xbox D3DFORMAT codes of the compressed formats (not swizzled on the Xbox,
# so their 4x4 blocks run in plain row order).
FMT_DXT1, FMT_DXT3, FMT_DXT5 = 0x0C, 0x0E, 0x0F
MAX_SIDE = 1024


class NoImage(Exception):
    """No usable title image; the message is the reason."""


# ── XBE and XPR0 ─────────────────────────────────────────────────────────

def xbe_section(data, name):
    """The raw bytes of the section called name, or None. Header: base
    address at 0x104, section count at 0x11C, section headers' address at
    0x120; each header is 56 bytes: flags, vaddr, vsize, raw offset, raw
    size, name address, ..."""
    if len(data) < 0x124 or data[:4] != b"XBEH":
        raise NoImage("not an XBE")
    base, = struct.unpack_from("<I", data, 0x104)
    count, = struct.unpack_from("<I", data, 0x11C)
    hdrs, = struct.unpack_from("<I", data, 0x120)
    off = hdrs - base
    if count > 4096 or off < 0 or off + count * 56 > len(data):
        raise NoImage("XBE section table out of range")
    want = name.encode("ascii")
    for i in range(count):
        _, _, _, raw, size, name_va = struct.unpack_from("<6I", data, off + i * 56)
        n = name_va - base
        if 0 <= n < len(data) and data[n:n + len(want) + 1] == want + b"\0":
            if raw + size > len(data):
                raise NoImage("%s runs past the end of the XBE" % name)
            return data[raw:raw + size]
    return None


def title_image_bytes(xbe):
    """The XPR0 bytes of the title image: $$XTIMAGE, else $$XSIMAGE."""
    for name in ("$$XTIMAGE", "$$XSIMAGE"):
        sec = xbe_section(xbe, name)
        if sec:
            return sec
    raise NoImage("the XBE has no title image section")


def parse_xpr0(blob):
    """(format, width, height, pixel bytes) of the first texture. The file
    header is 'XPR0', total size, header size; the D3DTexture follows:
    Common, Data, Lock, Format, Size, so Format sits at byte 24 and the
    pixels at header size + Data."""
    if len(blob) < 32 or blob[:4] != b"XPR0":
        raise NoImage("title image is not XPR0")
    _, header = struct.unpack_from("<II", blob, 4)
    data_off, _, fmt = struct.unpack_from("<III", blob, 16)
    kind = (fmt >> 8) & 0xFF
    w = 1 << ((fmt >> 20) & 0xF)
    h = 1 << ((fmt >> 24) & 0xF)
    if kind not in (FMT_DXT1, FMT_DXT3, FMT_DXT5):
        raise NoImage("title image format 0x%02X is not DXT1/3/5" % kind)
    if w > MAX_SIDE or h > MAX_SIDE or w < 4 or h < 4:
        raise NoImage("title image is %dx%d" % (w, h))
    start = header + data_off
    need = (w // 4) * (h // 4) * (8 if kind == FMT_DXT1 else 16)
    if start + need > len(blob):
        raise NoImage("title image data is truncated")
    return kind, w, h, blob[start:start + need]


# ── DXT ──────────────────────────────────────────────────────────────────

def _565(c):
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def _palette(c0, c1, four):
    a, b = _565(c0), _565(c1)
    if four or c0 > c1:
        return [a + (255,), b + (255,),
                tuple((2 * x + y + 1) // 3 for x, y in zip(a, b)) + (255,),
                tuple((x + 2 * y + 1) // 3 for x, y in zip(a, b)) + (255,)]
    return [a + (255,), b + (255,), tuple((x + y) // 2 for x, y in zip(a, b)) + (255,),
            (0, 0, 0, 0)]


def _alpha5(a0, a1):
    if a0 > a1:
        return [a0, a1] + [((7 - i) * a0 + i * a1 + 3) // 7 for i in range(1, 7)]
    return [a0, a1] + [((5 - i) * a0 + i * a1 + 2) // 5 for i in range(1, 5)] + [0, 255]


def decode_dxt(kind, w, h, data):
    """RGBA8 rows (a list of h bytearrays of 4*w bytes)."""
    rows = [bytearray(4 * w) for _ in range(h)]
    size = 8 if kind == FMT_DXT1 else 16
    pos = 0
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            blk = data[pos:pos + size]
            pos += size
            col = blk[size - 8:]
            c0, c1, idx = struct.unpack("<HHI", col)
            pal = _palette(c0, c1, kind != FMT_DXT1)
            alphas = None
            if kind == FMT_DXT3:
                bits, = struct.unpack("<Q", blk[:8])
                alphas = [((bits >> (4 * i)) & 15) * 17 for i in range(16)]
            elif kind == FMT_DXT5:
                ap = _alpha5(blk[0], blk[1])
                bits = int.from_bytes(blk[2:8], "little")
                alphas = [ap[(bits >> (3 * i)) & 7] for i in range(16)]
            for i in range(16):
                r, g, b, a = pal[(idx >> (2 * i)) & 3]
                if alphas is not None:
                    a = alphas[i]
                row = rows[by + i // 4]
                o = 4 * (bx + i % 4)
                row[o:o + 4] = bytes((r, g, b, a))
    return rows


# ── images: (w, h, rows of RGBA bytes) ───────────────────────────────────

def _premul(rows):
    out = []
    for row in rows:
        f = []
        for o in range(0, len(row), 4):
            a = row[o + 3]
            f.extend((row[o] * a / 255.0, row[o + 1] * a / 255.0, row[o + 2] * a / 255.0, float(a)))
        out.append(f)
    return out


def _unpremul(frows):
    out = []
    for f in frows:
        row = bytearray(len(f))
        for o in range(0, len(f), 4):
            a = min(255.0, max(0.0, f[o + 3]))
            if a < 0.5:
                continue
            k = 255.0 / a
            row[o] = min(255, max(0, int(f[o] * k + 0.5)))
            row[o + 1] = min(255, max(0, int(f[o + 1] * k + 0.5)))
            row[o + 2] = min(255, max(0, int(f[o + 2] * k + 0.5)))
            row[o + 3] = int(a + 0.5)
        out.append(row)
    return out


def _cubic(t):
    """Catmull-Rom (a = -0.5)."""
    t = abs(t)
    if t < 1:
        return 1.5 * t ** 3 - 2.5 * t ** 2 + 1
    if t < 2:
        return -0.5 * t ** 3 + 2.5 * t ** 2 - 4 * t + 2
    return 0.0


def _taps(src, dst):
    """Per output index, [(source index, weight)]: Catmull-Rom when
    enlarging, an area average when shrinking."""
    out = []
    scale = src / dst
    for x in range(dst):
        if dst >= src:
            c = (x + 0.5) * scale - 0.5
            i = math.floor(c)
            taps = [(min(src - 1, max(0, j)), _cubic(c - j)) for j in range(i - 1, i + 3)]
        else:
            lo, hi = x * scale, (x + 1) * scale
            taps = []
            j = int(lo)
            while j < hi and j < src:
                taps.append((j, min(hi, j + 1) - max(lo, j)))
                j += 1
        s = sum(wt for _, wt in taps)
        out.append([(j, wt / s) for j, wt in taps])
    return out


def resize(img, dw, dh):
    """Separable resize in premultiplied alpha (so transparent pixels do not
    bleed their colour into the edge)."""
    sw, sh, rows = img
    if (sw, sh) == (dw, dh):
        return img
    f = _premul(rows)
    tx = _taps(sw, dw)
    horiz = []
    for row in f:
        out = [0.0] * (4 * dw)
        for x, taps in enumerate(tx):
            r = g = b = a = 0.0
            for j, wt in taps:
                o = 4 * j
                r += row[o] * wt
                g += row[o + 1] * wt
                b += row[o + 2] * wt
                a += row[o + 3] * wt
            o = 4 * x
            out[o], out[o + 1], out[o + 2], out[o + 3] = r, g, b, a
        horiz.append(out)
    ty = _taps(sh, dh)
    res = []
    for taps in ty:
        if len(taps) == 1:
            res.append(list(horiz[taps[0][0]]))
            continue
        out = [0.0] * (4 * dw)
        for j, wt in taps:
            src = horiz[j]
            for o in range(4 * dw):
                out[o] += src[o] * wt
        res.append(out)
    return dw, dh, _unpremul(res)


def rounded_rect_layout(img, size):
    """macOS icon grid: the art at 824/1024 of the canvas, in a rounded
    rectangle with a 185/1024 corner radius, on a transparent canvas, so the
    icon sits the size of the others in the Dock and Finder."""
    body = max(1, round(size * 824 / 1024))
    radius = body * 185.0 / 824
    art = resize(img, body, body)[2]
    pad = (size - body) // 2
    rows = [bytearray(4 * size) for _ in range(size)]
    for y in range(body):
        for x in range(body):
            # Coverage of the rounded corner, anti-aliased over one pixel.
            cx = min(max(x + 0.5, radius), body - radius)
            cy = min(max(y + 0.5, radius), body - radius)
            d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            cov = min(1.0, max(0.0, radius - d + 0.5))
            if cov <= 0:
                continue
            o = 4 * x
            r, g, b, a = art[y][o:o + 4]
            p = 4 * (x + pad)
            rows[y + pad][p:p + 4] = bytes((r, g, b, int(a * cov + 0.5)))
    return size, size, rows


def generic_icon(size=128):
    """No game data: a neutral rounded square with a vertical gradient."""
    rows = []
    for y in range(size):
        t = y / (size - 1)
        c = (int(70 + 40 * (1 - t)), int(90 + 50 * (1 - t)), int(120 + 60 * (1 - t)), 255)
        rows.append(bytearray(bytes(c) * size))
    return size, size, rows


# ── files ────────────────────────────────────────────────────────────────

def png_bytes(img):
    w, h, rows = img

    def chunk(kind, body):
        c = kind + body
        return struct.pack(">I", len(body)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    raw = b"".join(b"\0" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# icns PNG entries: type, pixel size (ic10 is 512@2x).
ICNS_TYPES = (("icp4", 16), ("icp5", 32), ("ic07", 128), ("ic08", 256), ("ic09", 512),
              ("ic10", 1024))
ICO_SIZES = (16, 32, 48, 256)


def icns_bytes(pngs):
    """pngs: {pixel size: png bytes}."""
    body = b"".join(t.encode() + struct.pack(">I", 8 + len(pngs[s])) + pngs[s]
                    for t, s in ICNS_TYPES)
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def ico_bytes(pngs):
    """PNG-embedded entries, which Windows Vista and newer read."""
    head = struct.pack("<HHH", 0, 1, len(ICO_SIZES))
    off = 6 + 16 * len(ICO_SIZES)
    dirs, blobs = b"", b""
    for s in ICO_SIZES:
        p = pngs[s]
        dirs += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(p), off)
        off += len(p)
        blobs += p
    return head + dirs + blobs


def build_icons(img):
    """{file name: bytes} from a source image."""
    square = {s: png_bytes(resize(img, s, s)) for s in ICO_SIZES}
    mac = {s: png_bytes(rounded_rect_layout(img, s)) for _, s in ICNS_TYPES}
    return {"icon.png": square[256], NAME + ".icns": icns_bytes(mac),
            NAME + ".ico": ico_bytes(square)}


def source_image(xbe_path):
    """(image, description): the title image, or the generic icon and why."""
    try:
        with open(xbe_path, "rb") as f:
            xbe = f.read()
        kind, w, h, data = parse_xpr0(title_image_bytes(xbe))
        return (w, h, decode_dxt(kind, w, h, data)), "game title image (%dx%d)" % (w, h)
    except (OSError, NoImage, struct.error) as e:
        reason = e.strerror if isinstance(e, OSError) and e.strerror else str(e)
        return generic_icon(), "generic (%s)" % reason


def out_dir_allowed(out, root=ROOT):
    """Never into the source tree, where it could be committed: only a
    build-*/ dir, dist/, or anywhere outside the tree."""
    out = os.path.realpath(out)
    root = os.path.realpath(root)
    if os.path.commonpath([out, root]) != root:
        return True
    first = os.path.relpath(out, root).split(os.sep)[0]
    return first.startswith("build-") or first == "dist"


def icon_key(xbe_path):
    h = hashlib.sha256()
    try:
        with open(xbe_path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        sha = h.hexdigest()
    except OSError:
        sha = "absent"
    return {"version": VERSION, "xbe_sha256": sha}


def make_icons(xbe_path, out, force=False, root=ROOT):
    """Write the icon files to out unless icon.key says they are current.
    Returns (description, rebuilt)."""
    if not out_dir_allowed(out, root):
        raise ValueError("refusing to write the icon (game data) into the source tree: %s" % out)
    os.makedirs(out, exist_ok=True)
    key_path = os.path.join(out, "icon.key")
    key = icon_key(xbe_path)
    try:
        with open(key_path) as f:
            old = json.load(f)
    except (OSError, ValueError):
        old = None
    if (not force and old and old.get("key") == key
            and all(os.path.isfile(os.path.join(out, n)) for n in OUTPUTS)):
        return old.get("source", "cached"), False
    img, desc = source_image(xbe_path)
    for name, blob in build_icons(img).items():
        with open(os.path.join(out, name), "wb") as f:
            f.write(blob)
    with open(key_path, "w") as f:
        json.dump({"key": key, "source": desc}, f)
        f.write("\n")
    return desc, True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("xbe")
    ap.add_argument("out")
    ap.add_argument("--force", action="store_true", help="rebuild even when icon.key matches")
    a = ap.parse_args(argv)
    try:
        desc, rebuilt = make_icons(a.xbe, a.out, a.force)
    except ValueError as e:
        print("game_icon: %s" % e, file=sys.stderr)
        return 1
    print("icon: %s%s" % (desc, "" if rebuilt else " (cached)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

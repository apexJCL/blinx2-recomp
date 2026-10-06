#!/usr/bin/env python3
"""Tests for game_icon.py on synthetic textures and a synthetic XBE (no game
data). Plain asserts; runs alone or under pytest.

  python3 scripts/test_game_icon.py
  python3 -m pytest scripts/test_game_icon.py
"""

import os
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import game_icon as gi  # noqa: E402
import package_lib as pl  # noqa: E402

try:
    import pytest
except ImportError:
    pytest = None
if pytest is not None:
    @pytest.fixture
    def d(tmp_path):
        return str(tmp_path)

RED, BLUE = 0xF800, 0x001F   # RGB565


def bc1_block(c0, c1, idx):
    return struct.pack("<HHI", c0, c1, idx)


def xpr0(kind, side, blocks):
    """An XPR0 with one texture: header 2048 bytes, Data offset 0."""
    lg = side.bit_length() - 1
    fmt = (lg << 24) | (lg << 20) | (1 << 16) | (kind << 8) | 0x29
    data = b"".join(blocks)
    head = b"XPR0" + struct.pack("<II", 2048 + len(data), 2048)
    head += struct.pack("<5I", 0x00040001, 0, 0, fmt, 0) + b"\xff\xff\xff\xff"
    return head.ljust(2048, b"\0") + data


def xbe(sections):
    """A minimal XBE: header, a section table, the names, then the data."""
    base = 0x10000
    hdr = bytearray(0x400)
    hdr[:4] = b"XBEH"
    names_off = 0x200
    table_off = 0x180
    struct.pack_into("<I", hdr, 0x104, base)
    struct.pack_into("<I", hdr, 0x11C, len(sections))
    struct.pack_into("<I", hdr, 0x120, base + table_off)
    blob = bytes(hdr)
    raw = len(blob)
    out = bytearray(blob)
    n = names_off
    for i, (name, body) in enumerate(sections):
        out[n:n + len(name) + 1] = name.encode() + b"\0"
        struct.pack_into("<6I", out, table_off + 56 * i, 0, 0, len(body), raw, len(body), base + n)
        n += len(name) + 1
        raw += len(body)
    for _, body in sections:
        out += body
    return bytes(out)


def px(img, x, y):
    _, _, rows = img
    return tuple(rows[y][4 * x:4 * x + 4])


def checker_dxt1(side=16):
    """Blocks alternating solid red and solid blue (index 0 everywhere)."""
    blocks = []
    for by in range(side // 4):
        for bx in range(side // 4):
            c = RED if (bx + by) % 2 == 0 else BLUE
            blocks.append(bc1_block(c, 0, 0))
    return blocks


def test_dxt1_decode():
    kind, w, h, data = gi.parse_xpr0(xpr0(gi.FMT_DXT1, 16, checker_dxt1()))
    assert (kind, w, h) == (gi.FMT_DXT1, 16, 16)
    img = (w, h, gi.decode_dxt(kind, w, h, data))
    assert px(img, 0, 0) == (255, 0, 0, 255)
    assert px(img, 4, 0) == (0, 0, 255, 255)
    assert px(img, 5, 5) == (255, 0, 0, 255)
    # Three-colour mode (c0 <= c1): index 3 is transparent black, index 2
    # the midpoint.
    blk = bc1_block(BLUE, RED, (3 << 0) | (2 << 2) | (1 << 4))
    rows = gi.decode_dxt(gi.FMT_DXT1, 4, 4, blk)
    assert tuple(rows[0][0:4]) == (0, 0, 0, 0)
    assert tuple(rows[0][4:8]) == (127, 0, 127, 255)
    assert tuple(rows[0][8:12]) == (255, 0, 0, 255)
    # Four-colour mode: index 2 is two thirds c0.
    blk = bc1_block(RED, BLUE, 2)
    rows = gi.decode_dxt(gi.FMT_DXT1, 4, 4, blk)
    assert tuple(rows[0][0:4]) == (170, 0, 85, 255)


def test_dxt3_dxt5_alpha():
    alpha = sum((i % 16) << (4 * i) for i in range(16))
    blk3 = struct.pack("<Q", alpha) + bc1_block(BLUE, RED, 0)   # c0 <= c1: still 4-colour
    rows = gi.decode_dxt(gi.FMT_DXT3, 4, 4, blk3)
    assert [rows[i // 4][4 * (i % 4) + 3] for i in range(16)] == [17 * i for i in range(16)]
    assert tuple(rows[0][0:3]) == (0, 0, 255)
    # DXT5: a0 > a1 gives 8 levels; index 0 = a0, 1 = a1, 2 = (6a0 + a1) / 7.
    bits = (0 << 0) | (1 << 3) | (2 << 6)
    blk5 = bytes((210, 0)) + bits.to_bytes(6, "little") + bc1_block(RED, 0, 0)
    rows = gi.decode_dxt(gi.FMT_DXT5, 4, 4, blk5)
    assert [rows[0][4 * i + 3] for i in range(3)] == [210, 0, 180]
    # a0 <= a1: 6 levels, then 0 and 255 at indices 6 and 7.
    bits = (6 << 0) | (7 << 3)
    blk5 = bytes((0, 100)) + bits.to_bytes(6, "little") + bc1_block(RED, 0, 0)
    rows = gi.decode_dxt(gi.FMT_DXT5, 4, 4, blk5)
    assert [rows[0][4 * i + 3] for i in range(2)] == [0, 255]
    for kind in (gi.FMT_DXT3, gi.FMT_DXT5):
        k, w, h, _ = gi.parse_xpr0(xpr0(kind, 16, [blk3] * 16))
        assert (k, w, h) == (kind, 16, 16)


def test_bad_inputs_fall_back(d):
    good = xpr0(gi.FMT_DXT1, 16, checker_dxt1())
    for blob, why in ((b"XPR1" + good[4:], "not XPR0"),
                      (good[:24] + struct.pack("<I", 0x07710629) + good[28:], "not DXT1/3/5"),
                      (good[:-8], "truncated")):
        try:
            gi.parse_xpr0(blob)
            raise AssertionError("accepted: " + why)
        except gi.NoImage as e:
            assert why in str(e), (why, str(e))
    # Through the XBE: no section, then a bad one; both give the generic icon.
    path = os.path.join(d, "default.xbe")
    for sections, why in (([(".text", b"\0" * 16)], "no title image"),
                          ([("$$XTIMAGE", b"XPR1" + good[4:])], "not XPR0")):
        with open(path, "wb") as f:
            f.write(xbe(sections))
        img, desc = gi.source_image(path)
        assert desc.startswith("generic (") and why in desc, desc
        assert img[0] == img[1] == 128
    img, desc = gi.source_image(os.path.join(d, "absent.xbe"))
    assert desc.startswith("generic (")


def test_xbe_section_lookup(d):
    good = xpr0(gi.FMT_DXT1, 16, checker_dxt1())
    data = xbe([(".text", b"\x90" * 32), ("$$XSIMAGE", b"other"), ("$$XTIMAGE", good)])
    assert gi.xbe_section(data, "$$XTIMAGE") == good
    assert gi.title_image_bytes(data) == good
    # $$XSIMAGE is the fallback.
    data = xbe([("$$XSIMAGE", good)])
    assert gi.title_image_bytes(data) == good


def png_chunks(blob):
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    pos, out = 8, []
    while pos < len(blob):
        n, = struct.unpack_from(">I", blob, pos)
        kind = blob[pos + 4:pos + 8]
        body = blob[pos + 8:pos + 8 + n]
        crc, = struct.unpack_from(">I", blob, pos + 8 + n)
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF, kind
        out.append((kind, body))
        pos += 12 + n
    return out


def png_size(blob):
    chunks = png_chunks(blob)
    assert chunks[0][0] == b"IHDR" and chunks[-1][0] == b"IEND"
    return struct.unpack(">II", chunks[0][1][:8])


def test_file_structures(d):
    img = (16, 16, gi.decode_dxt(gi.FMT_DXT1, 16, 16, b"".join(checker_dxt1())))
    files = gi.build_icons(img)
    assert png_size(files["icon.png"]) == (256, 256)
    icns = files["BLiNX2.icns"]
    assert icns[:4] == b"icns" and struct.unpack(">I", icns[4:8])[0] == len(icns)
    pos, seen = 8, []
    while pos < len(icns):
        kind = icns[pos:pos + 4].decode()
        n, = struct.unpack(">I", icns[pos + 4:pos + 8])
        w, h = png_size(icns[pos + 8:pos + n])
        seen.append((kind, w))
        assert w == h
        pos += n
    assert seen == list(gi.ICNS_TYPES), seen
    ico = files["BLiNX2.ico"]
    zero, typ, count = struct.unpack("<HHH", ico[:6])
    assert (zero, typ, count) == (0, 1, len(gi.ICO_SIZES))
    for i, s in enumerate(gi.ICO_SIZES):
        w, h, _, _, planes, bpp, size, off = struct.unpack("<BBBBHHII", ico[6 + 16 * i:22 + 16 * i])
        assert (w or 256, h or 256, planes, bpp) == (s, s, 1, 32)
        assert png_size(ico[off:off + size]) == (s, s)


def test_resize_keeps_solid_colour():
    solid = (8, 8, [bytearray(bytes((10, 200, 30, 255)) * 8) for _ in range(8)])
    for s in (3, 16, 48, 100):
        w, h, rows = gi.resize(solid, s, s)
        assert (w, h) == (s, s)
        assert all(tuple(r[o:o + 4]) == (10, 200, 30, 255) for r in rows for o in range(0, 4 * s, 4))
    # The macOS layout: transparent margin, opaque centre.
    w, h, rows = gi.rounded_rect_layout(solid, 64)
    assert tuple(rows[0][0:4]) == (0, 0, 0, 0) and rows[32][4 * 32 + 3] == 255


def test_cache_and_out_dir(d):
    good = xpr0(gi.FMT_DXT1, 16, checker_dxt1())
    path = os.path.join(d, "default.xbe")
    with open(path, "wb") as f:
        f.write(xbe([("$$XTIMAGE", good)]))
    root = os.path.join(d, "tree")
    out = os.path.join(root, "build-pkg-macos", "icon")
    desc, rebuilt = gi.make_icons(path, out, root=root)
    assert desc == "game title image (16x16)" and rebuilt
    assert sorted(os.listdir(out)) == sorted(gi.OUTPUTS + ("icon.key",))
    assert gi.make_icons(path, out, root=root)[1] is False
    with open(path, "ab") as f:
        f.write(b"\0")
    assert gi.make_icons(path, out, root=root)[1] is True
    for bad in ("src", os.path.join("src", "build-pkg"), ""):
        try:
            gi.make_icons(path, os.path.join(root, bad), root=root)
            raise AssertionError("wrote into the tree: %r" % bad)
        except ValueError:
            pass
    assert gi.out_dir_allowed(os.path.join(root, "dist", "x"), root)
    assert gi.out_dir_allowed(os.path.join(d, "elsewhere"), root)


def test_staged_icon_check(d):
    os.makedirs(os.path.join(d, "game_files"))
    for rel in ("icon.png", "game_files/icon.png", "BLiNX2.ico"):
        open(os.path.join(d, rel), "w").close()
    probs = pl.staged_problems(d)
    assert sorted(p.split(":")[0] for p in probs) == ["BLiNX2.ico", "game_files/icon.png"], probs


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        if t.__code__.co_argcount:
            with tempfile.TemporaryDirectory() as d:
                t(d)
        else:
            t()
        print("ok %s" % t.__name__)
    print("%d tests passed" % len(tests))


if __name__ == "__main__":
    main()

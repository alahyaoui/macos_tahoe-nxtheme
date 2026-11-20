#!/usr/bin/env python3
"""
build_mytheme.py - build one .nxtheme per Switch menu target.

Standard library only (runs with the stock macOS python3).

Usage:
    python3 tools/build_mytheme.py backgrounds . layouts

  backgrounds dir : home.jpg lock.jpg apps.jpg user.jpg set.jpg news.jpg psl.jpg (1280x720 baseline JPEG)
  output dir      : receives MacOS_Tahoe_<target>.nxtheme files
  layouts dir     : optional; <target>/layout.json (+ common.json) for screens with a custom layout.
                    Screens without one get no layout.json, so the installer uses the stock layout.
"""
from __future__ import annotations

import json
import os
import struct
import sys

THEME_NAME = "MacOS Tahoe"
AUTHOR = "MyTheme"
INFO_VERSION = 15

# target id -> (background file, display name)
TARGETS = {
    "home": "Home menu",
    "lock": "Lock screen",
    "apps": "All apps",
    "user": "User page",
    "set":  "Settings",
    "news": "News",
    "psl":  "Player select",
}

# --------------------------------------------------------------------------- Yaz0

def yaz0_decompress(data: bytes) -> bytes:
    if data[:4] != b"Yaz0":
        raise ValueError("not Yaz0")
    size = struct.unpack(">I", data[4:8])[0]
    if size > 64 * 1024 * 1024:
        raise ValueError("Yaz0 size implausible")
    out = bytearray()
    src = 16
    n = len(data)
    while len(out) < size:
        if src >= n:
            raise ValueError("truncated Yaz0")
        code = data[src]; src += 1
        for bit in range(7, -1, -1):
            if len(out) >= size:
                break
            if code & (1 << bit):
                out.append(data[src]); src += 1
            else:
                b1, b2 = data[src], data[src + 1]; src += 2
                dist = ((b1 & 0x0F) << 8 | b2) + 1
                if b1 >> 4:
                    length = (b1 >> 4) + 2
                else:
                    length = data[src] + 0x12; src += 1
                start = len(out) - dist
                if start < 0:
                    raise ValueError("bad Yaz0 back-reference")
                for i in range(length):
                    out.append(out[start + i])
    return bytes(out)


def yaz0_compress(data: bytes, max_candidates: int = 24) -> bytes:
    """Greedy LZ77 Yaz0 encoder (window 0x1000, match 3..0x111)."""
    out = bytearray(b"Yaz0" + struct.pack(">I", len(data)) + b"\0" * 8)
    n = len(data)
    table = {}
    pos = 0

    def insert(p):
        if p + 3 <= n:
            k = data[p:p + 3]
            lst = table.get(k)
            if lst is None:
                table[k] = [p]
            else:
                lst.append(p)
                if len(lst) > 64:
                    del lst[:32]

    while pos < n:
        code_idx = len(out)
        out.append(0)
        code = 0
        for bit in range(7, -1, -1):
            if pos >= n:
                break
            best_len, best_dist = 0, 0
            if pos + 3 <= n:
                cands = table.get(data[pos:pos + 3])
                if cands:
                    max_len = min(0x111, n - pos)
                    checked = 0
                    for c in reversed(cands):
                        d = pos - c
                        if d > 0x1000:
                            break
                        l = 3
                        while l < max_len and data[c + l] == data[pos + l]:
                            l += 1
                        if l > best_len:
                            best_len, best_dist = l, d
                            if l == max_len:
                                break
                        checked += 1
                        if checked >= max_candidates:
                            break
            if best_len >= 3:
                d = best_dist - 1
                if best_len >= 0x12:
                    out += bytes([(d >> 8) & 0x0F, d & 0xFF, best_len - 0x12])
                else:
                    out += bytes([((best_len - 2) << 4) | ((d >> 8) & 0x0F), d & 0xFF])
                for p in range(pos, pos + best_len):
                    insert(p)
                pos += best_len
            else:
                code |= 1 << bit
                out.append(data[pos])
                insert(pos)
                pos += 1
        out[code_idx] = code
    return bytes(out)

# --------------------------------------------------------------------------- SARC

HASH_KEY = 0x65


def sarc_hash(name: str, key: int = HASH_KEY) -> int:
    h = 0
    for ch in name.encode("utf-8"):
        h = (h * key + ch) & 0xFFFFFFFF
    return h


def sarc_read(data: bytes) -> dict:
    if data[:4] == b"Yaz0":
        data = yaz0_decompress(data)
    if data[:4] != b"SARC":
        raise ValueError("not a SARC archive")
    bom = data[6:8]
    e = "<" if bom == b"\xff\xfe" else ">"
    hdr_len = struct.unpack(e + "H", data[4:6])[0]
    data_off = struct.unpack(e + "I", data[12:16])[0]
    p = hdr_len
    if data[p:p + 4] != b"SFAT":
        raise ValueError("missing SFAT")
    sfat_len, count = struct.unpack(e + "HH", data[p + 4:p + 8])
    nodes_at = p + sfat_len
    sfnt = nodes_at + count * 16
    if data[sfnt:sfnt + 4] != b"SFNT":
        raise ValueError("missing SFNT")
    names_at = sfnt + struct.unpack(e + "H", data[sfnt + 4:sfnt + 6])[0]
    files = {}
    for i in range(count):
        h, attr, s, t = struct.unpack(e + "IIII", data[nodes_at + i * 16:nodes_at + i * 16 + 16])
        if attr & 0x01000000:
            no = names_at + (attr & 0xFFFF) * 4
            name = data[no:data.index(b"\0", no)].decode("utf-8")
        else:
            name = "%08x.bin" % h
        if not (0 <= s <= t <= len(data) - data_off):
            raise ValueError("bad SARC node bounds")
        files[name] = data[data_off + s:data_off + t]
    return files


def _align(x, a):
    return (x + a - 1) // a * a


def sarc_write(files: dict, data_align: int = 0x80) -> bytes:
    """Little-endian SARC v1.0, nodes sorted by name hash (as SwitchThemes writes)."""
    items = sorted(files.items(), key=lambda kv: sarc_hash(kv[0]))
    names = bytearray()
    name_offs = []
    for name, _ in items:
        name_offs.append(len(names))
        names += name.encode("utf-8") + b"\0"
        while len(names) % 4:
            names += b"\0"
    header_size = 0x14 + 0x0C + 16 * len(items) + 0x08 + len(names)
    data_off = _align(header_size, 0x100)
    blob = bytearray()
    nodes = bytearray()
    for (name, content), no in zip(items, name_offs):
        start = _align(len(blob), data_align)
        blob += b"\0" * (start - len(blob))
        blob += content
        nodes += struct.pack("<IIII", sarc_hash(name), 0x01000000 | (no // 4), start, start + len(content))
    total = data_off + len(blob)
    out = bytearray()
    out += b"SARC" + struct.pack("<H", 0x14) + b"\xff\xfe" + struct.pack("<IIHH", total, data_off, 0x0100, 0)
    out += b"SFAT" + struct.pack("<HHI", 0x0C, len(items), HASH_KEY)
    out += nodes
    out += b"SFNT" + struct.pack("<HH", 0x08, 0) + names
    out += b"\0" * (data_off - len(out))
    out += blob
    return bytes(out)

# --------------------------------------------------------------------------- theme logic

def is_baseline_jpeg(b: bytes) -> bool:
    if b[:2] != b"\xff\xd8":
        return False
    i = 2
    while i + 4 <= len(b):
        if b[i] != 0xFF:
            return False
        m = b[i + 1]
        if m == 0xC0 or m == 0xC1:
            return True
        if m == 0xC2:
            return False  # progressive: rejected by the installer
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return False


def jpeg_size(b: bytes):
    i = 2
    while i + 9 <= len(b):
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


SZS_FOR_TARGET = {"home": "ResidentMenu.szs", "lock": "Entrance.szs", "apps": "Flaunch.szs",
                  "user": "MyPage.szs", "set": "Set.szs", "news": "Notification.szs",
                  "psl": "Psl.szs"}


def load_layouts(layout_dir: str) -> dict:
    """Read <layout_dir>/<target>/layout.json (and optional common.json)."""
    found = {}
    for target in TARGETS:
        p = os.path.join(layout_dir, target, "layout.json")
        if not os.path.isfile(p):
            continue
        with open(p, "rb") as f:
            raw = f.read()
        lay = json.loads(raw.decode("utf-8-sig"))
        if lay.get("TargetName") != SZS_FOR_TARGET[target]:
            raise ValueError(f"{p}: TargetName {lay.get('TargetName')} != {SZS_FOR_TARGET[target]}")
        entry = {"layout.json": raw, "LayoutInfo": lay.get("PatchName", "")}
        c = os.path.join(layout_dir, target, "common.json")
        if os.path.isfile(c):
            with open(c, "rb") as f:
                entry["common.json"] = f.read()
        found[target] = entry
    return found


def build_theme(target: str, jpg: bytes, layout: dict | None) -> bytes:
    if not is_baseline_jpeg(jpg):
        raise ValueError(f"{target}: image must be a baseline (non-progressive) JPEG")
    if jpeg_size(jpg) != (1280, 720):
        raise ValueError(f"{target}: image must be 1280x720, got {jpeg_size(jpg)}")
    info = {"Version": INFO_VERSION,
            "ThemeName": f"{THEME_NAME} - {TARGETS[target]}",
            "Author": AUTHOR,
            "Target": target}
    files = {"image.jpg": jpg}
    if layout:
        info["LayoutInfo"] = layout["LayoutInfo"]
        files["layout.json"] = layout["layout.json"]
        if "common.json" in layout:
            files["common.json"] = layout["common.json"]
    files["info.json"] = json.dumps(info, indent=2).encode("utf-8")
    return yaz0_compress(sarc_write(files))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    bg_dir, out_dir = argv[1], argv[2]
    layout_dir = os.path.expanduser(argv[3]) if len(argv) > 3 else None
    os.makedirs(out_dir, exist_ok=True)
    layouts = load_layouts(layout_dir) if layout_dir else {}
    for target in TARGETS:
        with open(os.path.join(bg_dir, f"{target}.jpg"), "rb") as f:
            jpg = f.read()
        lay = layouts.get(target)
        data = build_theme(target, jpg, lay)
        # round-trip check
        back = sarc_read(data)
        assert back["image.jpg"] == jpg
        assert json.loads(back["info.json"])["Target"] == target
        name = f"MacOS_Tahoe_{target}.nxtheme"
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(data)
        print(f"  {name:28s} {len(data):>8,d} bytes  layout: "
              f"{'custom' if lay else 'default'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

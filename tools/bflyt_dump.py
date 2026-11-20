#!/usr/bin/env python3
"""Read-only inspector for Switch .szs layout archives (Yaz0 SARC of BFLYT/BFLAN).

    python3 bflyt_dump.py ARCHIVE.szs                 # list files
    python3 bflyt_dump.py ARCHIVE.szs blyt/X.bflyt    # pane tree of one layout
    python3 bflyt_dump.py ARCHIVE.szs --all > out.txt # every layout
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_mytheme import sarc_read  # noqa: E402


def cstr(b, o, n=None):
    end = b.index(b"\0", o) if n is None else o + n
    s = b[o:end]
    return s.split(b"\0")[0].decode("utf-8", "replace")


def parse_bflyt(b):
    assert b[:4] == b"FLYT", "not a BFLYT"
    hdr = struct.unpack("<H", b[6:8])[0]
    nsec = struct.unpack("<H", b[0x10:0x12])[0]
    p = hdr
    out = {"panes": [], "materials": [], "textures": [], "groups": [], "layout": None}
    depth = 0
    last = None
    for _ in range(nsec):
        magic = b[p:p + 4].decode("latin1")
        size = struct.unpack("<I", b[p + 4:p + 8])[0]
        s = b[p:p + size]
        if magic == "lyt1":
            out["layout"] = struct.unpack("<ff", s[12:20])
        elif magic == "txl1":
            n = struct.unpack("<H", s[8:10])[0]
            base = 12
            for i in range(n):
                o = struct.unpack("<I", s[base + 4 * i:base + 4 * i + 4])[0]
                out["textures"].append(cstr(s, base + o))
        elif magic == "mat1":
            n = struct.unpack("<H", s[8:10])[0]
            for i in range(n):
                o = struct.unpack("<I", s[12 + 4 * i:16 + 4 * i])[0]
                name = cstr(s, o, 0x1C)
                black = s[o + 0x1C:o + 0x20].hex().upper()
                white = s[o + 0x20:o + 0x24].hex().upper()
                out["materials"].append((name, black, white))
        elif magic in ("pan1", "pic1", "txt1", "wnd1", "bnd1", "prt1", "scr1", "ali1"):
            flags, origin, alpha = s[8], s[9], s[10]
            name = cstr(s, 12, 24)
            tx, ty, tz, rx, ry, rz, sx, sy, w, h = struct.unpack("<10f", s[0x2C:0x54])
            pane = {"type": magic, "name": name, "depth": depth, "visible": bool(flags & 1),
                    "pos": (tx, ty), "rot": rz, "scale": (sx, sy), "size": (w, h),
                    "alpha": alpha, "origin": origin, "porigin": s[9], "usd": {}}
            if magic == "pic1":
                pane["vcol"] = [s[0x54 + 4 * i:0x58 + 4 * i].hex().upper() for i in range(4)]
                pane["mat"] = struct.unpack("<H", s[0x64:0x66])[0]
            elif magic in ("txt1",):
                pane["mat"] = struct.unpack("<H", s[0x58:0x5A])[0]
            elif magic == "wnd1":
                pass
            elif magic == "prt1":
                cnt = struct.unpack("<I", s[0x54:0x58])[0]
                po = 0x60 + cnt * 0x28
                try:
                    pane["part"] = cstr(s, po)
                except ValueError:
                    pane["part"] = "?"
            out["panes"].append(pane)
            last = pane
        elif magic == "usd1" and last is not None:
            n = struct.unpack("<H", s[8:10])[0]
            for i in range(n):
                e = 12 + 12 * i
                no, do, cnt, typ = struct.unpack("<IIHB", s[e:e + 11])
                key = cstr(s, e + no)
                if typ == 0:
                    val = cstr(s, e + do)
                elif typ == 1:
                    val = list(struct.unpack(f"<{cnt}i", s[e + do:e + do + 4 * cnt]))
                elif typ == 2:
                    val = [round(v, 3) for v in struct.unpack(f"<{cnt}f", s[e + do:e + do + 4 * cnt])]
                else:
                    val = f"<type {typ}>"
                last["usd"][key] = (typ, val)
        elif magic == "pas1":
            depth += 1
        elif magic == "pae1":
            depth -= 1
        elif magic == "grp1":
            out["groups"].append(cstr(s, 8, 0x22))
        p += size
    return out


def fmt(lay, mats):
    lines = []
    for pn in lay["panes"]:
        bits = [f"{'  ' * pn['depth']}{pn['type'][:3]} {pn['name']}",
                f"pos=({pn['pos'][0]:g},{pn['pos'][1]:g})", f"size=({pn['size'][0]:g},{pn['size'][1]:g})"]
        if pn["scale"] != (1.0, 1.0):
            bits.append(f"scale=({pn['scale'][0]:g},{pn['scale'][1]:g})")
        if pn["rot"]:
            bits.append(f"rot={pn['rot']:g}")
        if not pn["visible"]:
            bits.append("HIDDEN")
        o = pn["origin"]
        if o:
            bits.append(f"org={o & 3},{(o >> 2) & 3}/{(o >> 4) & 3},{(o >> 6) & 3}")
        if pn["alpha"] != 255:
            bits.append(f"a={pn['alpha']}")
        if "part" in pn:
            bits.append(f"part={pn['part']}")
        if "mat" in pn and pn["mat"] < len(mats):
            m = mats[pn["mat"]]
            bits.append(f"mat={m[0]}[b={m[1]} w={m[2]}]")
        if "vcol" in pn and set(pn["vcol"]) != {"FFFFFFFF"}:
            bits.append(f"vcol={pn['vcol']}")
        for k, (t, v) in pn["usd"].items():
            bits.append(f"{k}:{t}={v}")
        lines.append("  ".join(bits))
    return "\n".join(lines)


def main(argv):
    files = sarc_read(open(argv[1], "rb").read())
    if len(argv) == 2:
        for n in sorted(files):
            print(n, len(files[n]))
        return
    names = sorted(n for n in files if n.endswith(".bflyt")) if argv[2] == "--all" else [argv[2]]
    for n in names:
        lay = parse_bflyt(files[n])
        print(f"==== {n}  layout={lay['layout']}")
        print(fmt(lay, lay["materials"]))
        print()


if __name__ == "__main__":
    main(sys.argv)

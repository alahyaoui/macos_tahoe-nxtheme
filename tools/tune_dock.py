#!/usr/bin/env python3
"""Adjust the Home dock gap and rebuild the Home theme.

    python3 tools/tune_dock.py GAP [--ends PX]

GAP     space between two dock icons, in screen pixels (default 12.4)
--ends  space between the outer icons and the ends of the glass plate (default 18)

Run from the "MacOS Tahoe" folder. Updates layouts/home, redraws the glass plate in
backgrounds/home.jpg and rebuilds MacOS_Tahoe_home.nxtheme.
Needs: python3 -m pip install numpy scipy pillow
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ICON = 72                      # Nintendo's dock button size before scaling
SCALE, PLATE_H, PLATE_CY, DEFAULT_ENDS = 1.12, 112, 588, 18
MAIN = ["L_BtnNoti", "L_BtnShop", "L_BtnPvr", "L_BtnCtrl", "L_BtnSet", "L_BtnPow"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gap", type=float)
    ap.add_argument("--ends", type=float)
    a = ap.parse_args()
    plate_h, plate_cy = PLATE_H, PLATE_CY
    ends = DEFAULT_ENDS if a.ends is None else a.ends
    icon = ICON * SCALE
    pitch = icon + a.gap                       # screen px between icon centres
    plate_w = 5 * pitch + icon + 2 * ends
    if plate_w > 1240:
        sys.exit(f"dock would be {plate_w:.0f} px wide; keep it under 1240")

    lay_dir, bg_dir = "layouts", "backgrounds"
    lay_path = os.path.join(lay_dir, "home", "layout.json")
    with open(lay_path) as f:
        lay = json.load(f)
    extra = {"L_BtnSplay": 3.5 * pitch, "L_BtnVgc": 4.5 * pitch, "L_BtnLR": -3.5 * pitch}
    for fl in lay["Files"]:
        if fl["FileName"] != "blyt/RdtBase.bflyt":
            continue
        for p in fl["Patches"]:
            n = p["PaneName"]
            if n in MAIN:
                p["Position"] = {"X": round((MAIN.index(n) - 2.5) * pitch, 1), "Y": 0}
            elif n in extra:
                p["Position"] = {"X": round(extra[n], 1), "Y": 0}
    with open(lay_path, "w") as f:
        json.dump(lay, f, indent=2)

    import gen_bg                              # redraw the plate at the new width
    gen_bg.DOCK_CX, gen_bg.DOCK_CY, gen_bg.DOCK_W, gen_bg.DOCK_H = 640, plate_cy, plate_w, plate_h
    gen_bg.scene_home().save(os.path.join(bg_dir, "home.jpg"), "JPEG", quality=92,
                             optimize=True, progressive=False, subsampling=0)

    import build_mytheme as b                  # rebuild only the Home theme
    with open(os.path.join(bg_dir, "home.jpg"), "rb") as f:
        jpg = f.read()
    layouts = b.load_layouts(lay_dir)
    out = "MacOS_Tahoe_home.nxtheme"
    with open(out, "wb") as f:
        f.write(b.build_theme("home", jpg, layouts["home"]))
    print(f"icons {icon:.0f} px, gap {a.gap:g} px, ends {ends:g} px -> "
          f"dock {plate_w:.0f} x {plate_h} px; wrote {out}")


if __name__ == "__main__":
    main()

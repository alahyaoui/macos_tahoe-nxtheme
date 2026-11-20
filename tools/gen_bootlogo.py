#!/usr/bin/env python3
"""Original bitten-pear boot logo (white on black), drawn from signed distance fields.

    python3 gen_bootlogo.py OUT_DIR

Writes:
  OUT_DIR/bootloader/bootlogo.bmp    hekate splash: 1280x720 art rotated 90 deg CCW -> 720x1280,
                                     32-bit ARGB BMP (BI_BITFIELDS), as hekate requires
  OUT_DIR/switch_logo_308x350.png    image for switch-logo-patcher (Nintendo boot logo slot)
  OUT_DIR/pear_preview.png           landscape preview of the hekate splash
"""
import os
import struct
import sys

import numpy as np
from PIL import Image


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def circle(x, y, cx, cy, r):
    return np.hypot(x - cx, y - cy) - r


def seg(x, y, ax, ay, bx, by, r):
    px, py, vx, vy = x - ax, y - ay, bx - ax, by - ay
    t = np.clip((px * vx + py * vy) / (vx * vx + vy * vy), 0, 1)
    return np.hypot(px - vx * t, py - vy * t) - r


def pear_sdf(x, y):
    """Unit pear, centred, ~1.0 tall (y down). Distinct pear silhouette: narrow neck, wide base."""
    top = circle(x, y, -0.015, -0.20, 0.175)
    base = circle(x, y, 0.0, 0.17, 0.315)
    body = smin(top, base, 0.20)
    bite = circle(x, y, 0.385, 0.03, 0.145)          # bite on the right flank
    body = np.maximum(body, -bite)
    stem = seg(x, y, -0.02, -0.355, 0.035, -0.47, 0.022)
    # leaf: lens shape (intersection of two circles), tilted up-right from the stem
    lx, ly = x - 0.13, y + 0.43
    c, s = np.cos(-0.55), np.sin(-0.55)
    u, v = c * lx - s * ly, s * lx + c * ly
    leaf = np.maximum(circle(u, v, 0, 0.075, 0.105), circle(u, v, 0, -0.075, 0.105))
    return np.minimum(np.minimum(body, stem), leaf)


def render(w, h, size, cx, cy, ss=3):
    """White pear with a soft top-light gradient on black. size = pear height in px."""
    W, H = w * ss, h * ss
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    x = (xx / ss - cx) / size
    y = (yy / ss - cy) / size
    d = pear_sdf(x, y) * size * ss                   # distance in supersampled px
    a = np.clip(0.5 - d, 0, 1)
    shade = 0.86 + 0.14 * np.clip(0.5 - y, 0, 1)     # subtle glassy top light
    img = (a * shade)[..., None] * np.ones(3, np.float32)
    im = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
    return im.resize((w, h), Image.LANCZOS)


def write_argb_bmp(path, im):
    """32-bit BMP with BITMAPV4 header + alpha mask (A8R8G8B8), bottom-up rows."""
    im = im.convert("RGBA")
    w, h = im.size
    px = np.asarray(im)[::-1, :, [2, 1, 0, 3]].tobytes()   # BGRA, bottom-up
    hdr_size = 108
    off = 14 + hdr_size
    fh = b"BM" + struct.pack("<IHHI", off + len(px), 0, 0, off)
    ih = struct.pack("<IiiHHIIiiII", hdr_size, w, h, 1, 32, 3, len(px), 2835, 2835, 0, 0)
    ih += struct.pack("<IIII", 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    ih += b"BGRs" + b"\0" * 36 + struct.pack("<III", 0, 0, 0)
    with open(path, "wb") as f:
        f.write(fh + ih + px)


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(os.path.join(out, "bootloader"), exist_ok=True)
    splash = render(1280, 720, 300, 640, 352)
    splash.save(os.path.join(out, "pear_preview.png"))
    write_argb_bmp(os.path.join(out, "bootloader", "bootlogo.bmp"), splash.rotate(90, expand=True))
    render(308, 350, 250, 154, 182).save(os.path.join(out, "switch_logo_308x350.png"))
    print("wrote bootlogo.bmp (720x1280 ARGB), switch_logo_308x350.png, pear_preview.png")

#!/usr/bin/env python3
"""Render original 'liquid glass' wallpapers, 1280x720 baseline JPEG, one per Switch target."""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

S = 2                      # supersampling
W, H = 1280 * S, 720 * S
AR = W / H
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
U = xx / H                 # 0..1.777
V = yy / H                 # 0..1
PX = 1.0 / H               # one render pixel in uv units


def srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def mesh_gradient(base, blobs, warp=0.06, seed=0, fold_amp=0.16):
    rng = np.random.default_rng(seed)
    p1, p2 = rng.uniform(0, 6.28, 2)
    u = U + warp * np.sin(V * 5.1 + p1) + 0.5 * warp * np.sin(V * 11.3 + U * 3 + p2)
    v = V + warp * np.cos(U * 4.3 + p2) + 0.5 * warp * np.cos(U * 9.7 - V * 2 + p1)
    acc = np.zeros((H, W, 3), np.float32)
    wsum = np.full((H, W), 0.35, np.float32)
    acc += 0.35 * srgb_to_lin(base)
    for (bx, by, r, col) in blobs:
        w = np.exp(-((u - bx) ** 2 + (v - by) ** 2) / (r * r)).astype(np.float32) * 2.2
        acc += w[..., None] * srgb_to_lin(col)
        wsum += w
    img = acc / wsum[..., None]
    # soft silk folds: gives the glass something to bend
    a1, a2, a3 = rng.uniform(0, 6.28, 3)
    ph = (u * 2.3 + v * 1.4 + 0.35 * np.sin(v * 3.1 + a1) + 0.25 * np.sin(u * 2.2 + a2)) * 2 * np.pi
    folds = 0.6 * np.sin(ph) + 0.4 * np.sin(ph * 0.47 + u * 3.0 + a3)
    shade = 1 + fold_amp * folds - fold_amp * 0.6 * np.abs(folds) ** 3
    sheen = np.clip(np.sin(ph - 0.6), 0, 1) ** 12 * fold_amp * 1.1
    return img * shade[..., None].astype(np.float32) + (sheen[..., None] * (0.25 + img)).astype(np.float32)


# ---------------------------------------------------------------- signed distance fields (uv units)

def sdf_circle(cx, cy, r):
    return np.hypot(U - cx, V - cy) - r


def sdf_rrect(cx, cy, hw, hh, rad, ang=0.0):
    c, s = np.cos(ang), np.sin(ang)
    px, py = U - cx, V - cy
    qx, qy = np.abs(c * px + s * py) - (hw - rad), np.abs(-s * px + c * py) - (hh - rad)
    out = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
    return out + np.minimum(np.maximum(qx, qy), 0) - rad


def sdf_ribbon(y0, amp, freq, phase, slope, thick, tvar=0.35, tfreq=1.3, tphase=0.0):
    k = 2 * np.pi * freq
    cy = y0 + amp * np.sin(k * U + phase) + slope * (U - AR / 2)
    dcy = amp * k * np.cos(k * U + phase) + slope
    t = thick * (1 + tvar * np.sin(2 * np.pi * tfreq * U + tphase))
    return (np.abs(V - cy) - t) / np.sqrt(1 + dcy * dcy)


def smooth_union(a, b, k=0.06):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


# ---------------------------------------------------------------- glass compositing

def glass(img, d_uv, *, bevel=0.07, refract=95.0, frost=0.035, tint=(1, 1, 1),
          blur=1.2, disp=0.18, shadow=0.28, light=(-0.55, -0.83), spec=0.9,
          outline=0.0, shadow_dy=14, shadow_r=22):
    d = d_uv / PX                                     # render pixels, <0 inside
    alpha = np.clip(0.5 - d / 1.5, 0, 1)
    if alpha.max() == 0:
        return img
    # drop shadow
    if shadow > 0:
        sh = ndimage.shift(alpha, (shadow_dy * S, 0), order=1, mode="constant")
        sh = ndimage.gaussian_filter(sh, shadow_r * S)
        img = img * (1 - shadow * sh * (1 - alpha))[..., None]
    # height field and its slope
    b = bevel / PX
    t = np.clip(-d / b, 0, 1)
    h = np.sqrt(1 - (1 - t) ** 2)
    gy, gx = np.gradient(h)
    gx = ndimage.gaussian_filter(gx, 1.5)
    gy = ndimage.gaussian_filter(gy, 1.5)
    scale = refract * S * b / 40.0
    src = ndimage.gaussian_filter(img, (blur * S, blur * S, 0)) if blur > 0 else img
    out = np.empty_like(img)
    for ch, k in enumerate((1 + disp, 1.0, 1 - disp)):  # chromatic dispersion at edges
        coords = [yy + gy * scale * k * 8, xx + gx * scale * k * 8]
        out[..., ch] = ndimage.map_coordinates(src[..., ch], coords, order=1, mode="reflect")
    tint = srgb_to_lin(tint)
    out = out * tint * 1.06 + frost * (0.85 + 0.15 * out)
    # specular rims: bright on the lit edge, softer on the opposite edge
    ny, nx = np.gradient(d)
    nl = np.hypot(nx, ny) + 1e-6
    nx, ny = nx / nl, ny / nl
    rim = (1 - t) ** 5
    lit = np.clip(nx * light[0] + ny * light[1], 0, 1)
    opp = np.clip(-(nx * light[0] + ny * light[1]), 0, 1)
    edge = rim * (0.18 + 0.85 * lit ** 1.5 + 0.45 * opp ** 2) * spec
    inner = np.exp(-((-d - 2.5 * S) / (1.2 * S)) ** 2) * 0.35 * spec  # hairline just inside edge
    out = out + (edge + inner)[..., None]
    a = alpha[..., None]
    img = img * (1 - a) + out * a
    if outline > 0:  # thin darker hairline just outside the edge, so glass reads on light backgrounds
        ol = np.exp(-((d - 1.2 * S) / (1.1 * S)) ** 2) * outline
        img = img * (1 - ol)[..., None]
    return img


def finish(img, seed, vignette=0.18):
    v = 1 - vignette * (((U - AR / 2) / AR) ** 2 + (V - 0.5) ** 2) * 2.2
    img = img * v[..., None]
    rgb = lin_to_srgb(img)
    im = Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).resize((1280, 720), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    rng = np.random.default_rng(seed)
    a += rng.normal(0, 1.3, a.shape[:2])[..., None]   # luminance grain kills JPEG banding
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- scenes (light mode, for Basic White)
# Shared with tools/make_layouts.py: dock row centre 585 px from top, 6 buttons 100 px apart, ~81 px each.
DOCK_CX, DOCK_CY, DOCK_W, DOCK_H = 640, 585, 624, 118
LIGHT = dict(outline=0.10, shadow=0.10, frost=0.06, spec=0.8)


def px(x):
    return x / 720.0


def dock(img):
    d = sdf_rrect(px(DOCK_CX), px(DOCK_CY), px(DOCK_W / 2), px(DOCK_H / 2), px(34))
    return glass(img, d, bevel=0.035, refract=60, blur=10, frost=0.0, tint=(0.80, 0.83, 0.90),
                 shadow=0.14, shadow_dy=10, shadow_r=26, outline=0.16, spec=1.1)


def scene_home():
    img = mesh_gradient((0.94, 0.95, 0.99), [
        (0.20, 0.15, 0.55, (0.76, 0.85, 1.00)),
        (1.50, 0.20, 0.55, (0.90, 0.82, 0.99)),
        (1.00, 1.00, 0.55, (0.78, 0.94, 0.96)),
        (0.25, 0.95, 0.45, (1.00, 0.88, 0.84)),
    ], seed=1, fold_amp=0.05)
    img = glass(img, sdf_circle(1.62, 0.10, 0.24), bevel=0.09, **LIGHT)
    img = glass(img, sdf_circle(0.06, 0.98, 0.17), bevel=0.08, **LIGHT)
    img = dock(img)
    return finish(img, 11, vignette=0.05)


def scene_lock():
    img = mesh_gradient((0.99, 0.94, 0.91), [
        (0.20, 0.85, 0.55, (1.00, 0.83, 0.74)),
        (0.80, 0.25, 0.50, (0.99, 0.80, 0.87)),
        (1.60, 0.20, 0.55, (0.86, 0.85, 1.00)),
        (1.30, 0.95, 0.45, (1.00, 0.93, 0.78)),
    ], warp=0.08, seed=2, fold_amp=0.06)
    lens = smooth_union(sdf_circle(1.25, 0.46, 0.25), sdf_circle(1.52, 0.68, 0.14), 0.08)
    img = glass(img, lens, bevel=0.12, refract=110, **LIGHT)
    img = glass(img, sdf_ribbon(0.92, 0.04, 0.6, 1.2, -0.05, 0.05), bevel=0.05, **LIGHT)
    return finish(img, 12, vignette=0.05)


def scene_apps():
    img = mesh_gradient((0.94, 0.98, 0.97), [
        (0.20, 0.30, 0.55, (0.82, 0.96, 0.92)),
        (1.30, 0.15, 0.55, (0.84, 0.92, 0.99)),
        (1.60, 0.90, 0.50, (0.90, 0.97, 0.86)),
    ], seed=3, fold_amp=0.035)
    return finish(img, 13, vignette=0.04)


def scene_user():
    img = mesh_gradient((0.99, 0.96, 0.92), [
        (0.25, 0.25, 0.55, (1.00, 0.88, 0.78)),
        (1.20, 0.85, 0.55, (0.99, 0.84, 0.86)),
        (1.60, 0.20, 0.45, (1.00, 0.92, 0.76)),
    ], seed=4, fold_amp=0.04)
    return finish(img, 14, vignette=0.04)


def scene_set():
    img = mesh_gradient((0.95, 0.96, 0.97), [
        (0.20, 0.20, 0.55, (0.88, 0.90, 0.95)),
        (1.50, 0.25, 0.55, (0.93, 0.93, 0.96)),
        (1.30, 0.95, 0.45, (0.85, 0.90, 0.99)),
    ], warp=0.04, seed=5, fold_amp=0.03)
    return finish(img, 15, vignette=0.03)


def scene_news():
    img = mesh_gradient((0.94, 0.97, 1.00), [
        (0.30, 0.20, 0.55, (0.82, 0.90, 1.00)),
        (1.40, 0.20, 0.50, (0.92, 0.95, 1.00)),
        (1.00, 0.95, 0.55, (0.82, 0.95, 0.98)),
    ], seed=6, fold_amp=0.035)
    return finish(img, 16, vignette=0.03)


def scene_psl():
    img = mesh_gradient((0.96, 0.94, 0.99), [
        (0.30, 0.35, 0.55, (0.88, 0.84, 1.00)),
        (1.40, 0.65, 0.55, (0.99, 0.86, 0.93)),
        (0.95, 0.05, 0.45, (0.84, 0.88, 1.00)),
    ], warp=0.07, seed=7, fold_amp=0.05)
    return finish(img, 17, vignette=0.04)


SCENES = {"home": scene_home, "lock": scene_lock, "apps": scene_apps, "user": scene_user,
          "set": scene_set, "news": scene_news, "psl": scene_psl}

if __name__ == "__main__":
    out = sys.argv[1]
    names = sys.argv[2:] or list(SCENES)
    for n in names:
        SCENES[n]().save(f"{out}/{n}.jpg", "JPEG", quality=92, optimize=True,
                         progressive=False, subsampling=0)
        print("wrote", n)

#!/usr/bin/env python3
"""Generate the MacOS Tahoe layout.json / common.json files.

    python3 make_layouts.py SYSTEMDATA_DIR OUT_DIR

SYSTEMDATA_DIR is the folder NXThemes Installer exports ("Extract home menu"); the console's
own .szs files are read only to learn which layout files and panes exist on this firmware
and how big they are. Nothing from them is copied into the output: the JSON contains only
pane names and the values chosen here. Every patch is checked against the real pane list.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_mytheme import sarc_read          # noqa: E402
from bflyt_dump import parse_bflyt           # noqa: E402

AUTHOR = "MyTheme"
VERSION = 7

# ------------------------------------------------------------------ design tokens
ACCENT = [0.0, 0.48, 1.0, 1.0]          # macOS system blue
ACCENT_GLOW = [0.40, 0.70, 1.0, 1.0]
ACCENT_SHADOW = [0.0, 0.36, 0.85, 0.30]

# Home dock (shared with gen_bg.py, which paints the glass plate)
DOCK_Y = -225                 # 585 px from top
DOCK_SPACING = 110          # v5: wider dock
DOCK_SCALE = 1.12             # 72 px buttons -> ~81 px
DOCK_MAIN = ["L_BtnNoti", "L_BtnShop", "L_BtnPvr", "L_BtnCtrl", "L_BtnSet", "L_BtnPow"]
DOCK_EXTRA = {"L_BtnSplay": 385, "L_BtnVgc": 495, "L_BtnLR": -385}   # normally hidden slots
DOCK_BTN_FILES = ["RdtBtnNtf", "RdtBtnShop", "RdtBtnPvr", "RdtBtnCtrl", "RdtBtnSet",
                  "RdtBtnPow", "RdtBtnSplay", "RdtBtnVgc", "RdtBtnLR"]
SQUIRCLE = 0.25               # corner radius as a fraction of the side (macOS app icon ~22-25 %)

TARGET_SZS = {"home": "ResidentMenu", "lock": "Entrance", "apps": "Flaunch", "set": "Set",
              "news": "Notification", "user": "MyPage", "psl": "Psl"}
NAMES = {"home": "Home", "lock": "Lock", "apps": "All Apps", "set": "Settings",
         "news": "News", "user": "User Page", "psl": "Player Select", "common": "Common"}

FOCUS_PANES = ("N_BtnFocusKey", "P_InnerCursor")
BODY_PANES = ("P_BtnDecideKey", "P_BtnTouch", "P_BtnBase", "P_BtnCardBase", "P_BtnCardBaseInv",
              "P_BtnSelectShdw")
CAPSULE_HINTS = ("Island", "Center", "Dialog", "BtnLine", "LineAdd", "Vgc", "NewsMore",
                 "NtfBtnGood", "NtfBtnBad", "NtfBtnBookmark", "CheckAlarm", "NtfBtnShop",
                 "ChannelListCheckLine")


# ------------------------------------------------------------------ patch helpers
class Patches:
    def __init__(self, files):
        self.files = files            # {bflyt name: parsed layout}
        self.out = {}                 # {file: {pane: patch}}

    def has(self, f, pane=None):
        f = f if f.startswith("blyt/") else f"blyt/{f}.bflyt"
        if f not in self.files:
            return False
        return pane is None or any(p["name"] == pane for p in self.files[f]["panes"])

    def pane(self, f, pane):
        f = f if f.startswith("blyt/") else f"blyt/{f}.bflyt"
        for p in self.files[f]["panes"]:
            if p["name"] == pane:
                return p
        raise KeyError(f"{f}:{pane}")

    def _get(self, f, pane):
        f = f if f.startswith("blyt/") else f"blyt/{f}.bflyt"
        if not self.has(f, pane):
            raise KeyError(f"pane {pane} not in {f}")
        return self.out.setdefault(f, {}).setdefault(pane, {"PaneName": pane})

    def set(self, f, pane, **kw):
        p = self._get(f, pane)
        for k, v in kw.items():
            if k in ("Position", "Size", "Scale") and isinstance(v, tuple):
                v = {"X": v[0], "Y": v[1]}
            p[k] = v

    skipped = []

    def usd(self, f, pane, name, values, typ):
        # The installer can edit or extend an existing user-data block but cannot create one:
        # patches on panes without user data are silently dropped on the console (seen in v3).
        if not self.pane(f, pane)["usd"]:
            Patches.skipped.append(f"{f}:{pane}:{name}")
            return
        p = self._get(f, pane)
        lst = p.setdefault("UsdPatches", [])
        lst[:] = [u for u in lst if u["PropName"] != name]
        lst.append({"PropName": name, "PropValues": [str(v) for v in values], "type": typ})

    def radius(self, f, pane, r):
        if self.has(f, pane):
            self.usd(f, pane, "S_RoundRadius", [float(round(r, 1))], 2)

    def json(self):
        return [{"FileName": f, "Patches": list(p.values())} for f, p in sorted(self.out.items())]


def native_radius(pane):
    v = pane["usd"].get("S_RoundRadius")
    return v[1][0] if v and v[0] == 2 else 0.0


# ------------------------------------------------------------------ global passes
def pass_cursor(P):
    if not P.has("Cursor3"):
        return
    for pane, col in (("P_Main", ACCENT), ("P_Grow", ACCENT_GLOW)):
        if P.has("Cursor3", pane):
            P.usd("Cursor3", pane, "S_BorderColorSelect0", [0], 1)
            P.usd("Cursor3", pane, "S_BorderColor0", col, 2)
            P.usd("Cursor3", pane, "S_DropShadowColorSelect", [0], 1)
            P.usd("Cursor3", pane, "S_DropShadowColor", ACCENT_SHADOW, 2)
    P.usd("Cursor3", "P_Main", "S_BorderSize", [4.0], 2)


def pass_inner_rings(P):
    for f, lay in P.files.items():
        for p in lay["panes"]:
            if p["name"] == "P_InnerCursor" and p["alpha"] == 255 and "C_W" in p["usd"]:
                P.usd(f, "P_InnerCursor", "C_W", [0, 0, 0, 0], 1)
                P.usd(f, "P_InnerCursor", "S_BorderColorSelect0", [0], 1)
                P.usd(f, "P_InnerCursor", "S_BorderColor0", ACCENT, 2)
                P.usd(f, "P_InnerCursor", "S_BorderSize", [4.0], 2)


def pass_lines(P):
    for f in ("LineHeader_Root", "LineFooter"):
        if P.has(f, "P_Line"):
            P.set(f, "P_Line", Visible=False)


def pass_sidebar(P):
    if P.has("BgNav_Root", "P_NavBg"):
        w, h = P.pane("BgNav_Root", "P_NavBg")["size"]
        inset = 12
        P.set("BgNav_Root", "P_NavBg", Size=(w - 2 * inset, h - 2 * inset), Position=(0, -288 + inset))
        P.radius("BgNav_Root", "P_NavBg", 22)


def pass_buttons(P, skip=()):
    """Round every button template not handled explicitly."""
    for f, lay in P.files.items():
        base = f[5:-6]
        if base in skip:
            continue
        names = {p["name"]: p for p in lay["panes"]}
        fk = names.get("N_BtnFocusKey")
        if fk is None:
            continue
        w, h = fk["size"]
        if w <= 0 or h <= 0:
            continue
        if native_radius(fk) >= min(w, h) / 2 - 1:      # already round (avatars, sliders, pills)
            continue
        if any(k in base for k in CAPSULE_HINTS) and h <= 72:
            r = h / 2                                     # Tahoe capsule buttons
        elif h <= 72:
            r = 12                                        # list rows / sidebar items
        else:
            r = min(28, max(12, round(min(w, h) * 0.10)))  # cards and panels
        for pn in FOCUS_PANES:
            if pn in names:
                P.radius(f, pn, r + 2 if r < min(w, h) / 2 else r)
        for p in lay["panes"]:
            if p["type"] == "pic1" and p["name"] not in FOCUS_PANES and p["usd"] \
                    and abs(p["size"][0] - w) <= 12 and abs(p["size"][1] - h) <= 12:
                P.radius(f, p["name"], r)


# ------------------------------------------------------------------ screen designs
def design_home(P):
    # dock: one centred row of rounded-square buttons on the glass plate
    n = len(DOCK_MAIN)
    P.set("RdtBase", "N_System", Position=(0, DOCK_Y))
    for i, b in enumerate(DOCK_MAIN):
        P.set("RdtBase", b, Position=(round((i - (n - 1) / 2) * DOCK_SPACING), 0),
              Scale=(DOCK_SCALE, DOCK_SCALE))
    for b, x in DOCK_EXTRA.items():
        if P.has("RdtBase", b):
            P.set("RdtBase", b, Position=(x, 0), Scale=(DOCK_SCALE, DOCK_SCALE))
    for f in DOCK_BTN_FILES:
        if not P.has(f):
            continue
        side = P.pane(f, "P_PictBase")["size"][0]
        P.radius(f, "P_PictBase", side * SQUIRCLE)
        for pn in ("P_BtnDecideKey", "P_BtnTouch", "P_Effect"):
            P.radius(f, pn, side * SQUIRCLE)
        P.radius(f, "N_BtnFocusKey", P.pane(f, "N_BtnFocusKey")["size"][0] * SQUIRCLE + 2)
        if P.has(f, "N_Tip"):
            # label clear above the glass plate (v4 at 62 overlapped the plate's top edge)
            P.set(f, "N_Tip", Position=(0, 74))
    # news dot: L_New's position is animated (RdtBtnNtf_Active/Inactive keep it at 32,32), so
    # offset the dot inside its part instead -> lands under the icon like a macOS dock indicator
    P.set("IconNew", "P_Base_00", Position=(-32, -75.5))
    # macOS menu bar: users small at top-left, status items small at top-right
    P.set("RdtBase", "N_MyPage", Position=(-392, 334), Scale=(0.75, 0.75))
    P.set("RdtBase", "L_Hud", Position=(608, 334), Scale=(0.85, 0.85))
    menubar_order(P)
    # dock labels in the regular dark text colour instead of teal
    P.usd("RdtBalloonSystemApplet", "T_Main", "C_W", [9, 0, 0, 0], 1)

    # game tiles: rounded squares
    t = 256 * 0.205                                       # 52 px
    for pn in ("P_IconGame", "P_BtnBase", "P_Blank", "P_BtnDecideKey", "P_BtnTouch", "P_CardBack"):
        P.radius("RdtBtnIconGame", pn, t)
    for pn in FOCUS_PANES:
        P.radius("RdtBtnIconGame", pn, t + 4)

    # tile focus pane has no user data, so give the shared cursor a matching default radius;
    # buttons that carry their own radius keep it
    for pn in ("P_Main", "P_Grow"):
        P.radius("Cursor3", pn, t + 4)

    # "All software" button: rounded square instead of a circle
    f = "RdtBtnFullLauncher"
    for pn in ("P_PictBase", "P_BtnDecideKey", "P_BtnTouch", "P_Effect"):
        P.radius(f, pn, 160 * 0.22)
    P.radius(f, "N_BtnFocusKey", 170 * 0.22 + 2)


def menubar_order(P):
    """macOS order, right to left: clock, battery, Wi-Fi (Switch: battery, Wi-Fi, clock)."""
    if not P.has("Hud"):
        return
    P.set("Hud", "N_Time", Position=(0, 0))               # right-anchored: clock at the far right
    P.set("Hud", "L_BatteryConsole", Position=(-114, 0))  # centre-anchored, 50 px wide
    P.set("Hud", "N_Signal", Position=(-150, 0))          # right-anchored
    P.set("Hud", "N_BatteryNum", Position=(-190, 0))      # optional battery %, left of Wi-Fi


def design_apps(P):
    for f, side in (("FlcBtnIconGame", 174), ("FlcBtnIconGameEdit", 112)):
        r = side * 0.205
        for pn in ("P_IconGame", "P_BtnBase", "P_Blank", "P_BtnDecideKey", "P_BtnTouch"):
            P.radius(f, pn, r)
        for pn in FOCUS_PANES:
            P.radius(f, pn, r + 2)
    # Groups: rounded cards and rounded thumbnails
    f = "FlcBtnGrp"
    for pn in ("P_BtnSelectShdw", "P_BtnCardBase", "P_BtnCardBaseInv", "P_Bg", "P_BgIco",
               "P_BtnDecideKey", "P_BtnTouch"):
        P.radius(f, pn, 22)
    for pn in FOCUS_PANES:
        P.radius(f, pn, 24)
    # group thumbnails (P_Ico_*) have no user data on this firmware, so they stay square


def design_psl(P):
    # macOS login feel: larger glass cards centred on screen, prompt above, no divider
    # N_Cnt's X is animated per user count (PslSelectSinglePlayer_Num) to centre the row, and
    # L_Head is animated by _Skip, so: scale the parent N_PlateSize (keeps the row centred),
    # set only N_Cnt's Y, and move the prompt text inside its header part.
    m = "PslSelectSinglePlayer"
    P.set(m, "N_PlateSize", Scale=(1.25, 1.25))
    P.set(m, "N_Cnt", Position={"Y": 0})                 # cards centred on screen
    # prompt becomes the window title, top-left like every other screen's header
    P.set("DBtmHeaderNml", "T_00", Position=(0, 344))
    P.set("DBtmHeaderNml", "P_Line", Visible=False)
    # rounded card, avatar inset like a photo in a widget, name on the card; blue ring
    f = "BtnCardPlayer"
    P.set(f, "P_BtnCardBase", ColorTL="FFFFFFDC", ColorTR="FFFFFFDC",
          ColorBL="FFFFFFDC", ColorBR="FFFFFFDC")         # slightly translucent glass card
    P.set(f, "P_BgName", Visible=False)
    P.set(f, "P_PlayerImage", Size=(120, 120), Position=(0, -10))   # top-anchored: 10 px inset
    for pn in ("P_BtnCardBase", "P_BtnDecideKey", "P_BtnTouch"):
        P.radius(f, pn, 20)
    for pn in FOCUS_PANES:
        P.radius(f, pn, 22)


def design_lock(P):
    # "À la une" used the white text meant for Nintendo's dark news column; use the same dark
    # grey as "Commencer" so it reads on the light background
    for pn in ("P_Pict", "T_00", "T_01"):
        P.usd("EntBtnCenterNtf", pn, "C_W", [9, 0, 0, 0], 1)


DESIGNS = {"home": (design_home, {"RdtBtnIconGame", "RdtBtnFullLauncher", *DOCK_BTN_FILES}),
           "apps": (design_apps, {"FlcBtnIconGame", "FlcBtnIconGameEdit", "FlcBtnGrp"}),
           "psl": (design_psl, {"BtnCardPlayer"})}


def load_szs(path):
    files = sarc_read(open(path, "rb").read())
    return {n: parse_bflyt(b) for n, b in files.items() if n.endswith(".bflyt")}


def build(target, szs_path):
    P = Patches(load_szs(szs_path))
    design, skip = DESIGNS.get(target, (None, set()))
    if design:
        design(P)
    pass_buttons(P, skip)
    pass_cursor(P)
    pass_inner_rings(P)
    pass_lines(P)
    if target == "lock":
        design_lock(P)
        menubar_order(P)
    szs = os.path.basename(szs_path)
    doc = {"PatchName": f"MacOS Tahoe {NAMES[target]}", "AuthorName": AUTHOR,
           "TargetName": szs, "ID": f"MacOSTahoe:{target}:{VERSION}"}
    if target == "home":
        doc["HideOnlineBtn"] = True
    if target == "common":
        doc.pop("TargetName")
    doc["Files"] = P.json()
    return doc


def find(sysdir, name):
    hits = glob.glob(os.path.join(sysdir, "**", f"{name}.szs"), recursive=True)
    if not hits:
        raise FileNotFoundError(f"{name}.szs not found under {sysdir}")
    return hits[0]


if __name__ == "__main__":
    sysdir, out = sys.argv[1], sys.argv[2]
    for target, szs in TARGET_SZS.items():
        doc = build(target, find(sysdir, szs))
        os.makedirs(os.path.join(out, target), exist_ok=True)
        with open(os.path.join(out, target, "layout.json"), "w") as f:
            json.dump(doc, f, indent=2)
        n = sum(len(x["Patches"]) for x in doc["Files"])
        print(f"{target:5} {szs:18} {len(doc['Files']):3} files {n:4} pane patches")
    doc = build("common", find(sysdir, "common"))
    with open(os.path.join(out, "home", "common.json"), "w") as f:
        json.dump(doc, f, indent=2)
    n = sum(len(x["Patches"]) for x in doc["Files"])
    print(f"common common.szs          {len(doc['Files']):3} files {n:4} pane patches")

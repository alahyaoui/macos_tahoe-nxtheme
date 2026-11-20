# MacOS Tahoe (v11)

Seven Switch themes in a light, frosted-glass macOS Tahoe style, made for **Basic White**
and built against firmware 23.5.0. Everything is original: backgrounds, layouts and tools.

## What each screen gets
| File | Target | Design |
|---|---|---|
| MacOS_Tahoe_home.nxtheme | `home` | macOS-style menu bar (small user avatars top-left; Wi-Fi, battery, clock top-right), glass dock with 6 rounded-square buttons in macOS proportions, dark labels above the dock, news / new-friend indicator dot under its icon, rounded game tiles, rounded "All software" button, blue cursor. Also carries `common.json` (dialogs, footer buttons, cursor and footer line across the system menus). |
| MacOS_Tahoe_apps.nxtheme | `apps` | Rounded tiles; **Groups** get rounded cards and thumbnails |
| MacOS_Tahoe_psl.nxtheme  | `psl`  | Login-screen style: larger translucent user cards centred on screen, prompt as the top-left window title, aurora wallpaper |
| MacOS_Tahoe_set.nxtheme  | `set`  | Rounded list rows and highlights, capsule buttons |
| MacOS_Tahoe_user.nxtheme | `user` | Same as Settings, plus rounded friend/game cards |
| MacOS_Tahoe_news.nxtheme | `news` | Same treatment for channels and articles |
| MacOS_Tahoe_lock.nxtheme | `lock` | Blue cursor, readable "News" button on the light background |

Everywhere: macOS-blue selection cursor, header/footer separator lines hidden,
list rows 12 px corners, buttons as capsules, cards about 10 % corners.

## Dock size
One Home theme. Dock icons are ~81 px: on the 6.2" screen that is about the physical size of a
default 48 pt macOS dock icon. Gaps are ~15% of an icon, as on macOS.

## Adjusting the dock gap yourself
    python3 -m pip install numpy scipy pillow       # once
    python3 tools/tune_dock.py 10                   # 10 px between icons (current: 12.4)
    python3 tools/tune_dock.py 10 --ends 22         # also change the padding at both ends (current: 18)

It moves the dock buttons, redraws the glass plate to the new length and rebuilds
`MacOS_Tahoe_home.nxtheme`. Install the rebuilt Home theme to see it.

## Known limits (firmware 23.5.0)
- Elements without user data can't get rounded corners (the installer can edit user data but
  not create it): player avatars, group thumbnails, lock-screen news images stay square.
- The controller screens ("Manettes", "Changer le style/l'ordre") belong to Nintendo's
  controller applet, which NXThemes has no target for, and the User page footer line comes
  from that applet's own shared file. Both keep Nintendo's look.

## Boot logo (bitten pear)
Not part of the .nxtheme files: these go on the SD card separately. Both are optional.

**hekate splash** (any firmware): copy `bootlogo/bootloader/bootlogo.bmp` to `/bootloader/bootlogo.bmp`.
It is a 32-bit ARGB BMP (1280x720 art rotated 90 deg counter-clockwise), drawn by `tools/gen_bootlogo.py`.
It shows while hekate starts Atmosphere, so you need to boot through hekate (inject `hekate_ctcaer_*.bin`
as the payload, not `fusee.bin`). In `/bootloader/hekate_ipl.ini`:
- under `[config]`, `bootwait=3` (seconds the splash stays up; 0 hides it)
- the boot entry must not have a `logopath=` line pointing elsewhere (or set `logopath=bootloader/bootlogo.bmp`)

**Atmosphere splash** (the logo shown right after hekate's): Atmosphere stores it inside
`/atmosphere/package3`. Replace it with Atmosphere's own script and `bootlogo/atmosphere_splash_1280x720.png`:

    curl -O https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/utilities/insert_splash_screen.py
    cp /Volumes/<SD>/atmosphere/package3 package3.bak          # the script edits in place, no backup
    python3 -m pip install pillow
    python3 insert_splash_screen.py bootlogo/atmosphere_splash_1280x720.png /Volumes/<SD>/atmosphere/package3

Redo this after every Atmosphere update (updating replaces package3). To undo, copy package3.bak back.

**Nintendo Switch logo during boot** (optional, Atmosphere): generate the patches yourself with
[switch-logo-patcher](https://github.com/friedkeenan/switch-logo-patcher) from
`bootlogo/switch_logo_308x350.png`:

    git clone https://github.com/friedkeenan/switch-logo-patcher
    cd switch-logo-patcher && python3 -m pip install -r requirements.txt
    python3 gen_patches.py tahoe_pear_logo "../MacOS Tahoe/bootlogo/switch_logo_308x350.png"

then copy the `tahoe_pear_logo` folder to `/atmosphere/exefs_patches/`. The patcher covers firmware
up to 23.0.0 (as of Sep 2026); if 23.5.0 uses a different build of the display module the patch is
simply ignored and the Nintendo logo shows as usual. Delete the folder if anything looks wrong.

## Installing
Copy only the seven `.nxtheme` files to `/themes` on the SD card and install them with
NXThemes Installer. Remove any previously installed theme first, then reboot.

## Rebuilding
    python3 tools/make_layouts.py ../systemData layouts   # needs the "Extract home menu" export
    python3 tools/gen_bg.py backgrounds                   # needs numpy, scipy, Pillow
    python3 tools/build_mytheme.py backgrounds . layouts
    python3 tools/gen_bootlogo.py bootlogo                # needs numpy, Pillow

`make_layouts.py` reads the console's own layout files only to learn which elements exist and
their sizes; every patch is checked against them. `tools/bflyt_dump.py` prints any layout's
element tree, if you want to explore further.

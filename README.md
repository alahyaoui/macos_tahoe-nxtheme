# MacOS Tahoe (v4)

Seven Switch themes in a light, frosted-glass macOS Tahoe style, made for **Basic White**
and built against firmware 23.5.0. Everything is original: backgrounds, layouts and tools.

## What each screen gets
| File | Target | Design |
|---|---|---|
| MacOS_Tahoe_home.nxtheme | `home` | Glass dock with 6 rounded-square buttons and labels above them, rounded game tiles, rounded "All software" button, blue cursor. Also carries `common.json` (dialogs, footer buttons, cursor and footer line across the system menus). |
| MacOS_Tahoe_apps.nxtheme | `apps` | Rounded tiles; **Groups** get rounded cards and thumbnails |
| MacOS_Tahoe_psl.nxtheme  | `psl`  | Rounded user cards with the avatar inset like a photo, blue ring |
| MacOS_Tahoe_set.nxtheme  | `set`  | Rounded list rows and highlights, capsule buttons |
| MacOS_Tahoe_user.nxtheme | `user` | Same as Settings, plus rounded friend/game cards |
| MacOS_Tahoe_news.nxtheme | `news` | Same treatment for channels and articles |
| MacOS_Tahoe_lock.nxtheme | `lock` | Blue cursor, readable "News" button on the light background |

Everywhere: macOS-blue selection cursor, header/footer separator lines hidden,
list rows 12 px corners, buttons as capsules, cards about 10 % corners.

## Known limits (firmware 23.5.0)
- Elements without user data can't get rounded corners (the installer can edit user data but
  not create it): player avatars, group thumbnails, lock-screen news images stay square.
- The controller applet (Manettes) and the User page footer line are not part of these
  layout files, so they keep Nintendo's look.

## Installing
Copy only the seven `.nxtheme` files to `/themes` on the SD card and install them with
NXThemes Installer. Remove any previously installed theme first, then reboot.

## Rebuilding
    python3 tools/make_layouts.py ../systemData layouts   # needs the "Extract home menu" export
    python3 tools/gen_bg.py backgrounds                   # needs numpy, scipy, Pillow
    python3 tools/build_mytheme.py backgrounds . layouts

`make_layouts.py` reads the console's own layout files only to learn which elements exist and
their sizes; every patch is checked against them. `tools/bflyt_dump.py` prints any layout's
element tree, if you want to explore further.

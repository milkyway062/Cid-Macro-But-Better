# =========================
# Immutable Configuration Constants
# (values that never change at runtime)
# =========================

REJOIN_TIMEOUT = 60  # Seconds to wait for rejoin before retry

# Camera setup
UNIT_PANEL_POS   = (409, 309)
CAMERA_MOVE_OFFSET = (0, 10000)  # Relative mouse movement for camera tilt

# Return to spawn click sequence (window-relative; dx/dy added at call site)
RETURN_TO_SPAWN_CLICKS = [
    (30, 605),
    (708, 322),
    (755, 149),
]

# Auto positioner reference images
POSITIONER_IMAGES = [
    "Positioner\\Cid_Island.png",
    "Positioner\\Cid_Raid.png",
]

# DirectInput scan codes
KEYMAP = {
    "a":     0x1E,
    "s":     0x1F,
    "d":     0x20,
    "f":     0x21,
    "g":     0x22,
    "r":     0x13,
    "x":     0x2D,
    "w":     0x11,
    "q":     0x10,
    "1":     0x02,
    "2":     0x03,
    "3":     0x04,
    "4":     0x05,
    "5":     0x06,
    "6":     0x07,
    "i":     0x17,
    "o":     0x18,
    "e":     0x12,
    "v":     0x2F,
    "shift": 0x2A,
}

# Stock bar colours — green = available, red = active/cooldown; both mean stock exists
STOCK_COLOR = (21, 222, 51)
STOCK_RED   = (222, 21, 21)

# Result screen detection
RESULT_POS_OFFSET   = (364, 156)
RESULT_WIN_COLOR    = (230, 180, 20)
RESULT_LOSE_COLOR   = (220, 20, 20)

# Settings close button that appeared after AV update
RESTART_SETTINGS_CLOSE_OFFSET = (758, 151)

# Boss / Brook ultimate timing (seconds)
BROOK_ULT = 2.52
BOSS      = 7.79

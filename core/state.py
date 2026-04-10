import threading

# =========================
# Roblox window state (set by helpers.initialize / helpers._update_positions)
# =========================
rb_window = None
dx = 0
dy = 0

# =========================
# Runtime-mutable settings (overwritten by GUI at startup / on change)
# =========================
PRIVATE_SERVER_CODE    = ""  # paste your full private server link here
AUTO_REJOIN_AFTER_RUNS = 0       # 0 = disabled
VC_CHAT                = False   # True = use VC chat coord (202,64) instead of (145,64)
RUN_TIMEOUT            = 90.0    # max seconds per run before softlock watchdog fires
GLOBAL_REJOIN_TIMEOUT  = 300.0   # max seconds before full Roblox restart
WEBHOOK_URL            = ""      # Discord webhook URL (set via GUI)

# =========================
# Shared state dict (read by GUI tick loop)
# =========================
state = {
    "runs":           0,
    "wins":           0,
    "losses":         0,
    "session_start":  0.0,
    "run_start":      0.0,
    "run_timeout":    90.0,
    "running":        False,
    "last_webhook_ok": None,
}

# =========================
# Runtime flags
# =========================
SHUTDOWN             = False
USE_BROOK            = False
LAST_WEBHOOK_OK      = True
LAST_WEBHOOK_ATTEMPT = 0.0

# =========================
# Thread synchronization objects
# =========================
_click_lock  = threading.Lock()
_restart_run = threading.Event()   # set when a run should abort; cleared at start of each run
_match_active = threading.Event()  # set only during an active match
_restarting  = threading.Event()   # set during restart_match_ingame; pauses cancel detection

# =========================
# Thread handles
# =========================
_initialized       = False
_hotkey_registered = False
_macro_thread      = None

# =========================
# Runtime-computed position globals
# All start as (0, 0) and are populated by helpers._update_positions()
# =========================
BROOK_POS           = (0, 0)
ICHIGO_POS          = (0, 0)
SOKORA_POS          = (0, 0)
NEWSMAN_P1          = (0, 0)
UNIT_CLOSE          = (0, 0)
WAVE_SKIP           = (0, 0)
ABILITY1            = (0, 0)
ABILITY2            = (0, 0)
BROOK_ABILITY_CLOSE = (0, 0)
STOCK1              = (0, 0)
STOCK2              = (0, 0)
BOSS_ALIVE          = (0, 0)
PASSIVE_MENU_PIXEL  = (0, 0)
RESTART_SETTINGS_BTN = (0, 0)
RESTART_MATCH_BTN   = (0, 0)
RESTART_YES_BTN     = (0, 0)
RESTART_OK_BTN      = (0, 0)

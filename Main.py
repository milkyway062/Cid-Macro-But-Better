import logging
import pyautogui
import pygetwindow
import time
import os
import sys
import json
import requests
import subprocess
import ctypes
from datetime import datetime, timezone
from threading import Thread, Event
import threading
import io
import traceback
try:
    import psutil
except ImportError:
    raise SystemExit("psutil is not installed. Run: py -m pip install psutil")
sys.path.append(os.getcwd())
import InputHandler
import keyboard

# =========================
# Auto Rejoin Configuration
# =========================
PRIVATE_SERVER_CODE = "21768692868330557785126702085399"  # Set via GUI or change here
AUTO_REJOIN_AFTER_RUNS = 0  # 0 = disabled, set number of runs to enable
VC_CHAT = False  # Use VC chat close coord (202,64) instead of regular (145,64); set via GUI
REJOIN_TIMEOUT = 60  # Seconds to wait for rejoin before retry

# =========================
# Camera Setup Positions (relative to window)
# =========================
UNIT_PANEL_POS = (409, 309)
CAMERA_MOVE_OFFSET = (0, 10000)  # Relative mouse movement for camera

# =========================
# Return to Spawn Click Sequence (relative to window)
# =========================
RETURN_TO_SPAWN_CLICKS = [
    (30, 605),
    (708, 322),
    (755, 149)
]

# =========================
# Auto Positioner Images
# =========================
POSITIONER_IMAGES = [
    "Positioner\\Cid_Island.png",
    "Positioner\\Cid_Raid.png"
]

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# =========================
# Shared state (UI-accessible)
# =========================
state = {
    "runs": 0,
    "wins": 0,
    "losses": 0,
    "session_start": 0.0,
    "run_start": 0.0,
    "run_timeout": 90.0,
    "running": False,
    "last_webhook_ok": None,
}

# =========================
# Softlock / watchdog config
# =========================
RUN_TIMEOUT = 90.0            # max seconds a single run is allowed before watchdog force-restarts
GLOBAL_REJOIN_TIMEOUT = 300.0 # max seconds a run can take before full Roblox restart
LAST_WEBHOOK_OK = True
LAST_WEBHOOK_ATTEMPT = 0.0
SHUTDOWN = False  # cooperative shutdown flag for all loops


def _sleep(seconds: float, step: float = 0.05) -> bool:
    """Sleep for 'seconds', waking every 'step' to check SHUTDOWN.
    Returns True if completed normally, False if SHUTDOWN interrupted it."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if SHUTDOWN:
            return False
        time.sleep(min(step, max(0.0, deadline - time.time())))
    return True


def _key_hold(key: str, seconds: float) -> bool:
    """Hold a KEYMAP key for 'seconds', releasing immediately on SHUTDOWN.
    Returns True if completed, False if SHUTDOWN fired mid-hold."""
    InputHandler.KeyDown(KEYMAP[key])
    ok = _sleep(seconds)
    InputHandler.KeyUp(KEYMAP[key])
    return ok
_click_lock = threading.Lock()
_restart_run = threading.Event()   # set when cancel button detected; cleared each new run
_match_active = threading.Event()  # set only during an active match; gating cancel detection
_restarting = threading.Event()    # set during restart_match_ingame; pauses popup_watcher cancel detection
_initialized = False
_hotkey_registered = False
_macro_thread = None  # tracks the current macro worker thread

# Patch InputHandler.Click so all clicks are serialized under a lock
_original_click = InputHandler.Click
def _locked_click(x, y, delay):
    with _click_lock:
        _original_click(x, y, delay)
InputHandler.Click = _locked_click


# =========================
# Find Roblox window (best-effort at import; re-tried in initialize())
# =========================
rb_window = None
dx, dy = 0, 0
for _w in pygetwindow.getAllWindows():
    if _w.title == "Roblox":
        rb_window = _w
        break
if rb_window:
    dx, dy = rb_window.left, rb_window.top
else:
    logger.warning("Roblox window not found at import; will retry when Start is clicked.")

# =========================
# Keymap
# =========================
KEYMAP = {
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
    "f": 0x21,
    "g": 0x22,
    "x": 0x2D,
    "w": 0x11,
    "q": 0x10,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "i": 0x17,
    "o": 0x18,
    "e": 0x12,
    "v": 0x2F,
    "shift": 0x2A
}

# =========================
# Unit placement positions (computed from dx/dy; refreshed in _update_positions)
# =========================
BROOK_POS = (403 + dx, 372 + dy)
ICHIGO_POS = (412 + dx, 303 + dy)
SOKORA_POS = (421 + dx, 262 + dy)
NEWSMAN_P1 = (370 + dx, 324 + dy)

UNIT_CLOSE = (305 + dx, 233 + dy)
WAVE_SKIP = (616 + dx, 40 + dy)
ABILITY1 = (333 + dx, 278 + dy)
ABILITY2 = (333 + dx, 338 + dy)
BROOK_ABILITY_CLOSE = (590 + dx, 183 + dy)
STOCK1 = (601 + dx, 41 + dy)
STOCK2 = (356 + dx, 41 + dy)
STOCK_COLOR = (21, 222, 51)
BOSS_ALIVE = (310 + dx, 113 + dy)
BROOK_ULT = 2.52
BOSS = 7.79

PASSIVE_MENU_PIXEL = (35 + dx, 543 + dy)

RESTART_SETTINGS_BTN = (26  + dx, 610 + dy)
RESTART_MATCH_BTN    = (704 + dx, 292 + dy)
RESTART_YES_BTN      = (351 + dx, 367 + dy)
RESTART_OK_BTN       = (407 + dx, 360 + dy)


def _update_positions():
    """Re-compute all position globals after dx/dy change (e.g. window moved)."""
    global BROOK_POS, ICHIGO_POS, SOKORA_POS, NEWSMAN_P1
    global UNIT_CLOSE, WAVE_SKIP, ABILITY1, ABILITY2, BROOK_ABILITY_CLOSE
    global STOCK1, STOCK2, BOSS_ALIVE, PASSIVE_MENU_PIXEL
    global RESTART_SETTINGS_BTN, RESTART_MATCH_BTN,RESTART_YES_BTN, RESTART_OK_BTN
    BROOK_POS            = (403 + dx, 372 + dy)
    ICHIGO_POS           = (412 + dx, 303 + dy)
    SOKORA_POS           = (421 + dx, 262 + dy)
    NEWSMAN_P1           = (370 + dx, 324 + dy)
    UNIT_CLOSE           = (305 + dx, 233 + dy)
    WAVE_SKIP            = (616 + dx,  40 + dy)
    ABILITY1             = (333 + dx, 278 + dy)
    ABILITY2             = (333 + dx, 338 + dy)
    BROOK_ABILITY_CLOSE  = (590 + dx, 183 + dy)
    STOCK1               = (601 + dx,  41 + dy)
    STOCK2               = (356 + dx,  41 + dy)
    BOSS_ALIVE           = (310 + dx, 113 + dy)
    PASSIVE_MENU_PIXEL   = ( 35 + dx, 543 + dy)
    RESTART_SETTINGS_BTN = ( 26 + dx, 610 + dy)
    RESTART_MATCH_BTN    = (704 + dx, 292 + dy)
    RESTART_YES_BTN      = (351 + dx, 367 + dy)
    RESTART_OK_BTN       = (407 + dx, 360 + dy)


# =========================
# Webhook
# =========================
WEBHOOK_URL = ""  # Set via UI text box or replace here directly

def send_webhook(run_time: str, win: int, lose: int, task_name: str, img_bytes=None, retries: int = 3):
    global LAST_WEBHOOK_OK, LAST_WEBHOOK_ATTEMPT
    LAST_WEBHOOK_ATTEMPT = time.time()

    if not WEBHOOK_URL or not WEBHOOK_URL.startswith("https://discord.com/api/webhooks/"):
        logger.info("Webhook URL not configured; skipping webhook.")
        LAST_WEBHOOK_OK = False
        return False

    total_runs = win + lose
    if total_runs == 0:
        logger.warning("No wins or losses detected; skipping webhook.")
        LAST_WEBHOOK_OK = True
        return False

    win_ratio = (win / total_runs) * 100

    embed = {
        "title": "Loxer's Automation",
        "description": "",
        "color": 3447003,
        "fields": [
            {"name": "🕒 Run Time", "value": run_time, "inline": True},
            {"name": "⚔️ Wins", "value": str(win), "inline": True},
            {"name": "📈 Success Rate", "value": f"{win_ratio:.2f}%", "inline": True},
            {"name": "🔁 Total Runs", "value": str(total_runs), "inline": True},
            {"name": "⚙️ Current Task", "value": task_name}
        ],
        "image": {"url": "attachment://screenshot.png"} if img_bytes else {},
        "thumbnail": {"url": "https://media1.tenor.com/m/1VbR3kVavicAAAAC/gin.gif"},
        "footer": {"text": f"Loxer's Automation | Run time: {run_time}"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    payload = {
        "username": "Loxer's Automation",
        "avatar_url": "https://media1.tenor.com/m/mbhL7DZmXEMAAAAC/%D0%B0%D0%B0%D0%B0%D0%B0.gif",
        "embeds": [embed]
    }

    for attempt in range(1, retries + 1):
        try:
            if img_bytes:
                files = {"file": ("screenshot.png", img_bytes, "image/png")}
                data = {"payload_json": json.dumps(payload)}
                resp = requests.post(WEBHOOK_URL, data=data, files=files, timeout=10)
            else:
                headers = {"Content-Type": "application/json"}
                resp = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=10)

            if resp.status_code in (200, 201, 204):
                logger.info("Webhook sent successfully (attempt %d).", attempt)
                LAST_WEBHOOK_OK = True
                state["last_webhook_ok"] = True
                return True
            else:
                logger.warning("Webhook attempt %d failed: %s %s", attempt, resp.status_code, resp.text)
        except requests.RequestException:
            logger.exception("Webhook attempt %d raised an exception", attempt)
        time.sleep(1)

    logger.error("All %d webhook attempts failed.", retries)
    LAST_WEBHOOK_OK = False
    state["last_webhook_ok"] = False
    return False


def close_chat_and_objectives():
    """
    Close objectives UI, then double-click the chat button to ensure it closes.
    No-VC coord = (145, 64), VC coord = (202, 64). Objectives = (214, 353).
    """
    if rb_window:
        try:
            rb_window.activate()
        except Exception:
            pass
        _sleep(0.2)
    InputHandler.Click(214 + dx, 353 + dy, delay=0.1)
    _sleep(0.3)
    chat_x = 202 if VC_CHAT else 145
    InputHandler.Click(chat_x + dx, 64 + dy, delay=0.2)
    InputHandler.Click(chat_x + dx, 64 + dy, delay=0.2)
    logger.info("Chat double-clicked (x=%d)", chat_x)
    _sleep(0.5)


# =========================
# Auto Positioning Functions
# =========================


def auto_positioner(positioner_name: str, just_camera: bool = False):
    """
    Auto positioner for Cid raid.
    Resets camera via zoom keys, then walks back to spawn.
    If not just_camera, also polls for a positioner screenshot match.
    """
    logger.info("Starting auto positioner for %s", positioner_name)
    if not _sleep(1):
        return False

    try:
        # Click somewhere neutral to ensure Roblox has focus
        InputHandler.Click(UNIT_PANEL_POS[0] + dx, UNIT_PANEL_POS[1] + dy, delay=0.1)

        # Reset camera: hold zoom-in then zoom-out to get a consistent angle
        if not _key_hold("i", 2):
            return False

        # Nudge mouse down to tilt camera
        ctypes.windll.user32.mouse_event(0x0001, 0, CAMERA_MOVE_OFFSET[1], 0, 0)
        if not _sleep(1):
            return False

        if not _key_hold("o", 2):
            return False

        logger.info("Camera reset complete")

        if just_camera:
            # Match may have ended during camera setup — click retry if so
            if _check_match_end():
                InputHandler.Click(355 + dx, 470 + dy, delay=0.1)
                if not _sleep(5):
                    return False
                InputHandler.Click(UNIT_PANEL_POS[0] + dx, UNIT_PANEL_POS[1] + dy, delay=0.1)
            return_to_spawn()
            if not _sleep(1):
                return False
            InputHandler.RightClick(139 + dx, 343 + dy, delay=0.1)
            logger.info("Auto positioner done (camera only)")
            return True

        # Poll until one of the positioner reference images matches on screen
        logger.info("Polling for positioner image match...")
        deadline = time.time() + 60
        while time.time() < deadline:
            if SHUTDOWN:
                return False

            for img in POSITIONER_IMAGES:
                loc = _wait_for_image(img, timeout=1.0, confidence=0.85)
                if loc:
                    logger.info("Positioner matched: %s", img)
                    return True

            # If match ended while we were waiting, click retry and try again
            if _check_match_end():
                logger.info("Match ended during positioning — retrying")
                InputHandler.Click(355 + dx, 470 + dy, delay=0.1)
                if not _sleep(5):
                    return False
                InputHandler.Click(UNIT_PANEL_POS[0] + dx, UNIT_PANEL_POS[1] + dy, delay=0.1)

            return_to_spawn()
            if not _sleep(2):
                return False

        logger.warning("Positioner not found within 60s")
        return False

    except Exception:
        logger.exception("auto_positioner failed")
        return False


def _check_match_end():
    """Check if match has ended (Victory or Failed)."""
    try:
        # Check Victory.png
        if _wait_for_image("Victory.png", timeout=2.0, confidence=0.9):
            return True
        # Check Failed.png
        if _wait_for_image("Failed.png", timeout=2.0, confidence=0.9):
            return True
    except Exception:
        pass
    return False


def click_retry_button():
    """Click retry button if match ended."""
    try:
        # Try to find retry button
        retry_pos = _wait_for_image("Retry.png", timeout=3.0, confidence=0.8)
        if retry_pos:
            cx, cy = pyautogui.center(retry_pos)
            InputHandler.Click(cx, cy, delay=0.1)
            logger.info("Retry button clicked")
            return
        # Fallback - click bottom center
        InputHandler.Click(355 + dx, 470 + dy, delay=0.5)
        logger.info("Fallback retry click")
    except Exception as e:
        logger.exception("click_retry_button failed")


def return_to_spawn():
    """Click through return to spawn sequence (window-relative coords + dx/dy)."""
    logger.info("Returning to spawn")
    for pos in RETURN_TO_SPAWN_CLICKS:
        if SHUTDOWN: return
        InputHandler.Click(pos[0] + dx, pos[1] + dy, delay=0.2)
        _sleep(0.8)
    logger.info("Return to spawn complete")


# =========================
# Auto Rejoin Functions
# =========================
def get_roblox_exe_path() -> str | None:
    """Find and return the path to the running RobloxPlayerBeta.exe, or None."""
    try:
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                if "robloxplayerbeta" in proc.name().lower():
                    return proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        logger.exception("get_roblox_exe_path failed")
    return None


def _do_roblox_rejoin() -> bool:
    """
    Kill Roblox, relaunch it into the private server, and wait for the game to load.
    Returns True on success, False on failure.
    This is the shared core used by both disconnect_checker and auto_rejoin.
    """
    global rb_window, dx, dy

    # Find exe path before killing the process
    roblox_exe = get_roblox_exe_path()
    if not roblox_exe:
        logger.error("_do_roblox_rejoin: could not find RobloxPlayerBeta.exe")
        return False

    # Save window position/size before killing so we can restore it
    saved_rect = None
    if rb_window:
        try:
            saved_rect = (rb_window.left, rb_window.top, rb_window.width, rb_window.height)
            logger.info("Saved window rect: %s", saved_rect)
        except Exception:
            logger.warning("Could not save window rect")

    # Kill all Roblox processes
    logger.info("Killing Roblox processes")
    for proc in psutil.process_iter(["name"]):
        try:
            if "roblox" in proc.name().lower():
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _sleep(2)

    # Relaunch into private server
    rejoin_url = f"roblox://placeId=16146832113&linkCode={PRIVATE_SERVER_CODE}/"
    logger.info("Launching Roblox: %s", rejoin_url)
    subprocess.Popen([roblox_exe, rejoin_url])

    # Wait up to REJOIN_TIMEOUT seconds for the game to load
    deadline = time.time() + REJOIN_TIMEOUT
    while time.time() < deadline:
        if SHUTDOWN:
            return False

        # Re-locate the Roblox window in case it moved
        for w in pygetwindow.getAllWindows():
            if w.title == "Roblox":
                rb_window = w
                break

        if _wait_for_image("IsInGame.png", timeout=3.0, confidence=0.8):
            logger.info("Roblox reloaded successfully")
            _sleep(10)  # let it finish loading (interruptible)

            # Restore window to saved position/size
            if rb_window and saved_rect:
                try:
                    rb_window.moveTo(saved_rect[0], saved_rect[1])
                    rb_window.resizeTo(saved_rect[2], saved_rect[3])
                    logger.info("Restored window rect: %s", saved_rect)
                except Exception:
                    logger.warning("Could not restore window rect")

            # Recompute offsets now that window may have respawned
            if rb_window:
                dx, dy = rb_window.left, rb_window.top
                _update_positions()

            # Dismiss leaderboard (always press Tab — no detection needed)
            pyautogui.press("tab")
            time.sleep(1)

            return True

        time.sleep(2)

    logger.error("_do_roblox_rejoin: timed out waiting for game to load")
    return False


def disconnect_checker():
    """
    Daemon thread: watches for Roblox disconnect and rejoins automatically.
    Does NOT kill or restart the Python process — the macro thread keeps running.
    """
    logger.info("Disconnect checker started")
    while not SHUTDOWN:
        try:
            if _wait_for_image("Disconnected.png", timeout=2.0, confidence=0.9):
                logger.warning("Disconnect detected — rejoining")
                _restart_run.set()   # abort the current run cleanly
                _match_active.clear()
                ok = _do_roblox_rejoin()
                if ok:
                    logger.info("Rejoin successful, macro will restart run")
                else:
                    logger.error("Rejoin failed")
        except Exception:
            logger.exception("disconnect_checker error")
        time.sleep(2)
    logger.info("Disconnect checker stopped")


def _img(name: str) -> str:
    """Return absolute path for an image in the Images folder."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "Images", name)


# =========================
# Input helpers
# =========================
def exit_handler(x):
    """Called by the ; hotkey — stops the macro cooperatively (UI stays open)."""
    logger.info("Kill switch pressed — stopping macro.")
    stop()

def press(key: str) -> None:
    try:
        InputHandler.KeyDown(KEYMAP[key])
        time.sleep(0.02)
        InputHandler.KeyUp(KEYMAP[key])
    except Exception:
        logger.exception("press(%s) failed", key)

def place(unit: int, pos: tuple, max_retries=4, per_attempt_timeout=1.2) -> bool:
    logger.info("Placing Unit %s at %s (max_retries=%d)", unit, pos, max_retries)
    key = f"{unit}"
    for attempt in range(1, max_retries + 1):
        if SHUTDOWN:
            logger.info("Shutdown requested during place()")
            return False

        try:
            press(key)
            time.sleep(0.06)
            InputHandler.Click(*pos, delay=0.1)
        except Exception:
            logger.exception("Error sending input for place(%s) attempt %d", unit, attempt)

        start = time.time()
        while True:
            if SHUTDOWN:
                logger.info("Shutdown requested during place() wait")
                return False
            try:
                if pyautogui.pixelMatchesColor(*UNIT_CLOSE, expectedRGBColor=(255, 255, 255), tolerance=30):
                    logger.debug("place(): UNIT_CLOSE detected after attempt %d", attempt)
                    return True
                if pyautogui.pixelMatchesColor(725 + dx, 169 + dy, (255, 255, 255), tolerance=30):
                    logger.debug("place(): generic confirmation pixel detected after attempt %d", attempt)
                    return True
            except Exception:
                traceback.print_exc()
                break

            if time.time() - start > per_attempt_timeout:
                logger.warning("place(): attempt %d timed out after %.2fs", attempt, per_attempt_timeout)
                break

            time.sleep(0.05)

    logger.error("place(): all %d attempts failed for unit %s at %s", max_retries, unit, pos)
    return False

def select(pos: tuple):
    logger.info("Selecting unit at %s", pos)
    try:
        InputHandler.Click(*UNIT_CLOSE, delay=0.1)
        timedelta = time.time()
        InputHandler.Click(*pos, delay=0.1)
        while not pyautogui.pixelMatchesColor(*UNIT_CLOSE, expectedRGBColor=(255, 255, 255), tolerance=30):
            if SHUTDOWN or _restart_run.is_set():
                return
            if pyautogui.pixelMatchesColor(725 + dx, 169 + dy, (255, 255, 255), tolerance=30):
                break
            if time.time() - timedelta > 0.9:
                InputHandler.Click(*pos, delay=0.1)
                timedelta = time.time()
            time.sleep(0.01)
        logger.info("Selected unit at %s", pos)
    except Exception:
        logger.exception("select(%s) failed", pos)

def _img(name: str) -> str:
    """Return absolute path for an image in the Images folder."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "Images", name)


def _wait_for_image(name: str, timeout: float = 5.0, confidence: float = 0.7) -> object:
    """Poll for an image on screen; return its Box location or None on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if SHUTDOWN:
            return None
        try:
            loc = pyautogui.locateOnScreen(_img(name), confidence=confidence, grayscale=True)
            if loc:
                return loc
        except pyautogui.ImageNotFoundException:
            pass
        except Exception:
            logger.exception("_wait_for_image(%s) error", name)
        time.sleep(0.1)
    logger.debug("_wait_for_image(%s) timed out after %.1fs", name, timeout)
    return None


def restart_match_ingame():
    """Click through settings → Restart Match → Yes → confirmation button."""
    _restarting.set()
    try:
        logger.info("Restarting match via settings menu")

        # Step 1: open settings; wait for settings.png to appear then click Restart Match via offset
        InputHandler.Click(*RESTART_SETTINGS_BTN, delay=0.1)
        loc = _wait_for_image("settings.png", timeout=15.0)
        if loc:
            logger.info("Settings detected, clicking Restart Match")
            time.sleep(0.5)
        else:
            logger.warning("Settings page not detected; proceeding anyway")
        InputHandler.Click(*RESTART_MATCH_BTN, delay=0.1)

        # Step 2: fixed delay then click Yes
        time.sleep(0.5)
        InputHandler.Click(*RESTART_YES_BTN, delay=0.1)

        # Step 3: wait for confirmation dialog; click it
        loc = _wait_for_image("restart_confirmation.png", timeout=5.0)
        if loc:
            cx, cy = pyautogui.center(loc)
            InputHandler.Click(cx - 55, cy + 81, 0.1)
            logger.info("Restart confirmation clicked")
        else:
            logger.warning("restart_confirmation not detected; falling back to hardcoded Ok")
            InputHandler.Click(*RESTART_OK_BTN, delay=0.3)

    except Exception:
        logger.exception("restart_match_ingame failed")
    finally:
        _restarting.clear()

def cleanup_after_abort():
    """Deselect unit, close unit manager, then restart the match."""
    logger.info("Abort cleanup started")
    state["losses"] += 1
    state["runs"] += 1
    _match_active.clear()
    try:
        InputHandler.Click(*PASSIVE_MENU_PIXEL, delay=0.1)
    except Exception:
        logger.exception("cleanup_after_abort: deselect click failed")
    try:
        if pyautogui.pixelMatchesColor(615 + dx, 88 + dy, (11, 231, 241), tolerance=40):
            press("f")
    except Exception:
        logger.exception("cleanup_after_abort: unit manager close failed")
    time.sleep(0.3)
    if _restarting.is_set():
        logger.info("Abort cleanup waiting for watchdog restart to finish")
        while _restarting.is_set() and not SHUTDOWN:
            time.sleep(0.1)
    else:
        restart_match_ingame()
    logger.info("Abort cleanup done")

def dismiss_passive_menu():
    """Detect PASSIVE title text on screen; if found, click off-screen bottom-left to close it."""
    try:
        location = pyautogui.locateOnScreen(
            image=_img("passive_title.png"),
            grayscale=True,
            confidence=0.6,
        )
        if location:
            InputHandler.Click(*PASSIVE_MENU_PIXEL, delay=0.1)
            logger.info("Passive menu detected and dismissed")
            return True
    except pyautogui.ImageNotFoundException:
        pass
    except Exception:
        logger.exception("dismiss_passive_menu failed")
    return False

def click_vote_start():
    """Detect and click the Vote Start button if present."""
    try:
        location = pyautogui.locateOnScreen(
            image=_img("vote_start.png"),
            grayscale=True,
            confidence=0.6,
        )
        if location:
            cx, cy = pyautogui.center(location)
            cx += 124  # offset: image center is on text, button is 124px to the right
            InputHandler.Click(cx, cy, delay=0.1)
            logger.info("Vote start clicked at (%d, %d)", cx, cy)
            return True
    except pyautogui.ImageNotFoundException:
        pass
    except Exception:
        logger.exception("click_vote_start failed")
    return False

def dismiss_cancel_button():
    """Locate Cancel button via image match and click its center."""
    if _restarting.is_set() or not _match_active.is_set():
        return False
    try:
        location = pyautogui.locateOnScreen(
            image=_img("ability_in_use.png"),
            grayscale=True,
            confidence=0.6,
        )
        if location:
            cx, cy = pyautogui.center(location)
            InputHandler.Click(cx, cy, delay=0.1)
            logger.info("Cancel button clicked at (%d, %d) — aborting run", cx, cy)
            _restart_run.set()
            return True
    except pyautogui.ImageNotFoundException:
        pass
    except Exception:
        logger.exception("dismiss_cancel_button failed")
    return False

def brook_buff():
    logger.info("Doing Brook Buff")
    start = time.time()
    keys = ["a", "s", "d", "f", "g"]
    InputHandler.MoveTo(*BROOK_ABILITY_CLOSE)

    while True:
        if SHUTDOWN:
            return
        try:
            ability_open = pyautogui.pixelMatchesColor(*BROOK_ABILITY_CLOSE, (255, 255, 255), tolerance=30)
        except Exception:
            ability_open = False
            logger.exception("Error checking BROOK_ABILITY_CLOSE pixel")

        if ability_open:
            for k in keys:
                InputHandler.KeyDown(KEYMAP[k])
            time.sleep(0.02)
            for k in keys:
                InputHandler.KeyUp(KEYMAP[k])

            if time.time() - start > 6:
                if pyautogui.pixelMatchesColor(*WAVE_SKIP, expectedRGBColor=(255, 255, 255), tolerance=30):
                    logger.info("Wave skip detected during brook_buff")
                    break
        else:
            InputHandler.Click(*ABILITY1, delay=0.1)
            time.sleep(0.2)

            if time.time() - start > 8:
                logger.error("Brook ability never opened -> skipping")
                break

    InputHandler.Click(*BROOK_ABILITY_CLOSE, 0.1)
    logger.info("Brook buff done")


# =========================
# Boss watcher
# =========================
USE_BROOK = False

def boss_watcher():
    global USE_BROOK
    while True:
        try:
            while not _match_active.is_set():
                if SHUTDOWN:
                    return
                time.sleep(0.1)

            while not pyautogui.pixelMatchesColor(*BOSS_ALIVE, (255, 255, 255), tolerance=30):
                if SHUTDOWN or not _match_active.is_set():
                    break
                time.sleep(0.1)

            if not _match_active.is_set():
                continue

            while pyautogui.pixelMatchesColor(*BOSS_ALIVE, (255, 255, 255), tolerance=30):
                if SHUTDOWN or not _match_active.is_set():
                    break
                time.sleep(0.1)

            if not _match_active.is_set():
                continue

            boss_dead = time.time()
            logger.info("Boss is dead, starting ult offset wait")
            while time.time() - boss_dead < (BOSS - BROOK_ULT + 0.15):
                if SHUTDOWN or not _match_active.is_set():
                    break
                time.sleep(0.1)

            if not _match_active.is_set():
                continue

            USE_BROOK = True
            logger.info("USE_BROOK set; main loop should trigger Brook ult")
            while USE_BROOK:
                if SHUTDOWN:
                    return
                time.sleep(0.1)
        except Exception:
            logger.exception("boss_watcher encountered an error")
            time.sleep(0.5)


# =========================
# Popup watcher
# =========================
def _handle_settings_page():
    """If settings page is open unexpectedly, close it."""
    if _restarting.is_set() or _restart_run.is_set():
        return
    try:
        loc = pyautogui.locateOnScreen(_img("settings.png"), grayscale=True, confidence=0.7)
        if loc:
            InputHandler.Click(*RESTART_MATCH_BTN, delay=0.1)
            logger.info("Settings page detected by watcher, clicked Restart Match")
    except pyautogui.ImageNotFoundException:
        pass
    except Exception:
        logger.exception("_handle_settings_page error")

def popup_watcher():
    logger.info("Popup watcher started")
    while not SHUTDOWN:
        try:
            dismiss_passive_menu()
            dismiss_cancel_button()
        except Exception:
            logger.exception("popup_watcher error")
        time.sleep(0.1)


# =========================
# Softlock watchdog (runs forever; uses state["run_start"] and state["run_timeout"])
# =========================
def softlock_watchdog():
    logger.info("Softlock watchdog started")
    while True:
        try:
            run_start = state["run_start"]
            if run_start > 0:
                elapsed = time.time() - run_start
                if elapsed > state["run_timeout"]:
                    logger.error("Run timeout hit (%.1fs elapsed) — force restarting run", elapsed)
                    _restart_run.set()
                    state["run_start"] = 0.0
                    try:
                        restart_match_ingame()
                    except Exception:
                        logger.exception("watchdog: restart_match_ingame failed")  # prevent re-triggering until the next run starts
            time.sleep(1.0)
        except Exception:
            logger.exception("softlock_watchdog encountered an error")
            time.sleep(1.0)


def global_rejoin_watchdog():
    """
    Daemon thread: if a single run exceeds GLOBAL_REJOIN_TIMEOUT (5 min), kill and
    restart Roblox entirely. Resets the auto-rejoin run counter so it doesn't
    immediately trigger again on the fresh session.
    Only active while a run is in progress (state["run_start"] > 0).
    """
    logger.info("Global rejoin watchdog started")
    while True:
        try:
            run_start = state["run_start"]
            if run_start > 0 and not SHUTDOWN:
                elapsed = time.time() - run_start
                if elapsed > GLOBAL_REJOIN_TIMEOUT:
                    logger.error(
                        "Global rejoin watchdog: run exceeded %.0fs — restarting Roblox",
                        elapsed,
                    )
                    state["run_start"] = 0.0  # prevent re-trigger while restarting
                    state["runs"] = 0          # reset auto-rejoin run counter
                    _restart_run.set()         # abort current run cleanly
                    _do_roblox_rejoin()
            time.sleep(1.0)
        except Exception:
            logger.exception("global_rejoin_watchdog error")
            time.sleep(1.0)


# =========================
# Initialize / Start / Stop
# =========================
def initialize() -> bool:
    """Find the Roblox window, update coordinates, register hotkey. Returns True on success."""
    global rb_window, dx, dy, _initialized, _hotkey_registered
    rb_window = None
    for w in pygetwindow.getAllWindows():
        if w.title == "Roblox":
            rb_window = w
            break
    if not rb_window:
        logger.error("Roblox window not found.")
        return False
    dx, dy = rb_window.left, rb_window.top
    _update_positions()
    # Hotkeys (F1/F6) are registered by the GUI; nothing to do here
    _hotkey_registered = True
    _initialized = True
    logger.info("Initialized: Roblox window at (%d, %d)", dx, dy)
    return True


def start() -> bool:
    """Start the macro in a background thread. Returns False if Roblox not found."""
    global SHUTDOWN, _macro_thread
    if not initialize():
        return False
    SHUTDOWN = False
    state["running"] = True
    state["runs"] = 0
    state["wins"] = 0
    state["losses"] = 0
    state["session_start"] = time.time()
    state["run_start"] = 0.0

    # Start disconnect checker thread
    Thread(target=disconnect_checker, daemon=True).start()
    Thread(target=boss_watcher, daemon=True).start()
    Thread(target=popup_watcher, daemon=True).start()
    _macro_thread = Thread(target=main_loop, daemon=True)
    _macro_thread.start()
    return True


def stop():
    """Stop the macro cooperatively. Watcher threads will exit on their next SHUTDOWN check."""
    global SHUTDOWN
    SHUTDOWN = True
    state["running"] = False
    state["run_start"] = 0.0
    logger.info("Macro stop requested.")


# =========================
# Main loop
# =========================
def main_loop():
    logger.info("Main loop started")
    positioned = False
    chat_closed = False

    while not SHUTDOWN:
        _restart_run.clear()
        _match_active.clear()
        global USE_BROOK
        USE_BROOK = False
        state["run_start"] = time.time()
        logger.info("==== New run ====")

        # If we are in the lobby (e.g. after a rejoin or first start), navigate to Cid Raid
        if is_in_lobby() or _daily_rewards_visible():
            logger.info("In lobby — dismissing UI then navigating to Cid Raid")
            positioned = False   # reset so positioner runs again after rejoin
            chat_closed = False
            prepare_lobby()
            if SHUTDOWN:
                break
            if not lobby_path_cid_raid():
                continue
            if SHUTDOWN:
                break

        # Wait for vote_start, click it, then fall through to spawn detection
        VOTE_START_TIMEOUT = 60.0
        vote_wait_start = time.time()
        logger.info("Waiting for vote_start")
        while not SHUTDOWN and not _restart_run.is_set():
            if time.time() - vote_wait_start > VOTE_START_TIMEOUT:
                logger.warning("vote_start not seen within %.1fs, proceeding anyway", VOTE_START_TIMEOUT)
                break
            if _restarting.is_set():
                time.sleep(0.1)
                continue
            # Cancel popup takes priority — dismiss it without aborting (it's the "match restarted" alert)
            try:
                cancel_loc = pyautogui.locateOnScreen(
                    image=_img("ability_in_use.png"),
                    grayscale=True,
                    confidence=0.6,
                )
                if cancel_loc:
                    cx, cy = pyautogui.center(cancel_loc)
                    InputHandler.Click(cx, cy, delay=0.1)
                    logger.info("Cancel popup dismissed during vote_start wait")
                    time.sleep(0.1)
                    continue
            except pyautogui.ImageNotFoundException:
                pass
            except Exception:
                pass
            try:
                location = pyautogui.locateOnScreen(
                    image=_img("vote_start.png"),
                    grayscale=True,
                    confidence=0.6,
                )
                if location:
                    # Final safety check: don't click vote_start if cancel popup is visible
                    try:
                        cancel_check = pyautogui.locateOnScreen(
                            image=_img("ability_in_use.png"),
                            grayscale=True,
                            confidence=0.6,
                        )
                        if cancel_check:
                            cx2, cy2 = pyautogui.center(cancel_check)
                            InputHandler.Click(cx2, cy2, delay=0.1)
                            logger.info("Cancel popup dismissed — delaying vote_start click")
                            time.sleep(0.1)
                            continue
                    except Exception:
                        pass
                    cx, cy = pyautogui.center(location)
                    cx += 124  # button is 124px right of image center
                    InputHandler.Click(cx, cy, delay=0.1)
                    logger.info("Vote start clicked at (%d, %d), proceeding to spawn detection", cx, cy)
                    break
            except pyautogui.ImageNotFoundException:
                pass
            except Exception:
                logger.exception("vote_start wait error")
            time.sleep(0.1)

        if SHUTDOWN:
            break
        if _restart_run.is_set():
            cleanup_after_abort()
            continue

        try:
            if pyautogui.pixelMatchesColor(615 + dx, 88 + dy, (11, 231, 241), tolerance=40):
                press("f")
        except Exception:
            logger.exception("Error checking unit manager pixel")

        logger.info("Waiting for spawn")
        while not pyautogui.pixelMatchesColor(394 + dx, 123 + dy, expectedRGBColor=(10, 10, 10), tolerance=30):
            if SHUTDOWN or _restart_run.is_set():
                break
            if pyautogui.pixelMatchesColor(725 + dx, 169 + dy, (255, 255, 255), tolerance=30):
                InputHandler.Click(374 + dx, 474 + dy, 0.1)
            try:
                cancel_loc = pyautogui.locateOnScreen(
                    image=_img("ability_in_use.png"),
                    grayscale=True,
                    confidence=0.6,
                )
                if cancel_loc:
                    cx, cy = pyautogui.center(cancel_loc)
                    InputHandler.Click(cx, cy, delay=0.1)
                    logger.info("Cancel popup dismissed during spawn wait")
            except Exception:
                pass
            time.sleep(0.1)

        if SHUTDOWN:
            break
        if _restart_run.is_set():
            cleanup_after_abort()
            continue

        while pyautogui.pixelMatchesColor(394 + dx, 123 + dy, expectedRGBColor=(10, 10, 10), tolerance=30):
            if SHUTDOWN or _restart_run.is_set():
                break
            InputHandler.Click(472 + dx, 127 + dy, 0.1)
            try:
                cancel_loc = pyautogui.locateOnScreen(
                    image=_img("ability_in_use.png"),
                    grayscale=True,
                    confidence=0.6,
                )
                if cancel_loc:
                    cx, cy = pyautogui.center(cancel_loc)
                    InputHandler.Click(cx, cy, delay=0.1)
                    logger.info("Cancel popup dismissed during spawn confirm wait")
            except Exception:
                pass
            time.sleep(0.3)

        if SHUTDOWN:
            break
        if _restart_run.is_set():
            cleanup_after_abort()
            continue

        match_start = time.time()
        _match_active.set()
        logger.info("Match %d Started", state["runs"])
        try:
            if pyautogui.pixelMatchesColor(615 + dx, 88 + dy, (11, 231, 241), tolerance=40):
                press("f")
        except Exception:
            logger.exception("Error checking unit manager pixel after start")

        if SHUTDOWN:
            break

        # First thing on spawn: close objectives UI + chat (only once per session/rejoin)
        if not chat_closed:
            close_chat_and_objectives()
            chat_closed = True

        if SHUTDOWN:
            break

        if not positioned:
            # Close leaderboard before positioning (Tab is safe even if already closed)
            pyautogui.press("tab")
            _sleep(0.5)
            auto_positioner("Cid_Raid", just_camera=True)
            positioned = True
            if SHUTDOWN:
                break
            if not _sleep(1):
                break
            restart_match_ingame()
            if SHUTDOWN:
                break
            continue  # loop back: vote_start → spawn → real run (positioned=True, skips positioner)

        place(4, BROOK_POS)
        place(1, ICHIGO_POS)

        select(BROOK_POS)
        InputHandler.Click(*ABILITY1, delay=0.1)
        brook_buff()

        if SHUTDOWN:
            break
        brook_wait_start = time.time()
        BROOK_WAIT_TIMEOUT = 6.0
        while True:
            if SHUTDOWN:
                break
            try:
                if not pyautogui.pixelMatchesColor(*BROOK_ABILITY_CLOSE, (255, 255, 255), tolerance=30):
                    break
            except Exception:
                traceback.print_exc()
                break
            if time.time() - brook_wait_start > BROOK_WAIT_TIMEOUT:
                logger.warning("BROOK_ABILITY_CLOSE wait exceeded %.1fs; proceeding", BROOK_WAIT_TIMEOUT)
                break
            time.sleep(0.1)

        NEWSMAN_RETRY_DELAY = 0.6
        newsman_placed = False
        newsman_attempts = 0
        while not SHUTDOWN and not newsman_placed and not _restart_run.is_set():
            newsman_attempts += 1
            logger.info("Attempting to place Newsman (attempt %d)", newsman_attempts)
            try:
                place(5, NEWSMAN_P1)
            except Exception:
                logger.exception("Unexpected error while calling place() for Newsman")

            time.sleep(0.25)

            try:
                if (pyautogui.pixelMatchesColor(*UNIT_CLOSE, expectedRGBColor=(255, 255, 255), tolerance=30)
                        or pyautogui.pixelMatchesColor(725 + dx, 169 + dy, (255, 255, 255), tolerance=30)):
                    logger.info("Newsman placement confirmed")
                    newsman_placed = True
                    break
            except Exception:
                traceback.print_exc()

            logger.warning("Newsman placement not confirmed; retrying in %.2fs", NEWSMAN_RETRY_DELAY)
            time.sleep(NEWSMAN_RETRY_DELAY)

        time.sleep(0.2)

        try:
            if not place(3, SOKORA_POS):
                logger.warning("Sokora placement failed on first attempt")
        except Exception:
            logger.exception("Error placing Sokora")

        while pyautogui.pixelMatchesColor(*STOCK1, STOCK_COLOR, tolerance=40):
            if SHUTDOWN or _restart_run.is_set():
                break
            if pyautogui.pixelMatchesColor(725 + dx, 169 + dy, (255, 255, 255), tolerance=30):
                break
            press("q")
            select(SOKORA_POS)
            InputHandler.Click(*ABILITY1, delay=0.1)
            InputHandler.Click(*ICHIGO_POS, delay=0.1)
            time.sleep(0.4)

        if SHUTDOWN:
            break
        if _restart_run.is_set():
            cleanup_after_abort()
            continue
        press("f")
        start_section = time.time()
        while not SHUTDOWN:
            if _restart_run.is_set():
                break
            try:
                if pyautogui.pixelMatchesColor(615 + dx, 88 + dy, (11, 231, 241), tolerance=40):
                    break
            except Exception:
                traceback.print_exc()
            if time.time() - start_section > 5:
                logger.warning("Unit manager failed to open within 5s")
                break
            time.sleep(0.1)

        if SHUTDOWN:
            break
        select(SOKORA_POS)
        First = False
        while True:
            if SHUTDOWN or _restart_run.is_set():
                break
            if pyautogui.pixelMatchesColor(725 + dx, 169 + dy, (255, 255, 255), tolerance=30):
                break
            logger.debug("Attempting Sokora -> Gohan")
            press("q")
            if First and pyautogui.pixelMatchesColor(332 + dx, 317 + dy, expectedRGBColor=(216, 14, 18), tolerance=50):
                select(SOKORA_POS)
            InputHandler.Click(*ABILITY1, delay=0.1)

            try:
                gohan_location = pyautogui.locateOnScreen(
                    image=_img("Gohan.png"),
                    grayscale=True,
                    region=(435 + dx, 76 + dy, 792, 511),
                    confidence=0.75
                )
            except Exception:
                gohan_location = None
                logger.exception("Error locating Gohan image")

            if gohan_location:
                logger.info("Gohan found, clicking")
                InputHandler.Click(*pyautogui.center(gohan_location), delay=0.1)

            time.sleep(0.2)
            try:
                if pyautogui.pixelMatchesColor(453 + dx, 293 + dy, expectedRGBColor=(20, 20, 20), tolerance=30):
                    InputHandler.Click(407 + dx, 358 + dy, 0.1)
            except Exception:
                logger.exception("Error clicking confirmation in unit manager")

            if not pyautogui.pixelMatchesColor(*STOCK2, STOCK_COLOR, tolerance=40):
                break
            First = True

        if SHUTDOWN:
            break
        press("f")
        try:
            if pyautogui.pixelMatchesColor(453 + dx, 293 + dy, expectedRGBColor=(20, 20, 20), tolerance=30):
                InputHandler.Click(407 + dx, 358 + dy, 0.1)
        except Exception:
            logger.exception("Error closing unit manager")

        select(SOKORA_POS)
        press("x")
        try:
            if pyautogui.pixelMatchesColor(453 + dx, 293 + dy, expectedRGBColor=(20, 20, 20), tolerance=30):
                InputHandler.Click(407 + dx, 358 + dy, 0.1)
        except Exception:
            logger.exception("Error confirming sell Sokora")

        select(BROOK_POS)
        time.sleep(0.5)
        select(BROOK_POS)

        if _restart_run.is_set():
            cleanup_after_abort()
            continue
        logger.info("Waiting for USE_BROOK signal from watcher")
        while not USE_BROOK and not SHUTDOWN:
            if _restart_run.is_set() or pyautogui.pixelMatchesColor(725 + dx, 169 + dy, (255, 255, 255), tolerance=30):
                break
            time.sleep(0.01)

        try:
            if pyautogui.pixelMatchesColor(453 + dx, 293 + dy, expectedRGBColor=(20, 20, 20), tolerance=30):
                InputHandler.Click(407 + dx, 358 + dy, 0.1)
        except Exception:
            logger.exception("Error clicking confirmation before ability2")

        if SHUTDOWN:
            break
        if _restart_run.is_set():
            cleanup_after_abort()
            continue
        logger.info("Activating Brook Ability2")
        start_section = time.time()
        while not SHUTDOWN:
            if _restart_run.is_set():
                break
            try:
                if pyautogui.locateOnScreen(_img("endscreen.png"), grayscale=True, confidence=0.8):
                    logger.info("End screen detected, stopping ability2 loop")
                    break
            except pyautogui.ImageNotFoundException:
                pass
            except Exception:
                traceback.print_exc()
            if time.time() - start_section > 5:
                logger.warning("Ability2 loop timeout")
                break
            InputHandler.Click(*ABILITY2, delay=0.1)
            time.sleep(0.12)

        try:
            if pyautogui.pixelMatchesColor(453 + dx, 293 + dy, expectedRGBColor=(20, 20, 20), tolerance=30):
                InputHandler.Click(407 + dx, 358 + dy, 0.1)
        except Exception:
            logger.exception("Error clicking confirmation after ability2")

        # Match ended
        state["wins"] += 1
        total_elapsed = time.time() - state["session_start"]
        run_time_str = time.strftime("%H:%M:%S", time.gmtime(total_elapsed))

        try:
            screenshot = pyautogui.screenshot(region=(rb_window.left, rb_window.top, rb_window.width, rb_window.height))
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            Thread(
                target=send_webhook,
                args=(run_time_str, state["wins"], state["losses"], "Cid Macro", img_bytes),
                daemon=True
            ).start()
        except Exception:
            logger.exception("Screenshot or webhook thread start failed")

        USE_BROOK = False
        state["runs"] += 1

        # Check for auto rejoin after N runs
        if AUTO_REJOIN_AFTER_RUNS > 0 and state["runs"] >= AUTO_REJOIN_AFTER_RUNS:
            logger.info("Auto rejoin threshold reached (%d runs) — waiting for vote_start before restarting", AUTO_REJOIN_AFTER_RUNS)
            # Wait for vote_start to appear (reward credited) but don't click it
            vs_deadline = time.time() + 60.0
            while time.time() < vs_deadline:
                if SHUTDOWN:
                    break
                try:
                    if pyautogui.locateOnScreen(_img("vote_start.png"), grayscale=True, confidence=0.6):
                        logger.info("vote_start detected — reward collected, proceeding with rejoin")
                        break
                except pyautogui.ImageNotFoundException:
                    pass
                except Exception:
                    pass
                time.sleep(0.5)
            if SHUTDOWN:
                break
            state["runs"] = 0
            state["run_start"] = 0.0
            auto_rejoin()
            continue

    logger.info("Main loop exiting (SHUTDOWN=%s)", SHUTDOWN)


# =========================
# Lobby Detection & Navigation
# =========================
def _daily_rewards_visible() -> bool:
    """Check if the daily rewards popup is present (white pixel at 653,193)."""
    if not rb_window:
        return False
    try:
        return pyautogui.pixelMatchesColor(653 + dx, 193 + dy, (255, 255, 255), tolerance=10)
    except Exception:
        return False


def is_in_lobby() -> bool:
    """Return True if AreaIcon.png is visible (we are in the lobby, not in a match)."""
    if not rb_window:
        return False
    try:
        loc = pyautogui.locateOnScreen(_img("AreaIcon.png"), confidence=0.7, grayscale=True)
        return loc is not None
    except pyautogui.ImageNotFoundException:
        return False
    except Exception:
        logger.exception("is_in_lobby error")
        return False


def prepare_lobby() -> bool:
    """
    Wait for lobby to fully load (AreaIcon OR daily rewards visible),
    then dismiss daily rewards and leaderboard UI before navigation.
    """
    logger.info("prepare_lobby: waiting for lobby load")
    deadline = time.time() + 120.0
    while time.time() < deadline:
        if SHUTDOWN:
            return False
        if is_in_lobby() or _daily_rewards_visible():
            break
        if not _sleep(1):
            return False
    else:
        logger.warning("prepare_lobby: timed out waiting for lobby load")
        return False

    if SHUTDOWN:
        return False

    # Close daily rewards popup if present
    if _daily_rewards_visible():
        logger.info("prepare_lobby: closing daily rewards")
        InputHandler.Click(653 + dx, 193 + dy, delay=0.1)
        if not _sleep(0.5):
            return False

    # Close leaderboard tab (always click — no detection needed)
    logger.info("prepare_lobby: closing leaderboard")
    InputHandler.Click(642 + dx, 115 + dy, delay=0.1)
    if not _sleep(0.5):
        return False

    return True


def lobby_path_cid_raid() -> bool:
    """
    Navigate from the lobby to Cid Raid and start a match.
    Heavy reference from AIO lobby_path() Raids case.
    """
    logger.info("lobby_path_cid_raid: navigating to Ruined City Act 2")

    # Focus Roblox so clicks land correctly
    if rb_window:
        try:
            rb_window.activate()
            _sleep(0.5)
        except Exception:
            pass

    RAIDS_AREA       = (340, 400)         # Raids area button in main lobby map
    CREATE_MATCH     = (82,  288)          # Enter the raid portal
    RUINED_CITY_ITEM = (155, 321)          # "Ruined City" in left raid list
    START_FALLBACK   = (388, 340)          # Start button fallback coords
    POPUP_CLOSE      = (654, 187)

    # Wait for lobby (AreaIcon), close any popups while waiting
    deadline = time.time() + 60
    while time.time() < deadline:
        if SHUTDOWN:
            return False
        if is_in_lobby():
            break
        try:
            if pyautogui.pixelMatchesColor(POPUP_CLOSE[0] + dx, POPUP_CLOSE[1] + dy, (255, 255, 255), tolerance=5):
                InputHandler.Click(POPUP_CLOSE[0] + dx, POPUP_CLOSE[1] + dy, delay=0.1)
        except Exception:
            pass
        time.sleep(1)
    else:
        logger.warning("lobby_path_cid_raid: timed out waiting for lobby")
        return False

    if not _sleep(1): return False

    # Close popup if still open
    try:
        if pyautogui.pixelMatchesColor(POPUP_CLOSE[0] + dx, POPUP_CLOSE[1] + dy, (255, 255, 255), tolerance=5):
            InputHandler.Click(POPUP_CLOSE[0] + dx, POPUP_CLOSE[1] + dy, delay=0.1)
    except Exception:
        pass

    # From AreaIcon through Ruined City confirmation — retry up to 3 times.
    # Restarts Roblox if all attempts fail.
    MAX_ATTEMPTS = 3
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if SHUTDOWN:
            return False
        logger.info("lobby_path_cid_raid: navigation attempt %d/%d", attempt, MAX_ATTEMPTS)

        # Click AreaIcon to open the area selection menu
        area_icon = _wait_for_image("AreaIcon.png", timeout=10.0, confidence=0.7)
        if not area_icon:
            logger.warning("lobby_path_cid_raid: AreaIcon not found (attempt %d)", attempt)
            continue
        cx, cy = pyautogui.center(area_icon)
        InputHandler.Click(cx, cy, delay=0.1)
        if not _sleep(.5): return False

        # Click "Raids" in the area menu
        InputHandler.Click(RAIDS_AREA[0] + dx, RAIDS_AREA[1] + dy, delay=0.1)
        if not _sleep(2): return False

        # Walk forward then sprint right to the portal
        if not _key_hold("w", 3):
            return False

        InputHandler.KeyDown(KEYMAP["d"])
        InputHandler.KeyDown(KEYMAP["shift"])
        ok = _sleep(3)
        InputHandler.KeyUp(KEYMAP["d"])
        InputHandler.KeyUp(KEYMAP["shift"])
        if not ok:
            return False

        # Enter the Ruined City portal
        InputHandler.Click(CREATE_MATCH[0] + dx, CREATE_MATCH[1] + dy, delay=0.1)
        if not _sleep(1.5): return False

        # Select Ruined City and Act 2
        InputHandler.Click(RUINED_CITY_ITEM[0] + dx, RUINED_CITY_ITEM[1] + dy, delay=0.1)
        if not _sleep(0.5): return False
        InputHandler.Click(318 + dx, 271 + dy, delay=0.1)
        if not _sleep(0.5): return False

        # Confirm Ruined City banner is visible
        if _wait_for_image("ruined_city.png", timeout=3.0, confidence=0.7):
            logger.info("lobby_path_cid_raid: Ruined City confirmed on attempt %d", attempt)
            break
        logger.warning("lobby_path_cid_raid: Ruined City banner not detected (attempt %d/%d)", attempt, MAX_ATTEMPTS)
    else:
        logger.error("lobby_path_cid_raid: Ruined City never confirmed — restarting Roblox")
        auto_rejoin()
        return False

    # Click (447, 476) — optional cancel/friends-only button (not always present, safe to click blind)
    InputHandler.Click(447 + dx, 476 + dy, delay=0.1)
    if not _sleep(0.5): return False

    # Click (405, 363) — the green Start button in the lobby
    InputHandler.Click(405 + dx, 363 + dy, delay=0.1)
    if not _sleep(1.5): return False

    # Click StartButton.png — the actual "load into raid" confirmation that appears after Start
    start_btn = _wait_for_image("StartButton.png", timeout=8.0, confidence=0.8)
    if start_btn:
        cx, cy = pyautogui.center(start_btn)
        InputHandler.Click(cx, cy, delay=0.1)
        logger.info("lobby_path_cid_raid: load confirmation clicked")
    else:
        logger.warning("lobby_path_cid_raid: load confirmation not found, proceeding anyway")
    logger.info("lobby_path_cid_raid: complete")
    return True


def auto_rejoin():
    """
    Kill and restart Roblox to reset FPS leaks after N runs.
    Called from main_loop when the run threshold is reached.
    After this returns, main_loop continues and waits for vote_start normally.
    """
    logger.info("Auto rejoin: restarting Roblox to reset FPS leaks")
    ok = _do_roblox_rejoin()
    if ok:
        logger.info("Auto rejoin complete — continuing macro")
    else:
        logger.error("Auto rejoin failed — macro will attempt to continue anyway")
    return ok


if __name__ == "__main__":
    Thread(target=softlock_watchdog, daemon=True).start()
    Thread(target=global_rejoin_watchdog, daemon=True).start()
    state["session_start"] = time.time()
    try:
        if not initialize():
            logger.error("Cannot start: Roblox window not found.")
            sys.exit(1)
        Thread(target=boss_watcher, daemon=True).start()
        Thread(target=popup_watcher, daemon=True).start()
        main_loop()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        stop()
    except Exception:
        logger.exception("Unhandled exception in main")
        stop()
    sys.exit(0)

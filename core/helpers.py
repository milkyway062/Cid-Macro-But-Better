import logging
import time
import pygetwindow

import state
import config
import InputHandler

logger = logging.getLogger(__name__)

# Patch InputHandler.Click so all clicks go through a shared lock.
# This runs once at import time; helpers is always imported first by all other modules.
_original_click = InputHandler.Click

def _locked_click(x, y, delay):
    with state._click_lock:
        _original_click(x, y, delay)

InputHandler.Click = _locked_click


# ---------------------------------------------------------------------------
# Sleep / key helpers
# ---------------------------------------------------------------------------

def _sleep(seconds: float, step: float = 0.05) -> bool:
    """Sleep for 'seconds', waking every 'step' to check SHUTDOWN.
    Returns True if completed normally, False if interrupted."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if state.SHUTDOWN:
            return False
        time.sleep(min(step, max(0.0, deadline - time.time())))
    return True


def _key_hold(key: str, seconds: float) -> bool:
    """Hold a key for 'seconds'. Returns True if completed, False on SHUTDOWN."""
    InputHandler.KeyDown(config.KEYMAP[key])
    ok = _sleep(seconds)
    InputHandler.KeyUp(config.KEYMAP[key])
    return ok


def press(key: str) -> None:
    """Tap a key (down + 20 ms + up)."""
    try:
        InputHandler.KeyDown(config.KEYMAP[key])
        time.sleep(0.02)
        InputHandler.KeyUp(config.KEYMAP[key])
    except Exception:
        logger.exception("press(%s) failed", key)


# ---------------------------------------------------------------------------
# Position management
# ---------------------------------------------------------------------------

def _update_positions():
    """Recompute all screen-position globals from the current state.dx / state.dy."""
    dx = state.dx
    dy = state.dy
    state.BROOK_POS            = (403 + dx, 372 + dy)
    state.ICHIGO_POS           = (412 + dx, 303 + dy)
    state.SOKORA_POS           = (421 + dx, 262 + dy)
    state.NEWSMAN_P1           = (370 + dx, 324 + dy)
    state.UNIT_CLOSE           = (305 + dx, 233 + dy)
    state.WAVE_SKIP            = (616 + dx,  40 + dy)
    state.ABILITY1             = (333 + dx, 278 + dy)
    state.ABILITY2             = (333 + dx, 338 + dy)
    state.BROOK_ABILITY_CLOSE  = (590 + dx, 183 + dy)
    state.STOCK1               = (601 + dx,  41 + dy)
    state.STOCK2               = (356 + dx,  41 + dy)
    state.BOSS_ALIVE           = (310 + dx, 113 + dy)
    state.PASSIVE_MENU_PIXEL   = ( 35 + dx, 543 + dy)
    state.RESTART_SETTINGS_BTN = ( 26 + dx, 610 + dy)
    state.RESTART_MATCH_BTN    = (704 + dx, 292 + dy)
    state.RESTART_YES_BTN      = (351 + dx, 367 + dy)
    state.RESTART_OK_BTN       = (407 + dx, 360 + dy)


def extract_ps_link_code(value: str) -> str:
    """Return the bare link code from a full Roblox private-server URL or a raw code."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(value)
    qs = parse_qs(parsed.query)
    if "privateServerLinkCode" in qs:
        return qs["privateServerLinkCode"][0]
    return value


def initialize() -> bool:
    """Find the Roblox window, update coordinates. Returns True on success."""
    state.rb_window = None
    for w in pygetwindow.getAllWindows():
        if w.title == "Roblox":
            state.rb_window = w
            break
    if not state.rb_window:
        logger.error("Roblox window not found.")
        return False
    state.dx, state.dy = state.rb_window.left, state.rb_window.top
    _update_positions()
    state._hotkey_registered = True
    state._initialized       = True
    logger.info("Initialized: Roblox window at (%d, %d)", state.dx, state.dy)
    return True

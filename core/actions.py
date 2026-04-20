import logging
import time
import traceback
import ctypes
import pyautogui

import state
import config
import helpers
import detections
import InputHandler

logger = logging.getLogger(__name__)


def place(unit: int, pos: tuple, max_retries=4, per_attempt_timeout=1.2) -> bool:
    logger.info("Placing Unit %s at %s (max_retries=%d)", unit, pos, max_retries)
    key = f"{unit}"
    for attempt in range(1, max_retries + 1):
        if state.SHUTDOWN:
            logger.info("Shutdown requested during place()")
            return False

        try:
            helpers.press(key)
            InputHandler.Click(*pos, delay=0.1)
        except Exception:
            logger.exception("Error sending input for place(%s) attempt %d", unit, attempt)

        start = time.time()
        while True:
            if state.SHUTDOWN:
                logger.info("Shutdown requested during place() wait")
                return False
            try:
                if pyautogui.pixelMatchesColor(*state.UNIT_CLOSE, expectedRGBColor=(255, 255, 255), tolerance=30):
                    logger.debug("place(): UNIT_CLOSE detected after attempt %d", attempt)
                    return True
                if pyautogui.pixelMatchesColor(725 + state.dx, 169 + state.dy, (255, 255, 255), tolerance=30):
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
        InputHandler.Click(*state.UNIT_CLOSE, delay=0.1)
        timedelta = time.time()
        InputHandler.Click(*pos, delay=0.1)
        while not pyautogui.pixelMatchesColor(*state.UNIT_CLOSE, expectedRGBColor=(255, 255, 255), tolerance=30):
            if state.SHUTDOWN or state._restart_run.is_set():
                return
            if pyautogui.pixelMatchesColor(725 + state.dx, 169 + state.dy, (255, 255, 255), tolerance=30):
                break
            if time.time() - timedelta > 0.9:
                InputHandler.Click(*pos, delay=0.1)
                timedelta = time.time()
            time.sleep(0.01)
        logger.info("Selected unit at %s", pos)
    except Exception:
        logger.exception("select(%s) failed", pos)


def brook_buff():
    logger.info("Doing Brook Buff")
    start = time.time()
    keys  = ["a", "s", "d", "f", "g"]
    InputHandler.MoveTo(*state.BROOK_ABILITY_CLOSE)

    while True:
        if state.SHUTDOWN:
            return
        if state.USE_BROOK:
            logger.info("brook_buff: boss died — exiting buff early")
            break
        try:
            ability_open = pyautogui.pixelMatchesColor(
                *state.BROOK_ABILITY_CLOSE, (255, 255, 255), tolerance=30)
        except Exception:
            ability_open = False
            logger.exception("Error checking BROOK_ABILITY_CLOSE pixel")

        if ability_open:
            for k in keys:
                InputHandler.KeyDown(config.KEYMAP[k])
            time.sleep(0.02)
            for k in keys:
                InputHandler.KeyUp(config.KEYMAP[k])

            if time.time() - start > 6:
                if pyautogui.pixelMatchesColor(*state.WAVE_SKIP, expectedRGBColor=(255, 255, 255), tolerance=30):
                    logger.info("Wave skip detected during brook_buff")
                    break
        else:
            InputHandler.Click(*state.ABILITY1, delay=0.1)
            time.sleep(0.2)

            if time.time() - start > 8:
                logger.error("Brook ability never opened -> skipping")
                break

    InputHandler.Click(*state.BROOK_ABILITY_CLOSE, 0.1)
    logger.info("Brook buff done")


def return_to_spawn():
    """Click through the return-to-spawn sequence."""
    logger.info("Returning to spawn")
    for pos in config.RETURN_TO_SPAWN_CLICKS:
        if state.SHUTDOWN:
            return
        InputHandler.Click(pos[0] + state.dx, pos[1] + state.dy, delay=0.2)
        helpers._sleep(0.8)
    logger.info("Return to spawn complete")


def click_retry_button():
    """Click the retry button after a match ends."""
    try:
        retry_pos = detections._wait_for_image("Retry.png", timeout=3.0, confidence=0.8)
        if retry_pos:
            cx, cy = pyautogui.center(retry_pos)
            InputHandler.Click(cx, cy, delay=0.1)
            logger.info("Retry button clicked")
            return
        InputHandler.Click(355 + state.dx, 470 + state.dy, delay=0.5)
        logger.info("Fallback retry click")
    except Exception:
        logger.exception("click_retry_button failed")


def restart_match_ingame():
    """Click through settings → Restart Match → Yes → confirmation."""
    state._restarting.set()
    try:
        logger.info("Restarting match via settings menu")

        InputHandler.Click(*state.RESTART_SETTINGS_BTN, delay=0.1)
        loc = detections._wait_for_image("settings.png", timeout=15.0)
        if loc:
            logger.info("Settings detected, clicking Restart Match")
            time.sleep(0.5)
        else:
            logger.warning("Settings page not detected; proceeding anyway")
        InputHandler.Click(*state.RESTART_MATCH_BTN, delay=0.1)

        time.sleep(0.5)
        InputHandler.Click(*state.RESTART_YES_BTN, delay=0.1)

        loc = detections._wait_for_image("restart_confirmation.png", timeout=5.0)
        if loc:
            cx, cy = pyautogui.center(loc)
            InputHandler.Click(cx - 55, cy + 81, 0.1)
            logger.info("Restart confirmation clicked")
        else:
            logger.warning("restart_confirmation not detected; falling back to hardcoded Ok")
            InputHandler.Click(*state.RESTART_OK_BTN, delay=0.3)

        time.sleep(0.2)
        InputHandler.Click(*state.RESTART_SETTINGS_CLOSE, delay=0.1)
        logger.info("Settings panel closed after restart")

    except Exception:
        logger.exception("restart_match_ingame failed")
    finally:
        state._restarting.clear()


def cleanup_after_abort():
    """Deselect unit, close unit manager, then restart the match."""
    logger.info("Abort cleanup started")
    state.state["losses"] += 1
    state.state["runs"]   += 1
    state._match_active.clear()
    try:
        InputHandler.Click(*state.PASSIVE_MENU_PIXEL, delay=0.1)
    except Exception:
        logger.exception("cleanup_after_abort: deselect click failed")
    try:
        if pyautogui.pixelMatchesColor(615 + state.dx, 88 + state.dy, (11, 231, 241), tolerance=40):
            helpers.press("f")
    except Exception:
        logger.exception("cleanup_after_abort: unit manager close failed")
    time.sleep(0.3)
    if state._restarting.is_set():
        logger.info("Abort cleanup waiting for watchdog restart to finish")
        while state._restarting.is_set() and not state.SHUTDOWN:
            time.sleep(0.1)
    else:
        restart_match_ingame()
    logger.info("Abort cleanup done")


def auto_positioner(positioner_name: str, just_camera: bool = False):
    """
    Reset camera and optionally walk to spawn then poll for a positioner image match.
    """
    logger.info("Starting auto positioner for %s", positioner_name)
    if not helpers._sleep(1):
        return False

    try:
        InputHandler.Click(
            config.UNIT_PANEL_POS[0] + state.dx,
            config.UNIT_PANEL_POS[1] + state.dy,
            delay=0.1,
        )

        if not helpers._key_hold("i", 2):
            return False

        ctypes.windll.user32.mouse_event(0x0001, 0, config.CAMERA_MOVE_OFFSET[1], 0, 0)
        if not helpers._sleep(1):
            return False

        if not helpers._key_hold("o", 2):
            return False

        logger.info("Camera reset complete")

        if just_camera:
            if detections._check_match_end():
                InputHandler.Click(355 + state.dx, 470 + state.dy, delay=0.1)
                if not helpers._sleep(5):
                    return False
                InputHandler.Click(
                    config.UNIT_PANEL_POS[0] + state.dx,
                    config.UNIT_PANEL_POS[1] + state.dy,
                    delay=0.1,
                )
            return_to_spawn()
            if not helpers._sleep(1):
                return False
            InputHandler.RightClick(139 + state.dx, 343 + state.dy, delay=0.1)
            logger.info("Auto positioner done (camera only)")
            return True

        logger.info("Polling for positioner image match...")
        deadline = time.time() + 60
        while time.time() < deadline:
            if state.SHUTDOWN:
                return False

            for img in config.POSITIONER_IMAGES:
                loc = detections._wait_for_image(img, timeout=1.0, confidence=0.85)
                if loc:
                    logger.info("Positioner matched: %s", img)
                    return True

            if detections._check_match_end():
                logger.info("Match ended during positioning — retrying")
                InputHandler.Click(355 + state.dx, 470 + state.dy, delay=0.1)
                if not helpers._sleep(5):
                    return False
                InputHandler.Click(
                    config.UNIT_PANEL_POS[0] + state.dx,
                    config.UNIT_PANEL_POS[1] + state.dy,
                    delay=0.1,
                )

            return_to_spawn()
            if not helpers._sleep(2):
                return False

        logger.warning("Positioner not found within 60s")
        return False

    except Exception:
        logger.exception("auto_positioner failed")
        return False


def close_chat_and_objectives():
    """
    Close objectives UI, then double-click chat button.
    VC coord = (202,64), regular coord = (145,64). Objectives = (214,353).
    """
    if state.rb_window:
        try:
            state.rb_window.activate()
        except Exception:
            pass
        helpers._sleep(0.2)
    InputHandler.Click(214 + state.dx, 353 + state.dy, delay=0.1)
    helpers._sleep(0.3)
    chat_x = 202 if state.VC_CHAT else 145
    InputHandler.Click(chat_x + state.dx, 64 + state.dy, delay=0.2)
    InputHandler.Click(chat_x + state.dx, 64 + state.dy, delay=0.2)
    logger.info("Chat double-clicked (x=%d)", chat_x)
    helpers._sleep(0.5)

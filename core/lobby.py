import logging
import time
import subprocess
import pyautogui
import pygetwindow

try:
    import psutil
except ImportError:
    raise SystemExit("psutil is not installed. Run: py -m pip install psutil")

import state
import config
import helpers
import detections
import InputHandler

logger = logging.getLogger(__name__)


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
    Kill Roblox, relaunch into private server, wait for game to load.
    Returns True on success, False on failure.
    """
    roblox_exe = get_roblox_exe_path()
    if not roblox_exe:
        logger.error("_do_roblox_rejoin: could not find RobloxPlayerBeta.exe")
        return False

    saved_rect = None
    if state.rb_window:
        try:
            saved_rect = (
                state.rb_window.left, state.rb_window.top,
                state.rb_window.width, state.rb_window.height,
            )
            logger.info("Saved window rect: %s", saved_rect)
        except Exception:
            logger.warning("Could not save window rect")

    logger.info("Killing Roblox processes")
    for proc in psutil.process_iter(["name"]):
        try:
            if "roblox" in proc.name().lower():
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    helpers._sleep(2)

    rejoin_url = f"roblox://placeId=16146832113&linkCode={helpers.extract_ps_link_code(state.PRIVATE_SERVER_CODE)}/"
    logger.info("Launching Roblox: %s", rejoin_url)
    subprocess.Popen([roblox_exe, rejoin_url])

    deadline = time.time() + config.REJOIN_TIMEOUT
    while time.time() < deadline:
        if state.SHUTDOWN:
            return False

        for w in pygetwindow.getAllWindows():
            if w.title == "Roblox":
                state.rb_window = w
                break

        if detections._wait_for_image("IsInGame.png", timeout=3.0, confidence=0.8):
            logger.info("Roblox reloaded successfully")
            helpers._sleep(10)

            if state.rb_window and saved_rect:
                try:
                    state.rb_window.moveTo(saved_rect[0], saved_rect[1])
                    state.rb_window.resizeTo(saved_rect[2], saved_rect[3])
                    logger.info("Restored window rect: %s", saved_rect)
                except Exception:
                    logger.warning("Could not restore window rect")

            if state.rb_window:
                state.dx, state.dy = state.rb_window.left, state.rb_window.top
                helpers._update_positions()

            pyautogui.press("tab")
            time.sleep(1)
            return True

        time.sleep(2)

    logger.error("_do_roblox_rejoin: timed out waiting for game to load")
    return False


def auto_rejoin() -> bool:
    """
    Kill and restart Roblox to reset FPS leaks after N runs.
    Called from main_loop when the run threshold is reached.
    """
    logger.info("Auto rejoin: restarting Roblox to reset FPS leaks")
    ok = _do_roblox_rejoin()
    if ok:
        logger.info("Auto rejoin complete — continuing macro")
    else:
        logger.error("Auto rejoin failed — macro will attempt to continue anyway")
    return ok


def prepare_lobby() -> bool:
    """
    Wait for lobby to fully load, then dismiss daily rewards and leaderboard UI.
    """
    logger.info("prepare_lobby: waiting for lobby load")
    deadline = time.time() + 120.0
    while time.time() < deadline:
        if state.SHUTDOWN:
            return False
        if detections.is_in_lobby() or detections._daily_rewards_visible():
            break
        if not helpers._sleep(1):
            return False
    else:
        logger.warning("prepare_lobby: timed out waiting for lobby load")
        return False

    if state.SHUTDOWN:
        return False

    if detections._daily_rewards_visible():
        logger.info("prepare_lobby: closing daily rewards")
        InputHandler.Click(653 + state.dx, 193 + state.dy, delay=0.1)
        if not helpers._sleep(0.5):
            return False

    logger.info("prepare_lobby: closing leaderboard")
    InputHandler.Click(642 + state.dx, 115 + state.dy, delay=0.1)
    if not helpers._sleep(0.5):
        return False

    return True


def lobby_path_cid_raid() -> bool:
    """
    Navigate from the lobby to Ruined City Act 2 and start a match.
    Retries up to 3 times; calls auto_rejoin() if all attempts fail.
    """
    logger.info("lobby_path_cid_raid: navigating to Ruined City Act 2")

    if state.rb_window:
        try:
            state.rb_window.activate()
            helpers._sleep(0.5)
        except Exception:
            pass

    RAIDS_AREA       = (340, 400)
    CREATE_MATCH     = (82,  288)
    RUINED_CITY_ITEM = (155, 321)
    START_FALLBACK   = (388, 340)  # noqa: F841 — kept for reference
    POPUP_CLOSE      = (654, 187)

    # Wait for AreaIcon while dismissing any stray popups
    deadline = time.time() + 60
    while time.time() < deadline:
        if state.SHUTDOWN:
            return False
        if detections.is_in_lobby():
            break
        try:
            if pyautogui.pixelMatchesColor(
                POPUP_CLOSE[0] + state.dx, POPUP_CLOSE[1] + state.dy,
                (255, 255, 255), tolerance=5,
            ):
                InputHandler.Click(POPUP_CLOSE[0] + state.dx, POPUP_CLOSE[1] + state.dy, delay=0.1)
        except Exception:
            pass
        time.sleep(1)
    else:
        logger.warning("lobby_path_cid_raid: timed out waiting for lobby")
        return False

    if not helpers._sleep(1):
        return False

    try:
        if pyautogui.pixelMatchesColor(
            POPUP_CLOSE[0] + state.dx, POPUP_CLOSE[1] + state.dy,
            (255, 255, 255), tolerance=5,
        ):
            InputHandler.Click(POPUP_CLOSE[0] + state.dx, POPUP_CLOSE[1] + state.dy, delay=0.1)
    except Exception:
        pass

    MAX_ATTEMPTS = 3
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if state.SHUTDOWN:
            return False
        logger.info("lobby_path_cid_raid: navigation attempt %d/%d", attempt, MAX_ATTEMPTS)

        area_icon = detections._wait_for_image("AreaIcon.png", timeout=10.0, confidence=0.7)
        if not area_icon:
            logger.warning("lobby_path_cid_raid: AreaIcon not found (attempt %d)", attempt)
            continue
        cx, cy = pyautogui.center(area_icon)
        InputHandler.Click(cx, cy, delay=0.1)
        if not helpers._sleep(0.5):
            return False

        InputHandler.Click(RAIDS_AREA[0] + state.dx, RAIDS_AREA[1] + state.dy, delay=0.1)
        if not helpers._sleep(2):
            return False

        if not helpers._key_hold("w", 3):
            return False

        InputHandler.KeyDown(config.KEYMAP["d"])
        InputHandler.KeyDown(config.KEYMAP["shift"])
        ok = helpers._sleep(3)
        InputHandler.KeyUp(config.KEYMAP["d"])
        InputHandler.KeyUp(config.KEYMAP["shift"])
        if not ok:
            return False

        InputHandler.Click(CREATE_MATCH[0] + state.dx, CREATE_MATCH[1] + state.dy, delay=0.1)
        if not helpers._sleep(1.5):
            return False

        InputHandler.Click(RUINED_CITY_ITEM[0] + state.dx, RUINED_CITY_ITEM[1] + state.dy, delay=0.1)
        if not helpers._sleep(0.5):
            return False
        InputHandler.Click(318 + state.dx, 271 + state.dy, delay=0.1)
        if not helpers._sleep(0.5):
            return False

        if detections._wait_for_image("ruined_city.png", timeout=3.0, confidence=0.7):
            logger.info("lobby_path_cid_raid: Ruined City confirmed on attempt %d", attempt)
            break
        logger.warning(
            "lobby_path_cid_raid: Ruined City banner not detected (attempt %d/%d)",
            attempt, MAX_ATTEMPTS,
        )
    else:
        logger.error("lobby_path_cid_raid: Ruined City never confirmed — restarting Roblox")
        auto_rejoin()
        return False

    InputHandler.Click(447 + state.dx, 476 + state.dy, delay=0.1)
    if not helpers._sleep(0.5):
        return False

    InputHandler.Click(405 + state.dx, 363 + state.dy, delay=0.1)
    if not helpers._sleep(1.5):
        return False

    start_btn = detections._wait_for_image("StartButton.png", timeout=8.0, confidence=0.8)
    if start_btn:
        cx, cy = pyautogui.center(start_btn)
        InputHandler.Click(cx, cy, delay=0.1)
        logger.info("lobby_path_cid_raid: load confirmation clicked")
    else:
        logger.warning("lobby_path_cid_raid: load confirmation not found, proceeding anyway")

    logger.info("lobby_path_cid_raid: complete")
    return True

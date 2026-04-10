import logging
import time
import pyautogui

import state
import config
import detections
import lobby

logger = logging.getLogger(__name__)


def boss_watcher():
    """Daemon thread: watches for boss death and sets state.USE_BROOK."""
    while True:
        try:
            # Wait until a match is in progress
            while not state._match_active.is_set():
                if state.SHUTDOWN:
                    return
                time.sleep(0.1)

            # Wait for boss HP bar to appear (pixel turns white)
            while not pyautogui.pixelMatchesColor(*state.BOSS_ALIVE, (255, 255, 255), tolerance=30):
                if state.SHUTDOWN or not state._match_active.is_set():
                    break
                time.sleep(0.1)

            if not state._match_active.is_set():
                continue

            # Wait for boss to die (pixel goes non-white)
            while pyautogui.pixelMatchesColor(*state.BOSS_ALIVE, (255, 255, 255), tolerance=30):
                if state.SHUTDOWN or not state._match_active.is_set():
                    break
                time.sleep(0.1)

            if not state._match_active.is_set():
                continue

            boss_dead = time.time()
            logger.info("Boss is dead, starting ult offset wait")
            while time.time() - boss_dead < (config.BOSS - config.BROOK_ULT + 0.15):
                if state.SHUTDOWN or not state._match_active.is_set():
                    break
                time.sleep(0.1)

            if not state._match_active.is_set():
                continue

            state.USE_BROOK = True
            logger.info("USE_BROOK set; main loop should trigger Brook ult")
            while state.USE_BROOK:
                if state.SHUTDOWN:
                    return
                time.sleep(0.1)

        except Exception:
            logger.exception("boss_watcher encountered an error")
            time.sleep(0.5)


def popup_watcher():
    """Daemon thread: continuously dismiss passive menu and cancel button."""
    logger.info("Popup watcher started")
    while not state.SHUTDOWN:
        try:
            detections.dismiss_passive_menu()
            detections.dismiss_cancel_button()
        except Exception:
            logger.exception("popup_watcher error")
        time.sleep(0.1)


def disconnect_checker():
    """Daemon thread: watches for Roblox disconnect and rejoins automatically."""
    logger.info("Disconnect checker started")
    while not state.SHUTDOWN:
        try:
            if detections._wait_for_image("Disconnected.png", timeout=2.0, confidence=0.9):
                logger.warning("Disconnect detected — rejoining")
                state._restart_run.set()
                state._match_active.clear()
                ok = lobby._do_roblox_rejoin()
                if ok:
                    logger.info("Rejoin successful, macro will restart run")
                else:
                    logger.error("Rejoin failed")
        except Exception:
            logger.exception("disconnect_checker error")
        time.sleep(2)
    logger.info("Disconnect checker stopped")

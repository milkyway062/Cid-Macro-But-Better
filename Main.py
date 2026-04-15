import logging
import time
import sys
import os
import traceback
import pyautogui
from threading import Thread

# Add core/ folder to path so its modules are importable by name
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

import state
import config
import helpers
import detections
import actions
import lobby
import watchdogs
import softlocks
import webhook
import InputHandler
import cid_act2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def exit_handler(x):
    """Called by the ; hotkey — stops the macro cooperatively (UI stays open)."""
    logger.info("Kill switch pressed — stopping macro.")
    stop()


# =========================
# Main loop
# =========================
def main_loop():
    logger.info("Main loop started")
    positioned  = False
    chat_closed = False

    while not state.SHUTDOWN:
        state._restart_run.clear()
        state._match_active.clear()
        state.USE_BROOK            = False
        state.state["run_start"]   = time.time()
        logger.info("==== New run ====")

        # If we are in the lobby (e.g. after a rejoin or first start), navigate to Cid Raid
        if detections.is_in_lobby() or detections._daily_rewards_visible():
            logger.info("In lobby — dismissing UI then navigating to Cid Raid")
            positioned  = False
            chat_closed = False
            lobby.prepare_lobby()
            if state.SHUTDOWN:
                break
            if not lobby.lobby_path_cid_raid():
                continue
            if state.SHUTDOWN:
                break

        # Wait for vote_start, click it, then fall through to spawn detection
        VOTE_START_TIMEOUT = 60.0
        vote_wait_start    = time.time()
        logger.info("Waiting for vote_start")
        while not state.SHUTDOWN and not state._restart_run.is_set():
            if time.time() - vote_wait_start > VOTE_START_TIMEOUT:
                logger.warning("vote_start not seen within %.1fs, proceeding anyway", VOTE_START_TIMEOUT)
                break
            if state._restarting.is_set():
                time.sleep(0.1)
                continue
            # Cancel popup takes priority — dismiss without aborting
            try:
                cancel_loc = pyautogui.locateOnScreen(
                    image=detections._img("ability_in_use.png"),
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
                    image=detections._img("vote_start.png"),
                    grayscale=True,
                    confidence=0.6,
                )
                if location:
                    # Final safety check: don't click vote_start if cancel popup is visible
                    try:
                        cancel_check = pyautogui.locateOnScreen(
                            image=detections._img("ability_in_use.png"),
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

        if state.SHUTDOWN:
            break
        if state._restart_run.is_set():
            actions.cleanup_after_abort()
            continue

        try:
            if pyautogui.pixelMatchesColor(615 + state.dx, 88 + state.dy, (11, 231, 241), tolerance=40):
                helpers.press("f")
        except Exception:
            logger.exception("Error checking unit manager pixel")

        logger.info("Waiting for spawn")
        while not pyautogui.pixelMatchesColor(394 + state.dx, 123 + state.dy,
                                              expectedRGBColor=(10, 10, 10), tolerance=30):
            if state.SHUTDOWN or state._restart_run.is_set():
                break
            if pyautogui.pixelMatchesColor(725 + state.dx, 169 + state.dy, (255, 255, 255), tolerance=30):
                InputHandler.Click(374 + state.dx, 474 + state.dy, 0.1)
            try:
                cancel_loc = pyautogui.locateOnScreen(
                    image=detections._img("ability_in_use.png"),
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

        if state.SHUTDOWN:
            break
        if state._restart_run.is_set():
            actions.cleanup_after_abort()
            continue

        while pyautogui.pixelMatchesColor(394 + state.dx, 123 + state.dy,
                                          expectedRGBColor=(10, 10, 10), tolerance=30):
            if state.SHUTDOWN or state._restart_run.is_set():
                break
            InputHandler.Click(472 + state.dx, 127 + state.dy, 0.1)
            try:
                cancel_loc = pyautogui.locateOnScreen(
                    image=detections._img("ability_in_use.png"),
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

        if state.SHUTDOWN:
            break
        if state._restart_run.is_set():
            actions.cleanup_after_abort()
            continue

        state._match_active.set()
        logger.info("Match %d Started", state.state["runs"])
        try:
            if pyautogui.pixelMatchesColor(615 + state.dx, 88 + state.dy, (11, 231, 241), tolerance=40):
                helpers.press("f")
        except Exception:
            logger.exception("Error checking unit manager pixel after start")

        if state.SHUTDOWN:
            break

        if not chat_closed:
            actions.close_chat_and_objectives()
            chat_closed = True

        if state.SHUTDOWN:
            break

        if not positioned:
            pyautogui.press("tab")
            helpers._sleep(0.5)
            actions.auto_positioner("Cid_Raid", just_camera=True)
            positioned = True
            if state.SHUTDOWN:
                break
            if not helpers._sleep(1):
                break
            actions.restart_match_ingame()
            if state.SHUTDOWN:
                break
            continue  # loop back: vote_start → spawn → real run (positioned=True now)

        actions.place(4, state.BROOK_POS)
        actions.place(1, state.ICHIGO_POS)

        actions.select(state.BROOK_POS)
        InputHandler.Click(*state.ABILITY1, delay=0.1)
        actions.brook_buff()

        if state.SHUTDOWN:
            break
        brook_wait_start   = time.time()
        BROOK_WAIT_TIMEOUT = 6.0
        while True:
            if state.SHUTDOWN:
                break
            try:
                if not pyautogui.pixelMatchesColor(*state.BROOK_ABILITY_CLOSE, (255, 255, 255), tolerance=30):
                    break
            except Exception:
                traceback.print_exc()
                break
            if time.time() - brook_wait_start > BROOK_WAIT_TIMEOUT:
                logger.warning("BROOK_ABILITY_CLOSE wait exceeded %.1fs; proceeding", BROOK_WAIT_TIMEOUT)
                break
            time.sleep(0.1)

        NEWSMAN_RETRY_DELAY = 0.6
        newsman_placed  = False
        newsman_attempts = 0
        while not state.SHUTDOWN and not newsman_placed and not state._restart_run.is_set():
            newsman_attempts += 1
            logger.info("Attempting to place Newsman (attempt %d)", newsman_attempts)
            try:
                actions.place(5, state.NEWSMAN_P1)
            except Exception:
                logger.exception("Unexpected error while calling place() for Newsman")

            time.sleep(0.25)

            try:
                if (pyautogui.pixelMatchesColor(*state.UNIT_CLOSE, expectedRGBColor=(255, 255, 255), tolerance=30)
                        or pyautogui.pixelMatchesColor(725 + state.dx, 169 + state.dy, (255, 255, 255), tolerance=30)):
                    logger.info("Newsman placement confirmed")
                    newsman_placed = True
                    break
            except Exception:
                traceback.print_exc()

            logger.warning("Newsman placement not confirmed; retrying in %.2fs", NEWSMAN_RETRY_DELAY)
            time.sleep(NEWSMAN_RETRY_DELAY)

        time.sleep(0.2)

        try:
            if not actions.place(3, state.SOKORA_POS):
                logger.warning("Sokora placement failed on first attempt")
        except Exception:
            logger.exception("Error placing Sokora")

        while pyautogui.pixelMatchesColor(*state.STOCK1, config.STOCK_COLOR, tolerance=40):
            if state.SHUTDOWN or state._restart_run.is_set():
                break
            if pyautogui.pixelMatchesColor(725 + state.dx, 169 + state.dy, (255, 255, 255), tolerance=30):
                break
            helpers.press("q")
            actions.select(state.SOKORA_POS)
            InputHandler.Click(*state.ABILITY1, delay=0.1)
            InputHandler.Click(*state.ICHIGO_POS, delay=0.1)
            time.sleep(0.4)

        if state.SHUTDOWN:
            break
        if state._restart_run.is_set():
            actions.cleanup_after_abort()
            continue
        helpers.press("f")
        start_section = time.time()
        while not state.SHUTDOWN:
            if state._restart_run.is_set():
                break
            try:
                if pyautogui.pixelMatchesColor(615 + state.dx, 88 + state.dy, (11, 231, 241), tolerance=40):
                    break
            except Exception:
                traceback.print_exc()
            if time.time() - start_section > 5:
                logger.warning("Unit manager failed to open within 5s")
                break
            time.sleep(0.1)

        if state.SHUTDOWN:
            break
        actions.select(state.SOKORA_POS)
        First = False
        while True:
            if state.SHUTDOWN or state._restart_run.is_set():
                break
            if pyautogui.pixelMatchesColor(725 + state.dx, 169 + state.dy, (255, 255, 255), tolerance=30):
                break
            logger.debug("Attempting Sokora -> Gohan")
            helpers.press("q")
            if First and pyautogui.pixelMatchesColor(
                    332 + state.dx, 317 + state.dy, expectedRGBColor=(216, 14, 18), tolerance=50):
                actions.select(state.SOKORA_POS)
            InputHandler.Click(*state.ABILITY1, delay=0.1)

            try:
                gohan_location = pyautogui.locateOnScreen(
                    image=detections._img("Gohan.png"),
                    grayscale=True,
                    region=(435 + state.dx, 76 + state.dy, 792 - 435, 511 - 76),
                    confidence=0.75,
                )
            except Exception:
                gohan_location = None
                logger.exception("Error locating Gohan image")

            if gohan_location:
                logger.info("Gohan found, clicking")
                InputHandler.Click(*pyautogui.center(gohan_location), delay=0.1)

            time.sleep(0.2)
            try:
                if pyautogui.pixelMatchesColor(453 + state.dx, 293 + state.dy,
                                               expectedRGBColor=(20, 20, 20), tolerance=30):
                    InputHandler.Click(407 + state.dx, 358 + state.dy, 0.1)
            except Exception:
                logger.exception("Error clicking confirmation in unit manager")

            if not pyautogui.pixelMatchesColor(*state.STOCK2, config.STOCK_COLOR, tolerance=40):
                break
            First = True

        if state.SHUTDOWN:
            break
        helpers.press("f")
        try:
            if pyautogui.pixelMatchesColor(453 + state.dx, 293 + state.dy,
                                           expectedRGBColor=(20, 20, 20), tolerance=30):
                InputHandler.Click(407 + state.dx, 358 + state.dy, 0.1)
        except Exception:
            logger.exception("Error closing unit manager")

        actions.select(state.SOKORA_POS)
        helpers.press("x")
        try:
            if pyautogui.pixelMatchesColor(453 + state.dx, 293 + state.dy,
                                           expectedRGBColor=(20, 20, 20), tolerance=30):
                InputHandler.Click(407 + state.dx, 358 + state.dy, 0.1)
        except Exception:
            logger.exception("Error confirming sell Sokora")

        actions.select(state.BROOK_POS)
        time.sleep(0.5)
        actions.select(state.BROOK_POS)

        if state._restart_run.is_set():
            actions.cleanup_after_abort()
            continue
        logger.info("Waiting for USE_BROOK signal from watcher")
        while not state.USE_BROOK and not state.SHUTDOWN:
            if (state._restart_run.is_set()
                    or pyautogui.pixelMatchesColor(725 + state.dx, 169 + state.dy, (255, 255, 255), tolerance=30)):
                break
            time.sleep(0.01)

        try:
            if pyautogui.pixelMatchesColor(453 + state.dx, 293 + state.dy,
                                           expectedRGBColor=(20, 20, 20), tolerance=30):
                InputHandler.Click(407 + state.dx, 358 + state.dy, 0.1)
        except Exception:
            logger.exception("Error clicking confirmation before ability2")

        if state.SHUTDOWN:
            break
        if state._restart_run.is_set():
            actions.cleanup_after_abort()
            continue
        logger.info("Activating Brook Ability2")
        start_section = time.time()
        while not state.SHUTDOWN:
            if state._restart_run.is_set():
                break
            try:
                if pyautogui.locateOnScreen(detections._img("endscreen.png"), grayscale=True, confidence=0.8):
                    logger.info("End screen detected, stopping ability2 loop")
                    break
            except pyautogui.ImageNotFoundException:
                pass
            except Exception:
                traceback.print_exc()
            if time.time() - start_section > 5:
                logger.warning("Ability2 loop timeout")
                break
            InputHandler.Click(*state.ABILITY2, delay=0.1)
            time.sleep(0.12)

        try:
            if pyautogui.pixelMatchesColor(453 + state.dx, 293 + state.dy,
                                           expectedRGBColor=(20, 20, 20), tolerance=30):
                InputHandler.Click(407 + state.dx, 358 + state.dy, 0.1)
        except Exception:
            logger.exception("Error clicking confirmation after ability2")

        # Match ended — tally win and send webhook
        state.state["wins"]              += 1
        state.state["total_runs"]        += 1
        state.state["runs_since_rejoin"] += 1
        total_elapsed   = time.time() - state.state["run_start"]
        session_elapsed = time.time() - state.state["session_start"]
        run_time_str    = time.strftime("%H:%M:%S", time.gmtime(total_elapsed))
        total_time_str  = time.strftime("%H:%M:%S", time.gmtime(session_elapsed))

        try:
            Thread(
                target=webhook.send_webhook,
                args=(run_time_str, total_time_str, state.state["total_runs"],
                      state.state["runs_since_rejoin"]),
                daemon=True,
            ).start()
        except Exception:
            logger.exception("Webhook thread start failed")

        state.USE_BROOK        = False
        state.state["runs"]   += 1

        # Auto-rejoin after N runs
        if state.AUTO_REJOIN_AFTER_RUNS > 0 and state.state["runs"] >= state.AUTO_REJOIN_AFTER_RUNS:
            logger.info(
                "Auto rejoin threshold reached (%d runs) — waiting for vote_start before restarting",
                state.AUTO_REJOIN_AFTER_RUNS,
            )
            vs_deadline = time.time() + 60.0
            while time.time() < vs_deadline:
                if state.SHUTDOWN:
                    break
                try:
                    if pyautogui.locateOnScreen(
                            detections._img("vote_start.png"), grayscale=True, confidence=0.6):
                        logger.info("vote_start detected — reward collected, proceeding with rejoin")
                        break
                except pyautogui.ImageNotFoundException:
                    pass
                except Exception:
                    pass
                time.sleep(0.5)
            if state.SHUTDOWN:
                break
            state.state["runs"]      = 0
            state.state["run_start"] = 0.0
            lobby.auto_rejoin()
            continue

    logger.info("Main loop exiting (SHUTDOWN=%s)", state.SHUTDOWN)


# =========================
# Start / Stop
# =========================
def start() -> bool:
    """Start the macro in a background thread. Returns False if Roblox not found."""
    if not helpers.initialize():
        return False
    state.SHUTDOWN              = False
    state.state["running"]      = True
    state.state["runs"]              = 0
    state.state["total_runs"]        = 0
    state.state["wins"]              = 0
    state.state["losses"]            = 0
    state.state["runs_since_rejoin"] = 0
    state.state["session_start"]     = time.time()
    state.state["run_start"]         = 0.0

    Thread(target=watchdogs.disconnect_checker, daemon=True).start()
    Thread(target=watchdogs.popup_watcher,      daemon=True).start()

    if state.STRATEGY == "cid_act2":
        logger.info("Starting strategy: Cid Act 2 (team=%d)", state.ACT2_TEAM)
        # boss_watcher not started — Act 2 handles boss detection inline
        state._macro_thread = Thread(target=cid_act2.run_loop, daemon=True)
    else:
        logger.info("Starting strategy: Cid Raid")
        Thread(target=watchdogs.boss_watcher, daemon=True).start()
        state._macro_thread = Thread(target=main_loop, daemon=True)

    state._macro_thread.start()
    return True


def stop():
    """Stop the macro cooperatively. Watcher threads will exit on their next SHUTDOWN check."""
    state.SHUTDOWN              = True
    state.state["running"]      = False
    state.state["run_start"]    = 0.0
    logger.info("Macro stop requested.")


if __name__ == "__main__":
    Thread(target=softlocks.softlock_watchdog,    daemon=True).start()
    Thread(target=softlocks.global_rejoin_watchdog, daemon=True).start()
    state.state["session_start"] = time.time()
    try:
        if not helpers.initialize():
            logger.error("Cannot start: Roblox window not found.")
            sys.exit(1)
        Thread(target=watchdogs.boss_watcher,  daemon=True).start()
        Thread(target=watchdogs.popup_watcher, daemon=True).start()
        main_loop()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        stop()
    except Exception:
        logger.exception("Unhandled exception in main")
        stop()
    sys.exit(0)

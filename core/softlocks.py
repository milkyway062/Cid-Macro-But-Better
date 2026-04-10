import logging
import time

import state
import actions
import lobby

logger = logging.getLogger(__name__)


def softlock_watchdog():
    """
    Daemon thread: if a run exceeds state["run_timeout"], force-restart it.
    Reads run_timeout from state.state["run_timeout"] so the GUI can change it live.
    """
    logger.info("Softlock watchdog started")
    while True:
        try:
            run_start = state.state["run_start"]
            if run_start > 0:
                elapsed = time.time() - run_start
                if elapsed > state.state["run_timeout"]:
                    logger.error(
                        "Run timeout hit (%.1fs elapsed) — force restarting run", elapsed)
                    state._restart_run.set()
                    state.state["run_start"] = 0.0
                    try:
                        actions.restart_match_ingame()
                    except Exception:
                        logger.exception("watchdog: restart_match_ingame failed")
            time.sleep(1.0)
        except Exception:
            logger.exception("softlock_watchdog encountered an error")
            time.sleep(1.0)


def global_rejoin_watchdog():
    """
    Daemon thread: if a single run exceeds GLOBAL_REJOIN_TIMEOUT (5 min), kill and
    restart Roblox entirely. Resets the run counter so auto-rejoin doesn't re-fire.
    """
    logger.info("Global rejoin watchdog started")
    while True:
        try:
            run_start = state.state["run_start"]
            if run_start > 0 and not state.SHUTDOWN:
                elapsed = time.time() - run_start
                if elapsed > state.GLOBAL_REJOIN_TIMEOUT:
                    logger.error(
                        "Global rejoin watchdog: run exceeded %.0fs — restarting Roblox",
                        elapsed,
                    )
                    state.state["run_start"] = 0.0
                    state.state["runs"]      = 0
                    state._restart_run.set()
                    lobby._do_roblox_rejoin()
            time.sleep(1.0)
        except Exception:
            logger.exception("global_rejoin_watchdog error")
            time.sleep(1.0)

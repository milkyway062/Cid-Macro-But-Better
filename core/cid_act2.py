"""
core/cid_act2.py
Cid Act 2 strategy loop — ported from Kouhaii's Cid_Act_2.py.
"""
import logging
import time
from threading import Thread

import pyautogui

import state
import config
import helpers
import detections
import actions
import lobby
import webhook
import InputHandler

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
REPLAY_POS           = (590, 710)
VOTE_START_POS       = (840, 228)
CLOSE_POS            = (602, 380)
SKELE_CLOSE          = (931, 282)
ABILITY_POS          = (645, 450)
ABILITY_POS_2        = (645, 520)
RUNS_BEFORE_REJOIN   = 300
WEBHOOK_EVERY_N_RUNS = 50
GEMS_PER_WIN         = 150

# ── Unit data ─────────────────────────────────────────────────────────────────
# Sorted by slot key (1 = slot 1, 2 = slot 2, …).
# Schema is extensible — add "icon", "memoria", "familiar" fields later.
TEAMS = {
    1: [
        {"name": "Ichigo",     "key": "1", "pos": (805, 399)},
        {"name": "Sakura",     "key": "2", "pos": (829, 338)},
        {"name": "Skele King", "key": "3", "pos": (738, 399)},
        {"name": "Alucard",    "key": "4", "pos": (1003, 436)},
        {"name": "Rukia",      "key": "5"},
        {"name": "Gohan",      "key": "6"},
    ],
    2: [
        {"name": "Ichigo",     "key": "1", "pos": (682, 512)},
        {"name": "Sakura",     "key": "2", "pos": (711, 537)},
        {"name": "Skele King", "key": "3", "pos": (605, 509)},
        {"name": "Alucard",    "key": "4", "pos": (639, 373)},
        {"name": "Aki",        "key": "5", "pos": (688, 546)},
        {"name": "Gohan",      "key": "6"},
    ],
}


def _unit(team_num: int, key: str) -> dict:
    """Look up a unit by hotbar key for the given team."""
    for u in TEAMS[team_num]:
        if u["key"] == key:
            return u
    raise KeyError(f"No unit with key={key!r} in team {team_num}")


# ── Coordinate helpers ────────────────────────────────────────────────────────
def _p(x: int, y: int) -> tuple:
    """Offset raw window-relative coords by Roblox window position."""
    return (x + state.dx, y + state.dy)


def _pxl(x: int, y: int, rgb: tuple, tol: int = 20) -> bool:
    try:
        return pyautogui.pixelMatchesColor(x + state.dx, y + state.dy, rgb, tolerance=tol)
    except Exception:
        return False


def _img_exists(name: str, region=None, confidence: float = 0.7,
                grayscale: bool = True) -> bool:
    try:
        kw = dict(confidence=confidence, grayscale=grayscale)
        if region:
            rx, ry, rw, rh = region
            kw["region"] = (rx + state.dx, ry + state.dy, rw, rh)
        return pyautogui.locateOnScreen(detections._img(name), **kw) is not None
    except pyautogui.ImageNotFoundException:
        return False
    except Exception:
        return False


# ── Input helpers ─────────────────────────────────────────────────────────────
def _click(x: int, y: int, delay: float = 0.1) -> None:
    InputHandler.Click(x + state.dx, y + state.dy, delay)


def _rclick(x: int, y: int, delay: float = 0.5) -> None:
    InputHandler.RightClick(x + state.dx, y + state.dy, delay)


def _tap(key: str) -> None:
    InputHandler.KeyDown(config.KEYMAP[key])
    time.sleep(0.05)
    InputHandler.KeyUp(config.KEYMAP[key])
    time.sleep(0.05)


def _place_unit(unit: dict) -> None:
    pos = _p(*unit["pos"])
    InputHandler.MoveTo(*pos)
    time.sleep(0.02)
    InputHandler.KeyDown(config.KEYMAP[unit["key"]])
    time.sleep(0.02)
    InputHandler.KeyUp(config.KEYMAP[unit["key"]])
    time.sleep(0.06)
    InputHandler.Click(*pos, delay=0.1)


def _quick_rts() -> None:
    """Return to spawn (Kouhaii's quick_rts sequence)."""
    for x, y in [(232, 743), (1153, 503), (1217, 267)]:
        _click(x, y, delay=0.1)
        time.sleep(0.2)


# ── Chord spam ────────────────────────────────────────────────────────────────
_CHORD = ["a", "s", "d", "f", "g"]


def spam_chord_for_duration(duration: float = 2.0) -> None:
    """Hold A/S/D/F/G simultaneously for `duration` seconds."""
    deadline = time.time() + duration
    while time.time() < deadline:
        if state.SHUTDOWN:
            break
        for k in _CHORD:
            InputHandler.KeyDown(config.KEYMAP[k])
        time.sleep(0.02)
        for k in _CHORD:
            InputHandler.KeyUp(config.KEYMAP[k])
        time.sleep(0.05)
    # Safety release — prevents stuck keys if SHUTDOWN fires mid-press
    for k in _CHORD:
        try:
            InputHandler.KeyUp(config.KEYMAP[k])
        except Exception:
            pass


# ── Detection helpers ─────────────────────────────────────────────────────────
def _boss_hp_visible() -> bool:
    return _img_exists("Cid_Health.png", region=(555, 235, 125, 27),
                       confidence=0.7, grayscale=False)


def _is_win() -> bool:
    return _pxl(650, 270, (240, 178, 62), tol=20)


def _is_fail() -> bool:
    return _pxl(650, 270, (234, 62, 53), tol=20)


def _wait_start() -> bool:
    """Poll for vote_start.png up to 90 s. Returns True when found."""
    for _ in range(90):
        if state.SHUTDOWN:
            return False
        if _img_exists("vote_start.png", confidence=0.6, grayscale=True):
            return True
        time.sleep(1.0)
    return False


def _wait_end() -> str:
    """
    Spam ability 2 while polling win/fail pixels (20 s timeout).
    Returns 'win', 'fail', 'timeout', or 'stopped'.
    """
    deadline = time.time() + 20.0
    while time.time() < deadline:
        if state.SHUTDOWN:
            return "stopped"
        _click(*ABILITY_POS_2, delay=0.1)
        time.sleep(0.1)
        if _is_win():
            return "win"
        if _is_fail():
            return "fail"
        time.sleep(0.1)
    logger.warning("Act2: _wait_end timed out — restarting match")
    actions.restart_match_ingame()
    return "timeout"


# ── Auto-start helper ─────────────────────────────────────────────────────────
def _enable_auto_start() -> None:
    logger.info("Act2: enabling auto-start")
    try:
        _click(1184, 293, delay=0.3)
        time.sleep(1.0)
        _click(220, 879, delay=0.3)
        time.sleep(1.0)
        if _pxl(1180, 587, (33, 15, 24), tol=20):   # toggle only if off (dark pixel)
            _click(1180, 587, delay=0.3)
            time.sleep(1.0)
        _click(1223, 269, delay=0.3)
        time.sleep(1.0)
        _click(750, 286, delay=0.2)
        _click(750, 286, delay=0.2)
        time.sleep(0.5)
    except Exception:
        logger.exception("Act2: _enable_auto_start failed")


# ── Webhook ───────────────────────────────────────────────────────────────────
def _send_webhook(wins: int, losses: int, runs_since_rejoin: int) -> None:
    try:
        sess_elapsed = time.time() - state.state.get("session_start", time.time())
        run_elapsed  = time.time() - state.state.get("run_start", time.time())
        total_runs   = wins + losses
        run_time     = time.strftime("%H:%M:%S", time.gmtime(run_elapsed))
        total_time   = time.strftime("%H:%M:%S", time.gmtime(sess_elapsed))
        webhook.send_webhook(
            run_time=run_time,
            total_time=total_time,
            total_runs=total_runs,
            runs_since_rejoin=runs_since_rejoin,
        )
    except Exception:
        logger.exception("Act2: webhook failed")


# ── Team 1 sequence ───────────────────────────────────────────────────────────
def _run_team1() -> None:
    t = state.ACT2_TEAM
    skele   = _unit(t, "3")
    ichigo  = _unit(t, "1")
    alucard = _unit(t, "4")
    sakura  = _unit(t, "2")

    _place_unit(skele)
    time.sleep(0.1)
    _place_unit(ichigo)
    time.sleep(0.2)

    # Skele King ability → chord nuke
    _click(*skele["pos"])
    time.sleep(0.2)
    _click(*ABILITY_POS, delay=0.2)
    time.sleep(3.0)
    spam_chord_for_duration(duration=2.0)
    _click(*SKELE_CLOSE)
    time.sleep(1.2)

    # Wait for cooldown pixel to clear
    while _pxl(765, 791, (2, 0, 0)):
        if state.SHUTDOWN:
            return
        time.sleep(0.1)

    _place_unit(alucard)
    time.sleep(0.1)
    for _ in range(2):
        _tap("r")
        time.sleep(0.1)

    _place_unit(sakura)
    time.sleep(0.1)

    # Stock 1 loop
    temp = 0
    while _pxl(975, 140, (103, 219, 81)):
        if state.SHUTDOWN:
            return
        if temp >= 1:
            _click(*sakura["pos"])
            time.sleep(0.1)
        _click(*ABILITY_POS, delay=0.2)
        time.sleep(0.1)
        _click(*ichigo["pos"])
        time.sleep(0.2)
        temp += 1

    # Stock 2 loop
    while _pxl(830, 140, (103, 219, 81)):
        if state.SHUTDOWN:
            return
        _click(*sakura["pos"])
        time.sleep(0.1)
        _click(*ABILITY_POS, delay=0.2)
        time.sleep(0.1)
        _click(*skele["pos"])
        time.sleep(0.2)
        temp += 1

    _click(*sakura["pos"])
    time.sleep(0.1)
    _tap("x")
    time.sleep(0.1)
    for _ in range(2):
        _tap("r")
        time.sleep(0.1)
    _click(*ichigo["pos"])
    time.sleep(0.1)
    for _ in range(2):
        _tap("r")
        time.sleep(0.1)

    # Wait for boss HP bar to disappear (boss dead)
    temp_sec = 0.0
    while _boss_hp_visible():
        if state.SHUTDOWN:
            return
        time.sleep(0.1)
        temp_sec += 0.1
    if temp_sec < 1.5:
        time.sleep(2.0 - temp_sec)

    for _ in range(2):
        _tap("x")
        time.sleep(0.2)

    _click(*skele["pos"])
    if state.ACT2_CONSISTENT_NUKE:
        while not _boss_hp_visible():
            if state.SHUTDOWN:
                return
            time.sleep(0.1)
    else:
        time.sleep(state.ACT2_SKELE_WAIT)


# ── Team 2 sequence ───────────────────────────────────────────────────────────
def _run_team2() -> None:
    t = state.ACT2_TEAM
    skele   = _unit(t, "3")
    ichigo  = _unit(t, "1")
    sakura  = _unit(t, "2")
    alucard = _unit(t, "4")
    aki     = _unit(t, "5")

    _place_unit(skele)
    time.sleep(3.4)
    _place_unit(ichigo)
    time.sleep(2.6)
    _place_unit(aki)
    time.sleep(0.1)
    _place_unit(sakura)
    time.sleep(0.1)

    _click(*ABILITY_POS, delay=0.2)
    time.sleep(0.1)
    _click(*aki["pos"])
    time.sleep(0.1)
    _click(*sakura["pos"])
    time.sleep(0.1)
    _click(*ABILITY_POS, delay=0.2)
    time.sleep(0.1)
    _click(*ichigo["pos"])
    time.sleep(0.1)
    _click(*sakura["pos"])
    time.sleep(0.3)
    _tap("x")
    time.sleep(0.2)
    _click(*ichigo["pos"])
    time.sleep(0.3)
    for _ in range(2):
        _tap("r")
        time.sleep(0.2)
    time.sleep(0.2)
    for _ in range(2):
        _tap("x")
        time.sleep(0.2)

    while _boss_hp_visible():
        if state.SHUTDOWN:
            return
        time.sleep(0.1)
    time.sleep(0.2)
    _click(*CLOSE_POS)

    # Wait for Alucard hotbar slot to become available (slot 4 = x=800, y=826)
    while _pxl(800, 826, (35, 35, 35)):
        if state.SHUTDOWN:
            return
        time.sleep(0.1)

    _place_unit(alucard)
    time.sleep(0.5)
    _click(*skele["pos"])
    time.sleep(0.4)
    for _ in range(4):
        _click(*ABILITY_POS_2, delay=0.2)
        time.sleep(0.1)


# ── Main loop ─────────────────────────────────────────────────────────────────
def run_loop() -> None:
    """
    Cid Act 2 strategy loop. Launched as a daemon thread by Main.start()
    when state.STRATEGY == 'cid_act2'.
    """
    logger.info("Cid Act 2 run_loop started (team=%d)", state.ACT2_TEAM)

    first_match        = True
    auto_start_enabled = False
    runs_since_rejoin  = 0
    wins               = 0
    losses             = 0

    state.state["session_start"] = time.time()

    while not state.SHUTDOWN:
        state.state["run_start"] = time.time()
        logger.info("==== Act2 new run (runs_since_rejoin=%d) ====", runs_since_rejoin)

        # Periodic rejoin
        if runs_since_rejoin >= RUNS_BEFORE_REJOIN:
            logger.info("Act2: periodic rejoin after %d runs", runs_since_rejoin)
            runs_since_rejoin                = 0
            first_match                      = True
            auto_start_enabled               = False
            state.state["runs_since_rejoin"] = 0
            lobby._do_roblox_rejoin("Act2 periodic rejoin")
            if state.SHUTDOWN:
                break
            continue

        # Click replay to advance to next match (not needed on first match)
        if not first_match:
            _click(*REPLAY_POS)
            time.sleep(0.2)
            logger.info("Act2: waiting for vote_start after replay")
            if not _wait_start():
                if state.SHUTDOWN:
                    break
                logger.warning("Act2: vote_start not detected after replay, proceeding anyway")
            time.sleep(0.5)

        # First-match setup (once per session / after rejoin)
        if first_match:
            logger.info("Act2: first match setup")
            if not _wait_start():
                if state.SHUTDOWN:
                    break
                logger.warning("Act2: vote_start not detected, proceeding anyway")
            _quick_rts()
            time.sleep(0.5)
            _rclick(523, 544, delay=0.5)
            time.sleep(2.0)
            if state.ACT2_TEAM == 1:
                _rclick(580, 650, delay=0.5)
                time.sleep(2.0)
            _click(*VOTE_START_POS)
            first_match = False
            time.sleep(0.2)

        # Execute team sequence
        if state.ACT2_TEAM == 1:
            _run_team1()
        else:
            _run_team2()

        if state.SHUTDOWN:
            break

        # Wait for match end
        result = _wait_end()
        logger.info("Act2: match result = %s", result)

        if result == "stopped":
            break

        # Update counters
        runs_since_rejoin                += 1
        state.state["total_runs"]        += 1
        state.state["runs_since_rejoin"]  = runs_since_rejoin

        if result == "win":
            wins                  += 1
            state.state["wins"]   += 1
            if not auto_start_enabled:
                _enable_auto_start()
                auto_start_enabled = True
        elif result in ("fail", "timeout"):
            losses                  += 1
            state.state["losses"]   += 1

        # Webhook every N runs
        total = wins + losses
        if total % WEBHOOK_EVERY_N_RUNS == 0 and total > 0:
            Thread(
                target=_send_webhook,
                args=(wins, losses, runs_since_rejoin),
                daemon=True,
            ).start()

        logger.info("Act2 — runs: %d | wins: %d | losses: %d | gems: %d",
                    total, wins, losses, wins * GEMS_PER_WIN)

    logger.info("Cid Act 2 run_loop exiting (SHUTDOWN=%s)", state.SHUTDOWN)

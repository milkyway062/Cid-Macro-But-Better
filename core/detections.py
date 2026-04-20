import logging
import time
import os
import pyautogui

import state
import config
import InputHandler

logger = logging.getLogger(__name__)


def _img(name: str) -> str:
    """Return absolute path for an image in the Images folder (project root)."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "Images", name)


def _wait_for_image(name: str, timeout: float = 5.0, confidence: float = 0.7) -> object:
    """Poll for an image on screen; return its Box location or None on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if state.SHUTDOWN:
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


def is_victory() -> bool:
    """Pixel-based victory screen check."""
    try:
        return pyautogui.pixelMatchesColor(
            config.RESULT_POS_OFFSET[0] + state.dx,
            config.RESULT_POS_OFFSET[1] + state.dy,
            config.RESULT_WIN_COLOR,
            tolerance=30,
        )
    except Exception:
        return False


def is_defeat() -> bool:
    """Pixel-based defeat screen check."""
    try:
        return pyautogui.pixelMatchesColor(
            config.RESULT_POS_OFFSET[0] + state.dx,
            config.RESULT_POS_OFFSET[1] + state.dy,
            config.RESULT_LOSE_COLOR,
            tolerance=30,
        )
    except Exception:
        return False


def is_stock_available(pos: tuple) -> bool:
    """Return True if a stock slot is present (green = available, red = on cooldown)."""
    try:
        green = pyautogui.pixelMatchesColor(*pos, expectedRGBColor=config.STOCK_COLOR, tolerance=50)
        red   = pyautogui.pixelMatchesColor(*pos, expectedRGBColor=config.STOCK_RED,   tolerance=80)
        return green or red
    except Exception:
        return False


def _check_match_end() -> bool:
    """Return True if a Victory or Failed screen is visible."""
    try:
        if _wait_for_image("Victory.png", timeout=2.0, confidence=0.9):
            return True
        if _wait_for_image("Failed.png", timeout=2.0, confidence=0.9):
            return True
    except Exception:
        pass
    return False


def is_in_lobby() -> bool:
    """Return True if AreaIcon.png is visible (we are in the lobby)."""
    if not state.rb_window:
        return False
    try:
        loc = pyautogui.locateOnScreen(_img("AreaIcon.png"), confidence=0.7, grayscale=True)
        return loc is not None
    except pyautogui.ImageNotFoundException:
        return False
    except Exception:
        logger.exception("is_in_lobby error")
        return False


def _daily_rewards_visible() -> bool:
    """Return True if the daily rewards popup is present (white pixel at 654,187)."""
    if not state.rb_window:
        return False
    try:
        return pyautogui.pixelMatchesColor(654 + state.dx, 187 + state.dy,
                                           (255, 255, 255), tolerance=5)
    except Exception:
        return False


def dismiss_passive_menu() -> bool:
    """Detect passive title on screen; if found, click its center."""
    if not state.rb_window:
        return False
    region = (state.dx, state.dy, state.rb_window.width, state.rb_window.height)
    try:
        location = pyautogui.locateOnScreen(
            image=_img("passive_title.png"),
            grayscale=True,
            confidence=0.75,
            region=region,
        )
        if location:
            cx, cy = pyautogui.center(location)
            InputHandler.Click(cx, cy, delay=0.1)
            logger.info("Passive menu detected and dismissed")
            return True
    except pyautogui.ImageNotFoundException:
        pass
    except Exception:
        logger.exception("dismiss_passive_menu failed")
    return False


def click_vote_start() -> bool:
    """Detect and click the Vote Start button if present."""
    try:
        location = pyautogui.locateOnScreen(
            image=_img("vote_start.png"),
            grayscale=True,
            confidence=0.6,
        )
        if location:
            cx, cy = pyautogui.center(location)
            cx += 124  # button is 124px right of image center
            InputHandler.Click(cx, cy, delay=0.1)
            logger.info("Vote start clicked at (%d, %d)", cx, cy)
            return True
    except pyautogui.ImageNotFoundException:
        pass
    except Exception:
        logger.exception("click_vote_start failed")
    return False


def dismiss_cancel_button() -> bool:
    """Locate Cancel button via image match and click its center."""
    if state._restarting.is_set() or not state._match_active.is_set():
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
            state._restart_run.set()
            return True
    except pyautogui.ImageNotFoundException:
        pass
    except Exception:
        logger.exception("dismiss_cancel_button failed")
    return False

import logging
import time
import json
import requests
from datetime import datetime, timezone
from threading import Thread

import state

logger = logging.getLogger(__name__)


def send_webhook(run_time: str, total_time: str, total_runs: int,
                 runs_since_rejoin: int, retries: int = 3):
    state.LAST_WEBHOOK_ATTEMPT = time.time()

    if not state.WEBHOOK_URL or not state.WEBHOOK_URL.startswith("https://discord.com/api/webhooks/"):
        logger.info("Webhook URL not configured; skipping webhook.")
        state.LAST_WEBHOOK_OK = False
        return False

    embed = {
        "title":     "Loxer's Automation",
        "color":     3447003,
        "fields": [
            {"name": "🔁 Total Runs",         "value": str(total_runs),        "inline": True},
            {"name": "🕒 Run Time",            "value": run_time,               "inline": True},
            {"name": "⏱️ Total Time",          "value": total_time,             "inline": True},
            {"name": "📊 Runs Since Rejoin",   "value": str(runs_since_rejoin), "inline": True},
        ],
        "thumbnail": {"url": "https://media1.tenor.com/m/1VbR3kVavicAAAAC/gin.gif"},
        "footer":    {"text": f"Loxer's Automation | Run time: {run_time}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    payload = {
        "username":   "Loxer's Automation",
        "avatar_url": "https://media1.tenor.com/m/mbhL7DZmXEMAAAAC/%D0%B0%D0%B0%D0%B0%D0%B0.gif",
        "embeds": [embed],
    }

    headers = {"Content-Type": "application/json"}
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(state.WEBHOOK_URL, json=payload, headers=headers, timeout=10)
            if resp.status_code in (200, 201, 204):
                logger.info("Webhook sent successfully (attempt %d).", attempt)
                state.LAST_WEBHOOK_OK          = True
                state.state["last_webhook_ok"] = True
                return True
            else:
                logger.warning("Webhook attempt %d failed: %s %s", attempt, resp.status_code, resp.text)
        except requests.RequestException:
            logger.exception("Webhook attempt %d raised an exception", attempt)
        time.sleep(1)

    logger.error("All %d webhook attempts failed.", retries)
    state.LAST_WEBHOOK_OK          = False
    state.state["last_webhook_ok"] = False
    return False


def send_rejoin_webhook(reason: str, runs_since_rejoin: int, retries: int = 3):
    if not state.WEBHOOK_URL or not state.WEBHOOK_URL.startswith("https://discord.com/api/webhooks/"):
        logger.info("Webhook URL not configured; skipping rejoin webhook.")
        return False

    embed = {
        "title":     "Loxer's Automation — Rejoin",
        "color":     0xe67e22,
        "fields": [
            {"name": "⚠️ Reason",              "value": reason,                          "inline": True},
            {"name": "🔁 Runs This Session",   "value": str(state.state["runs"]),        "inline": True},
            {"name": "📊 Runs Since Rejoin",   "value": str(runs_since_rejoin),          "inline": True},
        ],
        "thumbnail": {"url": "https://media1.tenor.com/m/1VbR3kVavicAAAAC/gin.gif"},
        "footer":    {"text": "Loxer's Automation | Rejoin"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    payload = {
        "username":   "Loxer's Automation",
        "avatar_url": "https://media1.tenor.com/m/mbhL7DZmXEMAAAAC/%D0%B0%D0%B0%D0%B0%D0%B0.gif",
        "embeds": [embed],
    }

    headers = {"Content-Type": "application/json"}
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(state.WEBHOOK_URL, json=payload, headers=headers, timeout=10)
            if resp.status_code in (200, 201, 204):
                logger.info("Rejoin webhook sent (attempt %d).", attempt)
                return True
            else:
                logger.warning("Rejoin webhook attempt %d failed: %s %s", attempt, resp.status_code, resp.text)
        except requests.RequestException:
            logger.exception("Rejoin webhook attempt %d raised an exception", attempt)
        time.sleep(1)

    logger.error("All %d rejoin webhook attempts failed.", retries)
    return False

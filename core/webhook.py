import logging
import time
import json
import requests
from datetime import datetime, timezone

import state

logger = logging.getLogger(__name__)


def send_webhook(run_time: str, win: int, lose: int, task_name: str,
                 img_bytes=None, retries: int = 3):
    state.LAST_WEBHOOK_ATTEMPT = time.time()

    if not state.WEBHOOK_URL or not state.WEBHOOK_URL.startswith("https://discord.com/api/webhooks/"):
        logger.info("Webhook URL not configured; skipping webhook.")
        state.LAST_WEBHOOK_OK = False
        return False

    total_runs = win + lose
    if total_runs == 0:
        logger.warning("No wins or losses detected; skipping webhook.")
        state.LAST_WEBHOOK_OK = True
        return False

    win_ratio = (win / total_runs) * 100

    embed = {
        "title": "Loxer's Automation",
        "description": "",
        "color": 3447003,
        "fields": [
            {"name": "🕒 Run Time",      "value": run_time,                  "inline": True},
            {"name": "⚔️ Wins",          "value": str(win),                  "inline": True},
            {"name": "📈 Success Rate",  "value": f"{win_ratio:.2f}%",       "inline": True},
            {"name": "🔁 Total Runs",    "value": str(total_runs),           "inline": True},
            {"name": "⚙️ Current Task",  "value": task_name},
        ],
        "image":     {"url": "attachment://screenshot.png"} if img_bytes else {},
        "thumbnail": {"url": "https://media1.tenor.com/m/1VbR3kVavicAAAAC/gin.gif"},
        "footer":    {"text": f"Loxer's Automation | Run time: {run_time}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    payload = {
        "username":   "Loxer's Automation",
        "avatar_url": "https://media1.tenor.com/m/mbhL7DZmXEMAAAAC/%D0%B0%D0%B0%D0%B0%D0%B0.gif",
        "embeds": [embed],
    }

    for attempt in range(1, retries + 1):
        try:
            if img_bytes:
                files = {"file": ("screenshot.png", img_bytes, "image/png")}
                data  = {"payload_json": json.dumps(payload)}
                resp  = requests.post(state.WEBHOOK_URL, data=data, files=files, timeout=10)
            else:
                headers = {"Content-Type": "application/json"}
                resp    = requests.post(state.WEBHOOK_URL, json=payload, headers=headers, timeout=10)

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

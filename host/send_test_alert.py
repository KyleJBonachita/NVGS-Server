#!/usr/bin/env python3
"""Send one harmless desktop alert and test any configured webhook."""

import os

from nvgs_alerts import send_alert, send_desktop_notification

if __name__ == "__main__":
    title = "Test alert"
    detail = "Test only: the NVGS desktop alert connection is working."
    level = "warning"

    desktop_delivered = send_desktop_notification(title, detail, level)

    # Record and optionally forward the same test without creating a duplicate
    # desktop popup.
    desktop_setting = os.environ.get("NVGS_DESKTOP_NOTIFICATIONS")
    os.environ["NVGS_DESKTOP_NOTIFICATIONS"] = "false"
    delivered = send_alert(
        title,
        detail,
        level=level,
    )
    if desktop_setting is None:
        os.environ.pop("NVGS_DESKTOP_NOTIFICATIONS", None)
    else:
        os.environ["NVGS_DESKTOP_NOTIFICATIONS"] = desktop_setting

    webhook_configured = bool(os.getenv("NVGS_ALERT_WEBHOOK_URL", "").strip())
    failed = not desktop_delivered or (webhook_configured and not delivered)
    raise SystemExit(1 if failed else 0)

#!/usr/bin/env python3
"""Send one harmless desktop alert and test any configured webhook."""

import os

from nvgs_alerts import (
    send_alert,
    send_desktop_notification,
    send_fullscreen_alert,
    setting_enabled,
)

if __name__ == "__main__":
    title = "Test alert"
    detail = "Test only: the NVGS desktop alert connection is working."
    level = "warning"

    fullscreen_delivered = send_fullscreen_alert(title, detail, level)
    desktop_delivered = False
    if not fullscreen_delivered:
        desktop_delivered = send_desktop_notification(title, detail, level)

    # Record and optionally forward the same test without creating a duplicate
    # desktop or full-screen popup.
    desktop_setting = os.environ.get("NVGS_DESKTOP_NOTIFICATIONS")
    fullscreen_setting = os.environ.get("NVGS_FULLSCREEN_ALERTS")
    os.environ["NVGS_DESKTOP_NOTIFICATIONS"] = "false"
    os.environ["NVGS_FULLSCREEN_ALERTS"] = "false"
    delivered = send_alert(
        title,
        detail,
        level=level,
    )
    if desktop_setting is None:
        os.environ.pop("NVGS_DESKTOP_NOTIFICATIONS", None)
    else:
        os.environ["NVGS_DESKTOP_NOTIFICATIONS"] = desktop_setting
    if fullscreen_setting is None:
        os.environ.pop("NVGS_FULLSCREEN_ALERTS", None)
    else:
        os.environ["NVGS_FULLSCREEN_ALERTS"] = fullscreen_setting

    webhook_configured = bool(os.getenv("NVGS_ALERT_WEBHOOK_URL", "").strip())
    fullscreen_required = setting_enabled("NVGS_FULLSCREEN_ALERTS", default=True)
    failed = (
        not (fullscreen_delivered or desktop_delivered)
        or (fullscreen_required and not fullscreen_delivered)
        or (webhook_configured and not delivered)
    )
    raise SystemExit(1 if failed else 0)

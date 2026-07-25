#!/usr/bin/env python3
"""Send one harmless test message through the configured alert webhook."""

from nvgs_alerts import send_alert

if __name__ == "__main__":
    delivered = send_alert(
        "Test alert",
        "The NVGS remote alert connection is working.",
        level="test",
    )
    raise SystemExit(0 if delivered else 1)

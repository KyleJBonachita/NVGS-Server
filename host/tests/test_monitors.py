import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOST_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST_DIR))

import nvgs_auth_monitor  # noqa: E402
import nvgs_monitor  # noqa: E402
from nvgs_alerts import send_alert  # noqa: E402


class ConditionMonitorTests(unittest.TestCase):
    @patch("nvgs_monitor.read_text")
    def test_disconnected_network_link_is_unhealthy(self, read_text):
        read_text.side_effect = ["0", "down"]
        result = nvgs_monitor.check_network_link("enp3s0")
        self.assertFalse(result.healthy)
        self.assertIn("disconnected", result.detail)

    @patch("nvgs_monitor.read_text")
    def test_connected_network_link_is_healthy(self, read_text):
        read_text.side_effect = ["1", "up"]
        result = nvgs_monitor.check_network_link("enp3s0")
        self.assertTrue(result.healthy)
        self.assertIn("connected", result.detail)

    @patch("nvgs_monitor.glob.glob")
    @patch("nvgs_monitor.read_text")
    def test_unplugged_charger_is_unhealthy(self, read_text, glob):
        glob.return_value = ["/sys/class/power_supply/AC"]
        read_text.side_effect = ["Mains", "0"]
        result = nvgs_monitor.check_ac_power()
        self.assertFalse(result.healthy)
        self.assertIn("unplugged", result.detail)

    @patch("nvgs_monitor.socket.create_connection")
    def test_application_falls_back_to_port_check_without_ca(self, create_connection):
        create_connection.return_value.__enter__ = MagicMock()
        create_connection.return_value.__exit__ = MagicMock(return_value=False)
        with patch.dict(
            os.environ,
            {
                "NVGS_APP_HEALTH_URL": "https://localhost/api/health/",
                "NVGS_CA_FILE": "missing-test-ca.crt",
            },
            clear=False,
        ):
            result = nvgs_monitor.check_application()
        self.assertTrue(result.healthy)
        self.assertIn("port is open", result.detail)


class AuthenticationMonitorTests(unittest.TestCase):
    def test_failed_ssh_password_is_detected_and_summarized(self):
        message = (
            "Failed password for invalid user somebody from 10.20.30.40 "
            "port 50100 ssh2"
        )
        self.assertTrue(nvgs_auth_monitor.is_authentication_failure(message))
        summary = nvgs_auth_monitor.summarize(message)
        self.assertIn("somebody", summary)
        self.assertIn("10.20.30.40", summary)
        self.assertNotIn("Failed password", summary)

    def test_normal_login_message_is_ignored(self):
        self.assertFalse(
            nvgs_auth_monitor.is_authentication_failure(
                "Accepted publickey for administrator from 10.20.30.40"
            )
        )


class AlertHelperTests(unittest.TestCase):
    def test_alert_without_webhook_is_logged_only(self):
        with patch.dict(os.environ, {"NVGS_ALERT_WEBHOOK_URL": ""}, clear=False):
            delivered = send_alert("Test", "Local journal only")
        self.assertFalse(delivered)


if __name__ == "__main__":
    unittest.main()

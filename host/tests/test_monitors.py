import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOST_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST_DIR))

import nvgs_alert_overlay  # noqa: E402
import nvgs_auth_monitor  # noqa: E402
import nvgs_monitor  # noqa: E402
from nvgs_alerts import (  # noqa: E402
    send_alert,
    send_desktop_notification,
    send_fullscreen_alert,
)


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
        with patch.dict(
            os.environ,
            {
                "NVGS_ALERT_WEBHOOK_URL": "",
                "NVGS_DESKTOP_NOTIFICATIONS": "false",
                "NVGS_FULLSCREEN_ALERTS": "false",
            },
            clear=False,
        ):
            delivered = send_alert("Test", "Local journal only")
        self.assertFalse(delivered)

    @patch("nvgs_alerts.subprocess.run")
    @patch("nvgs_alerts.Path.exists", return_value=True)
    @patch("nvgs_alerts.subprocess.check_output", return_value="1000\n")
    @patch("nvgs_alerts.shutil.which")
    def test_desktop_alert_uses_logged_in_users_session(
        self,
        which,
        check_output,
        path_exists,
        run,
    ):
        del check_output, path_exists
        which.side_effect = lambda command: {
            "runuser": "/usr/sbin/runuser",
            "notify-send": "/usr/bin/notify-send",
        }.get(command)
        run.return_value.returncode = 0

        with patch.dict(
            os.environ,
            {
                "NVGS_DESKTOP_NOTIFICATIONS": "true",
                "NVGS_DESKTOP_USER": "robotics",
            },
            clear=False,
        ):
            delivered = send_desktop_notification(
                "AC power",
                "charger unplugged",
            )

        self.assertTrue(delivered)
        command = run.call_args.args[0]
        self.assertIn("robotics", command)
        session_bus = Path("/run/user") / "1000" / "bus"
        self.assertIn(
            f"DBUS_SESSION_BUS_ADDRESS=unix:path={session_bus}",
            command,
        )
        self.assertIn("--urgency=critical", command)
        self.assertIn("charger unplugged", command)

    @patch("nvgs_alerts.shutil.which")
    def test_desktop_alert_is_disabled_without_configuration(self, which):
        with patch.dict(
            os.environ,
            {"NVGS_DESKTOP_NOTIFICATIONS": "false"},
            clear=False,
        ):
            delivered = send_desktop_notification("Test", "Disabled")

        self.assertFalse(delivered)
        which.assert_not_called()

    @patch("nvgs_alerts.socket.AF_UNIX", new=1, create=True)
    @patch("nvgs_alerts.socket.socket")
    @patch("nvgs_alerts.Path.is_socket", return_value=True)
    @patch("nvgs_alerts.desktop_user_id", return_value="1000")
    def test_warning_is_sent_to_fullscreen_overlay(
        self,
        desktop_user_id,
        path_is_socket,
        socket_factory,
    ):
        del desktop_user_id, path_is_socket
        client = socket_factory.return_value.__enter__.return_value

        with patch.dict(
            os.environ,
            {
                "NVGS_FULLSCREEN_ALERTS": "true",
                "NVGS_DESKTOP_USER": "robotics",
            },
            clear=False,
        ):
            delivered = send_fullscreen_alert(
                "Network link",
                "Ethernet cable disconnected",
            )

        self.assertTrue(delivered)
        payload, destination = client.sendto.call_args.args
        self.assertIn(b"Ethernet cable disconnected", payload)
        self.assertTrue(destination.endswith("nvgs-alert-overlay.sock"))


class FullscreenOverlayTests(unittest.TestCase):
    def test_valid_warning_payload_is_parsed(self):
        alert = nvgs_alert_overlay.parse_alert(
            b'{"title":"AC power","detail":"charger unplugged",'
            b'"level":"warning","server":"NVGS-Server"}'
        )

        self.assertIsNotNone(alert)
        self.assertEqual(alert["title"], "AC power")
        self.assertEqual(alert["detail"], "charger unplugged")

    def test_recovery_payload_does_not_take_over_the_screen(self):
        alert = nvgs_alert_overlay.parse_alert(
            b'{"title":"AC power","detail":"charger connected",'
            b'"level":"recovery"}'
        )

        self.assertIsNone(alert)


if __name__ == "__main__":
    unittest.main()

import os
import sys
import types
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

    def test_link_outage_suppresses_dependent_warning_cascade(self):
        self.assertTrue(
            nvgs_monitor.suppress_during_link_outage("Internet", True)
        )
        self.assertTrue(
            nvgs_monitor.suppress_during_link_outage("Application", True)
        )
        self.assertFalse(
            nvgs_monitor.suppress_during_link_outage("AC power", True)
        )
        self.assertFalse(
            nvgs_monitor.suppress_during_link_outage("Internet", False)
        )


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

    def test_auth_retries_with_changing_ports_share_one_dedupe_key(self):
        first = "Failed password for user agent from 10.20.30.40 port 50100 ssh2"
        second = "Failed password for user agent from 10.20.30.40 port 50199 ssh2"
        self.assertEqual(
            nvgs_auth_monitor.authentication_event_key(first),
            nvgs_auth_monitor.authentication_event_key(second),
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
        self.assertIn("--urgency=normal", command)
        self.assertIn("--hint=boolean:transient:true", command)
        self.assertIn(
            "--hint=string:x-canonical-private-synchronous:nvgs-server-alert",
            command,
        )
        self.assertIn("charger unplugged", command)

    @patch("nvgs_alerts.send_desktop_notification")
    @patch("nvgs_alerts.send_fullscreen_alert", return_value=True)
    def test_warning_uses_one_local_ui_when_overlay_is_available(
        self,
        fullscreen_alert,
        desktop_notification,
    ):
        with patch.dict(
            os.environ,
            {"NVGS_ALERT_WEBHOOK_URL": ""},
            clear=False,
        ):
            send_alert("Network link", "Ethernet disconnected")

        fullscreen_alert.assert_called_once()
        desktop_notification.assert_not_called()

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
    def test_gtk_rendering_namespaces_are_pinned(self):
        requested_versions = []
        gi_module = types.ModuleType("gi")
        repository_module = types.ModuleType("gi.repository")
        repository_module.Gdk = object()
        repository_module.GdkPixbuf = object()
        repository_module.GLib = object()
        repository_module.Gtk = object()
        gi_module.repository = repository_module
        gi_module.require_version = lambda namespace, version: (
            requested_versions.append((namespace, version))
        )

        with patch.dict(
            sys.modules,
            {
                "gi": gi_module,
                "gi.repository": repository_module,
            },
        ):
            modules = nvgs_alert_overlay.load_gtk3_modules()

        self.assertEqual(
            requested_versions,
            [("Gdk", "3.0"), ("GdkPixbuf", "2.0"), ("Gtk", "3.0")],
        )
        self.assertEqual(
            modules,
            (
                repository_module.Gdk,
                repository_module.GdkPixbuf,
                repository_module.GLib,
                repository_module.Gtk,
            ),
        )

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

    def test_alert_burst_is_presented_as_one_dismissible_group(self):
        title, detail, count = nvgs_alert_overlay.format_alert_batch(
            [
                {
                    "title": "Network link",
                    "detail": "Ethernet disconnected",
                    "server": "NVGS",
                },
                {
                    "title": "Application",
                    "detail": "Health check unavailable",
                    "server": "NVGS",
                },
            ]
        )

        self.assertEqual(title, "Multiple server warnings")
        self.assertIn("Network link", detail)
        self.assertIn("Application", detail)
        self.assertIn("one dismissal", count)

    def test_same_warning_title_has_one_overlay_identity(self):
        first = {
            "title": "Network link",
            "detail": "Ethernet disconnected",
        }
        reminder = {
            "title": "network LINK",
            "detail": "Ethernet remains disconnected",
        }
        self.assertEqual(
            nvgs_alert_overlay.alert_identity(first),
            nvgs_alert_overlay.alert_identity(reminder),
        )

    def test_overlay_uses_bounded_focus_retries_and_keyboard_dismissal(self):
        source = (HOST_DIR / "nvgs_alert_overlay.py").read_text(encoding="utf-8")
        self.assertIn("window.set_accept_focus(True)", source)
        self.assertIn("window.set_focus_on_map(True)", source)
        self.assertIn("window.present_with_time(Gdk.CURRENT_TIME)", source)
        self.assertIn("gdk_window.focus(Gdk.CURRENT_TIME)", source)
        self.assertIn('GLib.timeout_add(300, focus_window)', source)
        self.assertIn("Gdk.KEY_Escape", source)
        self.assertIn("Gdk.KEY_KP_Enter", source)

    def test_overlay_is_not_marked_as_a_centered_dialog(self):
        source = (HOST_DIR / "nvgs_alert_overlay.py").read_text(encoding="utf-8")
        self.assertNotIn("WindowTypeHint.DIALOG", source)
        self.assertNotIn("window.set_modal(True)", source)
        self.assertNotIn("screen.get_width()", source)
        self.assertNotIn("screen.get_height()", source)
        self.assertIn("monitor.get_geometry()", source)
        self.assertLess(
            source.index("window.fullscreen()"),
            source.index("window.show_all()"),
        )

    def test_overlay_has_animated_background_and_sound_controls(self):
        source = (HOST_DIR / "nvgs_alert_overlay.py").read_text(encoding="utf-8")
        self.assertIn("Gtk.DrawingArea()", source)
        self.assertIn("PixbufAnimation.new_from_file", source)
        self.assertIn("background.queue_draw()", source)
        self.assertIn('sound_button = Gtk.Button(label="MUTE SOUND")', source)
        self.assertIn("Gdk.KEY_m", source)


if __name__ == "__main__":
    unittest.main()

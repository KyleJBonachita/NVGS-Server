import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]


class HostedNetworkInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refresh = (PROJECT_DIR / "scripts/refresh-dynamic-lan.sh").read_text(
            encoding="utf-8"
        )
        cls.download = (
            PROJECT_DIR / "scripts/download-session-control.sh"
        ).read_text(encoding="utf-8")

    def test_saved_interface_is_tried_before_automatic_ethernet(self):
        configured_check = 'elif valid_interface "$configured_interface"'
        automatic_ethernet = 'detected_interface="$(first_active_ethernet || true)"'
        self.assertIn(configured_check, self.refresh)
        self.assertIn(automatic_ethernet, self.refresh)
        self.assertLess(
            self.refresh.index(configured_check),
            self.refresh.index(automatic_ethernet),
        )

    def test_active_fallback_does_not_replace_saved_preference(self):
        self.assertIn(
            'if [[ -z "$requested_interface" && -z "$address_cidr" ]]',
            self.refresh,
        )
        self.assertIn(
            'set_env_value "NVGS_LAN_INTERFACE" "$configured_interface"',
            self.refresh,
        )
        self.assertIn(
            'set_env_value "NVGS_ACTIVE_LAN_INTERFACE" "$network_interface"',
            self.refresh,
        )

    def test_download_hostname_uses_the_active_hosting_interface(self):
        self.assertIn(
            'read_env_value "NVGS_ACTIVE_LAN_INTERFACE"',
            self.download,
        )
        self.assertIn(
            'ip -4 -o address show dev "$preferred_interface"',
            self.download,
        )


if __name__ == "__main__":
    unittest.main()

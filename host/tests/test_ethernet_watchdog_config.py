import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]


class EthernetWatchdogSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.watchdog = (PROJECT_DIR / "scripts/ethernet-watchdog.sh").read_text(
            encoding="utf-8"
        )
        cls.service = (
            PROJECT_DIR / "host/systemd/nvgs-ethernet-watchdog.service"
        ).read_text(encoding="utf-8")

    def test_driver_reload_is_limited_to_verified_r8169(self):
        self.assertIn('if [[ "$driver" != "r8169" ]]', self.watchdog)
        self.assertIn("driver_has_another_live_interface", self.watchdog)
        self.assertIn("pci_identity_matches", self.watchdog)

    def test_virtual_interfaces_cannot_report_physical_recovery(self):
        self.assertIn("is_physical_ethernet_interface", self.watchdog)
        for virtual_prefix in ("docker*", "br-*", "veth*", "virbr*", "podman*"):
            self.assertIn(virtual_prefix, self.watchdog)
        self.assertIn('[[ -e "/sys/class/net/$candidate/device" ]]', self.watchdog)

    def test_stuck_adapter_has_guarded_pci_recovery(self):
        self.assertIn("recover_verified_pci_device", self.watchdog)
        self.assertIn('> "$pci_path/reset"', self.watchdog)
        self.assertIn('> "$pci_path/remove"', self.watchdog)
        self.assertIn('> "$parent_rescan"', self.watchdog)
        self.assertIn("configured_pci_vendor", self.watchdog)
        self.assertIn("configured_pci_device", self.watchdog)
        self.assertIn('[[ "$configured_driver" == "r8169" ]]', self.watchdog)
        self.assertIn('"${actual_class,,}" == 0x0200*', self.watchdog)

    def test_automatic_reload_is_rate_limited(self):
        self.assertIn(
            "NVGS_ETHERNET_RELOAD_COOLDOWN_SECONDS:-600",
            self.watchdog,
        )
        self.assertIn("NVGS_ETHERNET_MAX_DRIVER_RELOADS:-1", self.watchdog)

    def test_watchdog_does_not_reboot_or_change_global_aspm(self):
        self.assertNotIn("reboot", self.watchdog)
        self.assertNotIn("pcie_aspm", self.watchdog)
        self.assertNotIn("/etc/default/grub", self.watchdog)
        self.assertNotIn("reset_subordinate", self.watchdog)

    def test_service_uses_root_owned_installed_helper(self):
        self.assertIn(
            "ExecStart=/usr/local/libexec/nvgs-ethernet-watchdog --watch",
            self.service,
        )
        self.assertIn("Restart=always", self.service)


if __name__ == "__main__":
    unittest.main()

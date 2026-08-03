import tempfile
import unittest
from pathlib import Path

from host.server_control_gui import (
    NetworkAddress,
    build_server_catalog,
    parse_lan_addresses,
    parse_primary_interface,
    preferred_nvgs_host,
    read_env_values,
    server_urls,
)


class ServerControlNetworkTests(unittest.TestCase):
    def test_default_route_interface_is_parsed(self):
        output = "default via 192.168.1.1 dev enp3s0 proto dhcp metric 100\n"
        self.assertEqual(parse_primary_interface(output), "enp3s0")

    def test_physical_addresses_are_kept_and_virtual_addresses_are_filtered(self):
        output = """\
2: enp3s0 inet 192.168.1.20/24 brd 192.168.1.255 scope global enp3s0
3: wlp2s0 inet 192.168.1.30/24 brd 192.168.1.255 scope global wlp2s0
4: docker0 inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
5: veth123 inet 169.254.10.2/16 brd 169.254.255.255 scope global veth123
"""
        addresses = parse_lan_addresses(output, "wlp2s0")
        self.assertEqual(
            addresses,
            [
                NetworkAddress("enp3s0", "192.168.1.20", False),
                NetworkAddress("wlp2s0", "192.168.1.30", True),
            ],
        )


class ServerCatalogTests(unittest.TestCase):
    def test_catalog_contains_nvgs_and_download_server(self):
        catalog = build_server_catalog({"DOWNLOAD_SERVER_PORT": "9090"})
        self.assertEqual([server.key for server in catalog], ["nvgs", "downloads"])
        self.assertEqual(catalog[1].port, 9090)

    def test_download_urls_include_every_detected_lan_address(self):
        server = build_server_catalog({})[1]
        addresses = [
            NetworkAddress("enp3s0", "192.168.1.20", True),
            NetworkAddress("wlp2s0", "192.168.1.30", False),
        ]
        self.assertEqual(
            server_urls(server, addresses, {}),
            [
                "http://download-system.local:8080/",
                "http://192.168.1.20:8080/",
                "http://192.168.1.30:8080/",
            ],
        )

    def test_download_urls_include_the_stable_local_name(self):
        server = build_server_catalog({})[1]
        addresses = [NetworkAddress("enp3s0", "192.168.1.20", True)]
        self.assertEqual(
            server_urls(
                server,
                addresses,
                {"DOWNLOAD_SERVER_NAME": "production-downloads.local"},
            ),
            [
                "http://production-downloads.local:8080/",
                "http://192.168.1.20:8080/",
            ],
        )

    def test_download_name_is_independent_from_nvgs_name(self):
        server = build_server_catalog({})[1]
        self.assertEqual(
            server_urls(
                server,
                [],
                {"NVGS_LAN_SERVER_NAME": "ticketing-system.local"},
            ),
            ["http://download-system.local:8080/"],
        )

    def test_nvgs_prefers_configured_stable_name(self):
        addresses = [NetworkAddress("enp3s0", "192.168.1.20", True)]
        env = {"SERVER_ADDRESS": "ticketing-system.local"}
        self.assertEqual(
            preferred_nvgs_host(env, addresses),
            "ticketing-system.local",
        )

    def test_env_reader_ignores_comments_and_quotes(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            env_path = Path(temporary_dir) / ".env"
            env_path.write_text(
                '# comment\nSERVER_ADDRESS="ticketing.local"\nPORT=8080\n',
                encoding="utf-8",
            )
            self.assertEqual(
                read_env_values(env_path),
                {"SERVER_ADDRESS": "ticketing.local", "PORT": "8080"},
            )


if __name__ == "__main__":
    unittest.main()

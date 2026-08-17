import tempfile
import unittest
from pathlib import Path

from host.server_control_gui import (
    NetworkAddress,
    build_server_catalog,
    count_download_files,
    find_download_name_conflicts,
    import_download_files,
    next_available_download_path,
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
6: tun0 inet 10.8.0.2/24 brd 10.8.0.255 scope global tun0
7: wg0 inet 10.9.0.2/24 brd 10.9.0.255 scope global wg0
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
    def test_catalog_contains_nvgs_downloads_and_gerry(self):
        catalog = build_server_catalog({"DOWNLOAD_SERVER_PORT": "9090"})
        self.assertEqual([server.key for server in catalog], ["nvgs", "downloads", "gerry"])
        self.assertEqual(catalog[1].port, 9090)
        self.assertEqual(catalog[2].port, 3000)

    def test_gerry_urls_include_every_detected_lan_address(self):
        server = build_server_catalog({"GERY_SERVER_PORT": "3030"})[2]
        addresses = [
            NetworkAddress("enp3s0", "192.168.1.20", True),
            NetworkAddress("wlp2s0", "192.168.1.30", False),
        ]
        self.assertEqual(
            server_urls(server, addresses, {}),
            [
                "http://192.168.1.20:3030/",
                "http://192.168.1.30:3030/",
            ],
        )

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

    def test_nvgs_urls_include_friendly_name_and_all_lan_addresses(self):
        server = build_server_catalog({})[0]
        addresses = [
            NetworkAddress("enp3s0", "192.168.10.112", False),
            NetworkAddress("wlp2s0", "192.168.5.237", True),
        ]
        self.assertEqual(
            server_urls(
                server,
                addresses,
                {"SERVER_ADDRESS": "ticketing-system.local"},
            ),
            [
                "https://ticketing-system.local/tickets/",
                "https://192.168.10.112/tickets/",
                "https://192.168.5.237/tickets/",
            ],
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


class DownloadLibraryTests(unittest.TestCase):
    def test_imports_regular_files_and_keeps_existing_names(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source_dir = root / "source"
            downloads_dir = root / "downloads"
            source_dir.mkdir()
            downloads_dir.mkdir()
            source = source_dir / "guide.pdf"
            image = source_dir / "guide.cover.png"
            source.write_bytes(b"new guide")
            image.write_bytes(b"png")
            (downloads_dir / "guide.pdf").write_bytes(b"existing guide")

            result = import_download_files([source, image], downloads_dir)

            self.assertEqual(result.errors, ())
            self.assertEqual(
                [item.name for item in result.copied],
                ["guide (2).pdf", "guide.cover.png"],
            )
            self.assertEqual(
                (downloads_dir / "guide.pdf").read_bytes(),
                b"existing guide",
            )
            self.assertEqual(
                (downloads_dir / "guide (2).pdf").read_bytes(),
                b"new guide",
            )
            self.assertEqual(count_download_files(downloads_dir), 3)

    def test_rejects_directories_hidden_files_and_library_files(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            downloads_dir = root / "downloads"
            downloads_dir.mkdir()
            hidden = root / ".secret"
            hidden.write_text("secret", encoding="utf-8")
            existing = downloads_dir / "existing.txt"
            existing.write_text("existing", encoding="utf-8")

            result = import_download_files(
                [root, hidden, existing],
                downloads_dir,
            )

            self.assertEqual(result.copied, ())
            self.assertEqual(len(result.errors), 3)

    def test_next_available_path_adds_a_number(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            downloads_dir = Path(temporary_dir)
            (downloads_dir / "photo.png").touch()
            (downloads_dir / "photo (2).png").touch()
            self.assertEqual(
                next_available_download_path(downloads_dir, "photo.png").name,
                "photo (3).png",
            )

    def test_replace_policy_updates_the_existing_file(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source_dir = root / "source"
            downloads_dir = root / "downloads"
            source_dir.mkdir()
            downloads_dir.mkdir()
            source = source_dir / "guide.pdf"
            source.write_bytes(b"new version")
            (downloads_dir / "guide.pdf").write_bytes(b"old version")

            result = import_download_files(
                [source],
                downloads_dir,
                conflict_policy="replace",
            )

            self.assertEqual(result.errors, ())
            self.assertEqual(
                (downloads_dir / "guide.pdf").read_bytes(),
                b"new version",
            )
            self.assertFalse((downloads_dir / "guide (2).pdf").exists())

    def test_finds_existing_and_repeated_batch_names(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            downloads_dir = root / "downloads"
            downloads_dir.mkdir()
            (downloads_dir / "existing.txt").touch()

            conflicts = find_download_name_conflicts(
                [
                    root / "existing.txt",
                    root / "first" / "repeated.png",
                    root / "second" / "repeated.png",
                ],
                downloads_dir,
            )

            self.assertEqual(conflicts, ("existing.txt", "repeated.png"))


if __name__ == "__main__":
    unittest.main()

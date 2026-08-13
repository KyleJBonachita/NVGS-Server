#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import shutil
import stat
import zipfile
from pathlib import Path

PLACEHOLDERS = {
    "server_name": "__NVGS_SERVER_NAME__",
    "server_ip": "__NVGS_SERVER_IP__",
    "server_ips": "__NVGS_SERVER_IPS__",
    "ticketing_url": "__NVGS_TICKETING_URL__",
    "certificate_sha256": "__NVGS_CERTIFICATE_SHA256__",
}


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def substitute(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for key, placeholder in PLACEHOLDERS.items():
        rendered = rendered.replace(placeholder, replacements[key])
    missing = [
        placeholder
        for placeholder in PLACEHOLDERS.values()
        if placeholder in rendered
    ]
    if missing:
        raise ValueError(f"Template still contains placeholders: {missing}")
    return rendered


def write_text(path: Path, content: str, *, windows: bool = False) -> None:
    newline = "\r\n" if windows else "\n"
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    path.write_text(
        normalized.replace("\n", newline),
        encoding="utf-8",
        newline="",
    )


def add_directory_to_zip(
    archive: zipfile.ZipFile,
    directory: Path,
    archive_root: str,
) -> None:
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        archive_name = f"{archive_root}/{relative}"
        info = zipfile.ZipInfo.from_file(path, archive_name)
        if path.suffix in {".run", ".sh"}:
            info.external_attr = (
                stat.S_IFREG
                | stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IXOTH
            ) << 16
        with path.open("rb") as source:
            archive.writestr(info, source.read())


def main() -> None:
    project_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Build the distributable NVGS client setup package."
    )
    parser.add_argument("--env", type=Path, default=project_dir / ".env")
    parser.add_argument(
        "--certificate",
        type=Path,
        default=project_dir / "nvgs-local-ca.crt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_dir / "client-setup-output",
    )
    args = parser.parse_args()

    env_path = args.env.resolve()
    certificate_path = args.certificate.resolve()
    output_root = args.output.resolve()
    templates_dir = project_dir / "client_setup_templates"

    if not env_path.is_file():
        raise SystemExit(f"Missing NVGS environment file: {env_path}")
    if not certificate_path.is_file() or certificate_path.stat().st_size == 0:
        raise SystemExit(f"Missing NVGS public certificate: {certificate_path}")

    env = parse_env(env_path)
    server_ip = env.get("SERVER_BIND_IP", "").strip()
    configured_server_ips = [
        value.strip()
        for value in env.get("NVGS_LAN_ADDRESSES", "").split(",")
        if value.strip()
    ]
    server_ips = list(dict.fromkeys([server_ip, *configured_server_ips]))
    server_name = (
        env.get("NVGS_LAN_SERVER_NAME", "").strip()
        or env.get("SERVER_ADDRESS", "").strip()
    ).lower()

    for candidate_ip in server_ips:
        try:
            parsed_ip = ipaddress.ip_address(candidate_ip)
        except ValueError as error:
            raise SystemExit(
                f"NVGS LAN address {candidate_ip!r} is invalid: {error}"
            ) from error
        if parsed_ip.version != 4 or not parsed_ip.is_private:
            raise SystemExit(
                "Client setup requires private IPv4 LAN addresses."
            )
    if (
        not server_name
        or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789.-"
            for character in server_name
        )
        or server_name.startswith((".", "-"))
        or server_name.endswith((".", "-"))
        or ".." in server_name
    ):
        raise SystemExit("NVGS_LAN_SERVER_NAME is missing or invalid.")

    certificate_sha256 = hashlib.sha256(
        certificate_path.read_bytes()
    ).hexdigest()
    ticketing_url = f"https://{server_name}/tickets/"
    replacements = {
        "server_name": server_name,
        "server_ip": server_ip,
        "server_ips": ",".join(server_ips),
        "ticketing_url": ticketing_url,
        "certificate_sha256": certificate_sha256,
    }

    package_dir = output_root / "NVGS-Client-Setup"
    archive_path = output_root / "NVGS-Client-Setup.zip"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()

    windows_dir = package_dir / "Windows"
    ubuntu_dir = package_dir / "Ubuntu"
    windows_dir.mkdir(parents=True)
    ubuntu_dir.mkdir(parents=True)

    windows_cmd = (
        templates_dir / "Install NVGS on Windows.cmd"
    ).read_text(encoding="utf-8")
    windows_script = substitute(
        (templates_dir / "install-nvgs-windows.ps1").read_text(
            encoding="utf-8"
        ),
        replacements,
    )
    ubuntu_script = substitute(
        (templates_dir / "Install NVGS on Ubuntu.run").read_text(
            encoding="utf-8"
        ),
        replacements,
    )

    write_text(
        windows_dir / "Install NVGS on Windows.cmd",
        windows_cmd,
        windows=True,
    )
    write_text(
        windows_dir / "install-nvgs-windows.ps1",
        windows_script,
        windows=True,
    )
    write_text(
        ubuntu_dir / "Install NVGS on Ubuntu.run",
        ubuntu_script,
    )
    (ubuntu_dir / "Install NVGS on Ubuntu.run").chmod(0o755)
    shutil.copy2(certificate_path, windows_dir / "nvgs-local-ca.crt")
    shutil.copy2(certificate_path, ubuntu_dir / "nvgs-local-ca.crt")

    readme = f"""NVGS CLIENT SETUP

Server: {server_name}
Preferred LAN address: {server_ip}
Available LAN addresses: {", ".join(server_ips)}
Ticketing link: {ticketing_url}
Certificate SHA-256: {certificate_sha256}

WINDOWS
1. Open the Windows folder.
2. Double-click "Install NVGS on Windows.cmd".
3. Approve the Windows Administrator prompt and click Yes.

UBUNTU
1. Open the Ubuntu folder.
2. Run "Install NVGS on Ubuntu.run" as a program.
   If the file manager opens it as text, open Terminal in this folder and run:
     bash "Install NVGS on Ubuntu.run"
3. Type INSTALL and enter the Ubuntu administrator password.

The installer trusts only the public NVGS CA, tests the listed LAN addresses,
maps the friendly name to the address reachable from that client, and creates
an NVGS Ticketing desktop shortcut. It never
contains the CA private key, server secrets, or user passwords.

If the server receives a different DHCP address, rebuild this package and run
the installer again on each client. A DHCP reservation or approved internal
DNS record removes that repeated step.
"""
    write_text(package_dir / "README.txt", readme, windows=True)

    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        add_directory_to_zip(archive, package_dir, package_dir.name)

    print(f"Client setup folder: {package_dir}")
    print(f"Client setup ZIP:    {archive_path}")
    print(f"Ticketing link:      {ticketing_url}")
    print(f"Certificate SHA-256: {certificate_sha256}")
    print()
    print("Distribute only to approved client laptops.")
    print("Do not commit client-setup-output or the certificate to Git.")


if __name__ == "__main__":
    main()

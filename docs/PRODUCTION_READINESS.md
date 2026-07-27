# Production readiness

This is the honest status of the NVGS ticketing project. “Implemented” means
the code or helper exists. It does not claim that an address was approved, a
certificate was installed on somebody else's laptop, or a backup was copied
to a device that has not been supplied.

| Item | Status | What remains outside the code |
| --- | --- | --- |
| Django ticketing interface | Implemented | Pull the update on Ubuntu and complete the browser pilot. |
| Fake users and tickets | Implemented | Run the pilot-data command, then follow `docs/PILOT.md` on approved laptops. |
| LAN address/DHCP reservation | Waiting for approval | Obtain the actual address, apply it to Ubuntu, then run `configure-approved-lan.sh`. |
| HTTPS on client laptops | Tooling ready | Verify the fingerprint, install the public CA on each approved client, and test without a warning. |
| NVIDIA login | Apps Script bridge implemented | The current bridge reuses the verified Workspace email. Official corporate SSO still requires identity-administrator approval. |
| Backup restore | Tooling ready | Run `verify-backup-restore.sh` against a real backup and review the saved PASS report. |
| Encrypted second backup | Tooling ready | Attach an approved second encrypted device and run `copy-backup-encrypted.sh`. |
| Completely-offline alert | External watcher implemented | Install it on a second approved Ubuntu device and add an approved webhook. |
| Real ticket import | Intentionally waiting | Import only after the pilot is accepted and a pre-import backup is verified. |

No script invents a network address or bypasses a corporate trust/identity
approval. Those decisions belong to the people responsible for the network
and client devices.

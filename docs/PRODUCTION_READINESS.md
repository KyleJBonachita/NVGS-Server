# Production readiness

This is the honest status of the NVGS ticketing project. “Implemented” means
the code or helper exists. It does not claim that an address was approved, a
certificate was installed on somebody else's laptop, or a backup was copied
to a device that has not been supplied.

| Item | Status | What remains outside the code |
| --- | --- | --- |
| Django ticketing interface | Implemented | Includes active/resolved queue tabs, quick actions, operations metrics, workstation health, profile editing, CSV export, and bulk actions. Continue normal-user feedback before importing real records. |
| Fake users and tickets | Pilot completed | The project team reported the Agent, Tech Team, TL, and Manager workflow pilot complete. |
| LAN address/DHCP reservation | Temporary dynamic mode implemented; reservation still waiting | Startup detects the current address and rebuilds client setup. Obtain a reservation or approved DNS name to remove client remapping. |
| HTTPS on client laptops | Installer implemented; per-device verification remains | Run the current setup ZIP as Administrator and confirm its hostname, port 443, and website checks on every approved laptop. |
| NVIDIA login | Apps Script bridge implemented | The current bridge reuses the verified Workspace email. Official corporate SSO still requires identity-administrator approval. |
| Backup restore | Tooling ready | Run `verify-backup-restore.sh` against a real backup and review the saved PASS report. |
| Encrypted second backup | Tooling ready | Attach an approved second encrypted device and run `copy-backup-encrypted.sh`. |
| Completely-offline alert | External watcher implemented | Install it on a second approved Ubuntu device and add an approved webhook. |
| Power Automate/Teams ticket alerts | Compatible delivery implemented; sender configuration remains | Configure an approved webhook or SMTP relay/service account. The email subject and JSON body match the existing `GRTKT_EVENT` flow. |
| Real ticket import | Intentionally waiting | Import only after the pilot is accepted and a pre-import backup is verified. |

No script invents a network address or bypasses a corporate trust/identity
approval. Those decisions belong to the people responsible for the network
and client devices.

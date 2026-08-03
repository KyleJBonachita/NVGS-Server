# Ubuntu Ethernet recovery diagnostics

Captured: 2026-08-03T13:01:43+08:00
Interface: vethec63598

## Watchdog status
● nvgs-ethernet-watchdog.service - NVGS automatic Ethernet stability and recovery watchdog
     Loaded: loaded (/etc/systemd/system/nvgs-ethernet-watchdog.service; enabled; vendor preset: enabled)
     Active: active (running) since Mon 2026-08-03 12:44:47 PST; 16min ago
   Main PID: 405840 (bash)
      Tasks: 2 (limit: 18562)
     Memory: 1.8M
        CPU: 9.168s
     CGroup: /system.slice/nvgs-ethernet-watchdog.service
             ├─405840 bash /usr/local/libexec/nvgs-ethernet-watchdog --watch
             └─410645 sleep 15

Aug 03 12:44:47 gear-ph-02 nvgs-ethernet-watchdog[405840]: 2026-08-03T12:44:47+08:00 enp109s0: Energy Efficient Ethernet is disabled.
Aug 03 12:44:47 gear-ph-02 nvgs-ethernet-watchdog[405924]: enp109s0: Energy Efficient Ethernet is disabled.
Aug 03 12:44:47 gear-ph-02 nvgs-ethernet-watchdog[405840]: 2026-08-03T12:44:47+08:00 enp109s0: cycling the Ethernet interface.
Aug 03 12:44:47 gear-ph-02 nvgs-ethernet-watchdog[405926]: enp109s0: cycling the Ethernet interface.
Aug 03 12:45:14 gear-ph-02 nvgs-ethernet-watchdog[405840]: 2026-08-03T12:45:14+08:00 enp109s0: Energy Efficient Ethernet is disabled.
Aug 03 12:45:14 gear-ph-02 nvgs-ethernet-watchdog[405840]: 2026-08-03T12:45:14+08:00 enp109s0: cycling the Ethernet interface.
Aug 03 12:45:14 gear-ph-02 nvgs-ethernet-watchdog[406120]: enp109s0: cycling the Ethernet interface.
Aug 03 12:45:25 gear-ph-02 nvgs-ethernet-watchdog[405840]: 2026-08-03T12:45:25+08:00 enp109s0: reloading verified Realtek driver r8169 (0000:6d:00.0).
Aug 03 12:45:28 gear-ph-02 nvgs-ethernet-watchdog[405840]: 2026-08-03T12:45:28+08:00 enp109s0: Ethernet recovered automatically.
Aug 03 12:45:28 gear-ph-02 nvgs-ethernet-watchdog[406273]: enp109s0: Ethernet recovered automatically.

## Watchdog journal
sudo: 1 incorrect password attempt

## Relevant kernel journal

## Interface and EEE
sudo: a password is required
sudo: a password is required

## PCI device
The Ethernet PCI device path is unavailable.

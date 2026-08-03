# Ubuntu Ethernet recovery diagnostics

Captured: 2026-08-03T13:02:07+08:00
Interface: vethec63598

## Watchdog status
● nvgs-ethernet-watchdog.service - NVGS automatic Ethernet stability and recovery watchdog
     Loaded: loaded (/etc/systemd/system/nvgs-ethernet-watchdog.service; enabled; vendor preset: enabled)
     Active: active (running) since Mon 2026-08-03 12:44:47 PST; 17min ago
   Main PID: 405840 (bash)
      Tasks: 2 (limit: 18562)
     Memory: 1.9M
        CPU: 9.388s
     CGroup: /system.slice/nvgs-ethernet-watchdog.service
             ├─405840 bash /usr/local/libexec/nvgs-ethernet-watchdog --watch
             └─410819 sleep 15

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
Aug 03 12:44:33 gear-ph-02 systemd[1]: Started NVGS automatic Ethernet stability and recovery watchdog.
Aug 03 12:44:33 gear-ph-02 nvgs-ethernet-watchdog[405418]: 2026-08-03T12:44:33+08:00 Automatic Ethernet recovery started.
Aug 03 12:44:33 gear-ph-02 nvgs-ethernet-watchdog[405445]: Automatic Ethernet recovery started.
Aug 03 12:44:33 gear-ph-02 nvgs-ethernet-watchdog[405418]: 2026-08-03T12:44:33+08:00 enp109s0: Energy Efficient Ethernet is disabled.
Aug 03 12:44:33 gear-ph-02 nvgs-ethernet-watchdog[405418]: 2026-08-03T12:44:33+08:00 enp109s0: Energy Efficient Ethernet is disabled.
Aug 03 12:44:33 gear-ph-02 nvgs-ethernet-watchdog[405516]: enp109s0: Energy Efficient Ethernet is disabled.
Aug 03 12:44:33 gear-ph-02 nvgs-ethernet-watchdog[405418]: 2026-08-03T12:44:33+08:00 enp109s0: cycling the Ethernet interface.
Aug 03 12:44:33 gear-ph-02 nvgs-ethernet-watchdog[405518]: enp109s0: cycling the Ethernet interface.
Aug 03 12:44:47 gear-ph-02 systemd[1]: Stopping NVGS automatic Ethernet stability and recovery watchdog...
Aug 03 12:44:47 gear-ph-02 systemd[1]: nvgs-ethernet-watchdog.service: Deactivated successfully.
Aug 03 12:44:47 gear-ph-02 systemd[1]: Stopped NVGS automatic Ethernet stability and recovery watchdog.
Aug 03 12:44:47 gear-ph-02 systemd[1]: Started NVGS automatic Ethernet stability and recovery watchdog.
Aug 03 12:44:47 gear-ph-02 nvgs-ethernet-watchdog[405840]: 2026-08-03T12:44:47+08:00 Automatic Ethernet recovery started.
Aug 03 12:44:47 gear-ph-02 nvgs-ethernet-watchdog[405855]: Automatic Ethernet recovery started.
Aug 03 12:44:47 gear-ph-02 nvgs-ethernet-watchdog[405840]: 2026-08-03T12:44:47+08:00 enp109s0: Energy Efficient Ethernet is disabled.
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

## Relevant kernel journal
Jul 30 15:23:43 gear-ph-02 kernel: ACPI: FACP 0x0000000045AD3000 000114 (v06 ACRSYS ACRPRDCT 00000002 1025 00040000)
Jul 30 15:23:43 gear-ph-02 kernel: ACPI: SSDT 0x0000000045AF1000 005D34 (v02 ACRSYS ACRPRDCT 00003000 1025 00040000)
Jul 30 15:23:43 gear-ph-02 kernel: ACPI: Reserving FACP table memory at [mem 0x45ad3000-0x45ad3113]
Jul 30 15:23:43 gear-ph-02 kernel: ACPI: Reserving SSDT table memory at [mem 0x45af1000-0x45af6d33]
Jul 30 15:23:43 gear-ph-02 kernel: ACPI: Reserving SSDT table memory at [mem 0x45aea000-0x45aed385]
Jul 30 15:23:43 gear-ph-02 kernel: NET: Registered PF_NETLINK/PF_ROUTE protocol family
Jul 30 15:23:43 gear-ph-02 kernel: audit: initializing netlink subsys (disabled)
Jul 30 15:23:43 gear-ph-02 kernel: acpi PNP0A08:00: _OSC: OS now controls [PCIeHotplug SHPCHotplug PME AER PCIeCapability LTR DPC]
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:01.0: [8086:a70d] type 01 class 0x060400 PCIe Root Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:01.0: PME# supported from D0 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:02.0: [8086:a788] type 00 class 0x030000 PCIe Root Complex Integrated Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:0e.0: [8086:a77f] type 00 class 0x010400 PCIe Root Complex Integrated Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:14.0: PME# supported from D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:16.0: PME# supported from D3hot
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:1a.0: [8086:7a48] type 01 class 0x060400 PCIe Root Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:1a.0: PME# supported from D0 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:1c.0: [8086:7a3c] type 01 class 0x060400 PCIe Root Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:1c.0: PME# supported from D0 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:1c.6: [8086:7a3e] type 01 class 0x060400 PCIe Root Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:1c.6: PME# supported from D0 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:1d.0: [8086:7a31] type 01 class 0x060400 PCIe Root Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:1d.0: PME# supported from D0 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:00:1f.3: PME# supported from D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:01:00.0: [10de:2860] type 00 class 0x030000 PCIe Legacy Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:01:00.0: PME# supported from D0 D3hot
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:01:00.1: [10de:22bd] type 00 class 0x040300 PCIe Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:02:00.0: [8086:1136] type 01 class 0x060400 PCIe Switch Upstream Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:02:00.0: PME# supported from D0 D1 D2 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:03:00.0: [8086:1136] type 01 class 0x060400 PCIe Switch Downstream Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:03:00.0: PME# supported from D0 D1 D2 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:03:01.0: [8086:1136] type 01 class 0x060400 PCIe Switch Downstream Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:03:01.0: PME# supported from D0 D1 D2 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:03:02.0: [8086:1136] type 01 class 0x060400 PCIe Switch Downstream Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:03:02.0: PME# supported from D0 D1 D2 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:03:03.0: [8086:1136] type 01 class 0x060400 PCIe Switch Downstream Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:03:03.0: PME# supported from D0 D1 D2 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:04:00.0: [8086:1137] type 00 class 0x0c0340 PCIe Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:04:00.0: PME# supported from D0 D1 D2 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:38:00.0: [8086:1138] type 00 class 0x0c0330 PCIe Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:38:00.0: PME# supported from D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:6c:00.0: [10ec:522a] type 00 class 0xff0000 PCIe Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:6c:00.0: PME# supported from D1 D2 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:6d:00.0: [10ec:3000] type 00 class 0x020000 PCIe Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:6d:00.0: PME# supported from D0 D1 D2 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:6e:00.0: [8086:272b] type 00 class 0x028000 PCIe Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:6e:00.0: PME# supported from D0 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 0000:01:00.1: extending delay after power-on from D3hot to 20 msec
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:00:01.0: PME: Signaling with IRQ 122
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:00:1a.0: PME: Signaling with IRQ 123
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:00:1a.0: AER: enabled with IRQ 123
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:00:1a.0: pciehp: Slot #24 AttnBtn- PwrCtrl- MRL- AttnInd- PwrInd- HotPlug+ Surprise+ Interlock- NoCompl+ IbPresDis- LLActRep+
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:00:1c.0: PME: Signaling with IRQ 124
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:00:1c.0: AER: enabled with IRQ 124
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:00:1c.6: PME: Signaling with IRQ 125
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:00:1d.0: PME: Signaling with IRQ 126
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:00:1d.0: AER: enabled with IRQ 126
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:03:01.0: pciehp: Slot #1 AttnBtn- PwrCtrl- MRL- AttnInd- PwrInd- HotPlug+ Surprise+ Interlock- NoCompl+ IbPresDis- LLActRep+
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 0000:03:03.0: pciehp: Slot #3 AttnBtn- PwrCtrl- MRL- AttnInd- PwrInd- HotPlug+ Surprise+ Interlock- NoCompl+ IbPresDis- LLActRep+
Jul 30 15:23:43 gear-ph-02 kernel: Loaded X.509 cert 'Build time autogenerated kernel key: 5670835b8aa8ad3921c34a2b3c2cc02d04b05894'
Jul 30 15:23:43 gear-ph-02 kernel: Loaded X.509 cert 'Canonical Ltd. Secure Boot Signing (ESM 2018): 365188c1d374d6b07c3c8f240f8ef722433d6a8b'
Jul 30 15:23:43 gear-ph-02 kernel: Loaded X.509 cert 'Canonical Ltd. Secure Boot Signing (2021 v2): 4cf046892d6fd3c9a5b03f98d845f90851dc6a8c'
Jul 30 15:23:43 gear-ph-02 kernel: Loaded X.509 cert 'Build time autogenerated kernel key: 5670835b8aa8ad3921c34a2b3c2cc02d04b05894'
Jul 30 15:23:43 gear-ph-02 kernel: pci 10000:e0:01.1: [8086:a72d] type 01 class 0x060400 PCIe Root Port
Jul 30 15:23:43 gear-ph-02 kernel: pci 10000:e0:01.1: PME# supported from D0 D3hot D3cold
Jul 30 15:23:43 gear-ph-02 kernel: pci 10000:e1:00.0: [1c5c:1959] type 00 class 0x010802 PCIe Endpoint
Jul 30 15:23:43 gear-ph-02 kernel: r8169 0000:6d:00.0: enabling device (0000 -> 0003)
Jul 30 15:23:43 gear-ph-02 kernel: r8169 0000:6d:00.0 eth0: RTL8125B, 74:d4:dd:59:4e:18, XID 641, IRQ 183
Jul 30 15:23:43 gear-ph-02 kernel: r8169 0000:6d:00.0 eth0: jumbo features [frames: 9194 bytes, tx checksumming: ko]
Jul 30 15:23:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: renamed from eth0
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 10000:e0:01.1: can't derive routing for PCI INT B
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 10000:e0:01.1: PCI INT B: no GSI
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 10000:e0:01.1: PME: Signaling with IRQ 185
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 10000:e0:01.1: AER: enabled with IRQ 185
Jul 30 15:23:43 gear-ph-02 kernel: pcieport 10000:e0:01.1: can't derive routing for PCI INT A
Jul 30 15:23:43 gear-ph-02 kernel: Consider using thermal netlink events interface
Jul 30 15:23:44 gear-ph-02 kernel: Bluetooth: BNEP (Ethernet Emulation) ver 1.3
Jul 30 15:23:44 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Jul 30 15:23:44 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Jul 30 15:23:47 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Up - 1Gbps/Full - flow control off
Jul 30 15:23:50 gear-ph-02 kernel: Initializing XFRM netlink socket
Jul 31 07:43:19 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Jul 31 08:16:18 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Up - 1Gbps/Full - flow control off
Jul 31 09:20:10 gear-ph-02 kernel: RDX: 00000000206d3124 RSI: 0000000000000000 RDI: 0000000000000000
Jul 31 09:20:22 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=user.slice,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Web Content,pid=23405,uid=1000
Jul 31 09:20:22 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=user.slice,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Privileged Cont,pid=22764,uid=1000
Jul 31 09:20:22 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=systemd-journald.service,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Isolated Web Co,pid=22987,uid=1000
Jul 31 09:20:22 gear-ph-02 kernel: RAX: fffffffffffffb00 RBX: 0000611ed3033d40 RCX: 0000000000000780
Jul 31 09:20:22 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=user.slice,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=WebExtensions,pid=22886,uid=1000
Jul 31 09:20:22 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=systemd-journald.service,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Isolated Web Co,pid=23315,uid=1000
Jul 31 09:20:22 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=init.scope,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Isolated Web Co,pid=23235,uid=1000
Jul 31 09:20:22 gear-ph-02 kernel: RSP: 002b:00007ebae9ff8d38 EFLAGS: 00010212
Jul 31 09:20:25 gear-ph-02 kernel: RSP: 002b:00007c2b3c7d31b8 EFLAGS: 00010202
Jul 31 09:20:25 gear-ph-02 kernel: RBP: 00007c2b3c7d3250 R08: 0000000000000000 R09: 0000000000000000
Jul 31 09:20:29 gear-ph-02 kernel: Code: 83 e8 04 7f d3 f3 c3 0f 1f 84 00 00 00 00 00 90 48 8d 04 49 4c 8d 0c 76 0f 28 02 0f 28 0c 0a 0f 28 14 4a 0f 28 1c 02 0f 29 07 <0f> 29 0c 37 0f 29 14 77 42 0f 29 1c 0f 48 8d 14 8a 48 8d 3c b7 41
Jul 31 09:20:35 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=init.scope,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=WebExtensions,pid=189341,uid=1000
Jul 31 09:20:47 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=containerd.service,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=WebExtensions,pid=189414,uid=1000
Jul 31 09:22:12 gear-ph-02 kernel: Code: 3c b7 41 83 e8 04 7f d3 f3 c3 0f 1f 84 00 00 00 00 00 90 48 8d 04 49 4c 8d 0c 76 0f 28 02 0f 28 0c 0a 0f 28 14 4a 0f 28 1c 02 <0f> 29 07 0f 29 0c 37 0f 29 14 77 42 0f 29 1c 0f 48 8d 14 8a 48 8d
Jul 31 09:22:16 gear-ph-02 kernel: RIP: 0033:0x7708c56210d3
Jul 31 09:22:16 gear-ph-02 kernel: Code: 1f 84 00 00 00 00 00 90 48 8d 04 49 4c 8d 0c 76 0f 28 02 0f 28 0c 0a 0f 28 14 4a 0f 28 1c 02 0f 29 07 0f 29 0c 37 0f 29 14 77 <42> 0f 29 1c 0f 48 8d 14 8a 48 8d 3c b7 41 83 e8 04 7f d3 f3 c3 0f
Jul 31 09:22:16 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=user.slice,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=WebExtensions,pid=189507,uid=1000
Jul 31 09:22:16 gear-ph-02 kernel: Code: 83 e8 04 7f d3 f3 c3 0f 1f 84 00 00 00 00 00 90 48 8d 04 49 4c 8d 0c 76 0f 28 02 0f 28 0c 0a 0f 28 14 4a 0f 28 1c 02 0f 29 07 <0f> 29 0c 37 0f 29 14 77 42 0f 29 1c 0f 48 8d 14 8a 48 8d 3c b7 41
Jul 31 09:22:17 gear-ph-02 kernel: RDX: 0000745a03e308e0 RSI: 0000000000000003 RDI: 6c732e2d3d454349
Jul 31 09:22:18 gear-ph-02 kernel: RSP: 002b:00007a18dbf5fd38 EFLAGS: 00010246
Jul 31 09:22:19 gear-ph-02 kernel: RBP: 00007b248c52d380 R08: 0000000000000000 R09: 0000000003e308e7
Jul 31 09:22:23 gear-ph-02 kernel: RIP: 0033:0x79e1d0a210d3
Jul 31 09:22:27 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=init.scope,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=WebExtensions,pid=195386,uid=1000
Jul 31 09:22:33 gear-ph-02 kernel: R13: 00000000000007c0 R14: 000070ac4252d360 R15: 0000000000000000
Jul 31 09:22:37 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=docker.service,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=WebExtensions,pid=195419,uid=1000
Jul 31 09:32:36 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=user.slice,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=WebExtensions,pid=195565,uid=1000
Jul 31 09:32:36 gear-ph-02 kernel: Code: 83 e8 04 7f d3 f3 c3 0f 1f 84 00 00 00 00 00 90 48 8d 04 49 4c 8d 0c 76 0f 28 02 0f 28 0c 0a 0f 28 14 4a 0f 28 1c 02 0f 29 07 <0f> 29 0c 37 0f 29 14 77 42 0f 29 1c 0f 48 8d 14 8a 48 8d 3c b7 41
Jul 31 09:32:39 gear-ph-02 kernel: RIP: 0033:0x7a6d0192d3b7
Jul 31 09:32:39 gear-ph-02 kernel: Code: 08 8b 07 be ff ff ff ff 83 c1 0a 89 c2 d3 e6 d3 ea f7 d6 83 e9 12 21 f0 44 8b 4f 0c 80 fa ff 74 1a 48 8b 77 18 00 76 ff fe ce <88> 36 48 ff c6 41 ff c9 7d f6 88 56 ff 48 89 77 18 41 ff c1 44 89
Jul 31 09:32:42 gear-ph-02 kernel: RIP: 0033:0x78dfc00210d3
Jul 31 09:32:42 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=user.slice,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Web Content,pid=204444,uid=1000
Jul 31 09:32:46 gear-ph-02 kernel: RIP: 0033:0x77e108d3a247
Jul 31 09:32:46 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=user.slice,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Web Content,pid=204475,uid=1000
Jul 31 09:33:26 gear-ph-02 kernel: RDX: 000055b436b11240 RSI: 000000000000d311 RDI: 0000000000000432
Jul 31 09:33:26 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=containerd.service,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Web Content,pid=204556,uid=1000
Jul 31 09:33:26 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=docker.service,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Web Content,pid=204544,uid=1000
Jul 31 09:33:26 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=accounts-daemon.service,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=Web Content,pid=204550,uid=1000
Jul 31 09:33:26 gear-ph-02 kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=user.slice,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/snap.firefox.firefox-fbdb6139-4d31-451e-b845-96e8c89993e5.scope,task=WebExtensions,pid=204493,uid=1000
Jul 31 14:49:00 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0: Unable to change power state from D3hot to D0, device inaccessible
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:29 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:29 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:55:30 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: r8169_apply_firmware failed: -110
Jul 31 14:55:31 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: phy_poll_reset failed: -110
Jul 31 14:55:31 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Jul 31 14:56:22 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_chipcmd_cond == 1 (loop: 100, delay: 100).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0: Unable to change power state from D3cold to D0, device inaccessible
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:52 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 14:56:53 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: r8169_apply_firmware failed: -110
Jul 31 14:56:54 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: phy_poll_reset failed: -110
Jul 31 14:56:54 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Jul 31 14:57:18 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_chipcmd_cond == 1 (loop: 100, delay: 100).
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0: Unable to change power state from D3cold to D0, device inaccessible
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:23 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:23 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Jul 31 16:59:24 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: r8169_apply_firmware failed: -110
Jul 31 16:59:24 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: phy_poll_reset failed: -110
Jul 31 16:59:25 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Jul 31 16:59:47 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_chipcmd_cond == 1 (loop: 100, delay: 100).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0: Unable to change power state from D3cold to D0, device inaccessible
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:58 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:17:59 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: r8169_apply_firmware failed: -110
Aug 01 00:18:00 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: phy_poll_reset failed: -110
Aug 01 00:18:00 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Aug 01 00:18:00 gear-ph-02 kernel: workqueue: rtl_task [r8169] hogged CPU for >10000us 4 times, consider switching to WQ_UNBOUND
Aug 01 00:18:53 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_chipcmd_cond == 1 (loop: 100, delay: 100).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0: Unable to change power state from D3cold to D0, device inaccessible
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 01 00:19:18 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: r8169_apply_firmware failed: -110
Aug 01 00:19:19 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: phy_poll_reset failed: -110
Aug 01 00:19:19 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Aug 01 00:19:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_chipcmd_cond == 1 (loop: 100, delay: 100).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0: Unable to change power state from D3cold to D0, device inaccessible
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:43 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 06:35:44 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: r8169_apply_firmware failed: -110
Aug 03 06:35:45 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: phy_poll_reset failed: -110
Aug 03 06:35:45 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Aug 03 08:43:43 gear-ph-02 kernel: br-84ae191758d6: port 2(veth8cd3ef1) entered blocking state
Aug 03 08:43:43 gear-ph-02 kernel: br-84ae191758d6: port 2(veth8cd3ef1) entered disabled state
Aug 03 08:43:43 gear-ph-02 kernel: veth8cd3ef1: entered allmulticast mode
Aug 03 08:43:43 gear-ph-02 kernel: veth8cd3ef1: entered promiscuous mode
Aug 03 08:43:43 gear-ph-02 kernel: eth0: renamed from vethd380e59
Aug 03 08:43:43 gear-ph-02 kernel: br-84ae191758d6: port 2(veth8cd3ef1) entered blocking state
Aug 03 08:43:43 gear-ph-02 kernel: br-84ae191758d6: port 2(veth8cd3ef1) entered forwarding state
Aug 03 08:45:10 gear-ph-02 kernel: br-84ae191758d6: port 2(veth8cd3ef1) entered disabled state
Aug 03 08:45:10 gear-ph-02 kernel: vethd380e59: renamed from eth0
Aug 03 08:45:10 gear-ph-02 kernel: br-84ae191758d6: port 2(veth8cd3ef1) entered disabled state
Aug 03 08:45:10 gear-ph-02 kernel: veth8cd3ef1 (unregistering): left allmulticast mode
Aug 03 08:45:10 gear-ph-02 kernel: veth8cd3ef1 (unregistering): left promiscuous mode
Aug 03 08:45:10 gear-ph-02 kernel: br-84ae191758d6: port 2(veth8cd3ef1) entered disabled state
Aug 03 09:00:01 gear-ph-02 kernel: br-84ae191758d6: port 3(veth46a0d31) entered blocking state
Aug 03 09:00:01 gear-ph-02 kernel: br-84ae191758d6: port 3(veth46a0d31) entered disabled state
Aug 03 09:00:01 gear-ph-02 kernel: veth46a0d31: entered allmulticast mode
Aug 03 09:00:01 gear-ph-02 kernel: veth46a0d31: entered promiscuous mode
Aug 03 09:00:01 gear-ph-02 kernel: br-84ae191758d6: port 3(veth46a0d31) entered blocking state
Aug 03 09:00:01 gear-ph-02 kernel: br-84ae191758d6: port 3(veth46a0d31) entered forwarding state
Aug 03 09:00:31 gear-ph-02 kernel: br-84ae191758d6: port 3(veth46a0d31) entered disabled state
Aug 03 09:00:31 gear-ph-02 kernel: br-84ae191758d6: port 3(veth46a0d31) entered disabled state
Aug 03 09:00:31 gear-ph-02 kernel: veth46a0d31 (unregistering): left allmulticast mode
Aug 03 09:00:31 gear-ph-02 kernel: veth46a0d31 (unregistering): left promiscuous mode
Aug 03 09:00:31 gear-ph-02 kernel: br-84ae191758d6: port 3(veth46a0d31) entered disabled state
Aug 03 12:44:33 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:33 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:33 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:33 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:33 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_chipcmd_cond == 1 (loop: 100, delay: 100).
Aug 03 12:44:34 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:34 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Aug 03 12:44:34 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:34 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:34 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:34 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:36 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: r8169_apply_firmware failed: -110
Aug 03 12:44:36 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: phy_poll_reset failed: -110
Aug 03 12:44:36 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Aug 03 12:44:47 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:47 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:47 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:47 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:47 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_chipcmd_cond == 1 (loop: 100, delay: 100).
Aug 03 12:44:48 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:48 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Aug 03 12:44:48 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:48 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:48 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:48 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:44:50 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: r8169_apply_firmware failed: -110
Aug 03 12:44:51 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: phy_poll_reset failed: -110
Aug 03 12:44:51 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Aug 03 12:44:51 gear-ph-02 kernel: workqueue: rtl_task [r8169] hogged CPU for >10000us 8 times, consider switching to WQ_UNBOUND
Aug 03 12:45:14 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:45:14 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:45:14 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_chipcmd_cond == 1 (loop: 100, delay: 100).
Aug 03 12:45:15 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:45:15 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: attached PHY driver (mii_bus:phy_addr=r8169-0-6d00:00, irq=MAC)
Aug 03 12:45:15 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:45:15 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:45:15 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:45:15 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:45:15 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:45:15 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_ocp_gphy_cond == 1 (loop: 10, delay: 25).
Aug 03 12:45:16 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: r8169_apply_firmware failed: -110
Aug 03 12:45:17 gear-ph-02 kernel: RTL8226B_RTL8221B 2.5Gbps PHY r8169-0-6d00:00: phy_poll_reset failed: -110
Aug 03 12:45:17 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: Link is Down
Aug 03 12:45:25 gear-ph-02 kernel: r8169 0000:6d:00.0 enp109s0: rtl_chipcmd_cond == 1 (loop: 100, delay: 100).
Aug 03 12:45:28 gear-ph-02 kernel: r8169 0000:6d:00.0: Unable to change power state from D3cold to D0, device inaccessible
Aug 03 12:45:28 gear-ph-02 kernel: r8169 0000:6d:00.0: Mem-Wr-Inval unavailable
Aug 03 12:45:28 gear-ph-02 kernel: r8169 0000:6d:00.0: error -EIO: PCI read failed
Aug 03 12:45:28 gear-ph-02 kernel: r8169: probe of 0000:6d:00.0 failed with error -5

## Interface and EEE
Settings for vethec63598:
	Supported ports: [  ]
	Supported link modes:   Not reported
	Supported pause frame use: No
	Supports auto-negotiation: No
	Supported FEC modes: Not reported
	Advertised link modes:  Not reported
	Advertised pause frame use: No
	Advertised auto-negotiation: No
	Advertised FEC modes: Not reported
	Speed: 10000Mb/s
	Duplex: Full
	Auto-negotiation: off
	Port: Twisted Pair
	PHYAD: 0
	Transceiver: internal
	MDI-X: Unknown
	Link detected: yes
netlink error: Operation not supported

## PCI device
The Ethernet PCI device path is unavailable.

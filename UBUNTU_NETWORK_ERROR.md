NVGS SERVER HUB - NETWORK RECOVERY

Trying Ethernet before using Wi-Fi...
- enp109s0 has no Ethernet carrier; check the cable, modem, or dock.
Ethernet could not be restored; Wi-Fi was left connected as a fallback.

Network device diagnostics:
lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 
enp109s0         DOWN           74:d4:dd:59:4e:18 <NO-CARRIER,BROADCAST,MULTICAST,UP> 
wlp110s0f0       UP             6c:f6:da:dd:60:a8 <BROADCAST,MULTICAST,UP,LOWER_UP> 
gpd0             DOWN           <POINTOPOINT,MULTICAST,NOARP> 
br-001c812964da  DOWN           0e:6e:b0:d5:d0:92 <NO-CARRIER,BROADCAST,MULTICAST,UP> 
docker0          DOWN           52:a2:9d:93:af:a1 <NO-CARRIER,BROADCAST,MULTICAST,UP> 
br-84ae191758d6  DOWN           66:0a:69:63:3b:df <NO-CARRIER,BROADCAST,MULTICAST,UP> 
br-389d989b5109  DOWN           f2:cd:35:d2:ff:b3 <NO-CARRIER,BROADCAST,MULTICAST,UP> 
default via 192.168.5.1 dev wlp110s0f0 proto dhcp metric 600 
169.254.0.0/16 dev wlp110s0f0 scope link metric 1000 
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown 
172.18.0.0/16 dev br-389d989b5109 proto kernel scope link src 172.18.0.1 linkdown 
172.20.0.0/16 dev br-84ae191758d6 proto kernel scope link src 172.20.0.1 linkdown 
172.21.0.0/16 dev br-001c812964da proto kernel scope link src 172.21.0.1 linkdown 
192.168.5.0/24 dev wlp110s0f0 proto kernel scope link src 192.168.5.237 metric 600 
DEVICE              TYPE      STATE                   CONNECTION      
wlp110s0f0          wifi      connected               WEW             
br-001c812964da     bridge    connected (externally)  br-001c812964da 
br-389d989b5109     bridge    connected (externally)  br-389d989b5109 
br-84ae191758d6     bridge    connected (externally)  br-84ae191758d6 
docker0             bridge    connected (externally)  docker0         
88:2F:92:D9:72:47   bt        disconnected            --              
p2p-dev-wlp110s0f0  wifi-p2p  disconnected            --              
enp109s0            ethernet  unavailable             --              
lo                  loopback  unmanaged               --              
gpd0                tun       unmanaged               --              
0000:6d:00.0 Ethernet controller [0200]: Realtek Semiconductor Co., Ltd. Killer E3000 2.5GbE Controller [10ec:3000] (rev ff)
	Kernel driver in use: r8169
	Kernel modules: r8169
0000:6e:00.0 Network controller [0280]: Intel Corporation Device [8086:272b] (rev 1a)
	Subsystem: Rivet Networks Device [1a56:1774]
	Kernel driver in use: iwlwifi
	Kernel modules: iwlwifi

If the Ethernet device is absent above, this is probably a driver,
kernel, firmware, dock/adapter, or hardware issue. Server Hub will not
guess and reload an unknown kernel driver automatically.
Useful follow-up command:
  sudo journalctl -k -b --no-pager | grep -Ei 'ethernet|network|link|firmware|r816|e1000|igc|tg3'

Automatic recovery could not restore Ethernet. Wi-Fi was not disabled.
Press Enter to close.

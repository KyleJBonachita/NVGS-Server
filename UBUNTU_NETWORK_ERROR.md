(base) gear-ph-02@gear-ph-02:~/Documents/Codes/NVGS-Server$ ip -4 -br address
lo               UNKNOWN        127.0.0.1/8 
enp109s0         UP             192.168.10.112/24 
br-001c812964da  UP             172.21.0.1/16 
br-389d989b5109  UP             172.18.0.1/16 
br-84ae191758d6  UP             172.20.0.1/16 
docker0          DOWN           172.17.0.1/16 
(base) gear-ph-02@gear-ph-02:~/Documents/Codes/NVGS-Server$ ip -4 route
default via 192.168.10.1 dev enp109s0 proto dhcp metric 100 
169.254.0.0/16 dev enp109s0 scope link metric 1000 
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown 
172.18.0.0/16 dev br-389d989b5109 proto kernel scope link src 172.18.0.1 
172.20.0.0/16 dev br-84ae191758d6 proto kernel scope link src 172.20.0.1 
172.21.0.0/16 dev br-001c812964da proto kernel scope link src 172.21.0.1 
192.168.10.0/24 dev enp109s0 proto kernel scope link src 192.168.10.112 metric 100 
(base) gear-ph-02@gear-ph-02:~/Documents/Codes/NVGS-Server$ sudo ufw status verbose
[sudo] password for gear-ph-02: 
Status: inactive
(base) gear-ph-02@gear-ph-02:~/Documents/Codes/NVGS-Server$ sudo ss -lntp | grep -E ':(443|8080)\b'
LISTEN 0      4096   192.168.10.112:443        0.0.0.0:*    users:(("docker-proxy",pid=7508,fd=8))   
LISTEN 0      4096          0.0.0.0:8080       0.0.0.0:*    users:(("docker-proxy",pid=6657,fd=8))   
(base) gear-ph-02@gear-ph-02:~/Documents/Codes/NVGS-Server$ 


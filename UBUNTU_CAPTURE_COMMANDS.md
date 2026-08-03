# Capture the failed Ethernet recovery

On the Ubuntu NVGS laptop, run:

```bash
cd ~/NVGS-Server
./scripts/capture-ethernet-diagnostics.sh
git add UBUNTU_NETWORK_ERROR.md
git commit -m "Update Ethernet watchdog error"
git push origin main
```

Run the capture while Ethernet is broken and before restarting Ubuntu. After
the push succeeds, return to the Codex chat on Windows and say **pushed**.

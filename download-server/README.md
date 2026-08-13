# DownloadServer

DownloadServer is a private, dependency-free file portal for devices connected
to the same Wi-Fi or local network.

## Start it from the Ubuntu NVGS host

1. Open **NVGS Server Hub** from Ubuntu Applications.
2. Drag files into **Download Library** or click **Choose files**. The Hub
   copies them into `download-server/downloads`.
3. Choose **Download Server** and keep its control terminal open.
4. Open or share `http://download-system.local:8080/`. The Hub and terminal
   also show direct Ethernet or Wi-Fi links as fallbacks.

The container binds to all active IPv4 interfaces on port `8080` by default.
Change `DOWNLOAD_SERVER_PORT` in the repository `.env` if that port is already
used. Change `DOWNLOAD_SERVER_NAME` only if a different `.local` name is
required. The name is published through the Ubuntu host's existing Avahi
service and is independent from NVGS's `ticketing-system.local` name, so it adds
negligible overhead. Download content is excluded from Git.

The Server Hub is the only upload surface. Network users can download files but
cannot upload, replace, or delete them. An existing filename is never
overwritten; the Hub adds a number such as `guide (2).pdf`. Files appear on the
download page immediately without restarting the server.

The Windows launcher below remains useful for standalone testing.

## Start it on Windows

1. Put the files you want to share inside the `downloads` folder. Subfolders are
   supported.
2. Double-click `Start Download Server.cmd`.
3. Keep the server window open.
4. Share the **Wi-Fi / LAN** address shown in that window with people on the
   same network.

The address normally looks like `http://192.168.1.25:8080`.

Windows may ask whether Node.js can communicate through the firewall. Allow it
on **Private networks** only. Do not select Public networks unless you understand
the security impact.

## Pictures and cover images

Image files (`JPG`, `PNG`, `WebP`, `GIF`, and similar) show their own preview.

To give another file a custom picture, put a cover image next to it and use this
naming pattern:

```text
product-catalog.pdf
product-catalog.cover.jpg
```

The more explicit `product-catalog.pdf.cover.jpg` style also works.

The cover image is shown on the page but is hidden from the downloadable file
list. PNG, WebP, GIF, AVIF, JPG, and JPEG covers are supported.

## Customize the page

Edit `config.json` to change the site name, headline, and description. Restart
the server after editing it.

## Stop it

Focus the server window and press `Ctrl+C`, or close the window.

## Production notes

- Anyone who can reach this computer on the local network can download the
  listed files. Do not place confidential material in `downloads`.
- Keep the host computer awake while people are downloading.
- Use a trusted, password-protected Wi-Fi network.
- Wi-Fi clients can use the server's Ethernet address when the modem/router
  bridges both onto the same LAN and guest/client isolation is disabled.
- Do not configure router port forwarding for this server.
- For access over the public internet, add authentication and HTTPS or use a
  managed file-delivery service.

## Optional settings

The default port is `8080`. To use a different port from PowerShell:

```powershell
$env:PORT = "9090"
node server.js
```

The server requires Node.js 20 or newer and has no third-party dependencies.

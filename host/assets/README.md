# Optional full-screen alert media

The alert overlay works without media files: it draws a lightweight animated
red warning background and loops Ubuntu's standard warning sound.

To customize it, place one GIF and/or one supported audio file in this
directory on the Ubuntu server. These names are recommended:

- `nvgs-alert-background.gif` — a looping animated GIF. Use the native display
  resolution (for example, 1920x1080); the overlay scales and crops it to fill
  the screen.
- `nvgs-alert-sound.oga`, `nvgs-alert-sound.ogg`, `nvgs-alert-sound.wav`, or
  `nvgs-alert-sound.mp3` — audio that restarts for as long as the alert remains
  open. The visible **Mute sound** button stops it immediately.

When a custom GIF is found, it completely replaces the built-in red animated
background: there is no red tint, stripe, or ring effect over the GIF. If the
recommended filename is absent, the overlay automatically uses the first GIF
and first supported audio file in this directory (alphabetically).

Custom OGG playback first uses `canberra-gtk-play`, then automatically tries
other installed Ubuntu players if the first player rejects the file. A failed
player is reported in the NVGS control terminal, and the on-screen sound button
offers a retry if every installed player fails.

These machine-specific media files are ignored by Git so a normal `git pull`
will not overwrite them. The paths can instead be supplied with
`NVGS_ALERT_BACKGROUND_GIF` and `NVGS_ALERT_SOUND_FILE`.

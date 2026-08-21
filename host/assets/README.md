# Optional full-screen alert media

The alert overlay works without media files: it draws a lightweight animated
red warning background and loops Ubuntu's standard warning sound.

To customize it, place either or both of these files in this directory on the
Ubuntu server:

- `nvgs-alert-background.gif` — a looping animated GIF. Use the native display
  resolution (for example, 1920x1080); the overlay scales and crops it to fill
  the screen.
- `nvgs-alert-sound.oga`, `nvgs-alert-sound.ogg`, `nvgs-alert-sound.wav`, or
  `nvgs-alert-sound.mp3` — audio that restarts for as long as the alert remains
  open. The visible **Mute sound** button stops it immediately.

These machine-specific media files are ignored by Git so a normal `git pull`
will not overwrite them. The paths can instead be supplied with
`NVGS_ALERT_BACKGROUND_GIF` and `NVGS_ALERT_SOUND_FILE`.

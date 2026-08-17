# Troubleshooting Guide

## VIVE tracker still detected as 0

Issue:
- Tracker value remains 0 after setup.

Cause:
- Device binding is incomplete or tracker service did not initialize.

Fix:
1. Restart tracker service.
2. Re-pair tracker in device manager.
3. Re-run detection command.
4. Validate tracker ID in telemetry output.

## Teleop not working and camera is black

Issue:
- Teleop controls do not respond and camera feed is black.

Cause:
- Camera process failed or permissions were not granted.

Fix:
1. Check camera device permissions.
2. Restart camera stream process.
3. Confirm camera device path is correct.
4. Relaunch teleop stack after camera is online.

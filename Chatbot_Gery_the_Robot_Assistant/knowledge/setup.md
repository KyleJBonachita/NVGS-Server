# Gr00t Setup Guide

## First-time setup checklist

- Install required drivers and dependencies from approved internal package list.
- Confirm hardware connection before launching teleop tools.
- Start local services in this order: base services, device detection, teleop stack.
- Verify tracker IDs and camera stream before running tasks.

## Startup sequence

1. Open terminal in project workspace.
2. Run base environment setup command.
3. Run device detection command.
4. Run teleop launch command.
5. Confirm all status indicators are green.

## Pre-shift checks

- Tracker count is correct.
- Camera feed is live.
- Network latency is within expected range.
- No critical errors in logs.

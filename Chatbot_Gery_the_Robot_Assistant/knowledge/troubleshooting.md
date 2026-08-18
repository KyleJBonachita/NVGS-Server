# Troubleshooting Guide

## VIVE trackers are detected as 0 or do not send data to Gr00t

System context:

- The **Vanilla laptop** is the Windows laptop that runs SteamVR and the VIVE Server.
- The **Ubuntu laptop** receives the tracker data in Gr00t and uses the agent's movements to control or simulate the robot together with video.
- A common symptom is that the Ubuntu side reports `0 trackers detected` even though the trackers were previously mapped.
- SteamVR can become confused when many trackers were previously connected. Fully restarting the VIVE Server can allow the current trackers to be detected again.
- An incorrect Vanilla-laptop IP address in the Ubuntu Gr00t interface can also prevent tracker data from arriving.

Troubleshooting:

1. Confirm that both VIVE trackers are charged and powered on.
   Confirm: Are both trackers powered on and ready?
2. Confirm that the required USB tracker dongles are connected to the Vanilla laptop.
   Confirm: Are the tracker dongles connected?
3. Confirm that the trackers are not physically obstructed.
   Confirm: Are the trackers unobstructed?
4. Determine whether the VIVE Server is running in automated or manual mode, then restart it completely.
   - **Automated mode:** Close the VIVE Server application completely. The automated launcher should restart it. Do not start a second manual instance while the automated instance is running.
   - **Manual mode:** Close the VIVE Server application. Open VS Code on the Vanilla laptop, open the `Documents` folder, open a Command Prompt terminal, then run these commands in order:

     ```cmd
     conda activate dexcap
     python ./vive_server.py
     ```

   Confirm: After the VIVE Server restarts, does SteamVR show two green tracker icons and does Ubuntu receive tracker data?
5. If the trackers are still missing, pair or connect them again in VIVE Hub. Previously mapped trackers normally recover automatically when the same trackers are used. If a tracker repeatedly loses its mapping, map it again.
   Confirm: Does SteamVR now show two green tracker icons and does Ubuntu receive tracker data?
6. Restart the entire Vanilla Windows laptop to clear a possible system-level problem, then start the normal VIVE workflow again.
   Confirm: After the Vanilla laptop restarts, are both trackers detected and sending data to Ubuntu?
7. On the Vanilla laptop, open Command Prompt and run `ipconfig`. Identify the current Vanilla-laptop IPv4 address, then confirm that the same address is entered in the Ubuntu Gr00t interface.
   Confirm: Is the correct current Vanilla-laptop IPv4 address configured in Gr00t, and is tracker data arriving?
8. If the IP is correct but tracker data still does not arrive, and the agent is authorized to reset the Vanilla laptop's network lease, run these commands in Command Prompt:

   ```cmd
   ipconfig /release
   ipconfig /renew
   ipconfig /flushdns
   ipconfig
   ```

   After renewal, verify the current Vanilla-laptop IPv4 address again and update the Ubuntu Gr00t interface if the address changed.
   Confirm: Are both trackers now detected and sending data to Ubuntu?

Success criteria:

- SteamVR on the Vanilla laptop shows two green VIVE tracker icons.
- The Ubuntu Gr00t interface no longer reports `0 trackers detected`.
- Ubuntu receives tracker movement data and the expected robot control or simulation responds.

Escalation:

- If the problem remains after all documented checks, create an NVGS ticket or report it to the Team Lead or Tech Team.
- Include whether automated or manual VIVE Server mode was used, the observed tracker count, the Vanilla laptop's current IPv4 address, visible error output, and the troubleshooting checks already completed.

## Teleop not working and camera is black

Issue:

- Teleop controls do not respond and the camera feed is black.

Cause:

- The camera process failed or permissions were not granted.

Troubleshooting:

1. Check camera device permissions.
2. Restart the camera stream process.
3. Confirm that the camera device path is correct.
4. Relaunch the teleop stack after the camera is online.

Escalation:

- If teleop or the camera remains unavailable after the documented checks, create an NVGS ticket or report it to the Team Lead or Tech Team with the visible error and steps already attempted.

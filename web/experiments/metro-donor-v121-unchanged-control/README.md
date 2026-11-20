# METRO-DONOR-V121-UNCHANGED-RAM-CONTROL

This is a diagnostic **positive control**, built from the user's exact currently installed HXtra v1.2.1 HXF (SHA256 `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`), following the **R02C startup freeze**. No R02C patch is included. Neither M4 nor SHARC code or installed feature selection is modified. The control is RAM-only and can be exited by power cycling the pedal.

Execute `python3 tools/build_metro_donor_v121_control.py` from repo root. It generates the donor-to-donor RAM plan, asserts zero changed eMMC sectors, and adds an independently calculated read-only eMMC CRC of the exact original 1.2.1 SHARC Entry2 partition (first sector `34819`, `1023` sectors, CRC32 `3485190247`). This makes the unchanged-donor control conform to the unmodified WebUSB runner's required nonempty positive donor check. No CRC checks or loader safety controls are bypassed.

Stage the generated `regions/` beside these HTML/JS files and the unchanged upstream `tools/ramboot/firmware-ramboot.dfu` renamed `firmware-ramboot.dfu`. Mac mini local test URL: `http://localhost:8765/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/`. Use this only after power-cycling R02C to the original installed firmware.

Interpretation: if unchanged donor freezes too, the defect is present without any R02C code and concerns its RAM-loading compatibility or boot procedure. If unchanged donor starts successfully, R02C's M4 or SHARC modifications become the remaining suspects. This positive control alone cannot distinguish those two R02C layers. Record Chrome's Save log and actual pedal display/audio state when reporting results.

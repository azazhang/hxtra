# METRO-LEDSYNC-R02C-DONOR-EGRESS WebUSB RAM runner

This directory contains the versioned browser runner source. It is for a **user-initiated RAM-only** test of the exact installed HXtra v1.2.1 donor, MD5 `93969635834cd6050dec7f137df1e4b9` (SHA256 `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`). It is **not** a firmware installation/updater. The permanent installed HXF remains unchanged.

Run `tools/build_metro_led_r02c.sh` from the repository to regenerate the HXF and verified `regions/plan.json` with 9 RAM transfer regions, 1 eMMC donor comparison and `writes='ram'`. Stage this HTML and JavaScript plus that generated `regions` directory and the pinned upstream loader `tools/ramboot/firmware-ramboot.dfu` (as `firmware-ramboot.dfu`) on a local `http://localhost` HTTP server, for example the existing Mac mini server under `/METRO-LEDSYNC-R02C-DONOR-EGRESS/`.

**Do not copy another firmware's `regions/plan.json`.** The HTML rejects an incorrect region/check count or non-RAM write mode. The loader bytes are already tested and unmodified from the working R02B2 loader. Explicit user action is required in Chrome for USB device selection and RAM execution.

After a successful RAM run, physical preset 41C with FS3 TAP, Metronome Time 1/4 and Accent 4 is the defined test. Read-only `tools/metro_led_r02c_probe.py` reads the new firmware's `0x50` output-event count (revision signature `0x43324352`). The donor GR DSP lacks the experimental R02B1E DSP return echo, so this telemetry **cannot** claim verified SHARC click consumption. Actual audible click vs visible LED phase and BPM-adjustment drift require physical listening or synchronized optical and audio measurements.

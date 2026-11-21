# METRO-LEDSYNC-M4LEDTRACE-R01

M4-only **unproven physical** diagnostic, built from exact installed donor.
Run no automatic firmware loads. The WebUSB loader only uploads SDRAM
regions; the user controls starting and selecting the pedal in Chrome.
The SHARC Entry2 and all 13 other non-M4 entries remain identical
to donor. This only traces visible FS3 LED-control ON/OFF transitions
with microsecond timer 0x28da6458, readable via USB 0x50.

- Project build: `tools/build_metro_ledtrace_r01.py`
- Test: `tests/test_metro_ledtrace_r01.py`
- Decoder: `tools/metro_ledtrace_r01_probe.py`
- Offline binary: `build/browser-ramrun/METRO-LEDSYNC-M4LEDTRACE-R01/METRO-LEDSYNC-M4LEDTRACE-R01.hxf`
- RAM plan: `build/browser-ramrun/METRO-LEDSYNC-M4LEDTRACE-R01/regions/plan.json`
- eMMC application writes: none
- eMMC overlay sectors: 0
- Upstream WebUSB `ramrun.js`: same SHA256 as donor control
- Hardware boot and real optical/audio phase: untested

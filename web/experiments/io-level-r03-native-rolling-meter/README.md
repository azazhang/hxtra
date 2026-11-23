# IO-LEVEL-R03-NATIVE-ROLLING-METER-DIAG

**Experimental, user-triggered RAM-only two-bar display.** Build from the
exact R03C user-flashed persistent firmware; R01's live native RX diagnostics
have already been physically verified.

- Frozen R03C SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- R03 HXF SHA256: `1f5852eea09a8ec6816231d0e993ca33194f1a82d7cb27216e75d14c41f89bc8`.
- Exactly 14 non-M4 archive entries byte-identical to frozen R03C.
- Exactly three M4 hook edits from R01: RX, Home paint, read-only 0x13 registration; no new DSP code.
- Home trial bars: left x24–155, right x164–295, y113–117.
- Sources: eight-record native packet, first pair IDs 2/5 and last pair IDs 1/5.
- Bar resolution: 132 independent pixels over -90..0 native dB.
- Editor command 0x13 returns live packet counts and last eight raw readings (read-only).
- Native stereo-bus mapping and calibrated dBFS are not yet verified.
- 0 eMMC overlays; 2 read-only eMMC identity checks; writes=RAM.
- The 0x4F native RX capture command still exists; 0x13 rolling diagnostic added.
- No default/global settings or preset records modified.
- **Do not use permanent Line 6 Updater to install this prototype.**

# IO-LEVEL-R04-FULL-NATIVE-EVENT-LEDGER

**Experimental, user-triggered RAM-only two-bar display.** Build from the
exact R03C user-flashed persistent firmware; R01's live native RX diagnostics
have already been physically verified.

- Frozen R03C SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- R04 HXF SHA256: `bc79e769bd9131139ad32c92d3fd8a15ba63eefe7b0fa7a260a1611efba68461`.
- Exactly 14 non-M4 archive entries byte-identical to frozen R03C.
- Exactly three M4 hook edits from R01: RX, Home paint, read-only 0x13 registration; no new DSP code.
- Home trial bars: left x24–155, right x164–295, y113–117.
- Sources: eight-record native packet, first pair IDs 2/5 and last pair IDs 1/5.
- Existing R03 trial bar resolution unchanged: 132 pixels over -90..0 native dB.
- Editor command 0x13 returns 640-byte ledger of up to 24 native object/parameter keys, with last/min/max/count (read-only).
- Native stereo-bus mapping and calibrated dBFS are not yet verified.
- 0 eMMC overlays; 2 read-only eMMC identity checks; writes=RAM.
- The 0x4F native RX capture command still exists; 0x13 now returns 640-byte full-event ledger.
- No default/global settings or preset records modified.
- **Do not use permanent Line 6 Updater to install this prototype.**

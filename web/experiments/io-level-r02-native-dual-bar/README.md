# IO-LEVEL-R02-NATIVE-DUAL-BAR-PROTOTYPE

**Experimental, user-triggered RAM-only two-bar display.** Build from the
exact R03C user-flashed persistent firmware; R01's live native RX diagnostics
have already been physically verified.

- Frozen R03C SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- R02 HXF SHA256: `349a71331f9f635705ecab7d08ab3aefad08821eb44e8fb1a6f72f8ef00d7f69`.
- Exactly 14 non-M4 archive entries byte-identical to frozen R03C.
- Only two additional M4 hook edits from R01; no new DSP code.
- Home trial bars: left x24–155, right x164–295, y113–117.
- Sources: eight-record native packet, first pair IDs 2/5 and last pair IDs 1/5.
- Native stereo-bus mapping and calibrated dBFS are not yet verified.
- 0 eMMC overlays; 2 read-only eMMC identity checks; writes=RAM.
- The 0x4F native RX capture command still exists.
- No default/global settings or preset records modified.
- **Do not use permanent Line 6 Updater to install this prototype.**

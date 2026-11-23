# IO-LEVEL-R05-LIVE-INPUT-OUTPUT-CANDIDATE-BARS

**Experimental, user-initiated RAM-only, two independently source-keyed live bars.**

- Exact user-installed R03C HXF donor SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- R05 candidate HXF SHA256: `3eef769a0457cfa1fa4d089a92b0ebab242b0570977d94c13fb155276243112a`.
- All 14 non-M4 archive entries byte-identical to R03C; no SHARC change.
- Left Home candidate (green): `0x00020002 / 3`, guitar-responsive in R04 HW03.
- Right Home candidate (blue): `0x0002002a / 1`, guitar- and TAP-responsive in R04 HW01-03.
- Home bar geometry: x24..155, x164..295; y113..117, 132 independent pixels each.
- Debounced frame/UI repaint max about 23 Hz; independent ~2s stale clear.
- Read-only `0x13` rolling 640-byte/24-key ledger and R01 `0x4F` retained.
- Source identities are PROVISIONAL: not externally calibrated to physical jack or Main/Send/USB.
- 9 RAM regions, 2 read-only eMMC CRC references, zero permanent flash writes.
- DSP Usage %, GR, USB Monitor, Metronome and presets remain untouched in firmware.
- **NEVER install with Line 6 Updater; opt-in Chrome WebUSB RAM trial only.**

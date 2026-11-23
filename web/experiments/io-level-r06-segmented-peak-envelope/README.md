# IO-LEVEL-R06-SEGMENTED-LED-PEAK-ENVELOPE

**Experimental, user-initiated RAM-only colored LED peak meter prototype.**

- Exact R03C frozen HXF donor SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- R06 candidate HXF SHA256: `1a2e9a914702a8e4940d3a090d7ae5e489868134860a1823caee214f29026084`.
- All 14 non-M4 archive entries byte-identical to R03C; no SHARC changes.
- R05 native keys unchanged: left `0x00020002 / 3`, right `0x0002002a / 1`.
- Two Home bars, 16 green/amber/orange/red independently lit 7x5 LED blocks
  each, 1px gaps; inside original x24..155 and x164..295, y113..117.
- Genuine native peak latch across RX windows, 2-tick peak visibility hold,
  12px/tick decay. Never generates fake amplitude from TAP.
- Read-only `0x13` IOM6 640-byte record with all 24 keyed native ledger rows
  and fresh Home paint/redraw/native-high telemetry at bytes 32..63.
- Source identities remain PROVISIONAL and uncalibrated to physical I/O.
- 9 RAM regions, 2 read-only eMMC CRC checks, zero persistent writes.
- DSP Usage %, GR, NAM, USB Monitor, Metronome, presets unaffected in binary.
- **Never install with Line 6 Updater; RAM-only Chrome WebUSB trial.**

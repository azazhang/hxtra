# IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE

**User-triggered experimental RAM-only capture.** Current device must already
have the exact R03C HWFLASH01 permanent firmware installed.

- Flashed R03C donor SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- Probe HXF SHA256: `1ea5799abbadc826253d4e7866ebc28d7003b9f89403640f6f7c1fa2353f0e86`.
- SHARC Entry2 and the other 13 non-M4 entries are bit-identical.
- Two added M4 hooks, original GR RX and editor registration preserved.
- No new SHARC code and no changed eMMC overlay sectors.
- Host-only, read-only command 0x4f returns real raw native 256-word RX frame.
- `tools/io_level_r01_native_frame_probe.py` captures samples.
- No visual input/output meter in R01; the event mapping is being measured.
- **No eMMC flash, device reset or WebUSB RAM run in the build/stage step.**

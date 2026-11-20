# HX Stomp / HXtra metronome: TAP-phase and re-enable investigations

## Version identifiers

- **METRO-TAPSYNC-R01-LOCKED**: experimental M4→SHARC parameter bridge, rejected after the Nov 20, 2026 UI freeze. Git tag `metro-tapsync-r01-ui-freeze`, commit `a812aae`. Its failed RAM image was SHA-256 `c5b0ce31810ddac5a89f6c840fc20e942bf9ef7fae43586d045e99b47eb87cac`. The M4 TAP LED callback synchronously called locks and ran VFP instructions with unverified FPU context. Both source build and WebUSB page were disabled. The user reported that turning the BPM parameter knob froze display and controls, but SHARC guitar and metronome audio continued. MCPX confirmed ordinary USB control queries timed out. This observation does **not** identify one specific deadlocking call.
- **METRO-TAPSYNC-R02A-M4EDGE**: read-only, counter-only M4 event diagnostic. Its purpose is to determine whether TAP-on events and 41C metronome re-enable events are observed correctly on the M4 while changing BPM. It **does not modify the metronome's SHARC click kernel or claim to synchronize audio**. It remains a diagnostic until hardware evidence supports a later transport design.
- **METRO-TAPSYNC-R02B-TRANSPORT** (reserved, no implementation or test claim): event delivery from the M4 to SHARC, contingent on R02A hardware measurements and identification of an actual M4→SHARC frame/parameter path that is safe outside the high-frequency callback.

## R02A engineering constraints

The original stock TAP callback at `0x28d9be92` called `FS_STATE=0x28d9607c`. R02A's replacement calls the exact original stock function and increments an aligned 32-bit counter. The bypass setter at `0x28e045a0` is chained *after* stock handling; for grid position 8 changing to enabled (bypass value zero), it increments a second aligned counter. Neither callback reads settings, calls DSP parameter functions, uses a VFP instruction, waits for a lock, sleeps, or modifies a stored preset.

The added read-only HX Editor USB service command `0x50` has no parameters. Its normal editor-handler context returns a MessagePack BIN8 of twelve bytes: `uint32_le tap_led_on_count`, `uint32_le metro_41c_enable_count`, `uint32_le 0x52303241` (R02A version sentinel). The host decodes it using `tools/metro_tapsync_r02a_probe.py` and rejects unknown signatures. This command runs in the editor service thread; it is not called by either realtime hook.

The diagnostic image uses the same stock Line 6 3.80.0 base and HXtra 1.2.1-compatible feature set used for the successful eight-block 41C preset test, plus `HX_METRO_EDGE_DIAG=1`. The rejected `HX_METRO_PHASE=1` flag remains quarantined in `build.py`. The test page and firmware are named with the complete `METRO-TAPSYNC-R02A-M4EDGE` identifier.

## R02A acceptance tests

1. Offline: assemble M4 module; disassemble realtime hooks; emulate their binary code on Cortex-M4; verify stock return value, event counters, and no lock/FPU calls. The USB editor reply must round-trip all counters and the exact version signature. Run existing click, metronome, HXtra, and RAM-loader suites with the stock 3.80.0 `.hxf` available.
2. Offline: inspect the full firmware's effect model schemas against the exact downloaded installed HXtra v1.2.1 `.hxf`; require all 792 model schemas, including preset 41C's eight blocks, to match. Generate the RAM-only overlay against the exact installed donor image and verify all planned memory and integrity checks.
3. Hardware: load *R02A* by HXtra's working WebUSB RAM path. Confirm 41C has eight blocks and ordinary audio, preset, screen and knobs work. Read command 0x50 repeatedly; TAP counter should increase with physical TAP LED on-edges at approximately the beat rate. If it does not, investigate the selected hook site before implementing a DSP bridge.
4. Hardware: vary BPM using the physical tempo parameter knob, including several rapid changes. During and after these changes, command 0x50 and `hx_ctl.py status` must continue responding. Observe whether the counter's cadence follows the LED. Any freeze rejects R02A.
5. Hardware: bypass and re-enable the 41C metronome. The second counter should increment exactly once per re-enable; if it does not, correct the M4 bypass setter mapping. This test is diagnostic only; the sound is expected to retain the R00/R01 non-synchronized behavior because the SHARC kernel is unchanged.
6. After the test: save observed counts and sample timestamps as `METRO-TAPSYNC-R02A-M4EDGE-hw*.jsonl`, along with the image hash, preset-integrity check, and WebUSB log. These are the evidence for designing R02B.

## Technical finding for R02B transport (research pending)

The verified SHARC→M4 256-word SPI frame path in `docs/research/m4/dsp-link.md` is **one direction**. No proof yet exists for safe manipulation of the M4→SHARC frame in the same fashion. The R01 event transport (USB Input Trim via synchronous M4 APIs) correctly reached the SHARC in simulation, but the M4 producer's runtime context was wrong. R02B must independently establish the event transport and cannot assume that M4 framebuffer or SPI tail padding is writable or forwarded unchanged. Avoid fresh FPU work or lock acquisition in M4 timing and DSP-link tasks.

### R02A offline build and test evidence (2026-11-20)

- Build command: `HX_NAM_SLOTS=1 HX_CLICK=1 HX_BPM=1 HX_GR=1 HX_FX_GATE=1 HX_GATE_SC=1 HX_USB_INPUT=1 HX_SCREEN_MIRROR=1 HX_METRO_EDGE_DIAG=1 python3 build.py ~/Downloads/HX_Stomp_v3.80.0_0x103966115.hxf -o build/HXStomp380_HXtra121_METRO-TAPSYNC-R02A-M4EDGE_RAM.hxf`. The serial execution finished with exit code 0; HXtra's embedded L6IA integrity checks passed.
- Image: `build/HXStomp380_HXtra121_METRO-TAPSYNC-R02A-M4EDGE_RAM.hxf` (45,846,880 bytes), SHA-256 `8f0653b0a9c0842ca45bc7c4b3ef892d54a766fe04e49d7720c2737fdbe6d70d`.
- Donor reference: `~/Downloads/HXtra_v1.2.1.hxf` (MD5 `93969635834cd6050dec7f137df1e4b9`), with matching eMMC hook layout; model ID, name and complete parameter schema comparison: 792/792 matches, including all 8 block models of 41C.
- Offline RAM plan: 9 upload regions, 73 overlay sectors in 10 runs, 7 eMMC comparison pieces spanning 10,648 donor sectors; all overlay writes redirected to SDRAM. Source log: `build/loader-investigation/METRO-TAPSYNC-R02A-M4EDGE_overlay_plan.log`.
- Direct R02A tests: 4 Unicorn binary-emulation tests + 2 host decoder tests, all passed.
- Broad regression command: `pytest -q tests/test_metro_r02a_m4edge.py tests/test_click.py tests/test_metronome.py tests/test_hxtra.py tests/test_ramrun.py` with `HX_STOMP_HXF` set to the stock download. Result: **174 passed, 1 failed**, with the one failure `test_built_files_match_source` requiring `nano.specs` and `nosys.specs` absent from the installed bare-metal GCC toolchain. It is an environment/toolchain test failure unrelated to any R02A patch. Separately the 2 new host decoder tests passed. The broad test result must not be reported as 175/175 passed.
- First full-build attempt produced the `.hxf` but the cleanup step failed after another test process removed a shared intermediate file in the same build directory. The serialized rerun completed successfully. Future runs in the same workspace should not overlap builds and HXtra tests that write intermediate files.
- Hardware testing of R02A is **pending**; the unit's USB editor response was confirmed responsive again at 02:04 EST, reading preset 122 "Super Lead".

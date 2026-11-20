# METRO-TAPSYNC-R02B1E-EVENT-ECHO

**Stage:** M4→SHARC **dynamic event** round-trip measurement, after R02B1's hardware-proven canary. The next audio-phase implementation remains `METRO-TAPSYNC-R02B2` and is not bundled into this diagnostic.

## Verified basis

`METRO-TAPSYNC-R02B1-SPI-CANARY` (Git HWQA tag `metro-tapsync-r02b1-hwqa-20261120`) ran on the real HX Stomp. In 27 USB samples the M4 TX marker `0x4D543242` appeared in DSP-probed `0xC3DA6` and then in the M4's received DSP frame word220. TX frames and DSP RX frames advanced continuously; 41C remained intact through four enable/bypass cycles and Time-knob and TAP changes. The M4 event counts were not echoed at that stage.

## Event records and integrity

The known TX callback at stock `0x10000e95` continues to stamp eligible (payload count <=230) M4 SPI TX frame words **240–243**: 240=`0x4D543242` (marker, written last), 241=integer TAP/LED-on event counter, 242=integer 41C metronome-enable event counter, 243=bitwise NOT of `(marker XOR TAP XOR enable)`. No callback calls a DSP parameter setter, takes a new lock or uses VFP. The M4 callback skips oversized and malformed frames without modifying them.

The diagnostic `src/sharc/frame_probe_r02b1.asm` variant copies these four words from the R02B1 hardware-confirmed receive buffer at **0xC3DA6–0xC3DA9** to the existing DSP→M4 GR return frame words **220–223**. This only operates when the GR meter's metered compressor wrapper runs, matching the successful 41C setup. The default `src/sharc/frame_probe.asm` is unchanged. There is no SHARC metronome click modification.

The M4 pre-stock RX callback `mp_rx_probe` reads the four mirror words, preserves the original frame, and counts valid and invalid echo checksums. A marked frame is valid if its echo marker equals `0x4D543242` and word223 equals `~(word220 ^ word221 ^ word222)` modulo 2^32. The marker and checksum can detect a torn or corrupted snapshot, although the XOR complement is an error-detection canary and not a cryptographic authentication code. The main hooks remain integer-only and bounded.

## Host telemetry and acceptance

Read-only HX Editor USB command `0x50` replies with MessagePack BIN8 length **48 bytes** (12 unsigned LE32 words): M4 TAP counter, M4 enable counter, TX stamped counter, TX skipped counter, GR-marked DSP RX frames, DSP echo marker, DSP echo TAP counter, DSP echo enable counter, DSP echo checksum, valid echo frames, bad-checksum echo frames, revision sentinel `0x31453142` (LE `B1E1`). Host `tools/metro_tapsync_r02b1e_probe.py` rejects any nonmatching firmware version and computes M4 minus echoed event-counter differences. Echo counts can lag the M4 instantaneous value by one or more transport cycles; **do not require exact simultaneity**.

The hardware success criterion is **changing, valid echoed event counts** during physical/virtual TAP and bypass operations, with no missed/duplicated increments after settling. Verify consecutive framed counters under multiple tempo changes, the TX skip and invalid-echo rates, continued 41C integrity and M4 USB/UI responsiveness. If the echoed numbers do not move, investigate the SHARC address / sample timing before proceeding to R02B2. If markers or checksums fail, diagnose frame handling rather than silently accepting TX count increments. The next stage should independently quantify end-to-end event delivery latency before assigning a precise acoustic phase tolerance.

## Implementation and build identity

- Branch `experiment/metro-tapsync-r02b1e-event-echo`, based on R02B1 HWQA commit `dbb0cd2`. Source changes are isolated from all R02A/B1 tags.
- Flag `HX_METRO_EVENT_ECHO=1`; otherwise the feature set matches the successful R02B1 RAM build: `HX_NAM_SLOTS=1 HX_CLICK=1 HX_BPM=1 HX_GR=1 HX_FX_GATE=1 HX_GATE_SC=1 HX_USB_INPUT=1 HX_SCREEN_MIRROR=1`.
- M4 Unicorn tests execute actual binary hooks; SHARC simulator tests verify four-word echo and unmodified default GR; host decoder tests reject older revisions and corrupted checksums.
- Compiled image, hash, model-schema audit, overlay plan, complete regressions, and any hardware observations are recorded below as available; do not claim an unperformed hardware test.

### Offline build and deployment verification (Nov 20, 2026)

- Firmware `build/HXStomp380_HXtra121_METRO-TAPSYNC-R02B1E-EVENT-ECHO_RAM.hxf`: **45,846,818 bytes**, SHA-256 **`376b0f86ef42625e2d89563423232be4f65ec4039b2e8461db9e6edbf6cdd066`**.
- Exact HXtra v1.2.1 donor comparison: **792 / 792 complete model names, parameter names, types, and ranges match**, including every block of 41C.
- Overlay plan: 9 RAM transfer regions; 73 sectors in ten runs; 7 installed-donor verification slices; no persistent eMMC writes. Plan SHA-256 **`1905982ed6602b77f7d7e578357cab1c9a96a0544eef3df9fa2367a1faeae28f`**. The installed eMMC comparison may be unavailable on this HX Stomp (`0x10b`), as documented by the prior working loader runs.
- Verified that both HXF and plan SHA-256 hashes match their copies at `~/Projects/hxtra-metronome-test/build/` on the Mac mini. WebUSB page and its plan resource returned HTTP 200 at `http://localhost:8765/METRO-TAPSYNC-R02B1E-EVENT-ECHO/`.
- Focused M4 Thumb-in-Unicorn, SHARC-in-ssim, host decoder, and cross-processor integration tests passed, including two different event-counter sets transmitted and independently decoded via DSP echo and USB formats. `tests/test_metro_r02b1e_roundtrip.py` covers the same actual binary M4 hooks and SHARC assembly included in this image.
- The `METRO-TAPSYNC-R02B1E-EVENT-ECHO/HWQA01` hardware script is `tools/metro_tapsync_r02b1e_hwqa.py` and compares the end-of-test 41C edit buffer to the pre-RAM backup, restores bypass, exercises FS3 TAP and six Time-knob changes, and requires valid echo and event delivery in every snapshot.
- **Hardware measurement pending** until user selects and starts the separate R02B1E RAM page. R02B1's verified fixed canary establishes the input address but cannot substitute for R02B1E's dynamic-event hardware observations.

### Final offline acceptance (2026-11-20)

- The full R02B1E regression invocation under `HX_METRO_EVENT_ECHO=1`, with the verified HX Stomp stock v3.80 HXF, passed **305 tests**, with **one explicitly deselected bootloader rebuild fixture** (`tests/test_ramrun.py::test_built_files_match_source`). The available local bare-metal ARM GCC installation lacks the newlib `nano.specs`/`nosys.specs` files required by this separate loader rebuild; the bundled RAM loader file was staged and its original upstream bytes retained. No other suite case failed.
- Tests included M4 executable Thumb callbacks; dynamic four-word SHARC echo; read-only host parser and version checking; two serial cross-architecture event changes; GR meter, Metronome, HXtra, click and RAM plan/regression tests. The cross-architecture test passes M4-created frame words into the SHARC assembly and returns them to the M4 receive callback and host decoder, with both TAP and enable values changing.
- Firmware HXF SHA-256 `376b0f86ef42625e2d89563423232be4f65ec4039b2e8461db9e6edbf6cdd066` and RAM plan SHA-256 `1905982ed6602b77f7d7e578357cab1c9a96a0544eef3df9fa2367a1faeae28f` verified on Mac mini. The live pedal still had R02B1 loaded when the R02B1E files were staged.
- **Disposition:** offline accepted. Hardware-dynamic echo remains untested until the next user-initiated RAM run. Do not infer exact audio phase synchronization from this diagnostic image.

### Real HX Stomp R02B1E hardware acceptance: HWQA-20261120

The user loaded the named R02B1E WebUSB image on the Mac mini's attached HX Stomp; USB command `0x50` returned the exact R02B1E sentinel and all 12 expected words. Sampled TX stamp count, GR return count and valid echoed event-frame count increased throughout. Original 41C had the same eight blocks and the M4 USB editor remained responsive.

**HWQA00 (10 USB samples)**: M4 TAP counter 62→69; DSP-echoed count matched in 9/10 samples. The remaining sample had an inconsistent, *wrong marker* (0x00010000), nonsensical echoed event values and failed the host-side integrity check. The firmware's internal bad-checksum count stayed at zero; its valid-frame count also continued rising. It is possible the editor's 48-byte diagnostic reply was torn across concurrent M4 RX updates, but this is **not proven**. A malformed marker return-frame, unrelated shared-buffer value, or M4 reply-copy race are other explanations. Keep the original anomalous record in `tests/hardware_evidence/METRO-TAPSYNC-R02B1E-EVENT-ECHO-HWQA00-20261120.jsonl`.

**HWQA00b (60 consecutive USB samples, 0.12-second spacing):** TAP counts 109→123 were exactly matched by the echoed counts on **all 60** readings; valid echoed-frame count increased by **17,060**, bad-checksum frame count remained **zero**, and sampled M4-minus-SHARC event-counter difference was always zero. Source: `tests/hardware_evidence/METRO-TAPSYNC-R02B1E-EVENT-ECHO-HWQA00b-20261120.jsonl`.

**HWQA01 (19 control-test snapshots):** Four selected metronome off/on cycles, exactly four increments to both the M4 and SHARC echo re-enable counts (0→4), zero increments on bypass. Six Time-knob changes (+1,−1,+3,−3,+5,−5) and two TAP sequences (approximately 150, then approximately 100 BPM) completed with responsive editor controls and intact 41C. M4 and echoed TAP counts advanced **167→189** across the test. All 19 echoed tuples had correct marker/checksum. 18/19 had identical instantaneous TAP counts; one lagged by one event during concurrent sampling, then converged. The DSP valid echoed-frame count grew by **26,648** during this test, with **zero** device-reported bad-checksum frames. At end, the full edit buffer compared equal to `build/pre_ram_edit_buffer.json`: all model IDs, parameters and bypass states identical, Metronome bypassed. Evidence: `tests/hardware_evidence/METRO-TAPSYNC-R02B1E-EVENT-ECHO-HWQA01-20261120.jsonl`. Test driver `tools/metro_tapsync_r02b1e_hwqa.py` logs any anomalous USB reply explicitly and retries up to four times.

**Conclusion:** M4 event counters were demonstrated to reach SHARC and return via the established SPI frame mechanism while TAP and bypass changed. This provides the transport basis for the `R02B2` metronome audio-phase implementation. It does **not** establish submillisecond M4→SHARC latency, absence of all torn samples, an acoustic click/LED phase tolerance, or any audio synchronization in the R02B1E build.

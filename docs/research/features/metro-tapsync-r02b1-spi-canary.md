# METRO-TAPSYNC-R02B1-SPI-CANARY

**Workstream:** metronome TAP phase lock and bypass re-enable; R02A hardware evidence is in `metro-tapsync-revisions.md`. **Stage:** M4→SHARC physical data path probe. **Output:** RAM-run firmware, M4/DSP binary unit tests, USB diagnostic command `0x50`. **No audio-phase change at this stage.**

## Reason for this stage

R02A passed live tests on Nov 20, 2026: the M4's TAP LED ON callback increments a counter at the actual LED beat; the DSP grid position 8 bypass setter callback increments once when preset 41C's metronome returns to enabled. Four on/off cycles, 6 Time-knob changes and TAP tempo changes 120→160→100 BPM kept the M4 editor and all eight blocks operational. R01 had frozen M4 UI because its LED callback called the DSP parameter setter and executed VFP instructions while the settings/control path might already hold locks.

R02B1 keeps the same bounded real-time M4 event producers and transports *the values* in SPI frames. It will determine whether the SHARC can observe and echo the signal, and where. The stock frame layout and its actual receive-buffer addresses must be verified on the pedal. Only after a successful two-way echo and latency check would R02B2 modify the SHARC metronome phase.

## M4 outgoing SPI frames

Disassembly of the stock HX Stomp 3.80 M4 firmware verifies the transmit callback at `0x10000e94` (Thumb pointer `0x10000e95`), associated with the literal at `0x28da6138`. The callback receives `r1` as a pointer to a 1 KB frame; in the stock implementation it writes the `0xFACEF00D` header, its payload length and the `0xD00FECAF` trailer. R02B1 chains **after** that callback, using the same `p.chain_ptr` pattern HXtra uses for the complementary receive callback.

The new `mp_tx_stamp` makes no API calls. It validates header, trailer and the payload count in the low half of frame word 1. It writes only when the payload count is **at most 230**, leaving 10 words before the reserved slot and 12 words before the trailer. For eligible frames it invalidates word 240, stores word 241 = current TAP count, 242 = metronome-enable count, 243 = bitwise NOT of `(count1 XOR count2 XOR marker)`, then commits the marker `0x4D543242` in word 240 last. It increments a TX counter; failed guards increment a skip counter. This is a canary and count transport, not phase correction.

All M4 hooks for TX, RX, TAP and enable use bounded integer memory operations, with no FPU instruction, OS API or new lock. The new code's actual Thumb instructions are executed and inspected in Unicorn tests.

## SHARC readout (candidate mapping, pending hardware confirmation)

The SHARC's `0x6082b3` boot/link setup references DMA regions starting at `0xc3cb6` and `0xc3eb6`; the two specific candidate sample words used here are `0xc3da6` and `0xc3fa6` (each +240). Those are **candidates**, not established M4→SHARC RX slots. In a separate opt-in source `src/sharc/frame_probe_r02b1.asm`, the existing gain-reduction meter's outgoing frame writer copies those two values to currently unused DSP→M4 frame words **220** and **221**. The existing frame marker at word 200 and all GR values are left intact. Only four additional SHARC instructions are needed. In a simulated 41C-compatible metered compressor, both probe values reach the outgoing frame, and default GR builds leave the words untouched.

The M4's existing receive callback pointer at `0x28da6134` (`0x10001095`) is chained to `mp_rx_probe` before the stock callback. On marked GR frames, this reads raw words 220/221 into the USB telemetry. It leaves received frames intact and does not parse their contents.

**If the two candidate words do not contain the transmitted marker or its 16-bit-halfword swap, it means that these candidate locations were not verified by this experiment.** A later revision should discover the SHARC's actual receive address from the SPI DMA descriptor and re-run the canary. M4 TX-stamp count alone establishes that the stock transmit callback ran, not end-to-end delivery.

## USB telemetry and hardware acceptance

The diagnostic command `0x50` returns MessagePack BIN8 containing 32 bytes, eight little-endian `u32` values: `[tap_on_count, metronome_reenable_count, spi_tx_stamped, spi_tx_skipped, gr_rx_frames_seen, rx_echo_220_raw, rx_echo_221_raw, revision_signature]`. The last signature is `0x31423252` (`R2B1` little-endian); the parser `tools/metro_tapsync_r02b1_probe.py` rejects other firmware.

A successful two-way transport requires: (i) 41C still has its original eight blocks; (ii) TAP edges increment at the commanded tempo, (iii) bypass/re-enable adds exactly one to the enable count, (iv) `spi_tx_stamped` increases during normal operation, (v) marked GR frames reach `mp_rx_probe`, and critically (vi) at least one echoed candidate equals `0x4D543242` or its halfword-swapped representation. The decoder displays both raw and swapped values. Confirm the M4 USB editor stays responsive through knob and TAP changes.

### Build and version identity

- Git branch: `experiment/metro-tapsync-r02b1-spi-canary`, originating from the fully hardware-tested `METRO-TAPSYNC-R02A-M4EDGE` tag.
- Build flag: `HX_METRO_SPI_CANARY=1` alongside `HX_GR=1`, `HX_CLICK=1` and the exact HXtra v1.2.1-compatible feature set (`HX_NAM_SLOTS=1 HX_BPM=1 HX_FX_GATE=1 HX_GATE_SC=1 HX_USB_INPUT=1 HX_SCREEN_MIRROR=1`).
- RAM HXF: `build/HXStomp380_HXtra121_METRO-TAPSYNC-R02B1-SPI-CANARY_RAM.hxf`, SHA-256 `0fb989b27980f4f793744aafb753e0cb20550248e52b531ecaf73c725f9f2e4b`, 45,846,774 bytes.
- Confirmed schema: 792/792 identical installed HXtra v1.2.1 model names and full parameter layouts, including 41C's eight block models.
- RAM plan: 9 memory regions, overlay of 73 sectors in 10 runs, 7 eMMC donor check ranges, all writes to RAM. Plan SHA-256 `825a42e12963f17663e187472f457359e866047511cc46a7197a2d1a4ff7d907`.
- Chrome WebUSB page on the Mac mini: `http://localhost:8765/METRO-TAPSYNC-R02B1-SPI-CANARY/` (verified HTTP 200). Unlike the quarantined R01 page, this test uses the known working HXtra WebUSB loader.
- R02B1 host probe on the Mac mini: `~/Projects/hxtra-metronome-test/build/browser-ramrun/METRO-TAPSYNC-R02B1-SPI-CANARY/probe_counters.sh`.

### Status

Offline implementation and binary tests completed; further regressions and real hardware end-to-end transport observations are separately recorded. No hardware result for R02B1 can be inferred from R02A's success.

### Offline regression results (November 20, 2026)

- New, instrumented-code tests: `tests/test_metro_r02b1_spi_canary.py` (six Unicorn M4 TX/RX and decoder tests) and `tests/test_metro_r02b1_sharc_echo.py` (two SHARC simulator tests) passed. Inherited R02A M4 edge-capture tests were adapted to R02B1's extended 32-byte diagnostic response and passed.
- The combined regression command with `HX_METRO_SPI_CANARY=1` and `HX_STOMP_HXF` set to the verified stock 3.80 HXF covered 276 tests in `tests/test_metro_r02a_m4edge.py`, `tests/test_metro_r02a_host.py`, `tests/test_metro_r02b1_spi_canary.py`, `tests/test_metro_r02b1_sharc_echo.py`, `tests/test_gr.py`, `tests/test_click.py`, `tests/test_metronome.py`, and `tests/test_hxtra.py`. It returned **275 passed, one golden-image MD5 mismatch**. That was traced to the pre-existing source change in commit `f206068` (the experimental click kernel with EMUCLK-gap checks), which produced `5fd1d13f7a758b73cac2ba52dea986d0` for the GR+CLICK golden build, versus the upstream click-kernel baseline `40d3c0e61c427897d332e317c428d535`. The test's pin was updated with the inherited commit identified; the upstream reference remains in the comment.
- A targeted re-run of the previously failing GR+CLICK pinned build, the GR frame-word preservation assertion, all six M4 canary tests, and both SHARC echo tests returned **10 passed in 23 seconds**. Together the 275-pass combined run and ten-pass targeted rerun establish that every distinct test in the 276-case suite passed with the correct inherited kernel baseline. A single full 276-case rerun after this pin adjustment was not performed.
- No R02B1 hardware behavior has yet been observed. The installed WebUSB test page and image were verified on the Mac mini, while the pedal remained in R02A RAM firmware.

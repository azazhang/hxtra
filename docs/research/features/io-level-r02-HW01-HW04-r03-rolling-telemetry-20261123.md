# IO-LEVEL-R03 — R02 static-bar failure investigation and rolling native meter diagnostics

Date: 2026-11-23 (America/New_York). Status: offline-qualified, user-triggered RAM prototype ready; no R03 physical test yet.

## Observed R02 failure and validated findings

User physically booted `IO-LEVEL-R02-NATIVE-DUAL-BAR-PROTOTYPE` and reported one horizontal bar staying static while playing. The user subsequently engaged the Metronome block (path0 slot7) to supply a repeatable signal.

**Checks on the running R02 HX Stomp, read-only through Mac mini:**
- The HX Edit editor query still worked; preset 122, "Super Lead" (setlist0) was unchanged. Metronome slot7 model181 was **on**.
- Existing M4 metronome diagnostic `0x50` returned revision `METRO-LEDSYNC-R03C-HWGLITCH-REPAIR`, the M4 metronome-active flag true, valid transmitted SPI event/checksum, and successive accepted LED-on events (665→668) while TAP blinked. This proves the LED-sync path and request bookkeeping continued, **not** that the SHARC rendered an audible click.
- A read-only **8-second, 8-channel, 48kHz** recording from Mac mini's HX Stomp USB audio input (AVFoundation index2) returned **digital silence (-inf dBFS) on all eight channels**. This establishes silence in that capture, not that the analogue Main/Phones/Send output was silent or that the user's clicks were inaudible. No output stimulus was transmitted.
- R02 read-only USB command `0x4F` collected 400 native RX snapshots and then 500 more snapshots with the metronome explicitly engaged. For the 400: 13 frames had nonzero native payload, **zero complete 44-word eight-record meter packets**. For the later 500: seven nonempty native payload frames, also **zero complete 44-word meter packets**. The R02 callback receives many more frames than the host periodically snapshots, so these observations **do not prove R02 never received a complete meter packet**.
- R01's earlier real HW02 capture with the same preset and metronome bypassed had three complete native eight-record packets, containing first-pair values -70.058, -68.963, -69.898 and last-pair maximum equal to that same first pair. Replaying the exact *physical packet* from HW02 through R02's **assembled Thumb machine code under Unicorn** produced left bin2, right bin2, with one redraw event. All three values fit the same R02 10-bin quantization interval, explaining why the display cannot show 1dB-level variations even when native readings change. This is a confirmed implementation limitation; it does not by itself establish why a guitar played into the actual input did not move the bars.

**Main unresolved questions:** Does the real native eight-record stream update continuously on R02/R03 while metronome plays? Do its first or last channel groups correspond to the selected physical instrument Input and physical Main/Send Output? Is the metronome audible through analogue outputs while USB recording is silent? Neither sampling a few random frames nor statically reading the graph resolves these questions. R03 solves the first question with a rolling on-device diagnostic and allows the second to be tested without guessing the stream's output layout.

## R03 design: actual code, not an assumed fix

**Firmware variant:** `IO-LEVEL-R03-NATIVE-ROLLING-METER-DIAG`.

Source:
- `src/m4/io_level_r03_native_meter_rolling.s`
- `tools/build_io_level_r03_native_rolling_meter.py`
- `tools/plan_io_level_r03_ram.py`
- `tools/stage_io_level_r03.py`
- `tools/io_level_r03_rolling_diag.py`
- offline assembled ARM tests `tests/test_io_level_r03_rolling_meter.py`
- exact HXF + RAM plan gate tests `tests/test_io_level_r03_staged_hxf_invariants.py`

R03 is built **from exactly frozen R03C + the reproduced physically booted R01 M4 snapshot overlay**, not from running or patched eMMC. It preserves the R01 editor command 0x4F and original R03C metronome command 0x50, existing GR, DSP Usage, Input Sidechain and USB Monitor. Only the M4 application Entry0 changes; Entry1–14 are byte-identical to the flashed R03C (including all SHARC instructions, firmware bootstream, loader, model database and assets). New M4 payload relative to R01 is **960 bytes**, with three new call/hook sites: RX callback `0x28da6134`, Home paint `0x28d96e28`, and editor command registration `0x28d96adc`. No SHARC code, no DSP bootstream growth and no persistent firmware data writes.

**Display:** two horizontal trial bars at x24..155 and x164..295, y113..117, still derived from first native two-record group IDs2/5 and final group IDs1/5. Native negative dB float values are converted via a pure-integer IEEE754-to-Q8 conversion in M4 callback, and displayed over 132 pixels at **~0.68 dB per pixel** from -90 through 0. R02 had only ten bins (up to 9dB per bin). Both bars atomically update from the same valid native packet. A changed pixel value requests a Home redraw; stale readings clear after a bounded period without valid meter packets. The native packet must have length44, exact envelope and validated first/last record IDs; no stale DMA memory is used.

**Diagnostic:** a separate read-only editor command **`0x13`** returns MessagePack BIN16 of precisely **64 bytes**, consisting of signature `IOM3`, the observed M4 RX-frame count, nonempty native RX-frame count, length44 candidates, fully accepted meter packet count, bar state-change count, packed left/right pixel widths, native header and **all eight actual raw native float32 values** from the last fully accepted packet. Crucially, these counts and values are updated *on the device at receipt time*, independent of the host USB read interval. A generation count is committed after all eight float values, and the diagnostic response retries a torn snapshot. Polling `0x13` at 5Hz can establish accepted meter packet frequency, record-by-record variation and whether bar width followed. The host read-only script `tools/io_level_r03_rolling_diag.py` decodes each returned value and captures an optional per-sample JSONL file **locally**.

The R03 physical port-to-record mapping is explicitly **unverified**; the left/right identity remains a provisional assignment. Thickness sliders and permanent firmware installation are deferred until actual source/port correspondence and Home-render compatibility pass physical test.

## Offline validation and staged hardware trial

R03 archive HXF SHA256: **`1f5852eea09a8ec6816231d0e993ca33194f1a82d7cb27216e75d14c41f89bc8`**.

Exact frozen flashed R03C HXF SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.

- Actual compiled Cortex-M4 code was exercised in Unicorn emulator for native packet gating, exact 132px geometry, 1dB sensitivity, stale value expiry, all-eight float/counter capture, read-only 0x13 registration and return of a stable 64-byte response. Nine tests passed.
- R03 archived firmware passed all 15 L6IA integrity/checksum validations and unpack→repack equality. New HXF differs from frozen R03C only in Entry0. R03 base reconstruction asserts the R01 HXF SHA is the exact physically booted R01 image.
- The RAM plan is tied to the *persistently flashed R03C* and contains exactly **nine RAM regions**, **two read-only eMMC CRC identity checks** (SHARC partition header plus 1023 complete payload sectors), **zero eMMC overlay sectors** and **writes=RAM**. RAM plan SHA256: `ce3d25feb7ebbfcfbc9d0ebd22e7ec4d0cf16c3281203caefb384c7e58a6212f`.
- Chrome WebUSB JavaScript passed Node parse and exact RAM-only preflight assertions. Mac mini host served the experimental page and RAM program regions with HTTP 200; local and Mac mini page/plan SHA hashes matched. No automation ran the boot or used Line6 Updater.
- The source branch is `experiment/io-level-r03-native-meter-rolling-telemetry-20261123`. R01, R02 and permanent R03C source/tag/image remain unchanged. The `.hxf` and raw DSP/native USB evidence are private local artifacts, excluded from Git.

## User-initiated hardware verification

On Mac mini Chrome: `http://localhost:8765/IO-LEVEL-R03-NATIVE-ROLLING-METER-DIAG/`.

Power-cycle to exit R02's RAM image and return to permanent R03C. Run R03 from Chrome using the existing WebUSB chooser. Confirm a normal boot, the two bars and Metronome block on (it may be reset to bypass/off by power cycle, so check). Then assistant performs **read-only** diagnostics from Mac mini:

```sh
cd "$HOME/Projects/hxtra-metronome-test"
.venv/bin/python tools/io_level_r03_rolling_diag.py --samples 60 --interval .2 \
  --out /tmp/io-level-r03-HW01-metronome-on.jsonl
```

Measure accepted packet count delta, actual eight float changes, bar state-change count, and visible motion. This directly separates lack of native updates, wrong record selection, insufficient screen sensitivity, and repaint problems. If the device freezes, save the Chrome WebUSB log and manually power-cycle to restore permanent R03C. **R03 is not certified for permanent flashing.**

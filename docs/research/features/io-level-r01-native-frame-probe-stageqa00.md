# IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE — prototype stage QA (2026-11-22)

## Engineering objective

Implement **continuous, simultaneous Input and Output level meters**, each a horizontal bar on its respective left/right half of HX Stomp's 320×240 Home screen, with independently adjustable 0–20 pixel thickness (0=off by default). The request is the original upstream [wisemandenny/hxtra#116](https://github.com/wisemandenny/hxtra/issues/116). It builds on the existing HXtra compressor gain reduction display, in particular `src/m4/gr_meter.s`.

The user requested: (1) explain the DSP *bootstream* and (2) investigate whether the device's existing Input/Output level measurement eliminates the need for any new SHARC peak-measurement code. After actual disassembly of the exact installed firmware, we isolated an **M4-only diagnostic prototype** to identify the native values before writing a UI that represents them. This is a real, compiled, verified binary and WebUSB RAM experiment; **it does not yet draw the intended two level bars.**

## Verified native DSP measurement

In the exact SHA-pinned R03C HXF, the stock SHARC process implementation of registered primitive `0x2390` is the 48-bit program at `PM 0x8da6a`. Its instructions at `0x8da6a..0x8da70` read 16 input samples from `I1`, compute their absolute value, and keep the largest. At `0x8da71..0x8da76` the current peak updates its `PM(0,I8)` and `PM(1,I8)` state. At `0x8da7f` it calls `0x8cbb8`, the native event queue routine: `0x8cbe1..0x8cbe6` write event fields including the sampled `R2` to a queue record. This is **actual executable code disassembled from the pinned R03C image**, not inference from comments.

The Input block includes `0x2390` primitives for L/R before the Input gate. The Output block's composite also includes metering primitives; selected path, event type and M4 message field mapping have not been resolved. We must not misidentify compressor GR frame words `216/217` as global input/output levels; those words are written by `src/sharc/frame_probe.asm` **only while a selected compressor runs**.

**Terminology:** Entry2's 524,288-byte partition carries the *SHARC bootstream*, a loader initialization image comprising PM instruction records, DM initialization records, zero-fill instructions and descriptors (also initial DSP app metadata). The initialized runtime code exists in SHARC program memory after boot. The bootstream is the **packaged persistent startup image**, rather than the machine's instruction-memory capacity. The exact installed R03C Entry2 has 524,212 bytes, leaving 76 bytes if new initialization records were to be appended. Because this R01 experiment changes **no DSP code or initialization record**, that 76-byte cap imposes **zero limitation on R01**.

## Exact frozen donor and R01 output

- Already flashed, user-confirmed duplicate-free and post-Updater editor-verified: `METRO-LEDSYNC-R03C-HWGLITCH-REPAIR`
- Pinned R03C HXF SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- New staged variant: `IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE`
- **New R01 HXF SHA256:** `1ea5799abbadc826253d4e7866ebc28d7003b9f89403640f6f7c1fa2353f0e86`.
- `tools/build_io_level_r01_native_frame_probe.py`: exact SHA guard on original R03C, changes only Entry0 (M4 code) and only 2 existing patched call sites plus segment/CRC headers, by chained hooks:
  - `0x28da6134`: DSP→M4 RX callback pointer, retains original R03C GR callback `0x28e55521`, runs snapshot before it;
  - `0x28d96adc`: existing HXtra/R03C editor-register chain `0x28e60f24`, runs new extra command registration after it.
- **Entries 1..14 all byte-identical to frozen R03C**, including **Entry1 bootloader**, **Entry2 entire SHARC kernel/bootstream**, all other models, image/font assets, global settings and DSP effects.
- Source `src/m4/io_level_r01_native_frame_probe.s`: one-shot receive-frame capture when armed, validates halfword-swapped SPI `FACEF00D`/trailer, copies 256 raw words (1,024 bytes) into a private back buffer, marks captured only *after* the full copy and `dmb`. Does not modify the incoming frame.
- On normal editor service 6 request command **`0x4f`** (unused stock command), copies the **complete** captured back-buffer into a private front-buffer only after it is ready, returns MessagePack `BIN16` of **1,040 bytes** (16-byte header + entire 1,024-byte raw frame), then arms the next capture. Existing `0x50` R03C LED timing diagnostics remain unchanged. There is no new UI redraw, settings write, DSP instruction, DMA modification or audio-sample write.
- Host decoder `tools/io_level_r01_native_frame_probe.py` checks `0x50` revision first, reads each 256-word raw frame with `0x4f`, verifies checksum/footer and header. Raw frame fields are deliberately **uninterpreted**. Capturing normal device messages might expose preset content; don't push raw captures publicly without checking.
- Distinct source branch `experiment/io-level-r01-native-frame-probe-20261122` from feasibility branch, while stable `R03C-HWGOOD01` and `HWFLASH01` remain intact.

## Offline and live-serving proof

1. `tools/l6ia_verify.py` checked **ALL OK** for all 15 firmware entries, packed `.hxf` roundtrip recovered the exact same `.l6ia`.
2. The M4 code compiled using the existing HXtra Thumb toolchain. `tests/test_io_level_r01_native_frame_probe.py` runs the **assembled machine code** in a Unicorn Cortex-M4 emulator; validates valid/invalid SPI frames, one-shot capture, no alteration of original DSP frame, correct editor command registration, `BIN16` response, stable front/back buffer operation and no promotion of incomplete frame data to output. The SHA-pinned R03C archive comparison confirms all other 14 entries intact.
3. The RAM plan, `tools/plan_io_level_r01_ram.py`, derives the application from **currently flashed R03C**, not the older original HXtra donor. Known M4 app CRC32 is `0x5ed9d947`. Plan has exactly 9 RAM regions, **0 eMMC overlay sectors**, **0 eMMC writes**. Because the WebUSB runner refuses zero eMMC identity checks, plan adds **2 read-only eMMC identity checks** against the *R03C* Entry2 descriptor (sector `0x8802`) and its first 1,023 full payload sectors. These cover R03C's custom SHARC timing kernel and refuse an unexpected base. No bootloader or firmware update run occurs in the build/stage.
4. `tools/stage_io_level_r01.py`: generates an explicit Chrome WebUSB page and copies the unchanged original HXtra RAM loader and browser script, with strict preflight for 9 RAM regions / 2 read-only eMMC checks / 0 overlays / RAM-only mode.
5. Node v24 parses the generated browser inline script and `ramrun.js`; no JS syntax errors. All Mini staging assets including the 9 RAM region binaries have been synced and the copied manifest SHA compared. **Mac mini static localhost page and plan both return HTTP 200** at `http://localhost:8765/IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE/`.
6. Automated off-device tests completed (see the exact current pytest output). **No user-triggered WebUSB load has yet been performed**. There is no claim of successfully running this new image on physical HX Stomp.

## User-initiated hardware step

**All physical RAM boot operations belong to the user**; assistant MUST NOT click the RAM loader, power-cycle or send writes to HX Stomp.

On the USB-connected Mac mini, in Chrome open:

`http://localhost:8765/IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE/`

Confirm the preflight shows **9 RAM regions**, 2 read-only eMMC checks, and zero overlays, then click **Run IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE from RAM** and follow Chrome's USB chooser. This is temporary. If no boot, save the browser log and manually power-cycle to recover permanently installed R03C.

Once it boots, the assistant can use only read-only editor USB query:

```sh
cd "$HOME/Projects/hxtra-metronome-test"
.venv/bin/python tools/io_level_r01_native_frame_probe.py \
    --samples 30 --interval .3 \
    --out tests/hardware_evidence/IO-LEVEL-R01-RXFRAMES-HW01-20261122.jsonl
```

Gather a baseline with no instrument signal, then compare known guitar-input activity and output activity for one preset; ideally run a controlled USB 5/6 test tone at known amplitudes with the correct preset source. Identify **actual** tagged values/peak magnitudes and separate Input from Output, then implement the 2-bar M4 display in `IO-LEVEL-R02` with the proper dB-to-pixel mapping and Global Settings virtual IDs. Existing `src/m4/gr_meter.s` provides reusable logarithm and Home widget rendering; avoid copying the GR stale/dirty overlap bugs documented upstream in [#176](https://github.com/wisemandenny/hxtra/issues/176) and [#185](https://github.com/wisemandenny/hxtra/issues/185).

**Acceptance:** This is a completed **offline-validated M4-only instrumented firmware prototype**. The actual simultaneous horizontal level meter is the next phase, contingent on mapping **measured** native incoming frame fields. No unnecessary SHARC duplicate peak calculator has been added or proposed as established necessary.

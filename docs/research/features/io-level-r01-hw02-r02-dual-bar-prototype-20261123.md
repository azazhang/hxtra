# HXtra I/O level meter: R01 hardware findings and R02 dual-bar prototype

Date: 2026-11-23. Research branch: experiment/io-level-r02-native-dual-bar-20261123.

## Outcome

The original SHARC firmware already measures and publishes audio levels. We independently traced its peak algorithm, metering primitives, queue publication and the native event packets observed through R01 on the physical HX Stomp. A user-triggered RAM prototype R02 is now packaged with two real-time horizontal Home bars. It adds **zero SHARC instructions** and changes **only the M4 application**, retaining the exact permanently flashed R03C and all existing 14 other HXF entries.

**Physical status:** R01 was successfully RAM-loaded by the user and its USB diagnostic query worked. R02 has passed offline assembled Cortex-M4 emulation tests and is staged on Mac mini for user-triggered RAM testing. R02 has **not** yet been physically booted; the left/right native meter groups are experimentally assigned until controlled input-versus-output testing establishes the actual route.

## Independently verified R01 evidence

- Flashed R03C SHA256: 42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b.
- Physically booted R01 SHA256: 1ea5799abbadc826253d4e7866ebc28d7003b9f89403640f6f7c1fa2353f0e86.
- Read-only editor query 0x50 returned the R03C signature and a valid TAP SPI integrity pair. New editor query 0x4F returned complete, valid raw 256-word DSP-to-M4 frames.
- Across a subsequent 500-frame capture lasting approximately 29 seconds, all frames had valid magic/trailer and complete monotonic snapshots. The *native* payload length histogram was: 0 words (483), 5 (2), 9 (9), 13 (1), 14 (2), 44 (3). Thus 17 were nonempty; three were complete native eight-record meter packets.
- **Material correction to the earlier probe decoder:** native payload length in the as-captured halfword-swapped M4 RX buffer is raw frame word 1 **shifted right 16 bits**. The original low-16 reading was incorrect. Stock M4 receiver disassembly at address 0x10001094 establishes the swap. Words beyond the declared native payload are leftover DMA contents. The corrected tools/io_level_native_protocol.py never interprets those as fresh measurements.
- Each native 44-word meter packet begins with the unswapped envelope 0x180000a8, 0x03800110. It then carries eight native five-word records, structurally [0, 3, family 0x00020000, channel ID, float32 dB-like value], at channel IDs **2,5,3,6,4,6,1,5**.
- The three complete packets, collected at trace sample indices 277, 284, and 462, carried first-pair IDs 2/5 at **−70.058, −68.963, −69.898** (equal pair values in each); middle IDs 3/6 and 4/6 at **−120**; last pair ID 1 at **−81.584, −81.424, −81.875** and last ID 5 equal to the first pair's ID 5. Other observed native event families were 0x00020002, 0x0002002a, 0x0002002e, which must not be misread as the eight-record meter packet.
- The currently loaded preset was identified by read-only HX Edit protocol as **setlist 0, preset 122, Super Lead**. No presets or global settings were changed. A read-only 4-second, eight-channel 48kHz HX Stomp USB audio recording returned digital silence on every channel. It establishes no physical channel mapping.
- Exact-image SHARC disassembly: primitive **0x2390** process code at **0x8da6a** computes abs/peak of 16 samples and sends a native queue event through **0x8da7f → 0x8cbb8**. Its stock init at **0x61047f** sets a 300-block publication interval (300×16/48000 = 0.1 second, ten updates per second while running). Parsed Entry4 composite graph lists the same native meter primitive at Input composite **0x600000** members 34/37, and Output composite **0x60000a** members 9/11. These claims are derived from actual HXF bytes, not source-comment assumptions.

The raw 500-frame capture remains in an untracked local file to avoid disclosing possible user preset details. The public repo contains the protocol parser, aggregate analyzer, and reproducible synthetic tests encoding only verified packet shapes and levels.

## R02 firmware and what it actually does

R02 name: **IO-LEVEL-R02-NATIVE-DUAL-BAR-PROTOTYPE**.
R02 HXF SHA256: **349a71331f9f635705ecab7d08ab3aefad08821eb44e8fb1a6f72f8ef00d7f69**.
R01 M4 app 1,033,892 bytes → R02 1,034,564 bytes: **672 bytes** of added application payload.

Builder: tools/build_io_level_r02_native_dual_bar.py. Assembly: src/m4/io_level_r02_native_dual_bar.s.

The builder checks the exact frozen R03C source SHA and reconstructs R01's HXF archive byte for byte against the image that was physically RAM booted. It then adds just two chained M4 hooks: RX pointer at **0x28da6134** (runs before original R01 + GR callback) and Home paint pointer at **0x28d96e28** (runs after original Home/GR/breathing callback). Existing R01 read-only USB command 0x4F remains present. Only M4 Entry0 changes relative to the exact original R03C; **all other 14 archive entries, including the SHARC bootstream, bootloader, model assets, and routing code, are unchanged**. The package passed all 15 L6IA entry checks and unpack→repack archive equality. There are zero extra SHARC instructions, initialized DSP bytes, or NAM slot reductions.

The listener accepts actual complete 44-word native meter messages with correct magic, trailer, envelope and first/last record identifiers. It reads the genuine transmitted float32 values, converts dB thresholds using integer ARM/Thumb comparisons (no FPU context), and stores both bar lengths atomically. Values outside the current native payload are never consumed. It requests Home redraw only when a bar length changes and clears stale values after approximately 4,600 incoming frames without a new native packet.

The **left green trial bar** at x24..155, y113..117 measures max of the first native pair (IDs 2/5); the **right blue trial bar** at x164..295, y113..117 measures max of the last native pair (IDs 1/5). Bars are 132×5 pixels, with 0–10 bins at [−90, −72, −60, −48, −36, −24, −18, −12, −6, −3]; high values render amber or red. The actual source-port mapping (Input vs Main/Send/USB Output) has not been physically proven and is the next RAM test's explicit objective. The fixed 5-pixel thickness is suitable for this experimental drawing; the original feature request's independent user settings can be added following successful mapping and lifecycle checks.

## Tests and controlled staging

- Six assembled-Cortex-M4/Unicorn tests of the actual R02 module: proper 44-word packet decoding, 0–10 binning including NaN/Inf rejection, invalid packet and stale-frame handling, precise actual fill ROM calls, and measured event ID ordering.
- Six native packet parser tests with real HW02 framing: full eight records, empty native payload with nonzero stale DMA contents, other native event families, partial records, and fail-closed invalid envelope.
- Original R01 one-shot double-buffered native RX diagnostic and R03C DSP image integrity tests retained.
- Stage tools/plan_io_level_r02_ram.py builds **nine RAM regions**, with **zero eMMC overlay sectors, writes=RAM**, and **two read-only CRC checks** of the flashed R03C Entry2 header (sector 0x8802) and the first 1,023 complete SHARC payload sectors. Plan SHA256 **fa00a6b82f338ef53536444843cd36a51ff03687685e0f9b15562adc441f309a**.
- Browser stage tools/stage_io_level_r02.py validates all SHA guards, firmware-entry invariants and RAM-only plan, then uses the same unchanged WebUSB loader and runner as previous tested releases. Mac mini browser page, largest M4 RAM region, and plan all returned HTTP 200. Local and Mac mini SHA256 hashes for the displayed page and plan matched. Neither stage nor analysis has contacted the pedal with a write, reset, RAM-run, or flash operation.

## User-controlled next physical test

The Mac mini Chrome page is:

http://localhost:8765/IO-LEVEL-R02-NATIVE-DUAL-BAR-PROTOTYPE/

The user should power-cycle to exit currently running R01 back to the permanently flashed R03C, then click Run on the R02 page and select the USB device. The preflight shows **9 RAM regions, 2 identity CRC checks, zero eMMC overlays, writes=RAM**. Test whether the two live bars appear and move appropriately on the Home screen, and which reacts to a selected instrument Input versus changing actual Output amplitude. Preserve user presets and feature settings. Verify DSP Usage %, existing GR, USB Monitor and the R03C metronome remain functional.

If the R02 RAM image freezes, the user should save the browser log and power-cycle to restore flashed R03C. **Never install experimental R02 with Line 6 Updater.** R02 physical boot, meter-to-port identity, calibrated amplitude and full feature parity have not yet been verified.

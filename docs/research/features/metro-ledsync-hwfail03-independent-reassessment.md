# METRO-LEDSYNC-HWFAIL03-REASSESS-20261120 — independent architecture review after third boot failure

Date: 2026-11-20 (America/New_York). Review-only work. No hardware boot, flash, preset edits, settings edits, or new firmware artifact were initiated for this reassessment.

## Scope / invariant

The user's goal is an **internal audible Metronome block** in preset 41C whose quarter-note clicks follow the **actual FS3 TAP LED illumination requests** during successive BPM changes, with stable downbeat/accent behavior across bypass/re-engage, while preserving the exact installed `~/Downloads/HXtra_v1.2.1.hxf` feature selection (DSP Usage Display, USB Monitor, additional footswitches and other additions) and saved global configuration. The donor SHA256 is `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`. All experiments must remain RAM-only until explicitly authorized otherwise.

## Hardware facts and boundary of evidence

- R02B2 was capable of booting and live M4-to-SHARC SPI event delivery was confirmed by diagnostics. The user initially heard click and TAP LED in phase, then observed drift after repeated physical BPM adjustments. Its rebuilt source omitted parts of the exact installed donor (notably DSP Usage Display and/or USB Monitor, depending on revision).
- The user reported a freeze on startup with combined M4+SHARC R02C. Editor SYN timed out; browser RAM-upload CRC checks succeeded. This does not identify the processor that stopped or prove SHARC code was executing.
- An unchanged HXtra v1.2.1 donor RAM boot was subsequently verified to complete and return an editor response. Thus the generic RAM boot path can boot the original donor.
- SHARC-only HWFAIL02, with exact donor M4 Entry0, also froze on startup. This implicates the SHARC Entry2 delta or its RAM-loading path independently of the R02C M4 LED hook.
- The later HWFAIL03 corrected one eMMC subheader sector `0x8802` (payload 524284 bytes, CRC `0x0f5d02e7`), keeping SHARC program bytes unchanged. The user reports **HWFAIL03 froze again on startup**. A fresh read-only USB query still enumerated HX Stomp but `hx_ctl.py --timeout 2 status` returned `no SYN reply`. The page had shown `Ready` before the test. The page was no longer in Chrome during post-report collection, so the browser transfer log from this exact run could not be preserved and the precise execution handoff could not be independently reverified. Treat the user-observed freeze as the hardware outcome, with stage and build-identity uncertainty explicitly retained.
- The HXtra donor HXF has 524212 bytes of SHARC bootstream in a 524288-byte partition (76 bytes headroom). HWFAIL02/HWFAIL03 modified it to 524284 bytes (4 bytes headroom) and changed the INIT_L32/INIT_L48 descriptor sequence. Original PM/DM final-memory equivalence checks are useful but do **not** model the device's loader, sequencing, DMA, boundary conditions, or kernel runtime integration.
- Focused offline tests were rerun in this conversation on `.venv12`: 15 passed for HWFAIL03 and R02D boot/metadata/compact source. They establish their asserted static properties, not that either image can boot.

## Independently reproduced defects not previously caught by those tests

### 1. Invalid SPI checksum is accepted by both R02C and R02D SHARC receivers

In `src/m4/metronome_led_egress.s`, the M4 publishes 4 SPI words at offsets 240..243: marker, TAP edge counter, enable count, and complemented-XOR integrity word; it commits the marker last. In `src/sharc/click_led_egress.asm` and `src/sharc/click_led_egress_compact.asm`, the SHARC code checks only `LED_RING` against `LED_MAGIC` and whether `LED_RING+1` differs from `C_LED_LAST`; it does not validate words +2 or +3. Under the actual assembled instructions in `ssim`, after initial marker+counter zero, injecting counter=1 with checksum=0xBAD0BAD0 causes **both R02C and R02D to accept the event and emit a 2000 Hz accented click**. This directly defeats the apparent integrity protocol. It is a verified software defect; corrupted/torn hardware SPI snapshots as the *cause* of the observed drift are unproved.

A reproducible negative regression gate is `tests/test_metro_ledsync_reassessment_faults.py`, currently xfailed on both variants. Do not turn the xfail into a passing assertion until the actual receiver validates the integrity and snapshot coherency and tests pass.

### 2. Immediate fallback to free-running local clock after marker invalidation

With external timing already acquired and a recent LED event, setting the M4 marker invalid while allowing audio callbacks to continue produced additional local SHARC beats **without new LED edges**. For both R02C and R02D under `ssim`, over 12000 samples (0.25 s) at a Time of 0.1 s, the accent/bar counter advanced from 1 to 3 and locally generated onsets appeared at offsets ~4784 and 9584 samples after the first 480-sample decay window. Loss of external timing may legitimately require fallback when TAP visibility is explicitly disabled or FS3 changes function; transient invalid packet handling requires a separate hysteresis/state/phase policy. As coded, it may recreate offbeat clicks during SPI disruption. This outcome is not evidence that transient corruption happened on the hardware.

### 3. The physical edge has not been measured

The current M4 hook follows the donor's post-`HX_BPM` visible FS3 LED sender continuation; this is a plausible electrical-command edge and is preferable to the earlier hidden logical TAP callback, especially when BPM setting switches to autonomous mode-2 LED blinking. It remains **untested on hardware in the donor-preserving R02C branch**. Host-sampled LED mode and TAP counters with ~130 ms poll spacing cannot prove optical LED/audio phase or capture individual BPM-change transitions with sufficient timing precision. Photodiode/video plus output audio capture would measure the actual timing path. The Mac mini's previous terminal audio capture was denied microphone permission, so no acoustic waveform supports prior latency claims.

## Revised causal assessment

The unchanged-donor RAM control boots; three SHARC-modified images are reported frozen (R02C combined, HWFAIL02 SHARC-only, HWFAIL03 SHARC-only with corrected header). This sharply prioritizes failures involving SHARC Entry2 rewriting, bootstream shape, or its overlay/application-load path, **rather than** the M4 LED event hook. Fixing header metadata was necessary for consistency but demonstrably insufficient for the user-reported HWFAIL03 result. It is not evidence that every detail of the loader reads the new header or that the SHARC kernel algorithm itself is broken. Any new full R02C/R02D test would mix new assumptions with unresolved boot failures.

R02D is **not approved as the next hardware candidate**: it keeps the same receiver checksum defect and performs seven descriptor merges (including PM-code and DM-data merges). Its equal payload length and passed simulator/static tests are insufficient boot-safety evidence.

## Architectural restart (proposal; NOT implemented)

1. **Return to the exact installed donor**, verify normal editor SYN and unchanged feature/UI behavior after a physical power cycle. Freeze state precludes live instrumentation until this occurs. No further experimental RUN is staged or requested now.
2. Isolate the *event-source question* with an **M4-only, read-only diagnostic**, anchored to exact donor M4 and original SHARC untouched: count and timestamp FS3 post-filter OFF-to-ON LED sends; expose a bounded trace through the existing editor query. Do not stamp SPI or modify live sound. Exercise genuine physical BPM knob changes, bypass/re-enable and LED Off, and measure LED output independently if necessary. The old R02A tests only the logical callback, not this downstream driver event.
3. Determine an **SHARC intervention that does not rewrite LDR block ordering or expand the already full Entry2**. A candidate is a compact *in-place* metronome-kernel substitution using the original LDR record topology with only changed PM instruction contents and CRC metadata; its instruction-budget feasibility and safety must be demonstrated offline first. Alternatively investigate a safe post-boot runtime PM patch path if the device architecture supports it. Neither option has yet been implemented or shown safe.
4. Rebuild a **complete validated event protocol**: marker + monotone event counter + enable/bar reset + integrity check (atomic/stable snapshot), explicit loss-of-lock versus intentionally-disabled-TAP policy, no phantom local triggers during tempo edits, count-jump handling, and first LED-on downbeat after re-engage. Test real assembled instructions, corrupt/torn reads, producer/consumer sampling races, tempo jumps, bypass, and block activation. The originally proven R02B1E transport and prior R02B2 regression lessons are useful, but do not prove this new integration.
5. Require **two separate acceptance gates**: (a) physical boot and feature-parity control, including editor and DSP percentage display; (b) synchronized light/audio timing through repeated *physical* tempo changes. CRC-successful RAM uploads and standalone SHARC simulations do not pass either gate.

Other possible architecture: make the DSP click the phase master and drive the TAP LED from DSP-to-M4 event telemetry, an existing verified transport direction. This potentially yields stable audio-clock timing but changes native TAP LED semantics, creates scheduling conflicts with other uses of FS3, and still requires a validated SHARC-side event producer. Investigate only if the LED-master method cannot be implemented safely. External MIDI-clock synchronization can offer a firmware-free fallback, though it does not by itself solve the internal Metronome block's phase-reset problem.

## Disposition and safe handoff

- **Reject:** further HWFAIL02/HWFAIL03 loading, R02C as a normal candidate, R02D as a presumptive fix, or any permanent HXtra firmware change.
- **Current device state:** post-HWFAIL03 frozen by user report; USB enumerated; editor SYN timed out. Physical power cycle is needed; donor recovery after this particular failure not yet observed.
- **Most important new evidence:** the R02C/R02D SHARC receiver accepts deliberately corrupted SPI events, plus immediate local fallback can create free-running clicks after loss of marker. These defects mean a successful boot alone would not validate the design.
- This report and the regression tests are review/diagnostic artifacts only; there is no new firmware binary and no live parameter or settings modification.

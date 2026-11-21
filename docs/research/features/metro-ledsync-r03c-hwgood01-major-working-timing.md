# METRO-LEDSYNC-R03C-HWGOOD01 — major working duplicate-free hardware milestone; M4 LED→TX latency quantified

**Date:** 2026-11-20 (America/New_York). **Firmware:** `METRO-LEDSYNC-R03C-HWGLITCH-REPAIR`. **Status:** the user reports that the occasional duplicate/double audible click seen in R03B **is resolved on physical R03C**. Independently verified R03C RAM handoff, normal HXtra editor response, correct live R03C telemetry and 23 distinct synchronized M4 TAP LED counts. **Outstanding:** perceptible FS3 optical LED → audible click delay remains unexplained and unmeasured end-to-end. Do not call this release phase/latency-perfect; preserve the exact working R03C binary as a baseline.

## Physical confirmation and milestone

User: "**the duplicate is resolved. this is can be flagged as a major working version. you can quantify how long does it take from the LED change to produce the click to see if it is the source of the lag.**"

Verified independently after user-initiated R03C RAM load:

- Mac mini Chrome WebUSB page `METRO-LEDSYNC-R03C-HWGLITCH-REPAIR` reports **RAM handoff complete** with all shown transfer-region CRCs successful and `started: the firmware runs from RAM`. This proves loader handoff, not sound/optical performance by itself.
- HXtra USB editor responded with `setlist 0 preset 122 "Super Lead"`, **all eight original model slots**, including **Metronome model181 in slot7 engaged** at that snapshot. No saved settings, preset edits, M4/eMMC firmware writes, or new experimental firmware load were performed by this inspection.
- Read-only USB editor command `0x50` returned the precise **R03C** signature and live FS3 LED count increments; correct 32-bit complemented M4 SPI TX event frames and M4 metronome-active flag.
- User confirmed real acoustic outcome: **no more double clicks** in R03C. This is a user-observed positive hardware acceptance result for that bug, rather than an independently captured audio waveform. Physical bypass / DSP usage percentage screen / USB Monitor feature presence were not rechecked in this turn and are not claimed newly validated.
- Preserve tested R03C HXF SHA256 **`42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`**. Installed original HXtra v1.2.1 donor SHA256 **`96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`**. R03C only modifies 4 original M4 hooks and the existing 142-word metronome SHARC record #177; 201 original SHARC boot descriptors and 524212-byte Entry2 length remain unchanged. Other 13 firmware entries byte-identical, zero permanent eMMC writes. Prior StageQA00 113 passed, 4 expected old-defect xfails, 1 skipped, 1 deselected.

**Milestone:** `METRO-LEDSYNC-R03C-HWGOOD01-MAJOR-WORKING-DUPLICATEFREE`. This is the first combined M4→SHARC user-confirmed duplicate-free hardware revision. R03A physically booted with the original free-running metronome, and R03B physically booted but generated duplicate clicks; they are retained as historically distinct artifacts. Do not overwrite or repurpose this tag for a later experimental audio phase correction.

## Real hardware timing — measured M4 LED command to first M4 SPI TX callback

A read-only 80-query run was collected from the running physical R03C on the Mac mini through `tools/metro_led_r03c_probe.py` over **13.087 seconds**. Source trace:

`tests/hardware_evidence/METRO-LEDSYNC-R03C-HWGOOD01-LED-TO-M4TX-80SAMPLES-20261120.jsonl`

SHA256 **`f725426c5425d859cdfcf6243744798c9b3af65c9c1794ca983b4382051a1b01`**. The corresponding reproducible computation is `tools/analyze_metro_r03c_hwgood01.py` and its generated structured result is `tests/hardware_evidence/METRO-LEDSYNC-R03C-HWGOOD01-LEDTX-TIMING-ANALYSIS-20261120.json`. Three focused data-integrity/reproducibility tests pass.

**Careful timestamp definition:** each captured M4 timestamp is obtained via the stock native 1-microsecond timer when the post-filter final FS3 TAP LED RGB **ON command is accepted by the M4**, *before the physical LED driver lights*. The second M4 timestamp is recorded when the first stock SPI TX callback sees and stamps that new event counter into the prepared TX frame, *before the actual SPI hardware sends the frame to SHARC*. Therefore the measured difference is **only M4 LED-command → first M4 SPI TX callback**, not photon→sound, not full actual SPI TX, not SHARC audio trigger.

The 80 USB snapshots contained **23 distinct sequential LED events**, event raw counter `2147484490..2147484512`, giving **23 unique microsecond observations**. Repeated snapshots of the same event were deduplicated to avoid falsely inflating the sample size.

| Actual M4 boundary measure | Value |
|---|---:|
| Minimum | **39 μs** = 0.039 ms |
| Median | **165 μs** = 0.165 ms |
| Mean | **225.30 μs** = 0.225 ms |
| Population SD | **126.30 μs** = 0.126 ms |
| 95th percentile (linear interpolated, 23 beats) | **408.2 μs** = 0.408 ms |
| Maximum | **419 μs** = 0.419 ms |

The event LED ON-to-ON intervals (22 adjacent physical M4 commands) had **599,942.5 μs median = 100.010 BPM**, consistent with a stable ~100 BPM setting. All 80 M4 event/checksum pairs were internally consistent and current. During this read-only run, the cumulative counters for skipped SPI frames, non-TAP/hidden-LED TX frames, TAP grace holds, explicit fallback frames, short LED reversals filtered and Metronome engage transitions were **unchanged**. The R03C M4 transport was operating regularly throughout the measured 13-second segment.

**Interpretation:** An early M4 software transport lag of **0.039–0.419 ms** is extremely small compared with a human-perceivable click lag of dozens of milliseconds and cannot independently explain the user's reported perceived delay. This **does not exclude** further delay from actual SPI delivery, SHARC receive/processing, sound generation, audio codec/buffering, the user's monitoring path, or optical LED hardware. None of those stages' **measured** delays are available in the current R03C diagnostic.

For clarity: the initial 12-snapshot probe covered **five** distinct LED event counters (568–572), with delays 392, 84, 401, 281, 405 μs. The subsequent 80-snapshot probe is the statistical basis for this report. Any earlier statement calling that initial probe "six distinct beats" was an overcount.

## Attempts at direct digital audible waveform acquisition

The Mac mini's real audio-device inventory showed **HX Stomp**, with 8 input/8 output USB channels at 48 kHz, and **Behringer FLOW 8 (Recording)** with 10 input/4 output USB channels at 48 kHz. To try measuring actual click onset, the existing `ffmpeg` AVFoundation input interface was used without changing HX Stomp settings, macOS microphone permissions, audio routing or hardware connection:

- Captured ~4.47s to WAV from HX Stomp via USB, downmixed to two channels; decoded to float32: **both channels all zero**.
- Captured ~3.61s direct HX Stomp USB 8-channel float32 recording: **all eight channels all zero**.
- Captured ~3.57s direct FLOW 8 USB 10-channel float32 recording: **all ten channels all zero**.

These recordings contain **no nonzero click samples**, so there is no audio onset to timestamp. We cannot determine from these samples alone whether audio was routed elsewhere, the interfaces were muted, or a macOS input-capture/privacy limitation caused the zeros. Do not claim either root cause without new evidence. The short captures were kept only in temporary `/tmp` paths, and are not part of the firmware release or data evidence. The created `tools/metro_r03c_audio_waveform.py` provides reproducible sample energy diagnostics, with no pedal writes.

For true **optical FS3 LED→audible click** offset with precision sufficient to assess perceptible lag, capture the physical optical transition and the click audio waveform with synchronized timing. One robust setup would be a photodiode watching FS3 TAP and HX Stomp audio output into two channels of the same external audio ADC. A synchronized video showing actual LED and capturing the speaker click could provide a rougher estimate. A later purely firmware-based M4→SHARC receive acknowledgement can isolate extra internal transport stages but still cannot replace physical optical/acoustic measurement.

## Acceptance state

- **Confirmed on hardware:** R03C boots; full 41C editor responsiveness; M4 visible-LED event counter moves consistently; user reports duplicate clicking gone.
- **Measured on hardware:** 23 LED events, M4 LED-command→first M4 SPI TX callback median 0.165ms, max 0.419ms at approximately 100.01 BPM; zero M4 packet consistency anomalies in 80 snapshots.
- **Still unverified:** actual optical→audio onset milliseconds, true SHARC receive and speaker/headphone buffering delay, full bypass/engage hardware parity, DSP Usage Display numbers and USB Monitor behavior in R03C.
- **Version policy:** preserve R03C as a major **duplicate-free working baseline**. Continue lag investigation on a **new distinct experimental branch**, not by modifying the major working source or changing the user's installed configuration. No new RAM load or firmware installation is needed to label/preserve this version.

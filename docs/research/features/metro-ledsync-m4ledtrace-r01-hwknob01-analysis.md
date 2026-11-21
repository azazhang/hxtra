# METRO-LEDSYNC-M4LEDTRACE-R01-HWKNOB01 — live BPM-change timing findings

**Status:** Completed hardware read-only capture, process stopped, source trace recovered, analysis reproduced, live editor and exact R01 USB signature rechecked. Hardware revision remains the same RAM-only M4LEDTRACE-R01; no new HXF, no SHARC patch, no saved settings or eMMC modification in this test.

## Provenance and data

- User confirmed new `METRO-LEDSYNC-M4LEDTRACE-R01` physically booted before the test. The Mac mini `hx_ctl.py status` responded before/after, displaying preset 41C (`setlist 0 preset 122 "Super Lead"`) with the eight expected signal chain blocks.
- Exact R01 read-only USB editor command `0x50` signature `0x31474c4d` was verified on-device. This is stronger than a successful WebUSB RAM-upload CRC. The M4 producer timestamps the final post-visibility-filter LED command, prior to light driver hardware output, via the stock 1-us timer `0x28da6458`. It records both visible-colour ON and OFF transitions and 32-bit event sequences in a 16-slot circular buffer.
- Host started bounded `tools/metro_ledtrace_r01_probe.py --samples 720 --interval .25` on Mac mini, stopped it after the user confirmed BPM-knob testing completed. Host sampler PID `97880` has terminated. This was **read-only** and did not change BPM or pedals settings programmatically.
- Raw capture `tests/hardware_evidence/METRO-LEDSYNC-M4LEDTRACE-R01-HWKNOB01-live.jsonl`: SHA256 `10066d19381694172983763b03b4af308ea98db2a80c035ead09da3a6f1f8671`, 659 JSONL records, host-sample elapsed 168.2668 s. The earliest sequence in the rolling buffer predates the first host query by a few seconds, which explains the LED-edge timestamp relative range of ~172.24 s.
- Complete deduplicated event range **380..999 inclusive (620 transitions)**, 310 ON and 310 OFF. All sequence IDs present, all alternating, no repeated-record timestamp conflicts and no unstable/rejected USB samples. This establishes no lost *observed M4 command events* in this capture. It does **not** rule out physical LED-driver losses or unseen acoustic issues.
- Source-grounded/reproducible analysis: `tools/analyze_metro_ledtrace_r01.py` produces `tests/hardware_evidence/METRO-LEDSYNC-M4LEDTRACE-R01-HWKNOB01-analysis.json`. Fixed rising-edge windows were identified manually from the stable period plateaus after examining the data, then tested numerically via OLS regression of event timestamp on contiguous beat index. These windows are **descriptive selections**, not a prespecified changepoint detector.

## Fixed-tempo stability

| Window rising seq | Approximate BPM, via OLS period | OLS beat period (ms) | RMS residual to fitted metronomic grid (ms) | Rising events |
| --- | ---: | ---: | ---: | ---: |
| 381..815, before edits | 110.0916 | 545.00076 | 0.3829 | 218 |
| 831..845 | 102.9203 | 582.97542 | 0.2187 | 8 |
| 853..871 | 93.8921 | 639.03165 | 0.1716 | 10 |
| 883..895 | 69.2058 | 866.97907 | 0.2489 | 7 |
| 907..917 | 56.2337 | 1066.97543 | 0.2160 | 6 |
| 939..999, after edits | 164.8387 | 363.99227 | 0.2524 | 31 |

The timing within stable plateaus is excellent. The long 110-BPM window spans about 118 seconds and has 0.383ms RMS residual against its *own* fitted period. The 165-BPM window also remains stable after rapid knob adjustments. This is M4 LED-command clock stability, **not** an LED/audio phase offset or proof that R02B2's DSP click was stable.

## Behavior at physical BPM changes: real phase discontinuities

The trace directly exhibits large *transient* ON-to-ON interval changes between these stable plateaus. The entire recording has a minimum ON-to-ON of **322.836 ms** and maximum of **1591.358 ms**.

Example: last 110-BPM stable ON seq815 and next ON seq817 were 322.836ms apart. The old stable period predicts 545.000756ms. The next ON arrived **222.164756ms earlier** than the extrapolated old LED beat. This is a measurable phase discontinuity of the *LED command clock*. A software metronome that simply updates its own BPM while keeping its prior phase will therefore **not** remain in phase. The exact instant of the user's knob movement was not independently timestamped, so the firmware subroutine responsible for this reset has not been uniquely identified.

Several rapid OFF→ON reversals occurred at the transition epochs:

| ON sequence | t since first observed command (s) | preceding LED dark command interval (ms) |
| --- | ---: | ---: |
| 819 | 119.381 | 8.029 |
| 821 | 119.960 | 9.129 |
| 823 | 120.538 | 7.189 |
| 849 | 128.131 | 16.159 |
| 899 | 146.948 | **1.870** |
| 919 | 157.560 | 9.335 |

These are valid, non-torn M4 events, clustered around the user's tempo adjustment session. A dark interval as short as 1.870ms may not register as a distinct visible LED OFF interval, depending on physical LED-controller timing and human visual integration. Thus a DSP clock slaved blindly to *every* OFF→ON M4 command could issue a click when no separate optical flash is perceptible. A universal filter threshold must not be hard-coded without physical/light validation. Conversely, rejecting a valid short OFF interval when the LED is actually visibly blinking could skip an intended beat.

The native firmware has two relevant timing mechanisms in the previously recovered donor disassembly: logical stock TAP beat task `0x28d9bdfc` and driver-managed LED blink mode controlled around `0x28db7f04`/period setter `0x28d9bef8`. The short OFF→ON commands and altered intervals are consistent with a timing mode or period update, but the trace alone does not distinguish which implementation path produced each event. It establishes the downstream events which any click-synchronization approach needs to handle.

## Engineering implications

1. The post-filter M4 LED command is the correct practical internal observation boundary to *start* with: it survives the exact donor boot, responds across actual BPM edits, and its timestamp stream is internally consistent. The old logical TAP callback was too early to guarantee final LED output.
2. Any SHARC click synchronized to LED commands must use explicitly validated event ordering and phase resets. Pure local DSP tempo extrapolation from prior beat duration is insufficient across these updates. It can produce the R02B2-style phase error observed by the user, although **the new R01 trace does not establish this as the sole cause**.
3. An M4 producer should distinguish long enough actual dark→lit periods from barely perceptible OFF→ON churn **only after calibrating physical visibility**, while still preserving the true phase of the next visible flash. The protocol needs a monotone counter, valid checksum across all fields, coherent snapshots and a defined bypass/loss-of-LED-mode policy.
4. The next SHARC implementation still faces a separate startup failure class: R02C, HWFAIL02 and HWFAIL03 all froze with altered SHARC Entry2 bootstreams. **Do not reuse R02D untested.** First prove an in-place patch that preserves original loader descriptor order, Entry2 length, and all unchanged content, or a demonstrably safe after-boot PM patch. The M4 R01 boot success eliminates the SHARC rewrite from this experiment but does not fix that problem.
5. Once an audio variant passes a real startup control and restores DSP Usage Display/USB Monitor feature parity, measure the audio transient against optical FS3 flashes (or at least M4 LED event timestamps with a calibrated audio capture). The present R01 trace cannot assert acoustic synchronization.

## Verification and remaining uncertainty

- Physical startup and editor USB: **passed** by user report plus Mac mini independent checks.
- Exact donor feature parity: Entries1..14 unchanged and donor M4 otherwise preserved offline; physical DSP percentage display and USB Monitor behavior not separately tested by the user in this run.
- Read-only LED timing and no data gaps: **passed** across 659 samples/620 transitions.
- Phase jumps during tempo changes: **observed**. No claim of accumulating drift at fixed BPM.
- Optical LED latency/dark-pulse visibility: **unmeasured**.
- Sound/LED metronome phase: **unmeasured** (SHARC click engine untouched).
- M4-to-SHARC integrity/SHARC boot safety: still a separate unvalidated design and test requirement.

The physical pedal remained responsive after the capture, with exact R01 USB revision still detected and the editor still returning 41C; no recorder process left running.

# R09: direct SHARC sample peak meters

RAM-only candidate. Exact frozen R03C installed donor SHA256 42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b. Candidate HXF SHA256 9c414ad9fcb238a2550445c37b42de0cc9f8eeb0c7b79f6f3a06e32c015425bc; plan SHA256 cf5f3d6bb48550cd95a8e7c9ec167cfa429d092db1de650ac00852adfc13a556.

## Implementation

Input peak uses the existing armed input-sidechain wrapper around 0x2390 (after the analog input jack reader, before gating). Output peak uses the existing Main output writer wrapper 0x2aa8, before the stock conversion/writer. Input and Main L/R magnitudes are accumulated separately. One sequence per 64 stereo 16-sample blocks (1024 samples/channel; 21.333 ms at 48 kHz). The output cumulative hot-window count is independent of M4/host sampling. The selected input path is the existing guitar-input sidechain capture; Main refers to the DSP Main jack writer, not universal Send/USB routing or an externally calibrated analog voltage.

The SHARC publishes tag, sequence, peaks, input call count, cumulative hot-window count and XOR-complement in words 224–230 of the statically identified TX DMA buffers c3eb6 and c3fb6. Guard header/trailer and native payload length before touching tail; commit tag last. M4 rejects wrong tags, checksum errors, invalid amplitudes and nonadvancing sequences, counts gaps, latches the interval's actual peaks and displays two independent 16-segment scales. Stale data expires. No native-meter or TAP-based fallback. Original R05 native ledger remains available on 0x13; 0x1d returns unique IOR9 signature, direct source sequence, producer and consumer counts, gaps and paint telemetry. The original R03C Home/GR chain is retained, followed by the new display only. The host audit compares direct-window evidence against native reports and observed TAP intervals without changing settings or recording raw audio.

## Exact donor and QA

- Entry2 remains 524212 bytes. The all-zero 796-word NAM scratch initialization record is replaced by an equal-size sequence of zero-fill prefix, new nonoverlapping DM and PM sections, and explicit zero tail. All following record byte offsets preserved. Exact two original PM instruction changes at e4f6f and e503c; original metronome unchanged. Added code and state fit the original free Block 3 interval with the two-NAM-slot allocation preserved.
- M4 only three existing hook sites and appended code; M0 identical. All other 13 archive entries identical to R03C. Candidate packed/unpacked roundtrip and archive verification pass.
- 183 regression tests passed, including positive and negative impulses at every position in a 16-sample block, stock Main output audio and state parity in all four USB output modes and circular-buffer modes, preserved stereo sidechain state, transport guards and checksums, duplicate/stale/missing sequence handling, independent peak hold and safe display geometry, and earlier meter regressions.
- RAM overlay reconstructs all 1025 SHARC sectors (header + payload) exactly, changes five payload sectors and header, validates two installed-image CRC checks, nine RAM regions, writes=ram. All deployed files match SHA256 on Mac mini; page and plan HTTP 200. Read-only audit script deployed.
- Physical boot, TX egress and coverage remain to be established on hardware. No device access, permanent write or preset/settings edit performed by builder/stager. User-initiated RAM load only; power-cycle restores installed firmware. Do not flash.

Mac mini: http://localhost:8765/IO-LEVEL-R09-DIRECT-SHARC-PEAK-METERS/

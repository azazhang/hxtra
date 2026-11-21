# METRO-LEDSYNC-M4LEDTRACE-R01 — donor-preserving LED edge timestamp probe

**Later hardware update (2026-11-20):** R01 subsequently booted successfully on the physical HX Stomp and passed USB editor / diagnostic identity checks; the read-only HWKNOB01 physical BPM-adjustment capture produced 659 valid samples and 620 consecutive LED command transitions. Stable tempo phases were sub-millisecond RMS, but large phase discontinuities and six OFF→ON gaps below 20 ms appeared during BPM adjustments. Full reproducible evidence: [METRO-LEDSYNC-M4LEDTRACE-R01-HWKNOB01](metro-ledsync-m4ledtrace-r01-hwknob01-analysis.md). All statements below about a not-yet-tested image are preserved as the historical *stage QA* snapshot taken before the successful HWBOOT01 and HWKNOB01 tests; they no longer describe the latest hardware state.

**State:** versioned, reproducible **offline-built**, independently re-tested, staged on Mac mini Chrome at **Ready**; **NO physical RAM run has occurred for R01**. Supersedes R02C/HWFAIL02/HWFAIL03 as the next *diagnostic* only. No permanent firmware writes. All records herein refer to this exact version.

## Purpose / unchanged user requirements

The user wants internal HXtra 1.2.1 Metronome quarter-note audio synchronized to the actual FS3 TAP LED during successive BPM knob changes, with correct accented downbeat after bypass/re-engage, and **every exact installed donor feature retained**, including DSP Usage Display, USB Monitor, model browser, global settings and 41C preset. Previous R02C/HWFAIL02/HWFAIL03 SHARC-bearing builds froze on startup. R02B2 booted and transmitted M4→SHARC events, but the user observed click/LED drift after BPM changes, and that rebuild did not preserve the donor's entire feature selection. See `metro-ledsync-hwfail03-independent-reassessment.md` for the cause analysis and reproduced checksum/fallback faults.

R01 is an **M4-only read-only telemetry probe**, not an audible synchronization fix. It identifies and timestamps the *final post-visibility-filter LED controller requests*. It neither modifies the SHARC/Metronome nor sends SPI telemetry nor changes a bypass handler, preset, or saved setting.

## Exact source and artifact identities

- Pinned installed reference `/Users/friend/Downloads/HXtra_v1.2.1.hxf`: SHA256 `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0` (MD5 `93969635834cd6050dec7f137df1e4b9`).
- Candidate name `METRO-LEDSYNC-M4LEDTRACE-R01`.
- Final HXF SHA256: `819343be4aa5cbd29b8e400941a1cca635e2ed9fa835d31b8b936337a6120d99`.
- Final L6IA SHA256: `4e789b4216fa29abeb53fa2a8c8e6010a31073fa32cd64fb6253b07cabcfe1c7`.
- RAM `regions/plan.json` SHA256: `0dae726091e84866c7ea9014560ab4e962978a0fb26def7e68b3eca2b08a9b79`.
- WebUSB `ramrun.js` SHA256 `8ae54c645dbb41c641a8c5c03cde25b19679dec8cd694d337ef5828a6a5601d7` (byte-identical to the previously used donor positive-control browser runner).
- DFU `firmware-ramboot.dfu` SHA256 `59efb032d61d7901c549271fa0a6e147683e08b0eeb1e7812b5e2681b2862931`.
- Exact changed firmware entries: **Entry0 M4 only**. Entries 1–14 are byte-identical to donor (including original almost-full SHARC Entry2, original DSP models and USB routing).
- Exact overwritten *original M4 code* sites: `0x28d98f78` (LED sender continuation, following HX_BPM final visibility filter) and `0x28d96adc` (original editor registration BL). All other original M4 bytes match the donor outside image metadata. **616 appended M4 bytes**.
- Nine RAM upload regions; `overlay_sectors=0`, `runs=0`, `writes=ram`, no eMMC app writes. Additional donor-reference read-only CRC check: sector 34819, count 1023, CRC32 3485190247. Prior loader runs returned `0x10b` and skipped actual eMMC verification, so this *cannot be claimed as a device-verified checksum until the loader succeeds*.

Two independently generated HXF and RAM plan artifacts were compared byte-for-byte and matched. HXF repack/unpack and L6IA CRC/Fletcher integrity also verified. The SHA-pinned donor remains unmodified on disk.

## Architectural probe

- `src/m4/metro_ledtrace_r01.s`: wraps the donor post-filter FS3 LED-send continuation. Receives final RGB requests, records only FS3 TAP dark→lit and lit→dark transitions, ignores repeated colour while lit and other footswitches. Uses **exact original M4 microsecond timer** `0x28da6458()` (tail-branch to register reader `0x28da37ac(1)`), which the stock tempo/task logic also uses.
- The ISR/hot path contains no settings mutations, locks or VFP. Timestamp capture adds bounded, in-memory operations. A 16-transition ring holds `{uint32_t micros,uint32_t (sequence<<1 | lit)}`. It can diagnose LED command intervals and mode-2 BPM transient behavior, including duty cycle. It **does not directly measure emitted light photons or audio timing**.
- USB editor command `0x50` returns MessagePack BIN8 of 148 bytes: 4-word header (sentinel `0x31474c4d` / `MLG1`, writer generation, event count, current LED state), 16 paired timestamp/sequence records, final generation. The producer uses odd/even generation and a memory barrier around each ring mutation. The reader obtains an atomic generation before copying and appends another generation after copying, so inconsistent samples are rejected. No SPI buffer modifications.
- `tools/metro_ledtrace_r01_probe.py` validates exact signature, payload length, generation stability, ring sequence coherence, LED states, and 32-bit microsecond wrap; it emits read-only timestamped JSONL samples.
- **Important extra correction from real full-firmware emulation:** the donor LED sender can enter the hook with SP modulo 8 equal to 4. The initial standalone M4 test started on an aligned SP and missed this. R01 now pads its stack **conditionally** around the nested clock call, restoring the original SP exactly before resuming the original donor LED code. Full-path Unicorn tests confirmed identical original/modified sender return PC/SP and LED hardware continuation in six input modes. The assembled-code smoke test also checks stack alignment at the original clock call.

## Tests and limitations

Focused new tests `test_metro_ledtrace_r01.py` (8) and `test_metro_ledtrace_r01_fullpath.py` (7) **15/15 passed**. Together they cover exact donor changed-site audit, actual executable M4 Thumb semantics, timing record order/clock rollover and wrap, TAP/other-footswitch distinctions, USB packet decode, torn-snapshot rejection, original sender continuation, and adaptive stack alignment in the full rebuilt donor.

Final combined relevant suite across R01, inherited R02C M4 full-path, R02A, RAM loader and the previously found SHARC defects: **52 passed, 1 skipped** (no HX_STOMP_HXF env var), **1 deselected** (`test_built_files_match_source`: installed ARM GCC lacks `nano.specs`), **2 xfailed** (the confirmed R02C/R02D SHARC checksum bugs remain unresolved and are absent from R01). Earlier unfiltered run showed that one loader-rebuild test fails specifically because `arm-none-eabi-gcc` cannot read `nano.specs`; the unchanged prebuilt DFU loader bytes are the same used by the passing donor RAM positive control.

No simulated test proves real M4 UI boot, real optical phase, audio click phase, or hardware timing continuity under BPM edits.

## Mac mini state, browser, next hardware acceptance

Staged read-only assets in `~/Projects/hxtra-metronome-test/build/browser-ramrun/METRO-LEDSYNC-M4LEDTRACE-R01/`. The local webserver serves `http://localhost:8765/METRO-LEDSYNC-M4LEDTRACE-R01/?build=819343be`. Chrome tab was refreshed after final binary sync; live read-only DOM query reports `stage=Ready`, `runDisabled=false`, 9 RAM regions (1.00 MiB), 1 read-only eMMC check and RAM-only writes. All versioned asset SHA256 hashes and plan structure were verified on the remote Mac mini. The new USB decoder was copied to the Mac mini's `tools/` and its import verified.

After HWFAIL03, the user independently physically power-cycled; a subsequent read-only HX editor `status` response returned 41C / `Super Lead` / all eight expected blocks, with Metronome as last block bypassed. This verifies pedal responsiveness before R01, though it does not independently establish every visual global setting.

**User-initiated physical test only**: choose the already-open `METRO-LEDSYNC-M4LEDTRACE-R01` page and click Run; Chrome may request the device during the WebUSB sequence. After run, verify actual pedal UI and editor SYN (ordinary `hx_ctl.py status`), then query `tools/metro_ledtrace_r01_probe.py --samples 40 --interval .25` using read-only USB, while user changes actual BPM knob. If it freezes, record actual frozen behavior and browser log and power-cycle; do not retry an old R02C/SHARC-bearing build. If it boots, identify R01 by its exact `0x50` signature, check DSP percentages/USB Monitor, and evaluate ON/OFF timing before considering any SHARC change.

**R01 has not yet been physically run or acoustically validated. No new firmware was flashed permanently.**

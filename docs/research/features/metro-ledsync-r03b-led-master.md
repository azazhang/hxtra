# METRO-LEDSYNC-R03B-LED-MASTER — donor-preserving M4→SHARC LED-master implementation

Date: 2026-11-20 (America/New_York). **Status: offline/StageQA00 validated; WebUSB staged Ready on Mac mini. No physical R03B load or synchronization acceptance yet.** Firmware changes are explicitly **RAM-only** and only initiated by the user.

## Purpose and starting physical controls

User's requirement: the internal Metronome block (model 181, preset 41C "Super Lead", signal grid8 / path0 slot7) must sound quarter-note clicks synchronized with the *actually displayed FS3 TAP LED*, even during repeated BPM changes, while preserving exact installed HXtra v1.2.1, its additional features including DSP Usage Display and USB Monitor, presets/settings and normal native function.

Known, verified controls:

- Pinned installed HXF `~/Downloads/HXtra_v1.2.1.hxf`, SHA256 `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`.
- R01's physical read-only M4 LED command trace: **620 contiguous ON/OFF transitions**, **310 ON**, six OFF→ON dark intervals under 20 ms (1.870, 7.189, 8.029, 9.129, 9.335, 16.159 ms), stable period plateaus 110/103/94/69/56/165 BPM, and a **−222.165ms phase jump** relative to the old 110 BPM beat after the knob moved. Only the M4 post-filter LED command was timestamped; optical latency and sound were not measured.
- Physical R03A SHARC-only in-place boot: WebUSB RAM handoff and independent editor SYN/preset-41C query succeeded. User subsequently reported **"behave like orignal HXtra firmware. click not synced."** This supports the audible native-shape kernel running on physical SHARC; lack of sync was expected because R03A's donor M4 lacked any LED event transmitter. It does not by itself quantify timing or independently check DSP percentage graphics and USB Monitor.
- Older R02C/HWFAIL02/HWFAIL03 SHARC-expanded/descriptor-altered images froze startup. R02D retained the unsupported LDR descriptor mergers and ignored SPI checksum; not advanced.
- Original R03A code initially showed a dual-issue register-alias bug (F1/R1) during development; it was fixed before the user tested R03A. In the *new R03B* source, a similar early-fusion bug was exposed by parity tests and removed before staging; F1 is now loaded after the final R1 write, merged with R9=NOT R8. These tests explicitly include 2nd/3rd callback oscillator state to rule out first-beat false positives.

## R03B architecture implemented

The M4 source `src/m4/metronome_led_r03b.s` derives from original donor-targeted R02C M4 egress hooks and reuses the proven R01 1-microsecond timer and stack-alignment treatment. Its event origin is the **post-visibility-filter final FS3 LED RGB command**, with TAP function byte checked. The handler deduplicates redundant LED sends and colours, and records the most recent full OFF timestamp. The subsequent ON is accepted only when the preceding dark interval was at least **20,000 microseconds**. First ON without a prior OFF is accepted. A 32bit modulo timestamp subtraction handles timer rollover. The 20ms threshold is a *deliberate engineering heuristic* based on six R01 physical command intervals; optical visibility was not independently measured and changing this threshold requires further hardware analysis.

The M4 original Metronome grid8 bypass setter is chained, preserving normal donor logic. It suppresses published events when bypassed. On transition from bypassed to engaged, it marks the next accepted LED ON for a bar accent reset. Repeated redundant "engage" calls do not re-reset accent.

On each valid stock SPI TX frame after the existing donor callback executes and only when payload word count is <=230, M4 writes **word240: full unsigned 32bit LED counter with epoch bit31**, and **word241: bitwise complement (~counter)**. Counter word is committed last, after an initial invalidation, a complement store and a memory barrier. First idle valid master state is `0x00000000,0xffffffff` (no premature click). When TAP assignment/LED visibility is unavailable, M4 explicitly publishes `(0,0)` so the SHARC can fall back to the original donor local Time click; irrelevant SPI frames are never modified and are counted as skipped.

The SHARC source `src/sharc/click_led_r03b_inplace.asm` retains the **original 142-instruction PM metronome record exactly in shape** at `0xe5386`, replacing only its instruction payload. The original 201 LDR records retain identical tags, lengths, addresses, ordering, prefix and FINAL_INIT tail. The donor's 145-word instance layout is preserved. On each 16-sample DSP callback, the receiver loads the two aligned SPI RX words at DM `0xc3da6` and `+1`, validates **the complete 32-bit complement relationship** before using event data, detects event-count changes, suppresses free-running local click when the master is present, and triggers a click on the next DSP block. A toggle in bit31 of the received event difference resets the accent bar state. Invalid **nonzero** frames suppress local beats until valid sync returns; explicit invalid `(0,0)` restores native donor local Time behavior. The combination was verified as actual assembled SHARC instructions in `ssim`; corrupt/mismatched or torn payload/checksum combinations fail to trigger new clicks.

The checksum is a **complement consistency check**, not cryptographic authentication or a full error-detecting CRC polynomial. Correlated simultaneous corruption of both words preserving the complement would pass; do not claim absolute protection against all corruption. Nor has hardware SPI receiver timing, physical optical phase or sample-level latency been measured. This is the first real combined audio-sync hardware candidate. There is no SHARC-to-M4 consumption acknowledgement in this image; the USB command reports only M4-side TX events.

## Exact donor and bootstream invariant

The output HXF was rebuilt from the exact installed donor and independently reloaded. Only L6IA entries **0 (M4 application)** and **2 (SHARC bootstream)** differ. All other 13 entries are byte-identical, preserving installed NAM, models, FX, USB Monitor, settings and other features.

- Original M4 code/data bytes changed only at four audited hook sites: `0x28d98f78` (final LED command), `0x28e045a0` (bypass setter entry), `0x28d96adc` (editor command registration chain) and `0x28da6138` (SPI TX callback pointer). New Thumb code is appended through original patcher; original DSP Usage Display and menu strings survive byte-for-byte.
- SHARC Entry2 original and new length **524212 bytes** with original **201 LDR blocks**, original process-code LDR block **#177**, **142 program words**. Only the instructions *inside this existing block* differ. Final instruction is an unreachable NOP after the last RTS to retain original record footprint; no new boot records, no descriptor merges, no relocated M4 code or user settings.
- HXF SHA256: `d1c9669734eecd928fbaecc82722b5d69c71ff40c1fcab15a1396d61e9053e6c`; L6IA SHA256 `5f46843ff7ee8da25e80206dcb91afb1c423257f7c470bb82fe78077c45396e2`.
- SHARC metadata header at eMMC sector **`0x8802`** reports *unchanged* length 524212 bytes and correct new CRC32 **`0x4051cf14`** (donor CRC32 `0xc273d05e`). This sector is served from a **RAM overlay**, never written persistently.
- The *genuinely different* payload sectors are zero-indexed **1004, 1005**. An unchanged 436-byte final partial payload sector 1023 is also placed in overlay due to 512-byte padding required by the loader. Thus **4 overlaid sectors** in **3 runs** including header; 9 RAM regions; 1 donor eMMC reference CRC (sector 34819, 1023 sectors, CRC32 3485190247). The entire header+1024 payload sector stream was reconstructed from the staged overlay table and verified against candidate HXF by tests.
- RAM plan SHA256 `8d9d839069dd849d9b86b200a6044e55429641457ab3a6545e4698843421ade2`. Mode `writes=ram`.
- Unmodified working donor-control WebUSB loader SHA256 `59efb032d61d7901c549271fa0a6e147683e08b0eeb1e7812b5e2681b2862931`, unchanged `ramrun.js` SHA256 `8ae54c645dbb41c641a8c5c03cde25b19679dec8cd694d337ef5828a6a5601d7`.
- Staged HTML SHA256 `40239d173bb23ca64924cc7bb1b67a6b64fccaf0963a9d7c703c0e6499705631`.

## Offline QA, physical trace replay, acceptance limits

`tests/test_metro_led_r03b_transport.py` assembles and executes the **real** M4 Thumb callbacks in a Unicorn M4 emulator, including original 1-us timer stub, final FS3 RGB bus signal and post-original SPI framing. It executes the **real** 142-PM-word SHARC process code in the project `ssim` simulator, including fully checked event/complement pairs and 16-sample audio blocks.

Passed focused tests: native donor bit-exact audio across 11 valid Time/Level/Accent/Thru sets with disabled M4 mode; real M4 counter→actual SHARC sound transient with accent at 2000Hz and ordinary at 1000Hz; no new clicks with valid idle count or absent events even after multiple free-running Time intervals; failed complement including deliberately corrupted 32bit integrity values and random single-bit flips is rejected; DSP bar accent resets on bit31 epoch; bypass and redundant engage; noTAP/hiddenLED local fallbacks; SPI frame-length guard; and actual 620-event physical R01 trace replay that filters exactly six dark gaps and produces 304 accepted commands. In-place binary and reconstructed RAM overlay plus diagnostic USB identity tests also passed.

**These tests establish deterministic software behavior and structural byte-level invariants.** They do **not** prove the combined firmware boots on physical HX Stomp, that a valid M4 SPI pair arrives at SHARC at each LED flash, that the DSP remains within CPU limits, that the optical LED is perceptible after short dark-gap filtering, or that audible click and optical LED remain phase-locked after real knob adjustments. All these are future physical acceptance checks. The actual optical command may lag the M4 callback and the audio has finite SPI + 16-sample block latency.

## Mac mini staging and test procedure

New user-driven Chrome tab opened on the Mac mini:

`http://localhost:8765/METRO-LEDSYNC-R03B-LED-MASTER/?build=d1c96697`

A read-only DOM query independently returned `stage=Ready`, `runDisabled=false`, `WebUSB available; 9 regions (1.00 MiB), 1 eMMC checks; RAM-only writes`, with the correct R03B four-sector preflight. The server returned HTTP 200 and all copied stage asset hashes matched local build hashes. **No R03B hardware RUN has been attempted or initiated by this work.** The physical unit still answered regular HXtra editor preset 41C on the old R03A image after staging. To proceed, the user controls the RAM-only Chrome button and device chooser.

After user-initiated RAM load, verify in order: (a) physical LCD normal boot, USB editor response and preset 41C, (b) DSP Usage numbers and USB Monitor still functioning, (c) engaged Metronome click audible and approximately phase-locked with visible FS3 TAP flash at stable tempo, (d) multiple substantial physical BPM knob changes followed by multi-beat observation at each, (e) bypass and re-engage sound/accent without a ghost click. The `tools/metro_led_r03b_probe.py` USB 0x50 diagnostic can report M4-received LED counter, short reversals filtered, SPI pairs stamped and actual latest written pair with full complement check. These values must **not** be misreported as SHARC acknowledgement or acoustic phase verification.

A WebUSB RAM transfer log can prove only upload and handoff; actual pedal startup and audible phase require independent hardware observations. If frozen, preserve browser log and power-cycle. Do not permanently install or retry a previously failed SHARC LDR-expansion image.

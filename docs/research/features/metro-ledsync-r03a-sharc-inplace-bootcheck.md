# METRO-LEDSYNC-R03A-SHARC-INPLACE-BOOTCHECK — SHARC record-topology isolation

**Created:** 2026-11-20, America/New_York. **State:** offline StageQA00 was followed by **successful physical R03A RAM handoff and confirmed M4/editor boot** (HWBOOT01), with acoustic SHARC metronome processing and physical DSP usage numbers still unverified. Supersedes R02C/HWFAIL02/HWFAIL03/R02D as the current **SHARC-only startup experiment**. R01 was running at staging time and was replaced in RAM by R03A at HWBOOT01. This is not a functional LED/audio synchronization firmware.

## HWBOOT01 — independently verified after physical RAM load

The user reported **loaded**. Mac mini Chrome WebUSB showed `R03A SHARC in-place RAM handoff reported`, with all listed payload transfers reporting CRC success and a terminal `started: the firmware runs from RAM` log. A separate read-only Mac mini USB/editor request returned `setlist 0 preset 122 "Super Lead"` with its original eight blocks, including Metronome model 181 slot7 bypassed. macOS `ioreg` enumerated an active HX Stomp USB device. This is **hardware evidence that the firmware M4 booted, the editor services are live, and the M4 can return the stored preset**. Because the Metronome was bypassed, this **does not establish SHARC audio DSP execution**, audible clicks, correct accent, or feature-display parity. Do not claim those are proven before direct physical verification. Exact observations are saved in `tests/hardware_evidence/METRO-LEDSYNC-R03A-SHARC-INPLACE-HWBOOT01-20261120.json`. The original WebUSB transfer validates region transmission, not independent eMMC/SHARC execution.

The tag for StageQA00 records earlier offline conditions and remains historical; do not relabel it as post-hardware validation.

## Goal and unchanged constraints

Implement HXtra v1.2.1 internal Metronome block audio clicks accurately following final FS3 TAP ring flashes through repeated knob BPM adjustments, with accent/bypass reset and full installed donor feature parity (DSP Usage %, USB Monitor, other custom features). Preserve user settings/presets and use RAM-only experimental loads. Earlier SHARC-bearing R02C/HWFAIL02/HWFAIL03 variants froze at startup, unlike untouched-donor or M4-only R01. R02D's seven reordered/merged boot records are untested and explicitly disallowed as a presumptive fix.

Pinned source: `~/Downloads/HXtra_v1.2.1.hxf`, SHA256 `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`, MD5 `93969635834cd6050dec7f137df1e4b9`.

## Independently verified SHARC boot structure

Original L6IA Entry2 comprises exactly 524212 bytes (76-byte partition headroom), containing **201 ordered LDR records**. The original metronome is LDR record **#177**, `INIT_L48` block of exactly 142 PM instructions at word address `0xe5386`. Its compiled code is identical to the historical v1.2.1 source `git show df327d5:src/sharc/click.asm`; this is asserted byte-for-byte against the installed firmware.

R03A regenerates code from that original source; SHARC dual-issued ALU+DM operations and valid model-domain simplifications (Accent integer 1..12; Thru boolean 0/1) free exactly enough instruction slots for a 15-instruction in-line event listener. A first attempt incorrectly used R1–R5 as scratch and clobbered already-hoisted float oscillator state, causing audible output equivalence test failures; it was corrected to scratch **R8–R11**, and the original exact bitwise audio output tests then pass over valid parameter domains, dynamic knob adjustments and 16-sample callbacks. No existing donor kernel memory-save/restore convention was removed.

R03A **only** replaces the 142 PM instruction data inside original record #177 (41 instruction words differ). All 201 LDR tags/lengths/base-address fields, record order, leading prefix and final tail are byte-identical; Entry2 remains exactly 524212 bytes. The M4 Entry0 is **bit-identical to the actual installed donor**, as are every other non-SHARC L6IA entry (14 unchanged entries). All additional SHARC program and data blocks are untouched.

The experimental receiver reads a *single* 32-bit aligned SPI M4→SHARC DM word `0xc3da6`, with a high-byte sentinel `0xA5` and a 24-bit event counter/epoch. Zero/absent packet means the original local free-running Time behavior; a valid zero-event packet suppresses local clicks; changed event counter generates click at the next 16-sample callback; epoch bit triggers accented downbeat. **Protocol security and robustness are incomplete**: there is currently only an 8-bit marker, no full integrity checksum, no M4 sender in this SHARC-only candidate, no tested lock-loss hysteresis, and no physical visibility/short-OFF interval filter. This cannot be considered final synchronization. Its purpose is *exclusively* the previous boot-freeze causal isolation.

## Binary, packaging, metadata and RAM overlay

- Firmware ID: `METRO-LEDSYNC-R03A-SHARC-INPLACE-BOOTCHECK`.
- Candidate HXF SHA256: `1b937f3f862d2e88138d872c0bb3c68913e412605f0655f535ec2da6f8524c78`.
- L6IA SHA256: `a148fe1a52cdf075b9bd148fca8bdc00ae2449b7e9ffa0bccc29f4e6f69bf083`.
- The SHARC payload's revised CRC header `0xdaa2f172` (previous `0xc273d05e`) and unchanged length **524212** are contained in a RAM-only overlay at on-card sector **`0x8802`**.
- The only *truly changed* 512-byte SHARC payload sector is zero-indexed **1004**, corresponding to original kernel record #177 (the donor's last partial payload sector 1023 is byte-identical before normal RAM zero padding).
- Runtime RAM loader's overlay table includes exactly three sectors: 1 metadata header; 1 changed PM payload; and 1 unchanged but padded last 436-byte SHARC payload fragment. The latter appears because `hxf_ram.overlay()` pads the final fragment to 512 bytes. Number of actual source payload sectors altered in HXF: **1**.
- Three sorted, non-overlapping overlay runs, nine staged SDRAM regions, and one read-only donor reference eMMC checksum: sector **34819**, count **1023**, CRC32 **3485190247**; all modifications use `writes=ram`. eMMC read-only CRC may be skipped by a previous `0x10b` loader status and must not be represented as actually verified on unit unless observed at runtime.
- RAM plan SHA256: `f4ee574a22cae9daecf6f4d7917249414b998711d4081176a55017fc96efba2a`.
- Unchanged successful donor-control WebUSB loader SHA256: `59efb032d61d7901c549271fa0a6e147683e08b0eeb1e7812b5e2681b2862931`.
- Unchanged donor-control `ramrun.js` SHA256: `8ae54c645dbb41c641a8c5c03cde25b19679dec8cd694d337ef5828a6a5601d7`.
- Mac mini staged page SHA256: `07690db01fc5740502f7c1c3018d8ea393d2110a497ea6a7a781ce314b65c667`.
- Full HXF .l6ia pack/reload CRC checks passed. `test_metro_led_r03a_bootplan.py` validates the exact in-place LDR record delta and simulates **all 1025 sectors** (header + full partition payload) as the runtime overlay would present them to the M4's original SHARC loader. This also confirms actual new header is served at `0x8802`.
- Build script: `tools/build_metro_led_r03a_inplace_source.py`, `tools/build_metro_led_r03a_sharc_inplace.py`; staging: `tools/stage_metro_led_r03a_inplace.py`.
- Offline tests `tests/test_metro_led_r03a_inplace.py` (15) and `tests/test_metro_led_r03a_bootplan.py` (4) **19/19 passed**.

## Pre-hardware Mac mini staging and acceptance

A separate user-initiated WebUSB page is already open on Mac mini Chrome:
`http://localhost:8765/METRO-LEDSYNC-R03A-SHARC-INPLACE-BOOTCHECK/?build=1b937f3f`.

Assets are staged at `~/Projects/hxtra-metronome-test/build/browser-ramrun/METRO-LEDSYNC-R03A-SHARC-INPLACE-BOOTCHECK/`. Their relevant SHA256 hashes were checked independently after copying, and the Mac mini staging HTTP server returned HTTP 200. A **read-only live Chrome DOM check returned `stage=Ready`, `runDisabled=false`**, nine RAM regions (1.00 MiB), one eMMC reference CRC, RAM-only writes and a log naming R03A with three metadata/payload overlay sectors. **No R03A hardware run was initiated.** As a last positive control, the physical pedal editor returned setlist0 preset122 Super Lead and R01's actual USB signature `METRO-LEDSYNC-M4LEDTRACE-R01` with live edge count. Thus the current running unit has not silently switched to R03A.

The **only hardware question** for R03A: Does a single revised, same-size SHARC process-code record boot normally under the exact installed donor M4 while preserving physical pedal controls and editor, DSP Usage %, USB Monitor and normal donor Metronome playback? The answer to this isolation test determines whether the in-place kernel is a viable boot-safe basis for later real LED synchronization.

After the user deliberately clicks **Run METRO-LEDSYNC-R03A-SHARC-INPLACE-BOOTCHECK from RAM**, independently check the editor SYN and preset 41C, and if possible test metronome sound and feature displays. The original M4 is unchanged; R03A must not be expected to respond to real FS3 LED events yet. An uploaded RAM CRC or tab "success" does not prove SHARC/audio boot. If frozen, record exact symptoms/log and power-cycle the unit; do not retry SHARC-old builds without cause isolation. No permanent firmware installation is authorized.

# IO-LEVEL-R04 — R03 stationary bar diagnosis and native incremental-event audit

Date: 2026-11-23 (America/New_York). Branch: `experiment/io-level-r04-all-native-meter-events-ledger-20261123`.

## User-reported failure

User booted experimental R03 on an HX Stomp, with the previously installed R03C metronome firmware remaining on permanent eMMC. The Home-screen horizontal meter showed only one- or two-pixel fluctuations; playing the guitar and enabling the metronome did not produce visible level movement. R02 had also shown essentially fixed bars.

The response is based on **live USB data from the physical R03**, exact binary disassembly/source audit, and assembled Cortex-M4 emulator tests.

## Actual R03 on-device measurements — verified

The read-only R03 command `0x13` returned a valid 64-byte `IOM3` response. A 60-sample/9.8-second host capture through Mac mini yielded:

| R03 on-device counter | First | Last | Difference |
| --- | ---: | ---: | ---: |
| DSP-to-M4 RX frames | 209,730 | 230,573 | +20,843 |
| Nonempty native payload frames | 12,993 | 13,475 | **+482** |
| 44-word candidates | 373 | 375 | **+2** |
| Fully accepted 44-word packets | 373 | 375 | **+2** |
| Bar state changes | 197 | 199 | **+2** |

Thus the experimental R03 listener accepted **2 of 482 nonempty native packets (0.41%)**, dropping **480 (99.59%)** without parsing their records. These actual on-device counts explain why R03 is an unsuitable *continuous* general I/O meter.

The displayed bar widths changed **29 → 30 → 29 pixels**, fully corresponding to the user's reported tiny oscillation. The 44-word packet's eight R03 reading fields were:

- Captured packet A: `[-69.6211, -69.6211, -120, -120, -120, -120, -81.9393, -69.6211]`
- Packet B: `[-69.0392, -69.0392, -120, -120, -120, -120, -81.9006, -69.0392]`
- Packet C: `[-69.8240, -69.8240, -120, -120, -120, -120, -81.9393, -69.8240]`

Both displayed bar algorithms choose the same value, because left selects the maximum of records 0/1, while right selects the maximum of records 6/7, and record7 equals record0/1. This **demonstrates two concrete R03 design problems**: (1) nearly all native messages are filtered out, and (2) the two trial bars are mathematically assigned to the same live signal in these observed packets. The inspected values do not establish that either bar corresponds to true guitar Input or Main Output.

Read-only R03 metronome diagnostic `0x50` independently showed the metronome M4-active flag true, valid M4→SHARC LED-event message/checksum, and LED event counter advancing 287→288 across successive requests. This confirms the metronome's M4 event transport, while audible SHARC output was not measured. A previously recorded 8-second, 8-channel HX Stomp USB capture during R02 metronome activity had digital silence in all USB inputs; it cannot exclude sound through analog Main/Phones outputs.

### Native short packets were always present

Prior 900 raw R01/R02 frame snapshots verified a native message envelope of four words, followed by one or more **five-word records** `[0, 3, object_family, parameter_id, float32]`. Values arriving in shorter packets include:

- `object_family=0x0002002a, parameter_id=1`, native float around −70.
- `object_family=0x00020002, parameter_id=3`, native float around −88.
- `object_family=0x0002002e, parameter_id=1`, float −1.
- The 44-word packet's eight entries, with family `0x00020000` and IDs 2,5,3,6,4,6,1,5.

The object family and parameter fields have **not** been proven to identify a specific physical signal port. The −1 event is an example of why one must not label all native floats as dBFS amplitude. Some are ordinary parameter values. Any final live meter must first establish source identity and units using actual measurements.

## R04 improvement: measure before choosing a bar's source

New source `src/m4/io_level_r04_full_native_event_ledger.s`. The R04 hook executes on the M4 and examines every SHARC→M4 frame, accepting any packet whose existing native framing, declared length, envelope and complete five-word record structure validate. It retains partial-packet tails untouched and rejects nonfinite value fields. The original R03 dual-bar paint and native 44-word listener are retained only as *diagnostic comparisons*; no claim of correct I/O mapping is made.

A bounded **24-key event ledger** stores one row per distinct `(object_family, parameter_id)`: exact last raw float, exact minimum/maximum raw floats and total record observation count. Float minima/maxima use monotone order over finite IEEE-754 values; every value remains reversible to its as-transmitted 32-bit native representation. The implementation tracks rapid transient maximum values on-device regardless of host USB polling frequency, so a short metronome click or guitar transient can be detected even if the host reads at only 5 Hz. If the 24 slots fill, pre-existing keys remain stable; any 24/24 result must be treated as potentially capacity-limited.

The existing read-only editor command **`0x13`** now returns **640 bytes** (MessagePack BIN16): original 64-byte R03 diagnostics (signature updated from `IOM3` to `IOM4`) followed by the 24 × 24-byte native-event ledger. A dedicated generation seqlock is incremented at the start and end of native record parsing. USB diagnostic replies retry a version change or in-progress writer before using the captured data. No user parameter, USB audio signal, settings, presets or permanent storage is written. R01 editor command `0x4F` and metronome command `0x50` are preserved.

Host collector: `tools/io_level_r04_native_ledger.py`; it labels records by actual object/parameter IDs and prints cumulative extrema, with optional JSONL saved privately. The physical source assignment remains intentionally unresolved until after the R04 on-pedal ledger is observed with a controlled active signal.

## Binary, QA and hardware safety

- Installed R03C HXF SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- R04 HXF SHA256: `bc79e769bd9131139ad32c92d3fd8a15ba63eefe7b0fa7a260a1611efba68461`.
- The builder starts from the *exact* frozen R03C and reproduces the physically tested R01 M4 overlay, checking its pinned SHA first. Then it appends **2,488 M4 app bytes** relative to R01 at only three new hook sites (native RX, Home repaint, editor command registration).
- All **14 non-M4 HXF entries**, including the entire SHARC bootstream, bootloader, model database and DSP processing code, are byte-identical to the user's installed R03C. **Zero new SHARC code and zero bootstream growth**.
- Actual L6IA integrity check passed all 15 sections; pack/unpack round-trip and original-entry structural parity passed.
- Tests `tests/test_io_level_r04_full_native_ledger.py`: 13 executed Cortex-M4 emulator tests, including: extraction from short 9-word packets with a distinct family, multiple record keys, exact min/max retention of brief −15dB excursions in otherwise −70dB signal, 640-byte stable USB response, invalid frames, unchanged original trial bar behavior and callback register integrity.
- Tests `tests/test_io_level_r04_host_ledger.py`: three exact raw response decoder tests. Tests `tests/test_io_level_r04_staged_hxf_invariants.py`: archive and RAM plan checks. Complete cross-R03C regression suite is tracked separately; do not assume a pass without test output.
- RAM planner builds **9 RAM regions**, 2 read-only exact-R03C SHARC eMMC CRC reference checks, **0 eMMC overlay sectors**, **writes=RAM**. Stage manifest and browser JS both assert these conditions. The HXF and all raw USB captures remain outside Git.
- Mac mini-only stage: `http://localhost:8765/IO-LEVEL-R04-FULL-NATIVE-EVENT-LEDGER/`, static page and RAM region HTTP 200, remote/local page and RAM plan SHA256 identical. **No automatic WebUSB RAM boot, firmware flash or device reboot occurred**.

## Targeted next step

The user can power-cycle from running R03 (RAM-only) to installed persistent R03C, open the above Mac mini Chrome page, and user-initiate the R04 RAM test. It is safe to leave the bars seemingly static: this phase collects **incremental event extrema**, which is the new observable.

After they say "running", the assistant reads command `0x13` with:

```sh
cd "$HOME/Projects/hxtra-metronome-test"
.venv/bin/python tools/io_level_r04_native_ledger.py --samples 60 --interval .15 \
  --out /tmp/io-level-r04-HW01-all-native-events.jsonl
```

Then compare, by exact native object/parameter key, record counts and observed maxima while the metronome is audibly running and guitar input is active. Identify the **actual** input and output signal fields, including whether the audible metronome reaches any existing meter. Only then revise the Home rendering to use different correctly mapped, full-resolution data. If a native output source is truly unavailable, separately document that before proposing any additional SHARC code.

**R04 is an experimental, user-triggered, RAM-only data diagnostic and is not approved for permanent updater flashing.**

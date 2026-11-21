# METRO-LEDSYNC-HWFAIL02 — SHARC-only startup failure, stale eMMC header, controlled fix

**Date:** 2026-11-20. **Exact installed donor:** `~/Downloads/HXtra_v1.2.1.hxf`, SHA256 `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`, MD5 `93969635834cd6050dec7f137df1e4b9`. The user required preserving every feature and Global Settings configuration from this exact installed image. **No experimental permanent firmware writes are allowed; every test is RAM-only.**

## HWFAIL02 physical outcome — reproducible, SHARC alone sufficient

The full R02C M4+SHARC candidate previously froze the pedal on startup (HWFAIL01). A positive control ran the byte-for-byte original donor image from RAM and returned normal HX Edit USB responsiveness, proving that the **ordinary donor RAM image and the same WebUSB loader can boot on this device**. The later `METRO-LEDSYNC-R02C-HWFAIL02-SHARC-ONLY` image kept the exact original installed donor M4 application and 13 other entries while changing only SHARC Entry2. **It froze again.**

Read-only inspection on the Mac mini at the time of this second freeze:

- `ioreg` enumerated the HX Stomp USB device. `.venv/bin/python tools/hx_ctl.py --timeout 2 status` returned `error: no SYN reply from the device within 2.0 s`. This is a confirmed firmware startup failure, with the exact SHARC exception/boot phase unresolved.
- The preserved browser WebUSB log `tests/hardware_evidence/METRO-LEDSYNC-R02C-HWFAIL02-SHARC-ONLY-20261120.json`, SHA256 `883b11bc7596d3fe0f4b17cbcb521aef9def480e440da0575c2dfdeebc5f097e`, shows all **9** RAM-region transfer CRCs succeeded, DFU and RAM loader completed, and application execution transfer was reported as successful. The eMMC loader initialization returned `0x10b`, so the original eMMC donor sectors were *not* physically CRC-verified by the loader.
- The prior unmodified-donor positive control (same WebUSB loader) booted successfully. Therefore the general RAM loader can boot the donor; **one or more SHARC Entry2 modifications are sufficient for the observed freeze**. The new M4 LED hook is not necessary for this failure.
- The failed SHARC-only browser runner was disabled and its failure notice staged to the Mac mini. Only a physical power cycle can exit the RAM application and restore the installed v1.2.1. Restoration **has not yet been verified after HWFAIL02**.

## A previously overlooked structural bug: stale SHARC partition metadata

The vendor's L6IA Entry2 `0x200`-byte subheader occupies one eMMC sector at absolute sector `0x8802`. Its little-endian fields contain magic `0x56112603`, the CRC32 of the payload at offset `+8`, and the byte length at offset `+12`. Source: `tools/l6ia.py`. The SHARC payload starts in the following eMMC sector `0x8803` (`tools/hxf_ram.py`).

| Image | Entry2 byte length | SHARC payload CRC32 | RAM overlay of metadata sector 0x8802 |
|---|---:|---|---|
| Exact installed donor | 524,212 | `0xc273d05e` | N/A — header remains installed |
| Working earlier R02B2 | 522,828 | `0xa1262820` | No; new payload is **shorter** than donor |
| Failed R02C | **524,284** | `0x0f5d02e7` | **No** |
| Failed HWFAIL02 SHARC-only | **524,284** | `0x0f5d02e7` | **No** |

The generic RAM planner `tools/hxf_ram.py::overlay(stock,new)` overlays *only* data from `PAYLOAD[i]`, not the entry's `PART_START[i]` subheader. The actual failed HWFAIL02 plan overlaid 11 changed SHARC payload sectors, including the last partition sector, **but it did not overlay the metadata header sector 0x8802**. Consequently a read of the on-card header still reports the original donor's 524,212-byte length and CRC even though the payload in RAM was replaced with a 524,284-byte image. The **72-byte discrepancy is directly verified** by the exact source HXF metadata and the runtime overlay table; earlier tests checked archive-internal CRC but did not inspect the physical eMMC mapping used by the RAM loader.

If the device's SHARC loader respects the on-card length field, it will read only 524,212 bytes of the extended 524,284-byte image, truncating the last 72 bytes of its `FINAL_INIT` boot block. This is a specific, plausible causal mechanism, especially since R02B2's shorter replacement did boot. **The exact startup code path's use of this field is not yet independently proved.** The mismatch itself is a confirmed bug and must be fixed regardless. An additional possibility is an SHARC LDR INIT command/bank/pipeline issue or crossing the 512 KiB partition boundary.

## HWFAIL03 — exact single-variable metadata correction (not yet physically tested)

The prepared `METRO-LEDSYNC-HWFAIL03-SHARC-HEADER-ONLY` RAM plan uses **exactly the same HXF** as failed HWFAIL02: SHA256 `3aa8d41b6d925272a00db2a16f2c112d1399f0adde70131ee3f78d47c09cf2ce`. Therefore the M4, SHARC program instructions, LDR initialization content, existing user settings and entire installed donor feature selection are identical to HWFAIL02.

The sole change is in the **RAM overlay**: add the corrected 512-byte metadata header at absolute eMMC sector `0x8802`. This header reports payload length **524,284** and payload CRC32 **`0x0f5d02e7`**, matching the exact HXF. The previous **11** payload overlay sectors are byte-for-byte unchanged. New total: **12** overlay sectors in 3 runs, 9 transfer regions, same donor-reference read-only check at Entry2 1023 sectors, `writes='ram'`. Plan SHA256 `a2e8544700df9032ec5aceab6b802f4e563fafe4a13e401653a9aae3b5cfc233`.

The independent `tests/test_metro_hwfail03_header_only.py` tests confirm no firmware binary change, identical original payload overlays, exactly one added metadata sector, and byte-for-byte reconstruction of **every** SHARC partition sector that the M4 can read. The planner is `tools/metro_led_hwfail03_header_only_plan.py`, which enforces the exact failed HXF SHA256 and reuses `tools/metro_led_r02d_ramplan_header.py`. It leaves the original generic RAM loader untouched. The user-initiated Mac mini Chrome test is staged at `http://localhost:8765/METRO-LEDSYNC-HWFAIL03-SHARC-HEADER-ONLY/`. This is a controlled causal experiment: if it boots, the absent metadata sector was sufficient for the failures; if it freezes, the header mismatch was a real bug but another SHARC issue remains. Do not declare success based solely on WebUSB transfer completion; require pedal UI and editor handshake.

## Alternative structural repair R02D — exact original SHARC Entry2 byte length (offline only)

Independently, `tools/metro_led_r02d_sharc_preserve_size.py` creates a same-length donor SHARC image: **524,212 bytes**, precisely matching installed payload length, with one original metronome instruction redirected to a **14-instruction** LED event shim in otherwise unused PM memory. Seven descriptor merges over physically contiguous initialization ranges reclaim exactly **84 bytes**, which offsets the shim's 84 bytes. SHARC final initialized **22,468 DM words** are individually unchanged, and only **15 PM addresses** differ (one original branch and 14 new words); the other 14 firmware entries are byte-identical to donor. All original HXtra UI features are preserved. HXF SHA256 `0f721c36e379e0df17edadc9cc841f52108fee8c8ab8a34f57b040731ded1875`.

For completeness, its separate RAM plan also overlays the **updated subheader CRC** at sector `0x8802` even though the byte length is unchanged. Total 20 overlay sectors, 3 runs, plan SHA256 `ee7034bfc1bd36ff062016e8adc4ce567b16f44c756c5046ac776ad9cb3cc06f`. The R02D source and `tests/test_metro_r02d_compact_sharc.py` and `tests/test_metro_r02d_boot_and_metadata.py` provide fully reproducible offline validation. This is **not** the next one-variable hardware test: it introduces seven descriptor re-orderings that would confound isolation of the header bug. It should remain offline until HWFAIL03's physical outcome is known.

**Outcome status:** HWFAIL02 failed; unchanged donor passed; HWFAIL03 and R02D are both untested on the physical device. Original installed HXtra v1.2.1 has not been modified by these RAM-only experiments.

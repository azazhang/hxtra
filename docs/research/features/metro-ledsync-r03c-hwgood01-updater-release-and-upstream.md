# R03C HWGOOD01 — updater-ready permanent HXF and upstream HXtra migration policy

**Date:** 2026-11-20 America/New_York. **Status:** permanent-installation package assembled, fully audited offline, copied to Mac mini Downloads, and exact SHA256 independently verified after copy. **No eMMC/firmware write initiated.** The device still runs the user-initiated RAM image. Its exact major-working firmware image remains unchanged.

## 1. Identified and physically tested image

- Release label: `METRO-LEDSYNC-R03C-HWGOOD01-UPDATER-READY-QA01`.
- Frozen physically booted and user-confirmed **duplicate-free** R03C candidate: `METRO-LEDSYNC-R03C-HWGLITCH-REPAIR`.
- HXF source file in MacBook Air repo:
  `build/browser-ramrun/METRO-LEDSYNC-R03C-HWGLITCH-REPAIR/METRO-LEDSYNC-R03C-HWGLITCH-REPAIR.hxf`
- HXF user-facing install location on the USB-connected **Mac mini** (the verified `~/Downloads` resolves through the external volume):
  `~/Downloads/HXtra_v1.2.1_METRO-LEDSYNC-R03C-HWGOOD01.hxf`
  i.e. `/Volumes/Samsung_T5/Downloads/HXtra_v1.2.1_METRO-LEDSYNC-R03C-HWGOOD01.hxf`.
- **Exact HXF SHA256:** `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- HXF bytes: **45,860,002**. The renamed installation copy is byte-for-byte identical to the exact image that supplied the successful R03C RAM hardware test. It was copied, not regenerated, modified or stripped. Existing installed HXtra v1.2.1 donor SHA256: `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`.

### What was independently verified, and what was not

`tools/audit_metro_r03c_permanent_hxf.py` parsed the exact packed HXF and its exact installed donor. It verified:

1. **Container:** complete FORM/L6FF length, correct HEAD payload length and MD5, unchanged device/version/product HEAD metadata outside updated size+MD5, exact four-chunk HEAD/dinf/dinf/data structure, valid two Updater `dinf` types/ranges with proper shifted offsets.
2. **Updater trailer:** original **101,392-byte P36Updater trailer is bit-for-bit unchanged**; the new `dinf` records accurately point to its shifted offset after an additional 864 bytes of appended M4 application code.
3. **Archive and bootloader:** all **15** firmware entries exist, only **0 (M4 application)** and **2 (SHARC DSP bootstream)** have different payload bytes. **Entry1 bootloader** and the other 13 entries are byte-identical in content and subheader to the user's installed HXtra 1.2.1 donor, despite shifted absolute offsets of later entries. The SHARC has the same 524,212-byte Entry2 payload, exactly 201 existing LDR descriptors, and only original metronome PM record #177 replaced with the same 142 instruction count.
4. **Integrity:** `tools/l6ia_verify.py` reports **ALL OK** across every archive entry's Fletcher and CRC fields, including M4 application internal image CRC and auxiliary model/string tables. Exact packed HXF decodes to the same independently verified 74-MB `.l6ia` archive. The candidate SHA256 on the Mac mini matches the pinned source SHA256 after the transfer.
5. **Runtime precursor:** R03C real HX Stomp RAM boots, responds through HX editor, and the user explicitly confirmed elimination of the audible duplicate-click fault. Read-only M4 hardware latency measured 23 physical LED events, median **0.165ms**, max **0.419ms** from final LED command to first M4 SPI TX callback.

**Boundary:** This audit checks all known firmware-container and embedded checksums. We have **not** tested the actual persistent Updater handshake, eMMC erase/write reliability, reloading code from persistent partitions or a post-flash cold boot. RAM success and offline integrity raise confidence but do not eliminate permanent-flashing risk. The physical DSP Usage percentages and USB Monitor behavior in R03C should be checked on the unit before or immediately after committing it to eMMC, since prior experimental versions had missing DSP percentages.

### Installed application & existing recovery images

On Mac mini:
- `/Applications/Line6/Line 6 Updater.app` **version 1.28**, bundle `com.line6.line6updater`, present.
- `/Applications/Line6/HX Edit.app` and `/Applications/Line6/Line 6 Central.app`, both present.
- Exact **factory recovery firmware 3.80.0** already downloaded:
  `~/Downloads/HX_Stomp_v3.80.0_0x103966115.hxf`; MD5 verified **`a2cd8f4ae56f49415380270ebc484bf1`**, matching the published HXtra source requirement.
- Exact original HXtra **1.2.1** HXF already downloaded:
  `~/Downloads/HXtra_v1.2.1.hxf`, SHA256 verified **`96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`**.
- Neither original file was modified or duplicated by this release preparation.

### How to install with Line 6 Updater (user starts only)

1. Stop any RAM-only debug capture/WebUSB loader, then **physically power-cycle** the HX Stomp to return to the already installed HXtra 1.2.1, so the normal original firmware/USB stack handles the updater session. The temporary RAM build is not automatically installed. If you have important new preset edits since the last backup, use HX Edit's normal **File → Create Backup** before flashing; backups are recommended by both HXtra and Line 6 for firmware updates. No backup was created by this work.
2. Quit **HX Edit**, browser WebUSB usage and other audio/USB programs that may claim the device. Keep device USB connected directly to Mac mini, power stable, prevent Mac sleep and disconnect external MIDI messages during the update.
3. Open `/Applications/Line6/Line 6 Updater.app`, choose the HX Stomp and the **local/Offline/Choose File** installation flow. Select exactly:
   `~/Downloads/HXtra_v1.2.1_METRO-LEDSYNC-R03C-HWGOOD01.hxf`.
   The local filename documents the known major-working release; its internal HEAD version remains the donor's original software version, by design.
4. Let the updater complete fully without interruption. Verify a **cold power-cycle** after updater success and the metronome's real audible quarter notes against the actual FS3 TAP LED. Confirm absence of duplicate clicks, stable BPM, bypass/re-engagement, and **DSP Usage percentages plus USB Monitor**.
5. **Failure recovery:** Line 6's HX Stomp update-recovery procedure: hold **Right Page** while powering on to enter update mode; if the Stomp enters update mode, use Line 6 Central or Line 6 Updater to reinstall the already-verified factory 3.80.0 .hxf, or previously installed HXtra 1.2.1. A blank/white screen is possible in update mode. Recovery is not guaranteed in every physical flash or hardware failure. Do not repeatedly flash uncertain experimental files.
6. Only when the updater reports success and cold boot passes should we mark a separate **HWFLASH01 persistent-eMMC hardware success** milestone. Until then this is **updater-ready QA01**, not a permanent-install success.

Official and upstream source URLs (all accessed 2026-11-20):
- HXtra building/installation guide: `https://github.com/wisemandenny/hxtra/blob/main/docs/building.md`.
- HXtra 1.2.1 release and prior 1.2.0 upgrade guidance: `https://github.com/wisemandenny/hxtra/releases`.
- Line 6 updating instructions: `https://kb.line6.com/updating-helix-hx`.
- Line 6 HX Stomp recovery: `https://kb.line6.com/helix-hx-update-recovery-instructions`.

## 2. Upstream HXtra updates: precise merge and binary portability constraints

The code workspace has **two remotes**:
- `origin`: `https://github.com/wisemandenny/hxtra.git` (original author and upstream).
- `fork`: `https://github.com/azazhang/hxtra.git` (the user's fork, with our branches and tests).

A fresh `git fetch --prune --tags origin` checked the public upstream as of 2026-11-20. Latest **published HXtra release remains v1.2.1**, published November 19, 2026, tag `fb23482`. The original `main` at our branch's fork point was `df327d5`; current upstream `origin/main` is `01708b4` (November 20). Its **two new commits** only add `.github/CODEOWNERS`; no upstream `src/`, `tools/` or DSP firmware-source change is present since the fork point. A read-only `git merge-tree --write-tree HEAD origin/main` completed without conflicts. Our existing stable firmware branch/source were **not merged or rebased by this check**.

**Git source updates and flashed firmware are different operations.** A new upstream release can generally be fetched and merged/rebased into our Git fork, but our custom R03C image will **not** automatically inherit changes from a new HXtra `.hxf`. Worse, if the official HXtra release modifies the same LED callback, bypass hook, SPI frames or SHARC metronome PM, an old binary patch applied blindly may overwrite or disable new features, cause freeze or damage persistence.

Our current integration is intentionally fail-closed and **version-specific**:
- `tools/build_metro_led_r03c.py` uses fixed M4 hook addresses/expected original instructions and requires the **exact user-selected HXtra v1.2.1 donor SHA256**. Other donors are rejected.
- Original SHARC PM block must still have 142 instructions at `0xe5386`, original 201 LDR records and same record #177 and memory layout.
- SPI TX event words **240/241** require their bytes remain unused and consistent with the callback and DSP RX stream. A later HXtra revision may claim those words or change SPI packet topology.
- The donor's DSP Usage Display, USB Monitor, NAM slots, loop gate and user-selected feature set must remain intact when rebuilding.

**Recommended future release intake, without corrupting stable R03C:**

1. Retain immutable R03C major-working tag `metro-ledsync-r03c-hwgood01-major-working-duplicatefree-20261120`, pinned binary SHA256 above and the updater-ready QA01 audit. Never overwrite either source baseline or exact HXF.
2. When upstream publishes `v1.2.2` or later, fetch the new release in a **separate integration branch/worktree**; read its changelog and compare actual `src/`, `tools/`, `tools/patch_click.py`, feature and DSP-space interfaces with R03C. Merge upstream Git source changes there first.
3. **Rebuild the new standard HXtra donor using the official stock HX Stomp 3.80.0 .hxf**, selecting the same DSP, NAM and UI feature configuration. HXtra's public setup page expects the official stock HXF as its input, **not a previously modified HXtra 1.2.1 image**.
4. Port our M4 and SHARC synchronization changes to the new upstream `Metronome` feature **at source level**; only reuse fixed addresses if independently revalidated against the newly built donor. Verify correct M4 byte signatures, SPI 240/241 availability, 142-instruction metronome PM layout or a revised explicit layout, descriptor topology, DSP space, and whether HXtra adds its own LED synchronization. R03C may need a compatible new event adapter, especially if upstream changes the TAP LED path or SHARC processing.
5. Build a **new, clearly versioned** HXF from the new HXtra donor, verify all 15 container entries and restore/update metadata, run emulator and live read-only capture, then test **from RAM** before considering a new permanent firmware flash.
6. If the upstream release provides no needed new features/fixes or is incompatible with the custom overlay, keep using the proven R03C image. Installing an upstream HXtra `.hxf` directly would replace the custom metronome behavior with whatever that upstream release includes. A future **official Line 6 stock base firmware** beyond 3.80.0 would require broader fresh binary/ABI analysis as well.

**Potential long-term maintenance improvement:** move this patch into HXtra's normal version-aware `tools/features`/Metronome build stages with explicit donor compatibility checks and automated regression fixtures. Our currently separate `src/m4/metronome_led_r03c.s`, `src/sharc/click_led_r03c_inplace.asm`, source builders and tests are suitable isolated starting points, but the patch is **not yet a standard HXtra feature toggle or a portable plugin**. We must not claim that a simple Git merge automatically makes it portable to all subsequent HXF binaries.

## 3. Source history and QA evidence

- Stable R03C user-confirmed HWGOOD01 tag: `metro-ledsync-r03c-hwgood01-major-working-duplicatefree-20261120`, commit `4e33ffb` (user evidence and first 23-event timing experiment).
- Installation-readiness audit: `tools/audit_metro_r03c_permanent_hxf.py` and `tools/l6ia_verify.py`. Release QR/manifest is stored in `tests/hardware_evidence/METRO-LEDSYNC-R03C-HWGOOD01-UPDATER-QA01-20261120.json`.
- The original HXF and installed HXtra donor are **not committed** to Git or published, to avoid redistributing Line 6 firmware. The verified release file exists only in the owner's local files.
- No Updater GUI action, eMMC write, preset edit, feature configuration change, user backup, or physical RAM reload was performed.

# METRO-LEDSYNC-R03C-HWFLASH01 — updater success and post-install USB hardware checks

**Hardware date:** 2026-11-21 (America/New_York). **Scope:** user's permanent installation of the exact R03C duplicate-free image; independent read-only post-install checks. **No subsequent firmware changes, USB writes, preset edits or pedal reboot performed by the assistant.**

## Verified persistent-install evidence

1. User reported: "firmware has been flashed in. check if everything is still alright."
2. Independently accessed **Line 6 Updater 1.28** via the Mac mini macOS Accessibility UI. Its actual completion screen reported **"Firmware Update Completed Successfully"**, followed by **"Your Line 6 product will now restart automatically, and will be ready for use."** This is upstream Updater's actual reported status, not inference from a WebUSB RAM handoff.
3. The HX Stomp USB device was detected by macOS after update. Initially the updater application still held interface 0, causing the read-only editor and R03C probe to return **"cannot claim interface 0 ([Errno 13] Access denied)"**. After confirming the actual Updater completion screen, a **normal AppleScript application quit** was requested; the updater process terminated without being killed. No update or restart command was issued remotely.
4. Read-only USB editor `tools/hx_ctl.py --timeout 3 status` succeeded **after Updater exit**. The current editor buffer returned **setlist 0 preset 122, "Super Lead", all 8 slots/models**. Slot7 is the Metronome (model181) and was reported **off/bypassed at the exact sampling moment**; this is a snapshot only and does not necessarily reflect the author's playback usage. Editor services were responsive.
5. Independent read-only USB librarian `tools/hx_ctl.py --timeout 3 presets --setlist 0` returned the expected indexed list of setlist0 names (e.g. FX:Stereo Swirl, FX:80's Craze, FX:Bloomin'Onion), proving both editor and librarian protocol paths survived update.
6. The macOS audio subsystem enumerated the **HX Stomp** as an 8-input/8-output, 48kHz USB audio device after the install. This proves USB audio interface enumeration, **not** audible audio, signal routing, the HXtra USB Monitor option, or an actual USB recording.
7. The extended read-only command `0x50` returned the exact **`METRO-LEDSYNC-R03C-HWGLITCH-REPAIR`** M4 signature in the running post-Updater firmware, with valid and current M4 SPI counter/complement frames. This distinguishes the running R03C code from the original HXtra v1.2.1 and from the older R03A/R03B prototypes.

**Interpretation:** The manufacturer updater reported a successful permanent installation, the device came back over USB, and the running firmware exposes R03C's exact diagnostic interface. These are strong post-flash success indications. The assistant has not read back the entire nonvolatile eMMC partition and has not personally performed an additional cold power-off/power-on. A future cold power-cycle that again returns R03C command 0x50 will be definitive independent evidence of persistence through complete power loss.

## Live post-flash R03C transport trace

Source: `tests/hardware_evidence/METRO-LEDSYNC-R03C-HWFLASH01-30SAMPLES-20261121.jsonl`. SHA256 `4401765fd1df02e6b83adf47e90c50092fc4ae24592b69fbc7f1825d89bcf1a2`.

- **30** successful read-only 84-byte R03C M4 diagnostic samples, **12 distinct, consecutive** accepted FS3 LED-ON counters (raw `2147485815..2147485826`; low31 `2167..2178`).
- **30/30** packet integrity/complement matches; **30/30** last M4 TX event equals current M4 LED event.
- Stock M4 timer LED ON-to-ON intervals: **11 adjacent periods**, median corresponds to approximately **110.0687 BPM**. This is observed M4 final LED scheduling only and does not prove physical LED optical-to-audio phase.
- Time from accepted final FS3 LED-ON command to first M4 SPI TX callback: **86 to 402 microseconds**, median **203 microseconds**, 12 distinct beat events.
- Across 30 samples, original counters for skipped SPI frames, short OFF→ON reversals filtered, non-TAP or hidden LED frames, local-mode fallback frames, TAP-dropout grace frames and Metronome on/off state changes were all **unchanged**. SPI producer stamped another **13,954 frames** without accumulating new skip/dropout events.
- These results agree with the pre-flash major working baseline (**23 distinct events; median 165μs, max419μs at ~100BPM**). The user can change BPM; the different ~110BPM postflash tempo is not a firmware regression.

## Installed artifact preserved

Exact persistent-install file already staged and independently SHA-verified in Mac mini's `~/Downloads/HXtra_v1.2.1_METRO-LEDSYNC-R03C-HWGOOD01.hxf`. After the flash, it still has SHA256:

`42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.

The original HXtra v1.2.1 HXF remains in the same Downloads folder, SHA256 `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`. All 15 internal firmware entries, the Updater metadata and the unchanged bootloader passed the earlier `tools/audit_metro_r03c_permanent_hxf.py` and `tools/l6ia_verify.py` offline audit. No changed binaries were built, staged to the browser or loaded by this postflash QA.

## Items that cannot be certified by these read-only checks

- **DSP Usage Display (percentages):** Cannot inspect the physical stomp LCD from these USB protocols. Previously early metronome prototypes lost DSP percentages, so this exact on-pedal visual check remains material. Firmware build preserved all other existing original code outside the four patch hooks and original 142-PM SHARC block, but that structural parity alone does not establish on-device UI rendering.
- **HXtra USB Monitor screen/behavior:** USB audio enumerates, but the HXtra menu's actual USB Monitor option was not visually/functionally tested. That remains pending on-pedal confirmation.
- **Audio:** The actual click audible after the flash, absence of double clicks, and click/LED phase were not measured during these automated checks. The user's **earlier R03C RAM-only** test confirmed double-click resolution; no new physical listening result was provided for persistent R03C yet.
- **Bypass/engage:** At read-only status time, editor reports slot7 model181 **off** while M4 diagnostics report `M4_Metronome_active_flag=true` and an advancing final LED-event counter. The R03C M4 source at `src/m4/metronome_led_r03c.s:214-217` explicitly initializes `mp_active=1` on boot; its dynamic bypass hook updates it when a matching model-state change event is received. The mismatch is **confirmed in internal bookkeeping** after boot. It does not by itself show a bypass audio leak because the SHARC graph may stop processing the bypassed effect. Re-engaging from a boot-bypassed preset could potentially fail to reset the downbeat as intended; this requires a separate physical bypass/re-engage test. **Do not silently call bypass handling validated.**
- **Cold start:** To establish persistence under complete loss of power, the user can manually power-cycle once the Update is finished, then we can query 0x50 again. The assistant did not physically cycle power; Updater indicated the device would restart automatically upon completion.

## Acceptance decision

**`METRO-LEDSYNC-R03C-HWFLASH01-UPDATER-SUCCESS-POSTBOOT-QA`: qualified pass.**

Firmware installation reported successful by Line 6 Updater; actual R03C code running post-update; editor, librarian, eight-channel USB audio enumeration and advancing M4 transport verified. No observed critical malfunction in measured interfaces. Visual screen features, audio and bypass remain user-confirmation items. The next firmware revision must be a new branch that leaves this major-working R03C HXF and tag intact. No firmware write or new code change was needed for this inspection.

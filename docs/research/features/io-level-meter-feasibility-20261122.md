# Dual input/output level meters — read-only feasibility audit (2026-11-22)

**Scope:** HX Stomp with the user's permanently installed, hardware-confirmed metronome version `METRO-LEDSYNC-R03C-HWGLITCH-REPAIR`, **HXtra 1.2.1**, HXF SHA256 `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`. This is **exploration only**. No firmware or device modification, new binary, RAM boot, changed preset, or claim of physical level-meter function. This research is on separate Git branch `research/hxtra-dual-io-levelmeter-feasibility-20261122`. The frozen flashed R03C branch/tag and binary must remain unchanged.

## Assessment

**Feasible in principle; adding an always-on, trustworthy continuous-level meter to the exact current full-featured 1.2.1/R03C binary is currently a constrained engineering project, not a trivial transplant of the GR meter.** UI code and signal locations are known. The outstanding gating step is an economical DSP sample + guaranteed-frame publication implementation that fits both (a) the DSP runtime memory/cycle budget and (b) the **very nearly full 512 KiB SHARC firmware bootstream partition**. New UI rendering must also coexist with the existing GR meter, BPM and breathing-line features.

## Requirement and upstream issue

The exact issue is [wisemandenny/hxtra#116](https://github.com/wisemandenny/hxtra/issues/116), titled **Configurable Input and Output level meters on the Home screen** (open, tagged `enhancement`/`High`). It requests simultaneous Input and Output bars, separately configurable `Mtr Thk` from 0 to 20 pixels (0=off by default), useful for input pad adjustment, preset-level matching and clipping. It suggests Input/Output block knobs or persistent Global Settings. Seven comments as of inspection: users support the idea; one notes the 320x240 screen is crowded and another suggests a third view alongside Chain and Footswitch. A user comment from `azazhang` supports it. There is no completed code or implementation specification in the issue comments.

Other upstream design warnings:
- [#176](https://github.com/wisemandenny/hxtra/issues/176): GR bar can persist after changing to a preset without its compressor; source lifecycle/stale state is unsafe to copy unquestioningly.
- [#185](https://github.com/wisemandenny/hxtra/issues/185): GR Middle layout gets black missing segments following preset/snapshot or mode changes, because stock divider relayout expands damage rectangles and the GR paint fails to dirty/redraw overlapping widgets. The issue includes pixel-level reproduction and a potential dirty-mark repair.
- [#184](https://github.com/wisemandenny/hxtra/issues/184): existing GR meter's Red Squeeze reads biased reduction even for low input. **That compressor-specific defect is not evidence that straightforward input/output absolute peaks are similarly biased**; it is a reason to validate all amplitude interpretations using known test signals.

Line 6's HX Edit guide, transcribed at https://www.manuals.ca/line-6/hx-stomp/manual?p=31, distinguishes the HX-class devices' **green/red signal/clip indicators** for Input/Output/Send/Loop blocks from continuous Inspector level meters explicitly described as **"Helix devices"** at https://www.manuals.ca/line-6/hx-stomp/manual?p=32. A native green/red status confirms some signal-level detection exists, but **does not establish that the M4 already receives a usable calibrated continuous meter value**. The GR developer's research `docs/research/m4/dsp-link.md` reports that searching the stock M4↔DSP message stream for level readings was attempted and abandoned. Investigating the Input/Output icon clip flag's data path is still worth a bounded read-only test because an actual float there would eliminate most new DSP code.

## Screen layout (first candidate; subject to pixel and mode tests)

HX Stomp display: **320x240 RGB565** (source `docs/research/m4/home-screen.md`); framebuffers column-major and bottom-up. The GR meter already draws along Top/Bottom/Left/Right or replaces the 4-segment divider at Middle. The preset name and chain occupy the upper part, and the bottom Home area contains footswitch labels. The default layout should keep the traditional Home screen usable.

User-proposed paired, *horizontal*, left/right bars could use a compact edge lane:

```text
     existing preset title / FX chain / footswitch labels
     IN [■■■■■■■□□□]      OUT [■■■■□□□□□□]
     x≈6..154                 x≈166..314
```

A trial implementation can use two **149 px** horizontal regions, 10 discrete cells per side or a continuous fill (sample peak on dBFS scale), with green→amber→red high-level marks and optional overload hold. Their vertical position and thickness must be validated on the **actual displayed Home, Stomp, Snapshot, Edit, split-path and preset-change states** before asserting safe y geometry. **Bottom-edge placement will conflict with GR's Bottom setting**; putting them over the Middle divider will conflict with GR's Middle mode and stock selected-segment navigation. Define a coexistence policy deliberately (e.g. hide I/O when GR occupies the same pixels, give user an I/O-only view, or assign a dedicated separate lane after screenshot collision testing). Avoid silently overwriting existing GR or screen content.

Prefer a **global** pair of 0..20 thickness settings, default 0, rather than modifying Input/Output model database records and per-preset parameter counts. `tools/features/dsp_meter.py`, `tools/features/bpm.py`, `tools/features/__init__.py`, `tools/patch_menu.py`, and `src/m4/virtual_settings.s` provide the full UI/configuration machinery. **No real setting ID has to be stolen:** `tools/setting_ids.py` currently allocates virtual IDs `0xcc..0xe5`. A read-only `setting_ids.virtual_problems()` check returned `[]` for two illustrative **5-bit** fields `0xe6` and `0xe7` in unused bits 0..4 and 5..9 of virtual container 114. This shows the settings store can represent 21 values. **Those IDs/fields are not claimed by any code, and must be allocated formally only on implementation.** Avoid reusing the obsolete physical IDs 63/74/78 etc. as HXtra's current virtual settings store is more robust across updates.

## DSP: actual signal points, verified from the shipped R03C binary

`docs/research/sharc/usb-routing.md` describes and in many cases hardware-tested the SHARC graph. Each processing primitive handles 16 floating point samples per audio block at 48 kHz; the registry is initialized from the actual firmware's Entry2 `LDR` program.

An independent **read-only disassembly of the exact R03C HXF** (parsing Entry2's 201 LDR descriptors) showed:

| Path / primitive | Exact registry word6 process target of R03C | Interpretation / integration |
| --- | --- | --- |
| Guitar jack Input reader `0x2a94`, registry `0x200000` | `0xe4f4a` | Already wrapped by `src/sharc/gate_sc.asm::ENTRY_2A94` for Input Sidechain; use its Input `0x2390` capture stage to meter the selected guitar signal, without disrupting input-gate sidechain |
| Aux/Return jack reader `0x2a97`, registry `0x200008` | `0x8cdca` | Original stock function; if meter must follow Aux/Return as selected input, may need separate path |
| USB source reader `0x2a9b`, registry `0x200010` | `0x8cdd2` | Original stock function; physical guitar-only reader is insufficient when preset input is USB 5/6 |
| Main jack output writer `0x2aa8`, registry `0x200018` | `0xe5024` | Already wrapped by `src/sharc/main_send.asm::ENTRY_2AA8`; `I1` contains its 16 pre-writer float samples per call, one channel per instance |
| Send jack output writer `0x2aaa`, registry `0x200020` | `0xe4ff6` | Already wrapped by `src/sharc/usb_monitor.asm::ENTRY_2AAA`; should be accounted for in Send/USB modes |
| USB output writer `0x2aac`, registry `0x200028` | `0xe5081` | Already wrapped by `src/sharc/main_send.asm::ENTRY_2AAC`; ch0,1 deliver USB1/2; ch2,3 USB3/4 |
| Phones writer `0x2aab`, registry `0x200030` | `0xe5046` | Already wrapped by `src/sharc/main_send.asm::ENTRY_2AAB`; beware volume control and distinct signal routes |
| Input block meter `0x2390`, registry `0x200378` | `0xe4f4d` | Already wrapped by gate sidechain; used to capture Input L and R before the Input Gate, with its own `SC_ARM` state |
| Compressor GR code | Actual entries in the `0xe51xx` PM region | GR already hooks compressor primitives, and can provide M4 meter frontend; must continue operating on its own terms |

The values above come from the *installed build's exact .hxf bytes*, **not just upstream source comments**. They demonstrate nontrivial overlap with already patched primitives: adding a second independent registry wrapper carelessly would overwrite the first and break USB Monitor or Sidechain. The safest source-level strategy integrates sampling **into/around the existing wrappers** through a deliberately shared hook or a provably safe trampoline, retaining original call and register contracts.

### Defining what the bars actually measure

**Input**: recommend the selected **Input block's post-ADC, pre-effects/input-gate digital signal**, stereo-combined as `max(abs(L),abs(R))` per 16-sample slice. This is appropriate to judge near-digital-full-scale levels and input-pad behavior, but needs an explicit choice for alternate USB/Aux/Return input paths and a test that the real Input Gate doesn't disguise the pre-gate meter. Note that zero after digital clipping tells nothing about *how far beyond the ADC rail the analogue signal went*.

**Output**: recommend **final processed level at the selected output bus**; default Main L/R, with Send/USB as the active source when `HX_USB_MONITOR` route is Send/USB. With split paths and mixed Main+Send, an explicitly defined combined or selectable policy is needed. Monitoring Main-only while the preset is routed to Send would produce an erroneous empty output meter. The `0x2aa8` writer is a good Main source *before its sample conversion/clipping*, and `0x2aaa`/`0x2aac` are viable Send/USB sources. Avoid conflating the audio that reaches USB 1/2, Main jacks, and headphones—the stock and HXtra graph can separate them.

The initial metric should be **sample peak in dBFS**, with an unambiguous scale. Combining 16-sample peaks over 64 DSP blocks gives **1024-sample / 21.333ms windows** (as existing `frame_probe.asm` does). Report perhaps 10–12 nonuniform bins covering `−60 … 0 dBFS`, with a fast attack, release, 0.5–1s peak hold and a marked clip region near full scale. An RMS or loudness-style meter would be more reliable for matching presets of different dynamics, and can be deferred because it requires more DSP accumulation and calibration. Sample peaks do not detect intersample clipping.

### Reuse opportunities and major caveats

- **M4 receive**: existing `tools/features/gr.py` + `src/m4/gr_meter.s::frame` receive a marked 256-word DSP→M4 frame on the existing stock callback `0x28da6134`. They read peak amplitudes (DSP frame words216/217), a window count (250), and convert IEEE float magnitude to base-2 log in `lg` (about 0.14dB approximation error, per source comments). Adapt the *absolute peak* calculation, not the GR ratio/threshold or release coefficient; M4 callback has no FPU context.
- **M4 UI**: `construct`, `erase`, `draw`, `layout`, widget initialization, widget locking, conditional repaint and `src/m4/dsp_meter.s` display code are reusable patterns. Receive-thread handlers should update **only numeric state** and request bounded repaints; create/move/paint widgets only in the UI context under the correct widget lock. Don't copy the #176/#185 lifecycle/damage bugs.
- **DSP GR peak**: `src/sharc/frame_probe.asm` already uses a 64-block peak window and writes `FP_WIN` into frame words216/217 with marker200. However this measurement is **from the selected compressor core**, not the device-wide input/output, and the GR publisher/scanner only operates while a relevant compressor core executes. Thus copying those two values alone is not a general input/output meter.
- **R03C metronome SPI transport**: its event/complement uses **M4→SHARC TX words240/241**, whereas GR transports DSP→M4 in the **opposite direction** using 200/216..218/250/251. These are separate directional frames and can coexist if both RX handlers and frame validity guards remain intact. Additional I/O meter telemetry should use a new identifiable tag, sequence/window and dedicated reserved words and must not mutate M4→SHARC counter240/241.
- **Guaranteed publisher**: the GR code scans memory to locate and cache valid SPI frame ring slots. A new non-compressor-dependent meter must be published continuously. A viable candidate is a short periodic publisher in an always-executed input/output-wrapper path, reusing a discovered frame address. This requires **new hardware tracing of the DSP receive frame** and careful cycle budgeting; it cannot simply rely on GR running. A shared cached-frame publish helper may avoid a second full memory scan; this is a *design proposal*, not hardware verified.

## Exact resource budget and the decisive installation constraint

From real R03C HXF, independently checked with `tools/metro_led_sharc_patch.py::parse_ldr`:

- Entry2 SHARC bootstream: **524,212 bytes of the 524,288-byte partition** → only **76 bytes** remaining. Its 201 descriptors are 81 tag1, 72 tag4, 23 tag3, 13 tag5, 8 tag10 and 4 tag2. Conventional append of even a small initialized code+data module would not fit. This is the **first gate** for full-feature parity.
- The actual live register targets match the upstream **two NAM A2 Lite slots + HX_CLICK + HX_FX_GATE + HX_GR + HX_USB_MONITOR + HX_GATE_SC** layout. `tools/block3.py` confirms 2-NAM room **2528 normal words**; those DSP features cost **240 + 291 + 780 + 414 + 324 = 2049 words**, leaving **479 normal words** before the kernel's calculated Block3 bound, independently of the 76-byte bootstream issue. This 479 is only *memory placement* headroom, not an unmeasured execution-time or eMMC budget.
- Exploratory scan of same-type, adjacent physical initialization record ranges in 201 LDR descriptors found a **naive upper bound** of 60 bytes from 4-byte DM records, 36 from PM records and 72 from tag1 records, **168 bytes total** in descriptor overhead if reorganized. That count does **not** validate reordering, alignment, duplicate/overlapping writes, zero-fill semantics or boot side effects, and even 76+168=**244 bytes** would leave minimal payload room for actual peak accumulation/publishing. More aggressive proven compression, code reuse, or removal of an existing feature would be necessary. **Never claim the entire 168 bytes are safely reclaimable.**
- The existing GR carries a scan of the entire prospective DSP frame-buffer memory and appends its own DSP code. A naive second copy could create a performance regression and cause freezes near the SHARC limit. Measure added cycles in the emulator and on hardware with worst-case presets before integration.
- M4 program code budget is much more generous (the repo documents >1MB free). Its main risks are home-screen paint races, hooks colliding with DSP Usage and GR and high-frequency UI invalidation; peak reporting at 20–40Hz is a reasonable starting target.

**Engineering implications:** do not try the stock `HX_CLICK` builder on top of the already HXtra-modified R03C file, nor rewrite the permanent image in place without revalidating the exact modified SHARC record topology. Keep the frozen R03C binary/feature set. Integrate source-level code into a new isolated experimental version, re-create from the exact selected donor, run all integrity/alias tests and only run it from RAM if user chooses. Reducing NAM slot count or removing GR/USB/sidechain would be a **real feature regression**, not a free workaround.

## Feasibility options, ranked

1. **First try: reuse a genuine native continuous signal value, if present.** Disassemble the stock Input/Output icon signal/clip status update, trace its data source and determine if it contains a real amplitude or only an enum/bool. If a float-like measured amplitude is already available on M4, the feature becomes an M4-only UI task and the 76-byte DSP bootstream limit is irrelevant. **No such usable continuous float has yet been identified.**
2. **Primary likely strategy: extend existing DSP Input/Output wrappers with a minimal shared peak accumulator and low-rate outgoing frame publisher.** This is architecturally grounded (physical paths already patched), but require a measurable new flash-space solution, deterministic DSP→M4 update independent of compressor and emulator/hardware proof.
3. **Fallback: rebuild DSP package and reclaim bootstream space via verified semantic-preserving initialization optimization**, with exact loaded DM/PM memory, all 15 entry checksums, unchanged bootloader, and a full functional parity suite. Reuse existing GR publishing/routing code where practical, but do not sacrifice GR.
4. **Lowest-priority alternative: a separate extra meter/monitor view**, as suggested in issue #116's comment, if the home screen's top/bottom edge cannot coexist with GR and existing UI.

## Testing required before claiming feature success

1. **Pre-implementation**: inspect the stock green/red signal indicator M4 code and trace its exact input. Bench-mark DSP cycles for the selected input/output primitives across guitar, USB, Aux, path B and all `HX_USB_MONITOR` modes.
2. **First prototype: UI-only** with synthetic fixed or ramp values on M4; verify both 160px regions and labels at all thicknesses, home/stomp/snapshot/preset changes and split/no-split, and no blanking of the stock divider/GR, BPM, breathing and DSP Usage %. This is offline or a new consented RAM-run only.
3. **DSP transport prototype**: inject known -60,-48,-36,-24,-18,-12,-6,-3,-1,0 dBFS 220Hz/1kHz waveforms via USB5/6 (source selected), validate 16 sample peak extraction and 1024-sample cadence, 5bit virtual thickness, stereo channel max, overload hold and decays. Cross-check against an independent 48kHz audio recording and/or DSP emulator, with sound effects off, then full preset chain.
4. **Worst-case**: near-90% DSP presets with 2 NAM, GR, Input Sidechain, USB Monitor+Main+Send, FX Gate, R03C metronome; no input switching, preset changes, snapshots, bypass, DSP Usage disappearance or double clicks. Measure persistent hook time and firmware boot correctness. No silent downgrade to fewer NAM slots or removal of features.
5. **Release gates**: no release HXF or updater flash before the new revision demonstrates boot, UI, correct meter reading, stable >several-minute test and original feature parity on physical Stomp through an explicitly initiated **RAM** run.

## Current conclusion

- Home-screen bars and global settings: **feasible; established M4 infrastructure**.
- Tap points for primary physical input/Main output: **verified in the R03C image**, but full selected Input/Output routing support requires additional work.
- GR's absolute dB math and screen widgets: **substantially reusable**, with source-known bugs to avoid.
- DSP→M4 telemetry when no compressor is present: **unproven**, primary new code.
- DSP memory: **479 normal words nominal headroom at 2 NAM slots** (need profiling).
- Persistent HXF's DSP bootstream partition: **76 bytes headroom**, primary gating obstacle.
- Stability of the exact flashed working R03C metronome, DSP Usage, GR, Sidechain and USB Monitor: mandatory hard constraint.
- No new firmware has been built, run or flashed, and no user device settings/presets were changed as part of this research.

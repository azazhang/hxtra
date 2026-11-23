# R04 HW03 guitar isolation → R05 two live candidate bars

Date: 2026-11-23 (America/New_York). R04 HW03 physically measured. R05 is a user-opt-in RAM experiment; physical R05 boot pending.

## R04 controlled guitar-only measurements

The user signaled readiness after bypassing the Metronome block and played guitar. A read-only 150-snapshot, 15.89-second native ledger capture was executed through R04 editor command 0x13. A later direct preset read verified setlist 0 / preset 122 "Super Lead", path 0 slot 7 (Metronome model 181) **off**. The separate M4 metronome-active flag remained true; that signal cannot substitute for the block's actual bypass state. No audio was injected and no pedal settings were changed by the assistant.

Native RX M4 frames: 1,160,222 → 1,196,473 (+36,251). Nonempty native packets: 34,705 → 35,488 (+783). Accepted 44-word packets: 2,957 → 3,077 (+120). R04 trial bar changes: 1,807 → 1,881 (+74), but widths remained close to 29px.

| Native event family / parameter | New records during HW03 | Last values across 150 host samples | Interpretation |
| --- | ---: | --- | --- |
| 0x0002002a /1 | +103 | -39.077 to -15.512 | Guitar responsive; also metronome pulse responsive in prior HW02 — output candidate |
| 0x0002002a /2 | +36 | -67.908 to -15.512 | Less frequent companion parameter; stale for much of sample |
| 0x00020002 /3 | +290 | -80.994 to -32.394 | Guitar responsive; no strong metronome signal in HW02 — input candidate |
| 0x00020000 /2 | +145 | -72.350 to -64.847 | Prior R03/R04 bar source: little useful guitar response |
| 0x00020000 /1 | +129 | -82.283 to -80.915 | Only baseline variation |
| 0x00020000 /3,4,6 | +143/+136/+275 | -120.0 constant | Inactive paths in this preset |
| 0x0002002e /1 | +194 | -1.0 to +77.352 | Not a reliable dB meter field |

Pearson sample-aligned correlation between 0x00020002/3 and 0x0002002a/1 during guitar playback was +0.6666, about +0.632 at a one-sample displacement. The old 0x00020000/2 bar source correlated only +0.171 with the 0x0002002a/1 guitar-responsive value.

In separate R04 HW02 observations with metronome on, 120 read-only 0x13/0x50 paired polls over 15.83s showed 29 TAP LED events and 24 high-level pulse runs in 0x0002002a/1. Pulse maxima were around -12.3 and aligned with TAP events; 0x00020002/3 remained near -88 to -87. Thus we have direct physical evidence that the first candidate is responsive to guitar, while the second tracks guitar and metronome. **Exact physical Guitar-In, Main, Send and USB bus assignment is not conclusively established.** These remain provisional candidate labels.

Private raw evidence, never committed to Git: Mac mini /tmp/io-level-r04-HW03-guitar-only-150.jsonl; source Mac also has a copy under /tmp.

## R05 code behavior

Branch: experiment/io-level-r05-live-input-output-candidate-bars-20261123.

Assembled M4 source: src/m4/io_level_r05_live_source_pairs.s. New R05 left/Home green source: exact native family 0x00020002, parameter 3. New right/Home blue source: exact native family 0x0002002a, parameter 1. Those are two separate incoming native events read in the R04 five-word event handler. Both keep the 132-pixel width scale over -90..0 dB-like units; the R04 24-key rolling 640-byte read-only editor 0x13 ledger remains available. Full 44-word packets still update diagnostic counters and raw readback, but their old wrong-family reading can no longer replace either bar.

Expected widths from actual observed HW03 guitar values: left about 13–84px, right about 75–109px. Metronome-only candidate output pulse -12.3 corresponds to about 114px and input candidate should remain near baseline. These are prediction/test targets based on real recorded values, **not physically verified R05 behavior**.

The M4 coalesces changed live states to at most one UI redraw per 100 SHARC/M4 receive callbacks (~23Hz at measured 2,300 frames/s), keeping the 132x5 pixel Home gap layout x24..155 and x164..295, y113–117. Each source has an independent 4,600-callback (~2-second) stale expiry. One source can clear without erasing the other. M4 source labels, display locations and original 0x13 ledger retained from R04 except the explicitly changed sources.

During assembled Cortex-M4 emulator testing, a genuine new R05 bug was caught: a UI throttle tick was not stored before an early branch; this would have prevented pending redraws. It was corrected before building/staging the candidate and the repaint test now passes. Tests cover input-only, output-only, combined signals, full 44-word old-family packets unable to overwrite new values, non-candidate native packets, delayed UI repaint, per-source stale expiry, and exact 640-byte ledger reply. Source and firmware must remain isolated from the already physically tested R04.

## Reproducible exact frozen build / risk controls

- Installed R03C HXF SHA256: 42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b
- R05 candidate HXF SHA256: 3eef769a0457cfa1fa4d089a92b0ebab242b0570977d94c13fb155276243112a
- R05 module adds 2,612 M4 app bytes relative to physically booted, SHA-pinned R01, modifying only the same three M4 hook sites.
- All 14 non-M4 L6IA entries are byte-identical to installed R03C. Additional SHARC instructions: 0. DSP bootstream byte growth: 0.
- R05 RAM plan SHA256: 9163e49b2b96afad749afc3e60796a84bbc13a68419fc97e8c8c7238ee6134ac.
- Nine M4 RAM regions, two read-only installed-R03C eMMC/SHARC CRC comparisons, zero eMMC overlays, zero permanent writes.
- USB Monitor, original R03C metronome code and M4 service 0x50, GR, DSP Usage %, stored presets, user global settings and R01 0x4F native capture preserved in the candidate binary. Actual physical Home rendering requires verification.
- Never install R05 with Line 6 Updater. It is **RAM-only, user-initiated Chrome WebUSB**.

## Hardware validation needed

After user power-cycles R04 back to persistent R03C, they may launch the R05 RAM trial from the Mac mini Chrome page at http://localhost:8765/IO-LEVEL-R05-LIVE-INPUT-OUTPUT-CANDIDATE-BARS/ . With metronome bypassed, guitar playing should produce independent bar activity. With guitar muted and metronome engaged, the blue right candidate should pulse, green left remain low. Assistant can read packed bar-state counters and current native event ledger through the same read-only 0x13 service, using tools/io_level_r04_native_ledger.py, and diagnose any discrepancy.

Physical R05 launch, source calibration and independent Main/Send/USB routing identification remain unresolved.

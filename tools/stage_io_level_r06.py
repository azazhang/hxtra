#!/usr/bin/env python3
"""Offline stage R06 two independent observed native-event candidate bars for opt-in WebUSB RAM test.

A physical R01 native-frame capture already established the packet shape.
R06 builds from exact permanently flashed R03C, adds M4 RX, Home and read-only editor subscribers, and
Home paint, and preserves R01's read-only editor 0x4f command.  No device
connection, power cycle, reset, or firmware install occurs in this script.
"""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_io_level_r06_segmented_peak_envelope import NAME,FROZEN_SHA256

def sha(data):
    return hashlib.sha256(data).hexdigest()

def stage():
    out=ROOT/'build/browser-ramrun'/NAME
    report=json.loads((out/'manifest-build.json').read_text())
    spec=json.loads((out/'manifest-plan.json').read_text())
    plan=json.loads((out/'regions/plan.json').read_text())
    assert report['variant']==spec['variant']==NAME
    assert report['donor_exact_flashed_R03C_SHA256']==spec['flashed_donor_R03C_SHA256']==FROZEN_SHA256
    assert report['HXF_SHA256']==spec['candidate_HXF_SHA256']
    assert report['modified_archive_entries']==spec['changed_archive_entries']==[0]
    assert report['original_14_non_M4_entries_identical']
    assert report['new_DSP_bootstream_bytes']==report['new_SHARC_instructions']==0
    assert report['R06_not_updater_flash_approved']
    assert report['actual_input_output_channel_mapping_verified'] is False
    assert report['audio_input_output_calibrated_on_unit'] is False
    assert plan['summary']['unit']=='HX Stomp'
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['overlay_sectors']==0
    assert plan['summary']['runs']==0 and plan['summary']['changed']==[]
    assert len(plan['checks'])==2 and len(plan['regions'])==9
    assert sha((out/'regions/plan.json').read_bytes())==spec['plan_sha256']
    template=ROOT/'web/experiments/io-level-r01-native-frame-probe'
    browser=(template/'ramrun.js').read_bytes()
    html=(template/'index.html').read_text()
    old='IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE'
    assert html.count(old)>=5
    html=html.replace(old,NAME)
    start=html.index('<p><strong>')
    end=html.index('<div id="status">')
    desc=f'''<p><strong>IO-LEVEL-R06: independent hardware-style colored LED peak meters.</strong>
This isolated M4-only experiment preserves R05's verified working native source IDs
exactly: left/Input candidate <code>0x00020002 / 3</code> and right/Output
candidate <code>0x0002002a / 1</code>. These are provisional physical jack
assignments, pending independent analog signal-path validation.</p>
<p><strong>NEW HOME DISPLAY:</strong> each bar has <strong>16 disjoint LED
blocks, each 7 by 5 pixels with a 1px dark gap</strong>, fitting exactly into
R05's original x24..155 (left) and x164..295 (right), y113..117. The first
10 LEDs are green, next 3 amber, next 2 orange, last 1 red. No other Home
widgets or global layout structures are changed.</p>
<p><strong>ACTUAL METER BALLISTICS:</strong> maximum real native level is
latched between 100-RX-frame (~43ms) display updates; 2-tick (~86ms) peak
visibility hold followed by 12px per tick (~300ms for a strong click to
reach baseline). This shows short native transients even if a later native
record is quieter when the LCD draw begins. It never creates meter peaks
from the TAP beat; R05 hardware measurements already confirmed that
some TAP beats have no high native peak at all. This build improves honest
visibility of peaks <em>that were reported</em>. It does not claim to repair
the earlier upstream intermittent missing-peak records.</p>
<p><strong>NEW READ-ONLY DIAGNOSTIC:</strong> editor command <code>0x13</code>
still returns exactly 640 bytes and the same 24 keyed native ledger rows at
bytes 64..639. The signature is now <code>IOM6</code>; bytes 32..63 contain
actual Home paint callback enters, UI redraw request count, painted/current
visual widths, native high-event counts, pending native peaks and high-level
paint calls. The original eight unselected bulk 44-word float samples in
those bytes are replaced. Source keys, R03C metronome <code>0x50</code>, and
R01 raw native capture <code>0x4F</code> are otherwise preserved.</p>
<p>Exact installed R03C donor SHA256:
<code>{FROZEN_SHA256}</code>. R06 candidate SHA256:
<code>{report['HXF_SHA256']}</code>. R06 adds
<strong>{report['R06_added_M4_app_bytes']} M4 app bytes</strong> relative to
pin-verified physically booted R01; only three M4 hook sites change.
All other 14 L6IA archive entries are exactly identical to R03C. No
SHARC instructions are added; the installed metronome, compressor GR,
DSP Usage %, NAM, USB Monitor, presets and settings are preserved.</p>
<p class="warn"><strong>RAM-ONLY USER TEST — do not flash with Line 6
Updater.</strong> Power-cycle out of currently running R05 to the permanently
installed R03C first, then use Chrome WebUSB to opt in to the RAM-only run.
Preflight verifies two read-only eMMC CRCs and stages nine RAM regions
without permanent eMMC writes or overlays. Check LEDs and color transitions,
guitar sensitivity, metronome clicks, DSP usage percentages and original
HXtra features. If the pedal freezes, record the browser log and power-cycle
back to permanent R03C. Physical R06 boot and performance are unverified.</p>
'''
    html=html[:start]+desc+html[end:]
    html=html.replace('Preflight: incorrect R01 RAM plan','Preflight: incorrect R06 RAM plan')
    html=html.replace('IO-LEVEL-R01 native meter event capture:',
                      'IO-LEVEL-R06 segmented native LED meter preflight:')
    html=html.replace('IO-LEVEL-R01 native RX frame preflight:',
                      'IO-LEVEL-R06 segmented colored LED RAM preflight:')
    html=html.replace('R01 native meter capture RAM handoff reported',
                      'R06 native LED peak-meter RAM handoff reported')
    html=html.replace('exact R03C donor, unchanged DSP, native RX capture via editor 0x4f',
                      'two native-key 16-segment LED bars, true-peak latch, 0x13 IOM6 paint diagnostics; unchanged SHARC')
    html=html.replace('WebUSB RAM handoff reported. Verify device operation; capture real DSP frames with tools/io_level_r01_native_frame_probe.py. No real input/output meter is drawn yet.',
                      'WebUSB RAM handoff reported. Verify 16 colored disjoint LED blocks in each Home meter; guitar/metronome physical behavior and DSP Usage%. Assistant can inspect IOM6 0x13 native peaks, repaint requests and Home paint callback counts. Do NOT flash.')
    assert 'manifest.checks?.length!==2' in html
    assert 'manifest.summary?.overlay_sectors!==0' in html
    assert 'manifest.summary?.changed?.length!==0' in html
    assert 'do not flash' in html.lower()
    assert old not in html
    web=ROOT/'web/experiments/io-level-r06-segmented-peak-envelope'
    web.mkdir(parents=True,exist_ok=True)
    (web/'index.html').write_text(html)
    (web/'ramrun.js').write_bytes(browser)
    (web/'README.md').write_text(f'''# {NAME}

**Experimental, user-initiated RAM-only colored LED peak meter prototype.**

- Exact R03C frozen HXF donor SHA256: `{FROZEN_SHA256}`.
- R06 candidate HXF SHA256: `{report['HXF_SHA256']}`.
- All 14 non-M4 archive entries byte-identical to R03C; no SHARC changes.
- R05 native keys unchanged: left `0x00020002 / 3`, right `0x0002002a / 1`.
- Two Home bars, 16 green/amber/orange/red independently lit 7x5 LED blocks
  each, 1px gaps; inside original x24..155 and x164..295, y113..117.
- Genuine native peak latch across RX windows, 2-tick peak visibility hold,
  12px/tick decay. Never generates fake amplitude from TAP.
- Read-only `0x13` IOM6 640-byte record with all 24 keyed native ledger rows
  and fresh Home paint/redraw/native-high telemetry at bytes 32..63.
- Source identities remain PROVISIONAL and uncalibrated to physical I/O.
- 9 RAM regions, 2 read-only eMMC CRC checks, zero persistent writes.
- DSP Usage %, GR, NAM, USB Monitor, Metronome, presets unaffected in binary.
- **Never install with Line 6 Updater; RAM-only Chrome WebUSB trial.**
''')
    loader=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/firmware-ramboot.dfu'
    assert loader.is_file() and loader.stat().st_size==4112
    shutil.copyfile(loader,out/'firmware-ramboot.dfu')
    for f in ('index.html','ramrun.js'):
        shutil.copyfile(web/f,out/f)
    staged={
       'variant':NAME,'stage':'OFFLINE_RAM_READY_HARDWARE_UNTESTED',
       'source_R03C_firmware_flashing_untouched':True,
       'hardware_boot_verified':False,
       'HXF_SHA256':report['HXF_SHA256'],
       'donor_R03C_SHA256':FROZEN_SHA256,
       'modified_L6IA_entries':[0],
       'other_14_L6IA_entries_byte_identical':True,
       'new_SHARC_instructions':0,
       'writes':'ram','eMMC_overlay_sectors':0,
       'eMMC_readonly_checks':2,
       'planned_RAM_regions':9,
       'plan_SHA256':spec['plan_sha256'],
       'loader_SHA256':sha(loader.read_bytes()),
       'browser_SHA256':sha(browser),
       'bars_drawn_in_M4_software':True,
       'diagnostic_read_only':True,
       'R06_event_ledger_command':0x13,
       'R06_event_ledger_response_bytes':640,
       'R06_event_ledger_slots':24,
       'R06_led_segments_per_bar':16,
       'R06_7px_LED_width_1px_gap':True,
       'R06_IOM6_signature':'IOM6',
       'R06_M4_native_peak_hold_per_interframe':True,
       'R06_paint_callback_telemetry_available':True,
       'R06_live_bar_resolution':132,
       'R06_input_candidate':['0x00020002',3],
       'R06_output_candidate':['0x0002002a',1],
       'R06_physical_mapping_provisional':True,
       'physical_Input_Output_mapping_verified':False,
       'user_initiated_only':True,
       'web_path':NAME,
    }
    (out/'manifest-stage.json').write_text(json.dumps(staged,indent=2)+'\n')
    print(json.dumps(staged,indent=2))
    return staged

if __name__=='__main__':
    stage()

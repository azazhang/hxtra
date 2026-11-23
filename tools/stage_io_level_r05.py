#!/usr/bin/env python3
"""Offline stage R05 two independent observed native-event candidate bars for opt-in WebUSB RAM test.

A physical R01 native-frame capture already established the packet shape.
R05 keeps exact permanently flashed R03C, adds M4 RX, Home and read-only editor subscribers, and
Home paint, and preserves R01's read-only editor 0x4f command.  No device
connection, power cycle, reset, or firmware install occurs in this script.
"""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_io_level_r05_live_source_pairs import NAME,FROZEN_SHA256

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
    assert report['R05_not_updater_flash_approved']
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
    desc=f'''<p><strong>IO-LEVEL-R05: two independently responsive native meter candidate bars.</strong>
R04's physical guitar-only capture with Metronome block bypassed showed a
strong guitar-responsive native value at <code>0x00020002 / parameter 3</code>,
while both guitar and metronome activity strongly changed another value at
<code>0x0002002a / parameter 1</code>. The two records varied independently
while the prior R02/R03/R04 trial bars read the wrong native family.</p>
<p><strong>Left green bar:</strong> provisional Input candidate
<code>0x00020002 / 3</code> (upstream guitar-responsive; physical input jack
identity not yet proven). <strong>Right blue bar:</strong> provisional Output
candidate <code>0x0002002a / 1</code> (tracks guitar and pulses aligned with
TAP/metronome; Main/Send/USB destination not yet proven). Each bar is
132 × 5 pixels at x24..155 or x164..295, y113..117. Real native values
are mapped over −90 to 0 dB-like units at approximately 0.68 dB/pixel.
Updates are independent for each source, with up to ~23 Home refreshes/sec,
and a two-second stale expiry per bar if its native source stops reporting.
Neither value is currently calibrated against external audio hardware.</p>
<p><strong>The existing native event ledger is preserved.</strong> Read-only
editor command <code>0x13</code> reports 24 keyed object/parameter rows with
last value, min, max and count in exactly 640 bytes. The R01 read-only raw
capture command <code>0x4F</code> and R03C metronome command
<code>0x50</code> are unchanged. The 44-word native meter packet is still
counted and recorded, but its wrong-family values are excluded from the
new two-bar display. No new SHARC code or DSP side processing is added.</p>
<p>Relative to the physically booted R01 M4 application, this R05 build adds
<strong>{report['R05_added_M4_app_bytes']} bytes</strong> at three hook sites
(RX callback, Home paint callback, read-only editor registration). All 14
non-M4 archive entries are identical to the installed R03C image
SHA256 <code>{FROZEN_SHA256}</code>. R05 HXF SHA256:
<code>{report['HXF_SHA256']}</code>. Global settings, presets,
DSP Usage %, gain-reduction meter, USB Monitor and metronome code are
preserved in the candidate image.</p>
<p class="warn"><strong>Opt-in RAM-only evaluation; do not flash with
Line 6 Updater.</strong> First power-cycle out of the currently running R04
RAM trial to the permanently installed R03C, then Run from Chrome WebUSB.
Preflight checks two read-only eMMC reference CRCs, stages nine RAM regions,
performs zero permanent eMMC writes and no eMMC overlay. Check that both
bars move independently while playing; with the guitar stopped, the
Output candidate should pulse with the metronome while the Input candidate
remains near baseline. These behaviors are physical test targets; R05
has passed only offline validation. If the device freezes, save the
Chrome log and power-cycle to return to permanent R03C.</p>
'''
    html=html[:start]+desc+html[end:]
    html=html.replace('Preflight: incorrect R01 RAM plan','Preflight: incorrect R05 RAM plan')
    html=html.replace('IO-LEVEL-R01 native meter event capture:',
                      'IO-LEVEL-R05 dual live native-key bar preflight:')
    html=html.replace('IO-LEVEL-R01 native RX frame preflight:',
                      'IO-LEVEL-R05 live native-key RAM preflight:')
    html=html.replace('R01 native meter capture RAM handoff reported',
                      'R05 dual live native candidate bar RAM handoff reported')
    html=html.replace('exact R03C donor, unchanged DSP, native RX capture via editor 0x4f',
                      'two separately selected 132px real native event bars; 0x13 rolling ledger; unchanged SHARC')
    html=html.replace('WebUSB RAM handoff reported. Verify device operation; capture real DSP frames with tools/io_level_r01_native_frame_probe.py. No real input/output meter is drawn yet.',
                      'WebUSB RAM handoff reported. Play guitar and engage metronome to verify separate left/right live native record sources. Read-only editor 0x13 24-key ledger retained. Do NOT flash.')
    assert 'manifest.checks?.length!==2' in html
    assert 'manifest.summary?.overlay_sectors!==0' in html
    assert 'manifest.summary?.changed?.length!==0' in html
    assert 'do not flash' in html.lower()
    assert old not in html
    web=ROOT/'web/experiments/io-level-r05-live-source-pairs'
    web.mkdir(parents=True,exist_ok=True)
    (web/'index.html').write_text(html)
    (web/'ramrun.js').write_bytes(browser)
    (web/'README.md').write_text(f'''# {NAME}

**Experimental, user-initiated RAM-only, two independently source-keyed live bars.**

- Exact user-installed R03C HXF donor SHA256: `{FROZEN_SHA256}`.
- R05 candidate HXF SHA256: `{report['HXF_SHA256']}`.
- All 14 non-M4 archive entries byte-identical to R03C; no SHARC change.
- Left Home candidate (green): `0x00020002 / 3`, guitar-responsive in R04 HW03.
- Right Home candidate (blue): `0x0002002a / 1`, guitar- and TAP-responsive in R04 HW01-03.
- Home bar geometry: x24..155, x164..295; y113..117, 132 independent pixels each.
- Debounced frame/UI repaint max about 23 Hz; independent ~2s stale clear.
- Read-only `0x13` rolling 640-byte/24-key ledger and R01 `0x4F` retained.
- Source identities are PROVISIONAL: not externally calibrated to physical jack or Main/Send/USB.
- 9 RAM regions, 2 read-only eMMC CRC references, zero permanent flash writes.
- DSP Usage %, GR, USB Monitor, Metronome and presets remain untouched in firmware.
- **NEVER install with Line 6 Updater; opt-in Chrome WebUSB RAM trial only.**
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
       'R05_event_ledger_command':0x13,
       'R05_event_ledger_response_bytes':640,
       'R05_event_ledger_slots':24,
       'R05_live_bar_resolution':132,
       'R05_input_candidate':['0x00020002',3],
       'R05_output_candidate':['0x0002002a',1],
       'R05_physical_mapping_provisional':True,
       'physical_Input_Output_mapping_verified':False,
       'user_initiated_only':True,
       'web_path':NAME,
    }
    (out/'manifest-stage.json').write_text(json.dumps(staged,indent=2)+'\n')
    print(json.dumps(staged,indent=2))
    return staged

if __name__=='__main__':
    stage()

#!/usr/bin/env python3
"""Offline stage R02 two horizontal DSP-native bars for opt-in WebUSB RAM test.

A physical R01 native-frame capture already established the packet shape.
R02 keeps exact permanently flashed R03C, adds only an M4 RX subscriber and
Home paint, and preserves R01's read-only editor 0x4f command.  No device
connection, power cycle, reset, or firmware install occurs in this script.
"""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_io_level_r02_native_dual_bar import NAME,FROZEN_SHA256

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
    assert report['R02_not_updater_flash_approved']
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
    desc=f'''<p><strong>IO-LEVEL-R02: two real-time Home-screen level bars based
on the HX Stomp's own native DSP metering events.</strong>
The previously booted R01 read-only capture observed three full native DSP
meter updates (eight five-word records) in 500 incoming RX frames.
This version uses only the validated 44-word native meter packet and leaves
the 512 KiB SHARC bootstream, metronome, USB Monitor, GR meter, DSP Usage
Display, presets and global settings byte-identical to permanently installed
R03C wherever applicable.</p>
<p><strong>Two experimental horizontal bars:</strong> the left green bar uses
the first native meter pair (IDs 2,5); the right blue bar uses the last native
meter pair (IDs 1,5). Each is 132 by 5 pixels in the Home-screen gap above
the bottom labels (x 24 or 164, y 113–117). The scale is approximately
−90 to 0 dB, with 10 stepped levels and amber/red near full scale.
Native activity is updated by the stock DSP at around 10 Hz and the
bars clear after prolonged missing meter packets. Other native packet
formats are ignored so that stale DMA buffer contents cannot masquerade
as a new signal value.</p>
<p><strong>Physical Input/Output assignment remains to be validated.</strong>
The first pair is temporarily drawn on the left and the last pair on the
right. We have NOT yet established which pair tracks the selected actual
physical or USB input and which tracks Main/Send output. This is an
experimental display to establish that mapping from a controlled signal,
not a calibrated two-bus meter ready for permanent installation.
The read-only R01 editor command <code>0x4F</code> stays available.</p>
<p>The candidate adds exactly <strong>{report['R02_added_M4_app_bytes']} bytes</strong>
to the R01 M4 application with only two extra M4 hook points.
All <strong>14 non-M4 firmware entries</strong> are identical to the
installed R03C image SHA256 <code>{FROZEN_SHA256}</code>.
The R02 HXF SHA256 is <code>{report['HXF_SHA256']}</code>. No SHARC code,
bootstream records, USB routing, saved setting, or footswitch function has
been changed by this build.</p>
<p class="warn"><strong>Opt-in RAM experiment ONLY. Do not flash with
Line 6 Updater.</strong> Power-cycle out of the currently running R01
RAM experiment to the permanently installed R03C first.
The preflight requires 9 RAM regions, 2 read-only eMMC identity checks
covering the frozen R03C SHARC partition, 0 eMMC overlays, and writes=RAM.
Press Run yourself, choose the USB device when prompted, and observe the
two bars while playing a known signal through the input and output paths.
No physical R02 test has occurred yet. If it freezes, save the browser
log, power-cycle and the permanently installed R03C returns.</p>
'''
    html=html[:start]+desc+html[end:]
    html=html.replace('Preflight: incorrect R01 RAM plan','Preflight: incorrect R02 RAM plan')
    html=html.replace('IO-LEVEL-R01 native meter event capture:',
                      'IO-LEVEL-R02 dual-bar native meter preflight:')
    html=html.replace('IO-LEVEL-R01 native RX frame preflight:',
                      'IO-LEVEL-R02 dual-bar native frame preflight:')
    html=html.replace('R01 native meter capture RAM handoff reported',
                      'R02 native dual-bar RAM handoff reported')
    html=html.replace('exact R03C donor, unchanged DSP, native RX capture via editor 0x4f',
                      'two Home bars from native DSP meter packets; unchanged SHARC; 0x4F capture retained')
    html=html.replace('WebUSB RAM handoff reported. Verify device operation; capture real DSP frames with tools/io_level_r01_native_frame_probe.py. No real input/output meter is drawn yet.',
                      'WebUSB RAM handoff reported. Test the two bars using real signal activity; verify first/last native pair mapping, DSP Usage %, GR, and R03C metronome. Do NOT flash.')
    assert 'manifest.checks?.length!==2' in html
    assert 'manifest.summary?.overlay_sectors!==0' in html
    assert 'manifest.summary?.changed?.length!==0' in html
    assert 'Do not flash' in html
    assert old not in html
    web=ROOT/'web/experiments/io-level-r02-native-dual-bar'
    web.mkdir(parents=True,exist_ok=True)
    (web/'index.html').write_text(html)
    (web/'ramrun.js').write_bytes(browser)
    (web/'README.md').write_text(f'''# {NAME}

**Experimental, user-triggered RAM-only two-bar display.** Build from the
exact R03C user-flashed persistent firmware; R01's live native RX diagnostics
have already been physically verified.

- Frozen R03C SHA256: `{FROZEN_SHA256}`.
- R02 HXF SHA256: `{report['HXF_SHA256']}`.
- Exactly 14 non-M4 archive entries byte-identical to frozen R03C.
- Only two additional M4 hook edits from R01; no new DSP code.
- Home trial bars: left x24–155, right x164–295, y113–117.
- Sources: eight-record native packet, first pair IDs 2/5 and last pair IDs 1/5.
- Native stereo-bus mapping and calibrated dBFS are not yet verified.
- 0 eMMC overlays; 2 read-only eMMC identity checks; writes=RAM.
- The 0x4F native RX capture command still exists.
- No default/global settings or preset records modified.
- **Do not use permanent Line 6 Updater to install this prototype.**
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
       'physical_Input_Output_mapping_verified':False,
       'user_initiated_only':True,
       'web_path':NAME,
    }
    (out/'manifest-stage.json').write_text(json.dumps(staged,indent=2)+'\n')
    print(json.dumps(staged,indent=2))
    return staged

if __name__=='__main__':
    stage()

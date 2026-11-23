#!/usr/bin/env python3
"""Stage an opt-in *RAM-only* native meter event capture web page (offline).

The user must click the WebUSB Run button. No device is contacted here.
Unlike the R03C boot from an HXtra 1.2.1 installation, this R01 donor
is the exact permanently-flashed R03C, so no SHARC/eMMC sector overlay.
"""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_io_level_r01_native_frame_probe import NAME,FROZEN_SHA256

def sha(data):return hashlib.sha256(data).hexdigest()

def stage():
    out=ROOT/'build/browser-ramrun'/NAME
    report=json.loads((out/'manifest-build.json').read_text())
    spec=json.loads((out/'manifest-plan.json').read_text())
    plan=json.loads((out/'regions/plan.json').read_text())
    assert report['name']==spec['variant']==NAME
    assert report['base_R03C_HXF_SHA256']==spec['flashed_donor_R03C_SHA256']==FROZEN_SHA256
    assert report['HXF_SHA256']==spec['candidate_HXF_SHA256']
    assert report['modified_archive_entries']==spec['changed_archive_entries']==[0]
    assert report['all_14_other_entries_including_SHARC_entry2_unchanged']
    assert report['new_DSP_bootstream_bytes']==0
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['overlay_sectors']==0
    assert plan['summary']['runs']==0 and plan['summary']['changed']==[]
    assert len(plan['checks'])==2 and len(plan['regions'])==9
    assert sha((out/'regions/plan.json').read_bytes())==spec['plan_sha256']
    template=ROOT/'web/experiments/metro-ledsync-r03c-hwglitch-repair'
    rawscript=(template/'ramrun.js').read_bytes()
    html=(template/'index.html').read_text()
    old='METRO-LEDSYNC-R03C-HWGLITCH-REPAIR'
    assert html.count(old)>=5
    html=html.replace(old,NAME)
    start=html.index('<p><strong>')
    end=html.index('<div id="status">')
    desc=f'''<p><strong>IO-LEVEL-R01: read-only capture of stock input/output meter messages.</strong>
This RAM diagnostic extends the exact user-flashed R03C firmware without changing
a single SHARC instruction, DSP audio model, DSP usage display, USB Monitor,
existing GR meter, original R03C LED-synchronized click, preset or global setting.
The stock SHARC Input block already runs native peak meter primitive
<code>0x2390</code> and sends its measurement to the standard DSP event queue.
This build records a complete, valid 256-word DSP-to-M4 receive frame exactly
as the M4 sees it, via read-only HXtra editor command <code>0x4F</code>.</p>
<p><strong>This first-stage prototype records the real data. It does not yet draw
input/output level bars.</strong> Their message offsets and interpretation must
be established from real frames before assigning peaks to the left/right bars.
After RAM boot, the host can read frames with
<code>tools/io_level_r01_native_frame_probe.py</code>. Querying command 0x4F
only returns the last fixed snapshot then arms a one-shot capture of the next
valid native frame. The stock GR receiver runs as before. No incoming DSP frame
is modified, and no new DSP code or new screen widgets run.</p>
<p><strong>Current installed firmware must be exactly R03C</strong> (the image
verified in the HWFLASH01 post-update QA). SHA256:
<code>{FROZEN_SHA256}</code>. R01 adds only two M4 hook edits and exactly
{report["new_entry0_size"] - report["original_entry0_size"]} bytes
to the existing M4 application image. All other <strong>14 archive entries</strong>,
including the SHARC bootstream and output-writer/sidechain patches, remain
byte-identical to the installed R03C. A static offline binary audit passed.</p>
<p class="warn"><strong>Opt-in hardware test, RAM only.</strong> The plan sends
nine RAM regions with <strong>zero permanent eMMC writes</strong> and
<strong>zero new SHARC overlay sectors</strong>. Two read-only
identity checks compare the installed SHARC partition header and its first
1,023 full payload sectors against the exact frozen R03C image before RAM
handoff. These checks cover R03C's distinct metronome DSP modifications. The current R03C
persistent installation remains recoverable by a power cycle. The on-device
behavior of this new M4 capture module has not yet been tested. If the device
freezes, save the browser log and power-cycle to return to installed R03C.</p>
'''
    html=html[:start]+desc+html[end:]
    expect="manifest.regions?.length!==9||manifest.checks?.length!==1||manifest.summary?.writes!=='ram'||manifest.summary?.overlay_sectors!==4||manifest.summary?.changed?.[0]?.[3]!==3||manifest.summary?.changed?.length!==1||manifest.summary?.changed?.[0]?.[0]!==2"
    assert html.count(expect)==1
    html=html.replace(expect,"manifest.regions?.length!==9||manifest.checks?.length!==2||manifest.summary?.writes!=='ram'||manifest.summary?.overlay_sectors!==0||manifest.summary?.runs!==0||manifest.summary?.changed?.length!==0")
    html=html.replace('Preflight: unexpected RAM plan (requires 9 regions, 1 verification range, RAM-only writes)',
                      'Preflight: incorrect R01 RAM plan (requires 9 regions, 0 eMMC overlays, 2 identity checks, RAM-only writes)')
    html=html.replace('R03C HWGLITCH repair preflight: 9 RAM regions, 1 eMMC reference check, 4 metadata/payload overlay sectors, writes=ram.',
                      'IO-LEVEL-R01 native meter event capture: 9 RAM regions, 0 changed eMMC sectors, 2 preflight eMMC identity CRC checks, writes=ram.')
    html=html.replace('Power-cycle to return to installed HXtra v1.2.1.',
                      'Power-cycle to return to permanently installed R03C.')
    html=html.replace('R03C HWGLITCH repair RAM handoff reported',
                      'R01 native meter capture RAM handoff reported')
    html=html.replace('exact donor, ordered LED events, dropout grace, read-only M4 transit timing',
                      'exact R03C donor, unchanged DSP, native RX capture via editor 0x4f')
    html=html.replace('WebUSB RAM handoff reported; verify startup, DSP Usage %, no double click, and M4 latency. Optical/audio lag remains unproven.',
                      'WebUSB RAM handoff reported. Verify device operation; capture real DSP frames with tools/io_level_r01_native_frame_probe.py. No real input/output meter is drawn yet.')
    html=html.replace('R03C HWGLITCH repair preflight:', 'IO-LEVEL-R01 native RX frame preflight:')
    assert old not in html
    assert "manifest.summary?.changed?.length!==0" in html
    assert 'does not yet draw' in html
    web=ROOT/'web/experiments/io-level-r01-native-frame-probe'
    web.mkdir(parents=True,exist_ok=True)
    (web/'index.html').write_text(html)
    (web/'ramrun.js').write_bytes(rawscript)
    (web/'README.md').write_text(f'''# {NAME}

**User-triggered experimental RAM-only capture.** Current device must already
have the exact R03C HWFLASH01 permanent firmware installed.

- Flashed R03C donor SHA256: `{FROZEN_SHA256}`.
- Probe HXF SHA256: `{report['HXF_SHA256']}`.
- SHARC Entry2 and the other 13 non-M4 entries are bit-identical.
- Two added M4 hooks, original GR RX and editor registration preserved.
- No new SHARC code and no changed eMMC overlay sectors.
- Host-only, read-only command 0x4f returns real raw native 256-word RX frame.
- `tools/io_level_r01_native_frame_probe.py` captures samples.
- No visual input/output meter in R01; the event mapping is being measured.
- **No eMMC flash, device reset or WebUSB RAM run in the build/stage step.**
''')
    loader=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/firmware-ramboot.dfu'
    assert loader.stat().st_size==4112
    shutil.copyfile(loader,out/'firmware-ramboot.dfu')
    for f in ('index.html','ramrun.js'):
        shutil.copyfile(web/f,out/f)
    final={
        'variant':NAME,
        'stage':'RAM-PREFLIGHT-OFFLINE-NO-HARDWARE-LOAD',
        'active_hardware_firmware_untouched':True,
        'hardware_tested':False,
        'modified_L6IA_entries':[0],
        'RAM_only':True,
        'overlay_sector_count':0,
        'read_only_emmc_identity_checks':2,
        'plan_sha256':spec['plan_sha256'],
        'r03c_donor_sha256':FROZEN_SHA256,
        'candidate_sha256':report['HXF_SHA256'],
        'loader_sha256':sha(loader.read_bytes()),
        'browser_script_sha256':sha(rawscript),
        'command':0x4f,
        'response_bytes':1040,
        'native_meter_field_offsets_verified':False,
        'UI_level_bars_implemented':False
    }
    (out/'manifest-stage.json').write_text(json.dumps(final,indent=2)+'\n')
    print(json.dumps(final,indent=2))
    return final
if __name__=='__main__':stage()

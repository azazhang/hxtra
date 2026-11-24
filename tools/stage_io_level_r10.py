#!/usr/bin/env python3
"""Stage final direct meter candidate for explicitly user-initiated RAM run only."""
import json,shutil,hashlib
from build_io_level_r10_receiver_fix import NAME,ROOT,FROZEN_SHA256,R05_SHA
def stage():
    out=ROOT/'build/browser-ramrun'/NAME
    b=json.loads((out/'manifest-build.json').read_text());p=json.loads((out/'manifest-plan.json').read_text());r=json.loads((out/'regions/plan.json').read_text())
    assert b['variant']==p['variant']==NAME and b['HXF_SHA256']==p['candidate_SHA256']
    assert b['R09_SHARC_byte_identical'] and b['M0_segment_identical'] and b['R03C_GR_Home_preserved'] and b['original_record_offsets_preserved']
    assert b['donor_R03C_SHA256']==p['donor_R03C_SHA256']==FROZEN_SHA256 and p['verified_all_1025_sectors']
    n=len(b['actual_changed_payload_sectors']);v=r['summary']
    assert v['writes']=='ram' and v['overlay_sectors']==n+1 and v['changed']==[[2,524212,524212,n]]
    assert len(r['regions'])==9 and len(r['checks'])==2
    assert hashlib.sha256((out/'regions/plan.json').read_bytes()).hexdigest()==p['plan_SHA256']
    template=ROOT/'web/experiments/io-level-r01-native-frame-probe'
    old='IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE'
    html=(template/'index.html').read_text().replace(old,NAME)
    a=html.index('<p><strong>');z=html.index('<div id="status">')
    desc=f'''<p><strong>R10: direct 16-segment Input and Main Output peak meters.</strong> R10 removes the invalid input-callback-count restriction (384 callbacks/window on the physical unit). Actual audio samples are measured in 1024-sample windows inside the original input-sidechain and Main output writer paths. The DSP publishes checksum-protected sequence-tagged peak values. The M4 performs independent peak holds, bounded display decay, and validates the measurement source. The original native meter ledger remains available solely for comparison.</p>
<p>The exact R03C donor is preserved except two existing SHARC hook instructions, added code in unused Block 3, equivalent zero initialization, and three M4 hook sites plus added code. The M0, metronome, original Home/GR path, NAM allocation and other archive entries are preserved. The SHARC partition remains 524212 bytes.</p>
<p>R03C: <code>{FROZEN_SHA256}</code><br>Candidate: <code>{b['HXF_SHA256']}</code></p>
<p class="warn"><strong>RAM only. Never install using Line 6 Updater.</strong> Power-cycle to the installed R03C before running. This plan verifies the installed SHARC CRCs and uses RAM-only sector redirection. R09 DSP boot and egress verified on hardware; R10 retains those exact DSP bytes. The new M4 receiver was tested with 698 checksum-valid captured hardware packets. Power-cycle to revert.</p>
'''
    html=html[:a]+desc+html[z:]
    before="if(manifest.regions?.length!==9||manifest.checks?.length!==2||manifest.summary?.writes!=='ram'||manifest.summary?.overlay_sectors!==0||manifest.summary?.runs!==0||manifest.summary?.changed?.length!==0) throw Error('Preflight: incorrect R01 RAM plan (requires 9 regions, 0 eMMC overlays, 2 identity checks, RAM-only writes)');"
    after=f"if(manifest.regions?.length!==9||manifest.checks?.length!==2||manifest.summary?.writes!=='ram'||manifest.summary?.overlay_sectors!=={n+1}||manifest.summary?.runs!=={v['runs']}||JSON.stringify(manifest.summary?.changed)!=='[[2,524212,524212,{n}]]') throw Error('Preflight: incorrect R10 RAM plan');"
    assert html.count(before)==1;html=html.replace(before,after)
    html=html.replace('IO-LEVEL-R01 native meter event capture: 9 RAM regions, 0 changed eMMC sectors, 2 preflight eMMC identity CRC checks, writes=ram.',f'R10 direct peaks: 9 RAM regions, {n+1} RAM-redirected SHARC sectors, 2 preflight eMMC identity CRC checks, writes=ram.')
    html=html.replace('exact R03C donor, unchanged DSP, native RX capture via editor 0x4f','exact R03C donor, direct SHARC peak windows, IORA read-only diagnostic via 0x1d')
    html=html.replace('R01 native meter capture RAM handoff reported','R10 direct meter RAM handoff reported')
    html=html.replace('WebUSB RAM handoff reported. Verify device operation; capture real DSP frames with tools/io_level_r01_native_frame_probe.py. No real input/output meter is drawn yet.','RAM handoff reported. R10 direct meter is ready for the read-only automated telemetry audit.')
    assert old not in html
    web=ROOT/'web/experiments/io-level-r10-direct-peak-receiver-fix';web.mkdir(parents=True,exist_ok=True)
    (web/'index.html').write_text(html);shutil.copyfile(template/'ramrun.js',web/'ramrun.js')
    (web/'README.md').write_text('# R10 direct peak receiver fix\n\nRAM-only user-initiated candidate. Power-cycle to revert. Never flash.\n')
    for f in ('index.html','ramrun.js'):shutil.copyfile(web/f,out/f)
    loader=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/firmware-ramboot.dfu';assert loader.stat().st_size==4112;shutil.copyfile(loader,out/'firmware-ramboot.dfu')
    (out/'manifest-stage.json').write_text(json.dumps({'variant':NAME,'stage':'OFFLINE_RAM_READY_HARDWARE_UNTESTED','HXF_SHA256':b['HXF_SHA256'],'plan_SHA256':p['plan_SHA256'],'writes':'ram','overlay_sectors':n+1,'identity_checks':2,'user_initiated_only':True},indent=2)+'\n')
    print('R10 staged locally',out)
if __name__=='__main__':stage()

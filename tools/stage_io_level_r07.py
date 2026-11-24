#!/usr/bin/env python3
"""Stage a user-initiated R07 RAM-only experiment, never flash the device."""
import json,shutil,hashlib
from build_io_level_r07_native_peak_retention import NAME,ROOT,FROZEN_SHA256,R05_SHA

def stage():
    out=ROOT/'build/browser-ramrun'/NAME
    b=json.loads((out/'manifest-build.json').read_text());p=json.loads((out/'manifest-plan.json').read_text());r=json.loads((out/'regions/plan.json').read_text())
    assert b['variant']==p['variant']==NAME and b['HXF_SHA256']==p['candidate_SHA256']
    assert b['R05_M4_byte_identical'] and b['exact_R05_SHA256']==R05_SHA
    assert b['donor_R03C_SHA256']==p['donor_R03C_SHA256']==FROZEN_SHA256
    assert b['actual_changed_payload_sectors']==[79] and p['verified_all_1025_sectors']
    assert r['summary']['writes']=='ram' and r['summary']['overlay_sectors']==r['summary']['runs']==2
    assert r['summary']['changed']==[[2,524212,524212,1]] and len(r['regions'])==9 and len(r['checks'])==2
    assert hashlib.sha256((out/'regions/plan.json').read_bytes()).hexdigest()==p['plan_SHA256']
    template=ROOT/'web/experiments/io-level-r01-native-frame-probe'
    old='IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE'
    html=(template/'index.html').read_text().replace(old,NAME)
    a=html.index('<p><strong>');z=html.index('<div id="status">')
    desc=f'''<p><strong>R07: native meter peak retention across rejected DSP reports.</strong>
The physical R05 tests established intermittent missed metronome peaks upstream of Home drawing. In the original SHARC meter primitive, the accumulated peak is unconditionally cleared even when the stock event queue rejects its publication. R07 retains the measured peak until the next successful normal publication. The display is the exact working R05 M4 binary. R06 and its defective segmented renderer are excluded.</p>
<p>Seven existing SHARC instruction slots are replaced in place; no instruction-count increase, no added bootstream records, no changed metronome kernel. The candidate changes one SHARC payload sector and its CRC header. The stock success path and sample acquisition are tested using the actual original machine instructions. It remains unproven that queue rejection caused the physical missed metronome clicks.</p>
<p>R03C reference: <code>{FROZEN_SHA256}</code><br>R05 reference: <code>{R05_SHA}</code><br>R07 candidate: <code>{b['HXF_SHA256']}</code></p>
<p class="warn"><strong>RAM-only experimental load. Do not flash with Line 6 Updater.</strong> Power-cycle to the installed R03C first. The plan checks the installed SHARC header and full defined sectors, stages nine RAM regions, redirects two sectors in RAM, and performs no permanent eMMC writes. If startup fails, power-cycle immediately. Test metronome-only, then guitar-only, and confirm DSP Usage numbers and normal audio behavior.</p>
'''
    html=html[:a]+desc+html[z:]
    before="if(manifest.regions?.length!==9||manifest.checks?.length!==2||manifest.summary?.writes!=='ram'||manifest.summary?.overlay_sectors!==0||manifest.summary?.runs!==0||manifest.summary?.changed?.length!==0) throw Error('Preflight: incorrect R01 RAM plan (requires 9 regions, 0 eMMC overlays, 2 identity checks, RAM-only writes)');"
    after="if(manifest.regions?.length!==9||manifest.checks?.length!==2||manifest.summary?.writes!=='ram'||manifest.summary?.overlay_sectors!==2||manifest.summary?.runs!==2||JSON.stringify(manifest.summary?.changed)!=='[[2,524212,524212,1]]') throw Error('Preflight: incorrect R07 RAM plan (requires 9 regions, 2 RAM-redirected SHARC sectors, 2 identity checks, RAM-only writes)');"
    assert html.count(before)==1;html=html.replace(before,after)
    html=html.replace('IO-LEVEL-R01 native meter event capture: 9 RAM regions, 0 changed eMMC sectors, 2 preflight eMMC identity CRC checks, writes=ram.','R07 peak retention: 9 RAM regions, 2 RAM-redirected SHARC sectors, 2 eMMC identity CRC checks, writes=ram.')
    html=html.replace('exact R03C donor, unchanged DSP, native RX capture via editor 0x4f','exact R05 M4, one in-place SHARC peak-retention edit, native ledger via editor 0x13')
    html=html.replace('R01 native meter capture RAM handoff reported','R07 native peak retention RAM handoff reported')
    html=html.replace('WebUSB RAM handoff reported. Verify device operation; capture real DSP frames with tools/io_level_r01_native_frame_probe.py. No real input/output meter is drawn yet.','RAM handoff reported. Engage metronome, leave guitar silent, and verify whether the right bar registers each click. Do not flash.')
    assert old not in html and 'overlay_sectors!==2' in html
    web=ROOT/'web/experiments/io-level-r07-native-peak-queue-retention';web.mkdir(parents=True,exist_ok=True)
    (web/'index.html').write_text(html);shutil.copyfile(template/'ramrun.js',web/'ramrun.js')
    (web/'README.md').write_text('# R07 native peak queue retention\n\nUser-initiated RAM trial only. R05 M4 binary unchanged; one in-place seven-slot SHARC patch. Hardware cause of missed peaks not yet verified. Never flash.\n')
    for f in ('index.html','ramrun.js'):shutil.copyfile(web/f,out/f)
    loader=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/firmware-ramboot.dfu';assert loader.stat().st_size==4112;shutil.copyfile(loader,out/'firmware-ramboot.dfu')
    (out/'manifest-stage.json').write_text(json.dumps({'variant':NAME,'stage':'OFFLINE_RAM_READY_HARDWARE_UNTESTED','HXF_SHA256':b['HXF_SHA256'],'plan_SHA256':p['plan_SHA256'],'R05_M4_byte_identical':True,'SHARC_replaced_instruction_slots':7,'writes':'ram','overlay_sectors':2,'identity_checks':2,'user_initiated_only':True},indent=2)+'\n')
    print('R07 staged locally',out)
if __name__=='__main__':stage()

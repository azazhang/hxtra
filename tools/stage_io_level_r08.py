#!/usr/bin/env python3
"""Stage opt-in RAM-only R08; preserve installed R03C and R05 bars."""
import json,shutil,hashlib
from build_io_level_r08_pcm_observer import NAME,ROOT,FROZEN_SHA256,R05_SHA

def stage():
    out=ROOT/'build/browser-ramrun'/NAME;b=json.loads((out/'manifest-build.json').read_text());p=json.loads((out/'manifest-plan.json').read_text());r=json.loads((out/'regions/plan.json').read_text())
    assert b['variant']==p['variant']==NAME and b['HXF_SHA256']==p['candidate_HXF_SHA256']
    assert b['R08_M0_segment_identical'] and b['R08_SHARC_identical'] and b['R08_R05_existing_Home_paint_unchanged']
    assert b['donor_R03C_SHA256']==p['flashed_donor_R03C_SHA256']==FROZEN_SHA256 and b['exact_R05_SHA256']==R05_SHA
    assert r['summary']['writes']=='ram' and r['summary']['overlay_sectors']==0 and len(r['regions'])==9 and len(r['checks'])==2
    assert hashlib.sha256((out/'regions/plan.json').read_bytes()).hexdigest()==p['plan_sha256']
    template=ROOT/'web/experiments/io-level-r01-native-frame-probe';old='IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE'
    h=(template/'index.html').read_text().replace(old,NAME);a=h.index('<p><strong>');z=h.index('<div id="status">')
    h=h[:a]+f'''<p><strong>R08: direct digital audio sample observer.</strong> A read-only M4 observer checks completed I2S receive buffers already written by the M0 USB audio coprocessor. The native R05 bars remain the comparator. The observer separately measures peak amplitudes and counts samples over thresholds on USB 1/2 (Main) and 5/6 (dry input). It validates descriptor addresses, lengths, channel framing, producer cursor continuity and overwrite risk, and reports skipped or rejected samples. No modification to the M0 audio code or SHARC firmware, and no audio samples or settings are written. Actual ring coverage and physical routing must be verified on the device.</p>
<p>Editor diagnostic <code>0x1d</code> returns 128 bytes with unique <code>IOR8</code> signature; R05 <code>0x13</code> and R03C <code>0x50</code> retained. R08 restores the original R03C DSP (no R07 queue patch), and keeps R05's solid bars intentionally.</p>
<p>Exact R03C SHA256 <code>{FROZEN_SHA256}</code>; R08 <code>{b['HXF_SHA256']}</code>.</p>
<p class="warn"><strong>RAM-only, do not flash.</strong> Power-cycle back to the permanently installed R03C first. Two read-only identity checks, nine RAM regions, zero eMMC overlays and no permanent writes. Engage metronome, leave guitar silent, and return to Home. If the unit freezes or sound glitches, power-cycle back to R03C.</p>
'''+h[z:]
    h=h.replace('incorrect R01 RAM plan','incorrect R08 RAM plan').replace('IO-LEVEL-R01 native meter event capture:','R08 direct PCM observer:').replace('exact R03C donor, unchanged DSP, native RX capture via editor 0x4f','exact R03C SHARC/M0, R05 display, direct PCM ring probe 0x1d').replace('R01 native meter capture RAM handoff reported','R08 direct PCM observer RAM handoff reported').replace('WebUSB RAM handoff reported. Verify device operation; capture real DSP frames with tools/io_level_r01_native_frame_probe.py. No real input/output meter is drawn yet.','R08 RAM handoff reported. Leave guitar silent, engage metronome and return to Home; read-only PCM/TAP/native comparison via 0x1d/0x50/0x13.')
    assert 'overlay_sectors!==0' in h and 'IOR8' in h and old not in h
    web=ROOT/'web/experiments/io-level-r08-direct-pcm-ring-observer';web.mkdir(parents=True,exist_ok=True);(web/'index.html').write_text(h);shutil.copyfile(template/'ramrun.js',web/'ramrun.js');(web/'README.md').write_text('# R08 direct PCM observer\n\nRead-only shared M0 ring observer, R05 display unchanged, R03C DSP/M0 unchanged. RAM-only. Physical coverage unverified.\n')
    for f in ('index.html','ramrun.js'):shutil.copyfile(web/f,out/f)
    loader=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/firmware-ramboot.dfu';assert loader.stat().st_size==4112;shutil.copyfile(loader,out/'firmware-ramboot.dfu')
    (out/'manifest-stage.json').write_text(json.dumps({'variant':NAME,'HXF_SHA256':b['HXF_SHA256'],'plan_SHA256':p['plan_sha256'],'signature':'IOR8','command':29,'hardware_tested':False,'writes':'ram','overlay_sectors':0,'R05_display_preserved':True,'SHARC_and_M0_unchanged':True},indent=2)+'\n');print('R08 staged',out)
if __name__=='__main__':stage()

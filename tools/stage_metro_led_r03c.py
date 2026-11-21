#!/usr/bin/env python3
"""Stage R03C's deduplicated, ordered LED-master and M4 latency probe.

User-initiated WebUSB RAM-only experiment; no firmware install, USB access
or automatic pedal reset. Page explicitly states the reported audible lag
is NOT corrected by this version; a read-only M4 boundary measurement
is included to isolate it on real hardware.
"""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_metro_led_r03c import NAME
from metro_led_donor_patch import DONOR_SHA256

def stage():
    out=ROOT/'build/browser-ramrun'/NAME
    build=json.loads((out/'manifest-build.json').read_text())
    planinfo=json.loads((out/'manifest-plan.json').read_text())
    plan=json.loads((out/'regions/plan.json').read_text())
    assert build['variant']==planinfo['variant']==NAME
    assert build['donor_sha256']==planinfo['donor_hxf_sha256']==DONOR_SHA256
    assert build['HXF_SHA256']==planinfo['candidate_hxf_sha256']
    assert build['modified_L6IA_entries']==[0,2]
    assert build['other_13_entries_byte_identical']
    assert not build['SHARC_LDR_header_or_order_change']
    assert build['SHARC_candidate_entry2_bytes']==524212
    assert build['SHARC_original_LDR_blocks']==build['SHARC_candidate_LDR_blocks']==201
    assert build['SHARC_metronome_kernel_PM_words']==142
    assert planinfo['header_overlay_emmc_sector']=='0x8802'
    assert planinfo['genuinely_changed_sharc_payload_sectors']==[1004,1005]
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['overlay_sectors']==4
    assert plan['summary']['runs']==3
    assert plan['summary']['changed']==[[2,524212,524212,3]]
    assert len(plan['regions'])==9 and plan['checks']==[[34819,1023,3485190247,2]]
    old='METRO-LEDSYNC-R03B-LED-MASTER'
    web=ROOT/'web/experiments/metro-ledsync-r03c-hwglitch-repair'
    template=ROOT/'web/experiments/metro-ledsync-r03b-led-master'
    web.mkdir(parents=True,exist_ok=True)
    script=(template/'ramrun.js').read_bytes()
    assert script==(ROOT/'web/experiments/metro-donor-v121-unchanged-control/ramrun.js').read_bytes()
    (web/'ramrun.js').write_bytes(script)
    html=(template/'index.html').read_text()
    assert html.count(old)>=5
    html=html.replace(old,NAME)
    start=html.index('<p><strong>')
    end=html.index('<div id="status">')
    replacement=f'''<p><strong>R03C: ordered TAP LED events, verified double-click repairs and read-only latency probe.</strong>
This is the experimental successor to physically booted R03B, which the
user reported sometimes produced two clicks close together at a stationary
BPM and a perceptible audible delay after the visible FS3 TAP LED.
The two previous software defects were independently reproduced with
actual SHARC instructions: a complete but stale SPI event pair could
retrigger a click, and transient invalid no-TAP frames could reactivate
the donor free-running click clock.</p>
<p>The new SHARC kernel rejects duplicate/older 31-bit event counts,
independently validates the complementary SPI pair and accepts genuine
re-engagement epoch advances. It retains the original <strong>142-instruction
metronome LDR record</strong> with all <strong>201 original SHARC boot
descriptors</strong> and unchanged Entry2 size <code>524212</code>.
An exact-power-of-two gain rescaling saved instruction space while keeping
the original click audio bit-for-bit identical in emulator parity tests.
The M4 publisher holds its latest valid count during transient FS3 TAP
visibility drops for up to <strong>4,600 SPI frames</strong> (roughly
2 seconds at the measured 2,300 frames/s). Sustained non-TAP mode resumes
the native donor metronome clock. Existing 20ms LED dark-interval filtering
remains unchanged.</p>
<p><strong>The perceptible LED-to-audio delay has NOT been resolved.</strong>
R03C adds a read-only native microsecond measurement from the accepted
post-filter M4 FS3 LED command to its first M4 SPI transmission.
After a hardware boot it can be queried using
<code>tools/metro_led_r03c_probe.py</code>, command <code>0x50</code>.
This measurement does NOT include SHARC reception, audio output buffering,
or actual LED optical latency. A later independent optical/audio recording
may be necessary to quantify and compensate audible delay. Do not interpret
an M4 transmit checksum as a DSP acknowledgement.</p>
<p>Firmware is derived strictly from the user's installed HXtra v1.2.1 HXF
SHA256 <code>{DONOR_SHA256}</code>. Only four audited original M4 hook sites
and one existing SHARC metronome PM record are altered; the other 13 L6IA
entries remain byte-for-byte identical. Installed DSP Usage Display,
USB Monitor, all other models/UI features, presets and global settings
are retained in the candidate package.</p>
<p class="warn"><strong>Experimental user-initiated RAM load only; hardware
behavior is unverified.</strong> Nine RAM regions, four RAM-only eMMC
redirect sectors including corrected SHARC CRC metadata at
<code>0x8802</code>, and one read-only donor-reference checksum.
There are NO permanent firmware/eMMC writes. R03B's physical boot and
audio complaints are separate evidence and do not prove R03C will boot
or correct perception. First check LCD/editor and donor features, then
listen for duplicate clicks without touching BPM, followed by repeated
BPM changes and bypass/re-engage. If it freezes, save the browser log
and power-cycle the pedal to restore the installed firmware.</p>
'''
    html=html[:start]+replacement+html[end:]
    assert "manifest.summary?.overlay_sectors!==4" in html
    assert "manifest.summary?.changed?.[0]?.[3]!==3" in html
    html=html.replace('R03B real LED-master preflight:',
                      'R03C HWGLITCH repair preflight:')
    html=html.replace('R03B LED-master RAM handoff reported',
                      'R03C HWGLITCH repair RAM handoff reported')
    html=html.replace('exact donor M4 four-site hooks and original 201 SHARC loader records intact',
                      'exact donor, ordered LED events, dropout grace, read-only M4 transit timing')
    html=html.replace('WebUSB RAM handoff reported; check pedal startup, DSP Usage %, USB Monitor, and click versus actual FS3 TAP ring.',
                      'WebUSB RAM handoff reported; verify startup, DSP Usage %, no double click, and M4 latency. Optical/audio lag remains unproven.')
    assert old not in html
    assert 'The perceptible LED-to-audio delay has NOT been resolved' in html
    (web/'index.html').write_text(html)
    (web/'README.md').write_text(f'''# {NAME}

RAM-only revision for the two SHARC event bugs reproduced after user HWGLITCH01
on R03B: backward accepted counts and intermittent no-TAP native fallback.

- Donor HXF SHA256: `{DONOR_SHA256}`.
- R03C candidate HXF SHA256: `{build['HXF_SHA256']}`.
- Four original M4 hooks, one original 142-word SHARC record; 201 LDR
  descriptors intact and Entry2 size 524212 bytes.
- Four RAM-only overlay sectors including metadata sector 0x8802.
- Full 32-bit complement validation; monotone low31 event guard.
- 4600 SPI-frame noTAP grace; known persistent mode switch reverts
  to native Time behavior. 20ms LED dark reversal filter unchanged.
- Extended 84-byte read-only M4 diagnostic 0x50 including actual
  accepted LED command to first M4 TX callback delay in microseconds.
- **No measured SHARC/audio or optical latency; acoustic lag NOT fixed.**
- 100% user-initiated experimental RAM transfer. No permanent eMMC writes.
- `tools/metro_led_r03c_probe.py` for read-only post-boot counters.
''')
    loader=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/firmware-ramboot.dfu'
    assert loader.is_file() and loader.stat().st_size==4112
    shutil.copyfile(loader,out/'firmware-ramboot.dfu')
    for f in ('index.html','ramrun.js'):
        shutil.copyfile(web/f,out/f)
    manifest={
       'variant':NAME,
       'stage':'STAGEQA00_OFFLINE_HW_UNTESTED',
       'hardware_run_initiated':False,
       'physical_boot_verified':False,
       'physical_double_click_fix_verified':False,
       'perceptible_LED_to_audio_delay_fixed':False,
       'latency_instrumentation_scope':'M4 accepted LED command -> first M4 SPI TX callback only',
       'donor_sha256':DONOR_SHA256,
       'hxf_sha256':build['HXF_SHA256'],
       'ram_plan_sha256':planinfo['plan_sha256'],
       'webusb_loader_sha256':hashlib.sha256((out/'firmware-ramboot.dfu').read_bytes()).hexdigest(),
       'webusb_script_sha256':hashlib.sha256(script).hexdigest(),
       'page_sha256':hashlib.sha256((out/'index.html').read_bytes()).hexdigest(),
       'unchanged_SHARC_LDR_descriptors':201,
       'only_modified_sharc_record':177,
       'M4_hook_sites':build['M4_changed_hook_sites'],
       'overlay_sectors':4,'RAM_only':True,
    }
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':print(json.dumps(stage(),indent=2))

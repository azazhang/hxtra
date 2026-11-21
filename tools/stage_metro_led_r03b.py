#!/usr/bin/env python3
"""Stage R03B user-initiated WebUSB RAM experiment (offline file staging only).

This packages the verified exact-donor M4+SHARC HXF plan, read-only
diagnostics and unmodified, previously working WebUSB RAM loader.
No browser click, no HX Stomp reset, and no eMMC writes.
"""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_metro_led_r03b import NAME
from metro_led_donor_patch import DONOR_SHA256

def build():
    out=ROOT/'build/browser-ramrun'/NAME
    plan=json.loads((out/'regions/plan.json').read_text())
    buildinfo=json.loads((out/'manifest-build.json').read_text())
    planinfo=json.loads((out/'manifest-plan.json').read_text())
    assert buildinfo['variant']==planinfo['variant']==NAME
    assert buildinfo['donor_sha256']==planinfo['donor_hxf_sha256']==DONOR_SHA256
    assert buildinfo['HXF_SHA256']==planinfo['candidate_hxf_sha256']
    assert buildinfo['modified_L6IA_entries']==[0,2]
    assert buildinfo['other_13_entries_byte_identical']
    assert not buildinfo['SHARC_LDR_header_or_order_change']
    assert buildinfo['SHARC_candidate_entry2_bytes']==524212
    assert buildinfo['SHARC_metronome_kernel_PM_words']==142
    assert planinfo['header_overlay_emmc_sector']=='0x8802'
    assert planinfo['genuinely_changed_sharc_payload_sectors']==[1004,1005]
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['overlay_sectors']==4
    assert plan['summary']['runs']==3
    assert plan['summary']['changed']==[[2,524212,524212,3]]
    assert len(plan['regions'])==9 and len(plan['checks'])==1
    assert plan['checks']==[[34819,1023,3485190247,2]]
    old='METRO-LEDSYNC-R03A-SHARC-INPLACE-BOOTCHECK'
    template=ROOT/'web/experiments/metro-ledsync-r03a-sharc-inplace-bootcheck'
    web=ROOT/'web/experiments/metro-ledsync-r03b-led-master'
    web.mkdir(parents=True,exist_ok=True)
    js=(template/'ramrun.js').read_bytes()
    assert js==(ROOT/'web/experiments/metro-donor-v121-unchanged-control/ramrun.js').read_bytes()
    (web/'ramrun.js').write_bytes(js)
    html=(template/'index.html').read_text()
    assert html.count(old)>=5
    html=html.replace(old,NAME)
    start=html.index('<p><strong>')
    end=html.index('<div id="status">')
    description=f'''<p><strong>R03B: actual FS3 TAP LED-driven Metronome audio (experimental).</strong>
This is the first combined, exact-installed-HXtra-v1.2.1 donor-based
M4-to-SHARC LED master candidate using the R03A kernel's physically
verified <strong>in-place 142-word SHARC process record</strong>.
All original 201 SHARC boot records remain in the same order, with the
same lengths and addresses. Entry2 stays <code>524212</code> bytes. The
exact donor M4 is altered only at four audited hook sites: post-filter
FS3 LED egress, Metronome bypass, diagnostic registration, and the existing
SPI TX callback. Other installed DSP/UI code, DSP Usage Display, USB
Monitor, menus, settings, presets, and saved configuration are untouched.
Exact installed donor SHA256: <code>{DONOR_SHA256}</code>.</p>
<p>The M4 publishes real final TAP LED ON commands into SPI words240/241 as
a 32-bit counter and its full bitwise complement. The SHARC validates both
before issuing any click; a failed or torn pair cannot trigger a beat.
The M4 suppresses OFF-&gt;ON reversals shorter than <strong>20ms</strong>:
the previous physical R01 trace found six such reversals (shortest 1.870ms)
during repeated BPM knob changes. These reversals may not be optically
perceptible; this filter is an explicit testable engineering assumption.
Bypass/re-engage causes the next accepted LED ON to trigger the accented
downbeat. Audio is scheduled on the next 16-sample SHARC block after the
validated SPI event. Absolute optical-to-audio latency and hardware
phase stability are <strong>not yet measured</strong>.</p>
<p class="warn"><strong>Unproven experimental firmware — user-initiated RAM load only.</strong>
The real R03A SHARC-only baseline booted and played as original HXtra;
the new M4 sender and combined audio synchronization have passed offline
Unicorn/ssim tests but <strong>have never been run together on hardware</strong>.
The plan overlays four RAM-only sectors: the revised SHARC CRC metadata at
on-card sector <code>0x8802</code>, two changed metronome PM payload sectors
and one copy of the zero-padded unchanged final partial sector. No eMMC
writes. The WebUSB handoff proves transfer CRCs, <strong>not</strong> a
successful physical startup. Verify pedal LCD, editor, DSP Usage percentages,
USB Monitor, and audible LED/click phase before reporting success. If frozen,
save this page's log and physically power-cycle to restore installed HXtra;
do not repeatedly reload old failed SHARC builds.</p>
'''
    html=html[:start]+description+html[end:]
    guard="manifest.summary?.overlay_sectors!==3"
    assert html.count(guard)==1
    html=html.replace(guard,
       "manifest.summary?.overlay_sectors!==4||manifest.summary?.changed?.[0]?.[3]!==3")
    html=html.replace(
      'R03A startup bootcheck preflight: 9 RAM regions, 1 eMMC reference check, 3 metadata/payload overlay sectors, writes=ram.',
      'R03B real LED-master preflight: 9 RAM regions, 1 eMMC reference check, 4 metadata/payload overlay sectors, writes=ram.')
    html=html.replace(
      'exact donor M4 and unchanged SHARC LDR descriptor topology',
      'exact donor M4 four-site hooks and original 201 SHARC loader records intact')
    html=html.replace(
      'R03A SHARC in-place RAM handoff reported',
      'R03B LED-master RAM handoff reported')
    html=html.replace(
      'WebUSB RAM handoff reported; physical SHARC and editor boot still unverified.',
      'WebUSB RAM handoff reported; check pedal startup, DSP Usage %, USB Monitor, and click versus actual FS3 TAP ring.')
    assert "manifest.summary?.overlay_sectors!==4" in html
    assert "manifest.summary?.changed?.[0]?.[3]!==3" in html
    assert old not in html
    assert "actual FS3 TAP LED-driven" in html
    (web/'index.html').write_text(html)
    (web/'README.md').write_text(f'''# {NAME}

Physical RAM-only user-driven sync candidate, following boot-tested R03A
SHARC kernel and R01 real M4 LED trace.

- Exact donor SHA256: `{DONOR_SHA256}`
- Candidate HXF SHA256: `{buildinfo['HXF_SHA256']}`
- M4 changed sites: `{buildinfo['M4_changed_hook_sites']}`.
- Original SHARC Entry2 524212 bytes and 201 LDR descriptor topology held.
- Exactly 4 RAM-overlay sectors incl metadata header at eMMC 0x8802.
- Real M4 LED ON before illumination command, validated 2-word complement
  at SHARC. 20ms dark-gap suppression derived from physical trace.
- No M4 or SHARC feature intentionally removed from donor.
- Optical latency/acoustic phase not yet measured; hardware run pending.
- `tools/metro_led_r03b_probe.py`: read-only M4 diagnostic 0x50.
- `tests/test_metro_led_r03b_transport.py`: full Unicorn/ssim integration.
- `tools/build_metro_led_r03b.py`: strict exact-donor packer.
- `tools/metro_led_r03b_ramplan.py`: verified RAM overlay planner.
- No permanent firmware write authorized.
''')
    donor_loader=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/firmware-ramboot.dfu'
    assert donor_loader.is_file() and donor_loader.stat().st_size==4112
    shutil.copyfile(donor_loader,out/'firmware-ramboot.dfu')
    for item in ('ramrun.js','index.html'):
        shutil.copyfile(web/item,out/item)
    meta={
        'variant':NAME,
        'stage':'STAGEQA00_OFFLINE_NOT_HARDWARE_TESTED',
        'hardware_run_initiated':False,
        'experimental_audio_sync_ready_for_hardware_test':True,
        'donor_sha256':DONOR_SHA256,
        'hxf_sha256':buildinfo['HXF_SHA256'],
        'ram_plan_sha256':planinfo['plan_sha256'],
        'webusb_loader_sha256':hashlib.sha256((out/'firmware-ramboot.dfu').read_bytes()).hexdigest(),
        'webusb_script_sha256':hashlib.sha256(js).hexdigest(),
        'page_sha256':hashlib.sha256((out/'index.html').read_bytes()).hexdigest(),
        'unchanged_SHARC_loader_descriptors':201,
        'only_changed_m4_sites':buildinfo['M4_changed_hook_sites'],
        'only_changed_sharc_record':177,
        'ram_overlay_sectors':plan['summary']['overlay_sectors'],
        'ram_only':True,
        'validated_M4_to_SHARC_offline':True,
        'physical_LED_audio_sync_verified':False,
        'physical_boot_verified':False,
    }
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    return meta

if __name__=='__main__':print(json.dumps(build(),indent=2))

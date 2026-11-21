#!/usr/bin/env python3
"""Stage an exact-donor SHARC-ONLY in-place startup isolation RAM experiment.

No device firmware write, no pedal USB interaction, no browser run. The
user decides whether to activate this as a RAM-only session.
"""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_metro_led_r03a_sharc_inplace import NAME,make
from metro_led_r02d_ramplan_header import make_plan
from metro_led_donor_patch import DONOR_SHA256
import patch_amp as pa,l6ia,hxf_ram as hr

def build(out=None):
    out=Path(out or ROOT/'build/browser-ramrun'/NAME)
    donor=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
    hxf=out/(NAME+'.hxf')
    existing=out/'manifest-build.json'
    planfile=out/'regions/plan.json'
    if existing.exists() and hxf.exists() and planfile.exists():
        # Separately staged after pinned HXF + header overlay were already
        # generated and independently inspected. No expensive rebuild here.
        info=json.loads(existing.read_text())
        assert info['variant']==NAME
        assert info['hxf_SHA256']==hashlib.sha256(hxf.read_bytes()).hexdigest()
        old_plan=json.loads(planfile.read_text())
        plan_info=dict(variant=NAME,
           total_overlay_sectors=old_plan['summary']['overlay_sectors'],
           runs=old_plan['summary']['runs'],
           header_overlaid_at_emmc_sector='0x8802',
           ram_regions=len(old_plan['regions']))
    else:
        info=make(donor,out)
        plan_info=make_plan(str(donor),str(hxf),str(out/'regions'),
                            expected_entry2_bytes=524212,variant=NAME)
    assert plan_info['variant']==NAME
    assert plan_info['total_overlay_sectors']==3
    assert plan_info['runs']==3
    assert plan_info['header_overlaid_at_emmc_sector']=='0x8802'
    plan=json.loads((out/'regions/plan.json').read_text())
    assert plan['summary']['changed']==[[2,524212,524212,2]]
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['overlay_sectors']==3
    assert plan['checks']==[[34819,1023,3485190247,2]]
    assert len(plan['regions'])==9
    # Prove 1 metadata + 2 PM payload sectors, and *all other sectors* original.
    before,_=pa.load_l6ia_from_any(str(donor))
    after,_=pa.load_l6ia_from_any(str(hxf))
    o=l6ia.parse(before)[2];n=l6ia.parse(after)[2]
    old_hdr=l6ia.swap32(o['sub']);new_hdr=l6ia.swap32(n['sub'])
    old_payload=hr.load(str(donor))[2]
    new_payload=hr.load(str(hxf))[2]
    patches=[i for i in range(1024) if old_payload[i*512:(i+1)*512]!=new_payload[i*512:(i+1)*512]]
    assert patches==[1004],patches # one truly modified 512B payload sector
    # hxf_ram.overlay() additionally pads and overlays the unchanged final
    # partial payload sector (1023) to a full 512B: extra table entry only.
    assert plan['summary']['changed']==[[2,524212,524212,2]]
    assert old_hdr!=new_hdr
    # The unchanged stock RAM positive-control loader is reused byte-for-byte.
    upstream=ROOT/'web/experiments/metro-donor-v121-unchanged-control'
    web=ROOT/'web/experiments/metro-ledsync-r03a-sharc-inplace-bootcheck'
    web.mkdir(parents=True,exist_ok=True)
    script=(upstream/'ramrun.js').read_bytes()
    (web/'ramrun.js').write_bytes(script)
    html=(upstream/'index.html').read_text()
    label='METRO-DONOR-V121-UNCHANGED-RAM-CONTROL'
    assert html.count(label)>=5
    html=html.replace(label,NAME)
    start=html.index('<p><strong>Startup isolation positive control:')
    end=html.index('<div id="status">')
    html=html[:start]+'''<p><strong>SHARC-only, original-boot-record in-place startup check.</strong>
This is the exact user's installed HXtra v1.2.1 firmware, with
<strong>only one existing SHARC 142-instruction metronome PM record</strong> altered.
All 201 original SHARC boot record descriptors, sizes, addresses and order
are preserved. Entry2 stays <code>524212</code> bytes. The original donor
M4, DSP Usage Display, USB Monitor, other DSP programs, models, presets and
settings are unchanged. Donor SHA256
<code>96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0</code>.</p>
<p>The new metronome branch is a proof-of-feasibility. This SHARC-only startup
check has <strong>no M4 TAP LED event transmitter</strong>, so normal metronome
behavior should remain free-running. Do not use this build to judge
LED/audio synchronization. It is intended to isolate whether the new
SHARC instructions can boot while preserving the donor's boot record
topology. The receiver's 1-word protocol still needs integrity hardening
before it becomes a final synchronization design.</p>
<p class="warn"><strong>Experimental RAM load, user-initiated only.</strong>
Nine RAM regions. Exactly three RAM-overlay sectors: the revised SHARC CRC
metadata header at eMMC sector <code>0x8802</code>, one changed SHARC
payload sector, and the zero-padded unchanged final partial payload sector. No permanent eMMC writes. One read-only donor-reference
checksum is attempted if the loader's card is readable. The WebUSB
handoff does not verify physical boot: inspect the real LCD and HX Edit
editor. If the pedal freezes, save the WebUSB log and physically power
cycle; do not retry a previous SHARC-failed image.</p>
''' + html[end:]
    guard="manifest.summary?.writes!=='ram'"
    assert html.count(guard)==1
    html=html.replace(
        guard,
        guard+"||manifest.summary?.overlay_sectors!==3||manifest.summary?.changed?.length!==1||manifest.summary?.changed?.[0]?.[0]!==2")
    assert 'manifest.summary?.overlay_sectors!==3' in html, 'Must enforce three-sector provenance'
    html=html.replace('Local RAM plan verified: 9 regions, 1 eMMC comparison, writes=ram.',
                      'R03A startup bootcheck preflight: 9 RAM regions, 1 eMMC reference check, 3 metadata/payload overlay sectors, writes=ram.')
    html=html.replace('unchanged installed v1.2.1 startup control',
                      'exact donor M4 and unchanged SHARC LDR descriptor topology')
    html=html.replace('Unmodified HXtra v1.2.1 running','R03A SHARC in-place RAM handoff reported')
    html=html.replace('SUCCESS: WebUSB reported RAM-run completion.',
                      'WebUSB RAM handoff reported; physical SHARC and editor boot still unverified.')
    html=html.replace('Only run once after power cycling R02C.','Do not run old R02C or R02D.')
    assert 'Startup isolation positive control:' not in html
    (web/'index.html').write_text(html)
    (web/'README.md').write_text(f'''# {NAME}

SHARC-only original-boot-record topology test. No M4 change, no enabled LED
transport. All exact installed donor features retained. The user decides
whether to run this RAM-only image.

* Exact donor L6IA entries changed: [2] only.
* Entry2 original / new size: 524212 / 524212 bytes.
* Original LDR records: 201, unchanged size/order/location/descriptor topology.
* Only mutated LDR record: #177, 142 PM instructions at 0xe5386.
* RAM hook overlays exactly sector 0x8802 plus one modified PM payload\n  sector and one padded unchanged final partial payload sector.
* eMMC writing: RAM redirect only.
* DSP audio equivalence for valid settings: checked in ssim.
* LED packet: exploratory, incomplete CRC; no M4 sender in this boot check.
* Physical boot: awaiting user test.
* Build and plan: `tools/stage_metro_led_r03a_inplace.py`.
* Tests: `tests/test_metro_led_r03a_inplace.py` and `tests/test_metro_led_r03a_bootplan.py`.
''')
    loader=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/firmware-ramboot.dfu'
    assert loader.is_file() and loader.stat().st_size==4112
    shutil.copyfile(loader,out/'firmware-ramboot.dfu')
    for name in ('ramrun.js','index.html'):
        shutil.copyfile(web/name,out/name)
    report={**info,**plan_info,
            'status':'STAGED_OFFLINE_ONLY_UNTESTED_ON_PHYSICAL_PEDAL',
            'webusb_loader_sha256':hashlib.sha256((out/'firmware-ramboot.dfu').read_bytes()).hexdigest(),
            'webusb_runtime_sha256':hashlib.sha256(script).hexdigest(),
            'web_index_sha256':hashlib.sha256((out/'index.html').read_bytes()).hexdigest(),
            'changed_SHARC_payload_sector_indices':patches,
            'additional_overlay_sector_reason':'unchanged final 436-byte Entry2 partial sector padded to 512 bytes by ram loader',
            'hardware_run_started':False,
            'experimental_audio_sync_ready':False}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    report=build()
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()

#!/usr/bin/env python3
"""User-initiated RAM-only test plan for M4-only IO-LEVEL-R06, on installed R03C.

The exact R03C donor was permanently flashed successfully via Line 6 Updater.
Because Entry1..14 are identical, *zero* sectors need redirecting from the
device's eMMC; only the rebuilt Entry0 application is loaded into SDRAM.

No pedal access, RAM run, and no persistent write from this builder.
"""
from pathlib import Path
import hashlib,json,struct,zlib,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import hxf_ram as hr,patch_amp as pa,l6ia
from build_io_level_r06_segmented_peak_envelope import NAME,FROZEN,FROZEN_SHA256

FROZEN_APP_CRC=0x5ed9d947
STOCK_APP_CRC=0x2b81e740

def sha(data):return hashlib.sha256(data).hexdigest()

def plan():
    base=FROZEN.read_bytes()
    assert sha(base)==FROZEN_SHA256
    current=hr.load(str(FROZEN),stock=True)
    n=struct.unpack_from('<I',current[0],4)[0]
    assert zlib.crc32(current[0][0x34:n])==FROZEN_APP_CRC
    orig=hr.APPS[STOCK_APP_CRC]
    _,hooks,card=orig
    segs,_=hr.app_segments(current[0])
    for fn,lit in hooks.values():
        assert hr.seg_read(segs,fn,len(hr.PROLOGUE))==hr.PROLOGUE
        assert struct.unpack('<I',hr.seg_read(segs,lit,4))[0]==card
    hr.APPS[FROZEN_APP_CRC]=orig
    out=ROOT/'build/browser-ramrun'/NAME
    cand=out/(NAME+'.hxf')
    donor,was=pa.load_l6ia_from_any(str(FROZEN))
    candidate,was2=pa.load_l6ia_from_any(str(cand))
    assert was and was2
    assert len(l6ia.parse(donor))==len(l6ia.parse(candidate))==15
    assert [i for i in range(15) if pa.get_entry_swapped(donor,i)!=pa.get_entry_swapped(candidate,i)]==[0]
    regions,checks,summary=hr.plan(str(cand),str(FROZEN),writes='ram')
    assert summary['unit']=='HX Stomp' and summary['writes']=='ram'
    assert summary['changed']==[] and summary['overlay_sectors']==0 and summary['runs']==0
    assert checks==[] and len(regions)==9
    # The browser RAM runner deliberately rejects a plan with zero hardware
    # identity checks. Even without changed sectors, verify the *installed*
    # exact R03C SHARC boot descriptor and all 1023 full payload sectors.
    # The 1023-sector CRC covers both R03C's unique modified SHARC sectors.
    header=pa.l6ia.swap32(l6ia.parse(donor)[2]['sub'])
    assert len(header)==512
    assert current[2][0:1023*512] and len(current[2])==524212
    checks=[(hr.PART_START[2],1,zlib.crc32(header),2),
            (hr.PAYLOAD[2],1023,zlib.crc32(current[2][:1023*512]),2)]
    assert len(checks)==2 and checks[0][0]==0x8802
    assert [r[2] for r in regions][-2:]==['hook, overlay table and sectors','boot descriptor']
    root=out/'regions'
    root.mkdir(parents=True,exist_ok=True)
    result={'regions':[],'checks':checks,'summary':summary}
    for i,(addr,data,label) in enumerate(regions):
        fname=f'{i:02d}_{addr:08x}.bin'
        (root/fname).write_bytes(data)
        result['regions'].append({'addr':addr,'file':fname,'label':label})
    planfile=root/'plan.json'
    planfile.write_text(json.dumps(result,indent=1)+'\n')
    report={
        'variant':NAME,'hardware_tested':False,
        'flashed_donor_R03C_SHA256':FROZEN_SHA256,
        'candidate_HXF_SHA256':sha(cand.read_bytes()),
        'donor_M4_application_internal_CRC32':hex(FROZEN_APP_CRC),
        'all_14_other_archive_entries_unchanged':True,
        'changed_archive_entries':[0],
        'ram_only':True,'eMMC_write_mode':summary['writes'],
        'eMMC_overlay_sectors':summary['overlay_sectors'],
        'eMMC_overlay_runs':summary['runs'],
        'eMMC_reference_sector_checks':len(checks),
        'eMMC_reference_check_reason':'verify flashed R03C SHARC partition header and 1023 full payload sectors before RAM handoff',
        'entry0_regions':len(regions),
        'plan_sha256':sha(planfile.read_bytes()),
        'physical_pedal_R03C_runtime_preflight_required':True,
    }
    (out/'manifest-plan.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report
if __name__=='__main__':plan()

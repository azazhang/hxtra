#!/usr/bin/env python3
"""METRO-LEDSYNC-R02C-HWFAIL01: isolate M4 startup hooks vs SHARC boot patch.

OFFLINE ONLY. Build two minimal interventions on the *exact installed* HXtra
v1.2.1 HXF, preserving every other original firmware entry and UI setting:
  - M4-only: R02C's five Entry0 hooks; *original* donor SHARC Entry2.
  - SHARC-only: R02C's Entry2 LDR changes; *original* donor M4 Entry0.

No device I/O; no permission to run the artifacts on hardware. For a
subsequent user-initiated RAM test, the unchanged-donor positive control must
first boot successfully. All plans still use `writes=ram` and the exact donor
CRC verification when eMMC is available. The isolated SHARC module will see no
R02C SPI event marker, so its metronome must fall back to the original local
clock; this is strictly a startup-isolation test.
"""
import hashlib,json,os,subprocess,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import patch_amp as pa
import hxf_ram as hr
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256,donor_patch
from metro_led_sharc_patch import sharc_patch

KINDS={
    'M4-ONLY':'METRO-LEDSYNC-R02C-HWFAIL01-M4-ONLY',
    'SHARC-ONLY':'METRO-LEDSYNC-R02C-HWFAIL01-SHARC-ONLY',
}


def main():
    if len(sys.argv)>2:raise SystemExit('usage: build_metro_r02c_hwfail01_ablations.py [EXACT-HXtra121.hxf]')
    donor=Path(sys.argv[1]) if len(sys.argv)==2 else Path.home()/'Downloads/HXtra_v1.2.1.hxf'
    raw=donor.read_bytes()
    assert hashlib.md5(raw).hexdigest()==DONOR_MD5
    assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
    original,ishxf=pa.load_l6ia_from_any(str(donor));assert ishxf
    donor_entries=[pa.get_entry_swapped(original,i) for i in range(15)]
    stock=hr.load(str(donor),stock=True)
    assert len(stock)==15 and len(stock[2])==524212
    check=[hr.PAYLOAD[2],1023,zlib.crc32(stock[2][:1023*512]),2]
    assert check==[34819,1023,3485190247,2]
    for kind,name in KINDS.items():
        if kind=='M4-ONLY':
            a,detail=donor_patch(original)
            assert detail['disallowed_m4_byte_mutations']==0
            assert pa.get_entry_swapped(a,0)!=donor_entries[0]
            assert all(pa.get_entry_swapped(a,i)==donor_entries[i] for i in range(1,15))
            altered=[0]
        else:
            a,detail=sharc_patch(original)
            assert pa.get_entry_swapped(a,2)!=donor_entries[2]
            assert all(pa.get_entry_swapped(a,i)==donor_entries[i] for i in list(range(2))+list(range(3,15)))
            altered=[2]
        label=ROOT/'build/startup-isolation'/name
        label.mkdir(parents=True,exist_ok=True)
        artifact=label/(name+'.l6ia')
        artifact.write_bytes(a)
        hxf=label/(name+'.hxf')
        subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(artifact),str(hxf),'--donor',str(donor)],cwd=ROOT,check=True)
        back,ishxf=pa.load_l6ia_from_any(str(hxf))
        assert ishxf and back==a
        assert [i for i in range(15) if pa.get_entry_swapped(back,i)!=donor_entries[i]]==altered
        subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(artifact)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        region=label/'regions'
        subprocess.run([sys.executable,str(ROOT/'tools/metro_led_r02c_ramplan.py'),'plan',str(hxf),'--stock',str(donor),'--out',str(region)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        manifest=region/'plan.json'
        plan=json.loads(manifest.read_text())
        assert plan['summary']['writes']=='ram' and len(plan['regions'])==9
        if kind=='M4-ONLY':
            assert plan['summary']['overlay_sectors']==0 and plan['checks']==[]
            # Same positive, read-only original donor E2 CRC check as R02C.
            plan['checks']=[check]
            manifest.write_text(json.dumps(plan,indent=2)+'\n')
        else:
            assert plan['summary']['overlay_sectors']>0 and len(plan['checks'])==1
            assert plan['checks'][0]==check
        report={
            'tag':name,'test_kind':kind,'experimental_hardware_run_permitted':False,
            'exact_donor_sha256':DONOR_SHA256,'mutated_l6ia_entries':altered,
            'original_untouched_other_entries':14,'feature_selection':'exact original installed HXtra v1.2.1',
            'ram_only':True,'regions':len(plan['regions']),'checks':plan['checks'],
            'overlay_sectors':plan['summary']['overlay_sectors'],
            'hxf_sha256':hashlib.sha256(hxf.read_bytes()).hexdigest(),
            'plan_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'entry2_bytes':len(hr.load(str(hxf))[2]),
            'purpose':'Diagnose R02C hardware startup freeze, after positive-control result',
        }
        (label/'manifest-hwfail01.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()

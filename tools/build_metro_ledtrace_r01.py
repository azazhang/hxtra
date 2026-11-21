#!/usr/bin/env python3
"""Build offline, byte-audited M4-only LED time-trace from exact installed HXtra.

No device access and no UI actions. Produces versioned .l6ia/.hxf,
nine-region RAM-only plan, donor-reference read-only CRC, and manifest.
"""
from pathlib import Path
import hashlib,json,subprocess,sys,zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import patch_amp as pa
import hxf_ram as hr
from metro_ledtrace_r01_donor_patch import patch_donor,DONOR_MD5,DONOR_SHA256
NAME='METRO-LEDSYNC-M4LEDTRACE-R01'

def run(donor:Path,output:Path):
    raw=donor.read_bytes()
    assert hashlib.md5(raw).hexdigest()==DONOR_MD5
    assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
    before,ishxf=pa.load_l6ia_from_any(str(donor))
    assert ishxf
    candidate,info=patch_donor(before)
    output.mkdir(parents=True,exist_ok=True)
    l6ia=output/(NAME+'.l6ia')
    hxf=output/(NAME+'.hxf')
    l6ia.write_bytes(candidate)
    subprocess.run([sys.executable,str(ROOT/'tools/l6ia_verify.py'),str(l6ia)],
                   cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(ROOT/'tools/hxf.py'),'pack',str(l6ia),
                    str(hxf),'--donor',str(donor)],cwd=ROOT,check=True,
                   stdout=subprocess.DEVNULL)
    back,ishxf=pa.load_l6ia_from_any(str(hxf))
    assert ishxf and back==candidate
    assert [i for i in range(15) if pa.get_entry_swapped(back,i)!=pa.get_entry_swapped(before,i)]==[0]
    orig_e2=hr.load(str(donor),stock=True)[2]
    assert orig_e2==hr.load(str(hxf))[2] and len(orig_e2)==524212
    region=output/'regions'
    subprocess.run([sys.executable,str(ROOT/'tools/metro_led_r02c_ramplan.py'),
                    'plan',str(hxf),'--stock',str(donor),'--out',str(region)],
                   cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    plan_path=region/'plan.json'
    plan=json.loads(plan_path.read_text())
    assert plan['summary']['unit']=='HX Stomp'
    assert plan['summary']['writes']=='ram'
    assert plan['summary']['overlay_sectors']==0
    assert plan['summary']['changed']==[]
    assert plan['checks']==[]
    assert len(plan['regions'])==9
    check=[hr.PAYLOAD[2],1023,zlib.crc32(orig_e2[:1023*512]),2]
    assert check==[34819,1023,3485190247,2]
    plan['checks']=[check]  # original donor verification if loader has eMMC access
    plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    manifest={'variant':NAME,'status':'OFFLINE_UNTESTED_ON_PHYSICAL_PEDAL',
              'source_donor_sha256':DONOR_SHA256,
              'M4_original_hook_sites':info['patch_sites'],
              'modified_entries':[0],
              'non_M4_entries_preserved_byte_identical':14,
              'M4_appended_bytes':info['modified_entry0_bytes']-info['original_entry0_bytes'],
              'led_timestamp_microsecond_source':'stock M4 0x28da6458',
              'led_hook':'stock 0x28d98f78 after HX_BPM final visible RGB',
              'message':'read-only USB command 0x50, 148-byte trace',
              'HXF_sha256':hashlib.sha256(hxf.read_bytes()).hexdigest(),
              'L6IA_sha256':hashlib.sha256(l6ia.read_bytes()).hexdigest(),
              'plan_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest(),
              'regions':9,'overlay_sectors':0,'writes':'ram',
              'reference_check':check,
              'hardware_run_initiated':False}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

def main():
    if len(sys.argv)>3:raise SystemExit('Usage: build_metro_ledtrace_r01.py [donor.hxf] [output-dir]')
    donor=Path(sys.argv[1]) if len(sys.argv)>1 else Path.home()/'Downloads/HXtra_v1.2.1.hxf'
    dest=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'build/browser-ramrun'/NAME
    print(json.dumps(run(donor,dest),indent=2))
if __name__=='__main__':
    main()

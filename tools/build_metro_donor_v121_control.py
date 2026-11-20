#!/usr/bin/env python3
"""RAM-run *unmodified* exact installed HXtra 1.2.1 for R02C freeze isolation.

The generic RAM planner has zero E2 checks when original==candidate; this
control adds one positive, read-only checksum over 1023 original donor sectors
for safety, matching R02C's independent CRC. No persistent eMMC writes.
"""
import hashlib,json,os,subprocess,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import hxf_ram as hr
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256


def main():
    if len(sys.argv)>2:raise SystemExit('usage: build_metro_donor_v121_control.py [EXACT-DONOR-HXF]')
    donor=Path(sys.argv[1]) if len(sys.argv)==2 else Path.home()/'Downloads/HXtra_v1.2.1.hxf'
    raw=donor.read_bytes()
    assert hashlib.md5(raw).hexdigest()==DONOR_MD5
    assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
    out=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/regions'
    out.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,str(ROOT/'tools/metro_led_r02c_ramplan.py'),'plan',str(donor),'--stock',str(donor),'--out',str(out)],cwd=ROOT,check=True)
    f=out/'plan.json';plan=json.loads(f.read_text())
    assert len(plan['regions'])==9
    assert plan['summary']['unit']=='HX Stomp' and plan['summary']['writes']=='ram'
    assert not plan['summary']['changed'] and not plan['summary']['overlay_sectors'] and not plan['summary']['runs']
    assert plan['checks']==[]
    stock=hr.load(str(donor),stock=True)
    whole=len(stock[2])//hr.SECTOR
    assert whole==1023
    actual=zlib.crc32(stock[2][:whole*hr.SECTOR])
    assert hr.PAYLOAD[2]==34819 and actual==3485190247
    plan['checks']=[[hr.PAYLOAD[2],whole,actual,2]]
    f.write_text(json.dumps(plan,indent=2)+'\n')
    print('UNMODIFIED_DONOR_CONTROL',json.dumps({'original_hxf_sha256':DONOR_SHA256,'changed_emmc_sectors':0,'ram_regions':9,'eMMC_reference_check':plan['checks'][0], 'plan_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'output':str(out)}))
if __name__=='__main__':main()

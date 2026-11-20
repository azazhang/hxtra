"""METRO-LEDSYNC-R02C-HWFAIL01: exact-donor startup isolation evidence.

No hardware access or HXF mutation. Read prebuilt candidate images and the
user's exact installed v1.2.1 HXF to verify only one firmware layer is changed
at a time and all RAM writes target SDRAM.
"""
import hashlib,json
from pathlib import Path
import pytest
import patch_amp as pa
import hxf_ram as ram
from metro_led_donor_patch import DONOR_SHA256

ROOT=Path(__file__).resolve().parents[1]
DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
NAMES={
 'M4-ONLY':([0],0),
 'SHARC-ONLY':([2],11),
}

@pytest.fixture(scope='module')
def images():
 if not DONOR.exists():pytest.skip('exact installed HXtra 1.2.1 donor unavailable')
 raw=DONOR.read_bytes()
 assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
 d,_=pa.load_l6ia_from_any(str(DONOR))
 original=[pa.get_entry_swapped(d,i) for i in range(15)]
 out={}
 for kind,(changed,overlay) in NAMES.items():
  label=f'METRO-LEDSYNC-R02C-HWFAIL01-{kind}'
  root=ROOT/'build/startup-isolation'/label
  hxf=root/(label+'.hxf');p=root/'regions/plan.json'
  if not hxf.exists() or not p.exists():pytest.skip(f'{label} not built')
  candidate,is_hxf=pa.load_l6ia_from_any(str(hxf));assert is_hxf
  entries=[pa.get_entry_swapped(candidate,i) for i in range(15)]
  report=json.loads((root/'manifest-hwfail01.json').read_text())
  plan=json.loads(p.read_text())
  assert [i for i,(a,b) in enumerate(zip(original,entries)) if a!=b]==changed
  assert report['mutated_l6ia_entries']==changed
  assert plan['summary']['overlay_sectors']==overlay
  assert plan['summary']['writes']=='ram'
  assert report['hxf_sha256']==hashlib.sha256(hxf.read_bytes()).hexdigest()
  assert report['plan_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
  out[kind]=(entries,plan,report)
 return original,out


def test_m4_only_does_not_touch_original_donor_sharc_or_any_other_entry(images):
 donor,out=images
 entries,plan,report=out['M4-ONLY']
 assert entries[0]!=donor[0]
 assert all(entries[i]==donor[i] for i in range(1,15))
 assert len(ram.load(str(DONOR),stock=True)[2])==524212
 assert report['entry2_bytes']==524212
 assert plan['summary']['overlay_sectors']==0


def test_sharc_only_does_not_touch_original_donor_m4_or_other_features(images):
 donor,out=images
 entries,plan,report=out['SHARC-ONLY']
 assert entries[2]!=donor[2]
 assert all(entries[i]==donor[i] for i in list(range(2))+list(range(3,15)))
 assert report['entry2_bytes']==524284
 assert plan['summary']['overlay_sectors']==11


def test_both_ablations_require_positive_read_only_donor_crc_and_ram_writes(images):
 _,out=images
 for kind,(entries,plan,report) in out.items():
  assert len(plan['regions'])==9
  assert plan['checks']==[[34819,1023,3485190247,2]]
  assert report['experimental_hardware_run_permitted'] is False
  assert report['exact_donor_sha256']==DONOR_SHA256
  assert report['ram_only'] is True
  assert all(r['addr']>=0x28000000 for r in plan['regions'])


def test_unmodified_donor_startup_control_is_truly_unmodified(images):
 _,out=images
 original=ROOT/'build/browser-ramrun/METRO-DONOR-V121-UNCHANGED-RAM-CONTROL/regions/plan.json'
 if not original.exists():pytest.skip('original donor control not generated')
 data=json.loads(original.read_text())
 assert data['summary']['overlay_sectors']==0
 assert data['summary']['changed']==[]
 assert data['summary']['writes']=='ram'
 assert data['checks']==[[34819,1023,3485190247,2]]
 assert len(data['regions'])==9

"""HWFAIL03 compares one-factor metadata fix against actual failed SHARC-only run.

The donor and SHARC binary are exactly those used in HWFAIL02; only one new
RAM overlay sector is added (the SHARC partition metadata header). Full
sector-by-sector reconstructed device readback is checked for equality with
the HXF's header and payload. These checks do not prove hardware startup.
"""
from pathlib import Path
import hashlib,json,struct,zlib
import patch_amp as pa,hxf_ram as hr,l6ia
from metro_led_donor_patch import DONOR_SHA256
from metro_led_hwfail03_header_only_plan import HWFAIL02_HXF_SHA256

ROOT=Path(__file__).resolve().parent.parent
D=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
NAME='METRO-LEDSYNC-R02C-HWFAIL01-SHARC-ONLY'
H=ROOT/'build/startup-isolation'/NAME/(NAME+'.hxf')
P=ROOT/'build/startup-isolation/METRO-LEDSYNC-HWFAIL03-HEADER-ONLY/regions/plan.json'
P2=ROOT/'build/startup-isolation'/NAME/'regions/plan.json'

def setup():
 assert hashlib.sha256(D.read_bytes()).hexdigest()==DONOR_SHA256
 assert hashlib.sha256(H.read_bytes()).hexdigest()==HWFAIL02_HXF_SHA256
 o,_=pa.load_l6ia_from_any(str(D));n,_=pa.load_l6ia_from_any(str(H))
 return o,n,json.loads(P.read_text()),json.loads(P2.read_text())

def runs(plan):
 row=next(r for r in plan['regions'] if r['label'].startswith('hook, overlay'))
 origin=row['addr'];raw=(P.parent/row['file']).read_bytes() if plan['summary']['overlay_sectors']==12 else (P2.parent/row['file']).read_bytes()
 off=plan['summary']['table']-origin
 n=struct.unpack_from('<I',raw,off)[0]
 entries=[struct.unpack_from('<3I',raw,off+4+12*i) for i in range(n)]
 return origin,raw,entries

def mem_sector(plan,sector):
 origin,raw,rr=runs(plan)
 hits=[]
 for start,count,mem in rr:
  if start<=sector<start+count:
   begin=mem-origin+512*(sector-start)
   hits.append(raw[begin:begin+512])
 assert len(hits)<=1
 return hits[0] if hits else None

def test_exact_same_hxf_with_one_extra_header_overlay_sector():
 old,candidate,new,failed=setup()
 for k in range(15):
  if k!=2:assert pa.get_entry_swapped(old,k)==pa.get_entry_swapped(candidate,k)
 assert new['summary']['changed']==failed['summary']['changed']==[[2,524212,524284,11]]
 assert new['summary']['overlay_sectors']==failed['summary']['overlay_sectors']+1==12
 assert len(new['regions'])==len(failed['regions'])==9
 assert new['summary']['writes']==failed['summary']['writes']=='ram'
 assert new['checks']==failed['checks']==[[34819,1023,3485190247,2]]


def test_single_new_header_run_and_every_existing_sector_identical():
 old,candidate,new,failed=setup()
 start=hr.PART_START[2];end=start+1024
 assert mem_sector(failed,start) is None
 assert mem_sector(new,start) is not None
 for sector in range(start+1,end+1):
  assert mem_sector(new,sector)==mem_sector(failed,sector),(hex(sector),'overlay changed old content')


def test_all_sharc_partition_sectors_reconstruct_exact_candidate_HXF():
 old,candidate,new,failed=setup()
 old_entry=l6ia.parse(old)[2];new_entry=l6ia.parse(candidate)[2]
 a=l6ia.swap32(old_entry['sub']);b=l6ia.swap32(new_entry['sub'])
 assert a!=b and len(a)==len(b)==512
 assert struct.unpack_from('<I',a,12)[0]==524212
 assert struct.unpack_from('<I',b,12)[0]==524284
 assert mem_sector(new,hr.PART_START[2])==b
 payload=hr.load(str(H))[2];donor_payload=hr.load(str(D))[2]
 for sector in range(1024):
  s=hr.PAYLOAD[2]+sector
  data=mem_sector(new,s)
  if data is None:
   data=donor_payload[sector*512:sector*512+512].ljust(512,b'\0')
  assert data==payload[sector*512:sector*512+512].ljust(512,b'\0'),hex(s)
 assert struct.unpack_from('<I',b,8)[0]==zlib.crc32(payload)

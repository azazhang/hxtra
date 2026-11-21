#!/usr/bin/env python3
"""Build an exact-donor R02D RAM plan including changed SHARC metadata sector.

The earlier R02C/HWFAIL02 RAM plans overlaid only payload sectors. Because
Entry 2 grew 72 bytes, the on-card subheader (sector 0x8802) still advertised
the donor's shorter payload and CRC. This plan explicitly includes the patched
HXF's 512-byte Entry2 header as a *RAM overlay*, never writing eMMC.

The default shared hxf_ram implementation is unchanged. Its overlay function
is replaced only inside this one short-lived offline plan-construction
process, with every generated run then checked byte-for-byte against source.
"""
from pathlib import Path
import argparse,hashlib,json,struct,zlib,sys
import hxf_ram as hr,l6ia,patch_amp as pa
from metro_led_r02c_ramplan import DONOR_APP_CRC, STOCK_APP_CRC
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256


def make_plan(donor_path, candidate_path,out,expected_entry2_bytes=524212,variant="METRO-LEDSYNC-R02D-SHARC-SIZE-PRESERVED-HEADER-OVERLAY"):
    donor=Path(donor_path).read_bytes();cand=Path(candidate_path).read_bytes()
    assert hashlib.md5(donor).hexdigest()==DONOR_MD5
    assert hashlib.sha256(donor).hexdigest()==DONOR_SHA256
    # This installed HXtra app has different application CRC than stock 3.80,
    # while the existing eMMC read/write driver entry points and literals are
    # byte-identical. Verify and register the *known* donor explicitly.
    source=hr.load(str(donor_path),stock=True)
    valid_len=struct.unpack_from('<I',source[0],4)[0]
    assert zlib.crc32(source[0][0x34:valid_len])==DONOR_APP_CRC
    reference=hr.APPS[STOCK_APP_CRC]
    _,driver_functions,card=reference
    segments,_=hr.app_segments(source[0])
    for fname,(fn,lit) in driver_functions.items():
        assert hr.seg_read(segments,fn,len(hr.PROLOGUE))==hr.PROLOGUE,(fname,'prologue changed')
        assert struct.unpack('<I',hr.seg_read(segments,lit,4))[0]==card,(fname,'driver changed')
    hr.APPS[DONOR_APP_CRC]=reference
    original,_=pa.load_l6ia_from_any(str(donor_path))
    modified,_=pa.load_l6ia_from_any(str(candidate_path))
    original_ents=l6ia.parse(original);new_ents=l6ia.parse(modified)
    assert len(original_ents)==len(new_ents)==15
    assert [i for i in range(15) if pa.get_entry_swapped(original,i)!=pa.get_entry_swapped(modified,i)]==[2]
    old_hdr=l6ia.swap32(original_ents[2]['sub']);new_hdr=l6ia.swap32(new_ents[2]['sub'])
    assert len(old_hdr)==len(new_hdr)==512 and old_hdr!=new_hdr
    magic,version,crc,plen=struct.unpack_from('<4I',new_hdr)
    assert magic==0x56112603 and plen==expected_entry2_bytes
    assert crc==zlib.crc32(hr.load(str(candidate_path))[2]);assert original_ents[2]['payload_len']==524212
    # Add exactly one physically updated SHARC subheader sector at eMMC 0x8802.
    old_overlay=hr.overlay
    def with_header(stock,new):
        sectors,notes=old_overlay(stock,new)
        assert [i for i,*rest in notes]==[2] and notes[0][1:3]==(524212,expected_entry2_bytes)
        assert all(sec!=hr.PART_START[2] for sec,_ in sectors)
        return [(hr.PART_START[2],new_hdr)]+sectors,notes
    hr.overlay=with_header
    try:
        regions,checks,summary=hr.plan(str(candidate_path),str(donor_path),writes='ram')
    finally:
        hr.overlay=old_overlay
    assert len(regions)==9 and summary['writes']=='ram' and summary['overlay_sectors']>1
    assert checks==[[hr.PAYLOAD[2],1023,zlib.crc32(hr.load(str(donor_path),stock=True)[2][:1023*512]),2]] or checks==[(hr.PAYLOAD[2],1023,zlib.crc32(hr.load(str(donor_path),stock=True)[2][:1023*512]),2)]
    # Inspect the actual RAM hook binary's overlay table and verify that the
    # real runtime read_hook overlay_find() will return this exact new header.
    hook=[(addr,data) for addr,data,label in regions if label.startswith('hook, overlay table')]
    assert len(hook)==1
    addr,data=hook[0]
    table=summary['table'];offset=table-addr
    nrun=struct.unpack_from('<I',data,offset)[0]
    hits=[]
    for i in range(nrun):
        sector,n,memaddr=struct.unpack_from('<3I',data,offset+4+12*i)
        assert n>=1
        if sector<=hr.PART_START[2]<sector+n:
            rel=memaddr-addr+512*(hr.PART_START[2]-sector)
            hits.append(data[rel:rel+512])
    assert hits==[new_hdr],f'Overlay hook does not contain exact new metadata sector ({len(hits)} matches)'
    assert summary['overlay_sectors']==1+len(old_overlay(hr.load(str(donor_path),stock=True),hr.load(str(candidate_path)))[0])
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    meta={'regions':[],'checks':checks,'summary':summary}
    for i,(addr,raw,label) in enumerate(regions):
        fn=f'{i:02d}_{addr:08x}.bin'
        (out/fn).write_bytes(raw)
        meta['regions'].append({'addr':addr,'file':fn,'label':label})
    (out/'plan.json').write_text(json.dumps(meta,indent=1))
    report=dict(variant=variant,hardware_tested=False,
      donor_sha256=DONOR_SHA256,candidate_hxf_sha256=hashlib.sha256(cand).hexdigest(),
      original_entry2_bytes=original_ents[2]['payload_len'],candidate_entry2_bytes=plen,
      original_header_crc=hex(struct.unpack_from('<I',old_hdr,8)[0]),candidate_header_crc=hex(crc),
      header_overlaid_at_emmc_sector=hex(hr.PART_START[2]),header_overlay_exact=True,
      total_overlay_sectors=summary['overlay_sectors'],runs=summary['runs'],
      ram_regions=len(regions),ram_only=summary['writes']=='ram',
      plan_sha256=hashlib.sha256((out/'plan.json').read_bytes()).hexdigest())
    print(json.dumps(report,indent=2))
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('donor');ap.add_argument('candidate');ap.add_argument('out')
    args=ap.parse_args()
    make_plan(args.donor,args.candidate,args.out)
if __name__=='__main__':main()

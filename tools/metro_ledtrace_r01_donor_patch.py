#!/usr/bin/env python3
"""METRO-LEDSYNC-M4LEDTRACE-R01 — immutable donor-based M4-only diagnostic.

Only the final LED sender continuation and editor registration are hooked.
The installed original SHARC Entry2 and all 13 other non-M4 entries are
bit-identical to the exact donor. This script has NO pedal/USB access.
Output is an offline L6IA analysis archive (no automatic RAM test).
"""
import argparse,hashlib,json,struct
from pathlib import Path
import patch_amp as pa
import patch_menu as pm
import usb_commands
import l6ia
from metro_led_donor_patch import DONOR_MD5,DONOR_SHA256

LED_SITE=0x28d98f78
REG_SITE=0x28d96adc
REG_TARGET=0x28e1661c
PATCH_SITES=(LED_SITE,REG_SITE)

def patch_donor(archive):
    load=lambda i:pa.get_entry_swapped(archive,i)
    original=load(0)
    p=pm.Patch(original,[],{},load)
    assert p.read(LED_SITE,4)==bytes.fromhex('85b01a78')
    assert p.read(REG_SITE,4)==pm.bl(REG_SITE,REG_TARGET)
    assert p.read(0x28d98f74,4)==pa.thumb_bw(0x28d98f74,0x28e4d632)
    assert p.read(0x28d9be92,4)==pm.bl(0x28d9be92,0x28e55060)
    m=p.module('src/m4/metro_ledtrace_r01.s',inc={'usb.inc':usb_commands.inc('metronome_phase')})
    p.put(LED_SITE,pa.thumb_bw(LED_SITE,m['mt_led_entry']),
          'post-HX_BPM final visible FS3 LED command')
    p.chain_bl(REG_SITE,REG_TARGET,after=m['mt_register'])
    p.finish_chains()
    replaced=p.output()
    assert set(replaced)=={0}
    modified=replaced[0]
    changed=[i for i,(a,b) in enumerate(zip(original,modified)) if a!=b]
    allowed=set(range(0,24))
    for site in PATCH_SITES:
        off=p.off(site,4)
        allowed.update(range(off,off+4))
    for seg in p.segs:
        allowed.update(range(seg[0],seg[0]+20))
    illegal=[i for i in changed if i not in allowed and i<len(original)-8]
    assert not illegal,illegal[:30]
    out,_,_=l6ia.rebuild_archive(archive,replaced)
    for entry in range(1,15):
        assert pa.get_entry_swapped(out,entry)==load(entry),f'non-M4 entry {entry} changed'
    for label in [b'DSP Usage Display',b'Breathing Line',b'Path A',b'Main+Snd',b'FS1 Hold']:
        assert label in modified,label
    return out,{'variant':'METRO-LEDSYNC-M4LEDTRACE-R01',
                'patch_sites':[hex(x) for x in PATCH_SITES],
                'original_entry0_bytes':len(original),
                'modified_entry0_bytes':len(modified),
                'new_thumb_symbols':{k:hex(m[k]) for k in ('mt_led_entry','mt_capture','mt_command')},
                'original_non_M4_entries_byte_identical':14,
                'original_SHARC_entry2_byte_identical':True,
                'disallowed_original_M4_modifications':len(illegal)}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('donor')
    a.add_argument('output')
    v=a.parse_args()
    d=Path(v.donor)
    raw=d.read_bytes()
    assert hashlib.md5(raw).hexdigest()==DONOR_MD5
    assert hashlib.sha256(raw).hexdigest()==DONOR_SHA256
    archive,is_hxf=pa.load_l6ia_from_any(str(d))
    assert is_hxf
    out,info=patch_donor(archive)
    dst=Path(v.output)
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_bytes(out)
    print(json.dumps({**info,'analysis_only':True,'source_donor_sha256':DONOR_SHA256,
                      'archive_sha256':hashlib.sha256(out).hexdigest(),'output':str(dst)},indent=2))
if __name__=='__main__':
    main()

#!/usr/bin/env python3
"""R02C direct donor patch: M4 LED-output telemetry ONLY (NOT a complete metronome-sync image).

Input must be the user's exact installed HXtra v1.2.1 .hxf (MD5 pinned).
Preserves all 14 non-M4 entries exactly, including the SHARC 512 KiB image,
NAM, GR, USB Monitor, all M4 features, model names, boot graphics/settings.
Only modifies five checked sites within the donor M4 Entry 0 and appends a
self-contained M4 diagnostic module; no other donor code bytes may change.

This script does NOT install, reboot, or communicate with an HX Stomp.
Its output is a L6IA analysis artifact, not a complete audio sync fix.
"""
import argparse,hashlib,os,struct
import patch_amp as pa
import patch_menu as pm
import usb_commands
import l6ia

DONOR_MD5='93969635834cd6050dec7f137df1e4b9'
DONOR_SHA256='96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0'
LED_SINK=0x28d98f78
BYPASS=0x28e045a0
REGISTER_ALL_CALL=0x28d96adc
REGISTER_ALL=0x28e1661c
TX_CB_LIT=0x28da6138
RX_CB_LIT=0x28da6134
PATCH_SITES=(LED_SINK,BYPASS,REGISTER_ALL_CALL,TX_CB_LIT,RX_CB_LIT)


def donor_patch(archive):
    load=lambda n: pa.get_entry_swapped(archive,n)
    donor_e0=load(0)
    p=pm.Patch(donor_e0,[],{},load)
    assert p.read(LED_SINK,4)==bytes.fromhex('85b01a78'), 'wrong actual LED sender continuation'
    assert p.read(BYPASS,4)==bytes.fromhex('2de9f041'), 'bypass setter differs from installed HXtra v1.2.1'
    assert p.read(REGISTER_ALL_CALL,4)==pm.bl(REGISTER_ALL_CALL,REGISTER_ALL), 'editor registration differs'
    assert p.read(TX_CB_LIT,4)==struct.pack('<I',0x10000e95), 'donor TX callback not as audited'
    assert p.read(RX_CB_LIT,4)==struct.pack('<I',0x28e55521), 'donor GR RX callback not as audited'
    # Explicitly verify unchanged full installed Tap Command/BPM feature hooks:
    assert p.read(0x28d9be92,4)==pm.bl(0x28d9be92,0x28e55060)
    assert p.read(0x28d98f74,4)==pa.thumb_bw(0x28d98f74,0x28e4d632)
    assert p.read(0x28e4d650,6)==bytes.fromhex('0ff294439a79'), 'bpm_data visible flag source does not match installed donor'
    m=p.module('src/m4/metronome_led_egress.s',inc={'usb.inc':usb_commands.inc('metronome_phase')})
    p.put(LED_SINK,pa.thumb_bw(LED_SINK,m['mp_led_entry']),'donor LED output AFTER visibility filter')
    p.chain_entry(BYPASS,bytes.fromhex('2de9f041'),after=m['mp_bypass'])
    p.chain_bl(REGISTER_ALL_CALL,REGISTER_ALL,after=m['mp_register'])
    p.chain_ptr(TX_CB_LIT,p.u32(TX_CB_LIT),after=m['mp_tx_stamp'])
    p.chain_ptr(RX_CB_LIT,p.u32(RX_CB_LIT),before=m['mp_rx_probe'])
    p.finish_chains()
    replaced=p.output()
    assert set(replaced)=={0},f'extra changed entries: {list(replaced)}'
    new_e0=replaced[0]
    # All old M4 code/data bytes, including installed HXtra UI hooks, are
    # bitwise identical unless they belong to a precisely audited patch site
    # or the Entry0 section headers/CRC metadata.
    changed=[i for i,(a,b) in enumerate(zip(donor_e0,new_e0)) if a!=b]
    allowed=set(range(0,24))
    for va in PATCH_SITES:
        o=p.off(va,4)
        allowed.update(range(o,o+4))
    # Entry0 footer has CRC32s, and code-segment length/pointers are in the
    # segment header; both are structure metadata, not feature configuration.
    for seg in p.segs:
        allowed.update(range(seg[0],seg[0]+20))
    disallowed=[i for i in changed if i not in allowed and i< len(donor_e0)-8]
    assert not disallowed,(len(disallowed),disallowed[:25])
    out,_,_=l6ia.rebuild_archive(archive,replaced)
    for n in range(1,15):
        assert pa.get_entry_swapped(out,n)==load(n),f'original donor Entry{n} altered'
    assert new_e0.find(b'DSP Usage Display')>=0
    assert new_e0.find(b'Breathing Line')>=0
    return out,dict(entry0_old=len(donor_e0),entry0_new=len(new_e0),patch_sites=[hex(x) for x in PATCH_SITES],
        thumb_symbols={k:hex(m[k]) for k in ('mp_led_entry','mp_led_capture','mp_bypass','mp_register','mp_tx_stamp','mp_rx_probe')},
        donor_sha256=DONOR_SHA256,untouched_other_entries=14,disallowed_m4_byte_mutations=0)


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('donor')
    a.add_argument('out_l6ia')
    opt=a.parse_args()
    data=open(opt.donor,'rb').read()
    assert hashlib.md5(data).hexdigest()==DONOR_MD5, 'NOT the exact user-installed HXtra v1.2.1 donor (MD5 check)'
    assert hashlib.sha256(data).hexdigest()==DONOR_SHA256, 'donor SHA256 mismatch'
    archive,is_hxf=pa.load_l6ia_from_any(opt.donor)
    assert is_hxf
    out,report=donor_patch(archive)
    with open(opt.out_l6ia,'wb') as f:f.write(out)
    import json
    print(json.dumps({'status':'M4-only donor-preserving analysis artifact; SHARC audio not modified',**report,
       'out_archive_sha256':hashlib.sha256(out).hexdigest(),'output':opt.out_l6ia},indent=2))
if __name__=='__main__':main()

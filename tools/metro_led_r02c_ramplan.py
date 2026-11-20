#!/usr/bin/env python3
"""METRO-LEDSYNC-R02C-DONOR-EGRESS RAM planner; exact installed HXtra v1.2.1 donor.

This is *not* a generic upstream hxf_ram change. Only the exact, independently
checked v1.2.1 HXF below is permitted as a reference. Never bypass eMMC CRCs.
"""
import hashlib
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools'))
import hxf_ram as hr

DONOR_MD5 = '93969635834cd6050dec7f137df1e4b9'
DONOR_APP_CRC = 0xbe5d84a0
STOCK_APP_CRC = 0x2b81e740


def enable_exact_donor():
    if '--no-emmc-check' in sys.argv or '--writes' in sys.argv and sys.argv[sys.argv.index('--writes') + 1] != 'ram':
        raise SystemExit('Safety check: eMMC verification and --writes ram are mandatory')
    if '--stock' not in sys.argv:
        raise SystemExit('Expected --stock PATH_TO_HXtra_v1.2.1.hxf')
    donor_path = sys.argv[sys.argv.index('--stock') + 1]
    md5 = hashlib.md5(open(donor_path, 'rb').read()).hexdigest()
    if md5 != DONOR_MD5:
        raise SystemExit('Unknown donor; reference firmware MD5 mismatch')
    donor = hr.load(donor_path, stock=True)
    app = donor[0]
    crc = zlib.crc32(app[0x34:struct.unpack_from('<I',app,4)[0]])
    if crc != DONOR_APP_CRC:
        raise SystemExit('Unknown donor application CRC')
    stock_app = hr.APPS[STOCK_APP_CRC]
    _, funcs, card = stock_app
    segs, _ = hr.app_segments(app)
    for name, (fn, lit) in funcs.items():
        if hr.seg_read(segs, fn, len(hr.PROLOGUE)) != hr.PROLOGUE:
            raise SystemExit(f'{name} hook prologue changed in donor')
        if struct.unpack('<I',hr.seg_read(segs,lit,4))[0] != card:
            raise SystemExit(f'{name} eMMC driver literal changed in donor')
    hr.APPS[DONOR_APP_CRC] = stock_app
    original_loader = hr.Loader
    class StrictLoader(original_loader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if not self.info['flags'] & 2:
                raise SystemExit('ABORT: eMMC not initialized; cannot verify donor reference. Power-cycle the pedal.')
    hr.Loader = StrictLoader
    print('Verified HXtra v1.2.1 donor identity and original eMMC hook sites')


if __name__ == '__main__':
    enable_exact_donor()
    hr.main()

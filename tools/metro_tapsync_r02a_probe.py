#!/usr/bin/env python3
"""METRO-TAPSYNC-R02A-M4EDGE: read-only edge-counter probe via USB 0x50.

Use after loading the named R02A RAM image. The command uses HXtra's existing
editor USB service and returns 12-byte MessagePack binary with the two u32
counts and an exact build diagnostic sentinel. It makes no pedal state changes.
"""
import argparse
import json
import struct
import time

import hx_ctl

CMD = 0x50
SENTINEL = 0x52303241  # ASCII 'A20R' in LE bytes, exact R02A image


def decode(data):
    if not isinstance(data, bytes) or len(data) != 12:
        raise ValueError(f'METRO-TAPSYNC-R02A: expected 12 binary bytes, got {type(data).__name__}/{len(data) if hasattr(data,"__len__") else "?"}')
    beats, resumes, tag = struct.unpack('<3I', data)
    if tag != SENTINEL:
        raise ValueError(f'METRO-TAPSYNC-R02A: unexpected firmware sentinel 0x{tag:08x}')
    return {'revision': 'METRO-TAPSYNC-R02A-M4EDGE', 'tap_led_on_count': beats,
            'metro_41c_enable_count': resumes, 'raw_tag': f'0x{tag:08x}'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples', type=int, default=6)
    ap.add_argument('--interval', type=float, default=0.5)
    ap.add_argument('--out', help='optional JSONL log')
    a = ap.parse_args()
    if not 1 <= a.samples <= 250 or not 0 <= a.interval <= 30:
        ap.error('samples 1..250; interval 0..30 seconds')
    ctl = hx_ctl.HxCtl()
    try:
        with open(a.out, 'w') if a.out else __import__('contextlib').nullcontext() as logfile:
            for i in range(a.samples):
                row = {'sample':i, 'monotonic':time.monotonic(), **decode(ctl.ed.request(CMD, timeout=4))}
                print(json.dumps(row), flush=True)
                if logfile: logfile.write(json.dumps(row)+'\n')
                if i+1<a.samples:time.sleep(a.interval)
    finally:
        ctl.close()


if __name__ == '__main__':
    main()

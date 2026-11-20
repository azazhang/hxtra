#!/usr/bin/env python3
"""METRO-TAPSYNC-R02B1-SPI-CANARY: read M4-to-SHARC SPI canary telemetry.

The 0x50 response is a 32-byte MessagePack BIN8 of eight little-endian u32s.
This is a transport diagnostic; no metronome audio phase is modified.
"""
import argparse
import json
import struct
import time

import hx_ctl

SIG = 0x31423252                    # little-endian bytes "R2B1"
CANARY = 0x4D543242                 # M4 SPI frame slot 240


def decode(data):
    if not isinstance(data,bytes) or len(data)!=32:
        raise ValueError(f'METRO-TAPSYNC-R02B1: expected exactly 32 bytes; got {type(data).__name__} {len(data) if hasattr(data,"__len__") else "?"}')
    beat,enable,tx,skips,rx,d0,d1,tag = struct.unpack('<8I',data)
    if tag!=SIG:
        raise ValueError(f'METRO-TAPSYNC-R02B1: wrong firmware signature 0x{tag:08x}')
    return {'revision':'METRO-TAPSYNC-R02B1-SPI-CANARY', 'tap_led_on_count':beat,
            'metro_41c_enable_count':enable,'spi_tx_stamped':tx,'spi_tx_skipped':skips,
            'dsp_rx_frames_with_gr_marker':rx,
            'dsp_echo_candidate_a_raw':f'0x{d0:08x}',
            'dsp_echo_candidate_b_raw':f'0x{d1:08x}',
            'dsp_echo_candidate_a_halfword_swapped':f'0x{((d0<<16)|(d0>>16))&0xffffffff:08x}',
            'dsp_echo_candidate_b_halfword_swapped':f'0x{((d1<<16)|(d1>>16))&0xffffffff:08x}',
            'canary':f'0x{CANARY:08x}' }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples',type=int,default=8)
    ap.add_argument('--interval',type=float,default=0.4)
    ap.add_argument('--out')
    a=ap.parse_args()
    if not 1<=a.samples<=250 or not 0<=a.interval<=30:ap.error('samples must be 1..250 and interval 0..30')
    with hx_ctl.HxCtl(timeout=3) as c:
        import contextlib
        with (open(a.out,'w') if a.out else contextlib.nullcontext()) as out:
            for i in range(a.samples):
                row={'sample':i,'monotonic':time.monotonic(),**decode(c.ed.request(0x50,timeout=4))}
                txt=json.dumps(row)
                print(txt,flush=True)
                if out:out.write(txt+'\n')
                if i+1<a.samples:time.sleep(a.interval)
if __name__=='__main__':main()

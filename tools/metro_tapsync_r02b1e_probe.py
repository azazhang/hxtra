#!/usr/bin/env python3
"""METRO-TAPSYNC-R02B1E-EVENT-ECHO live readout for M4->SHARC event words.

USB command 0x50 reports 48 bytes (12 little-endian u32 words). The four
SHARC mirror values refer to the most recently received return frame; event
counts need not coincide exactly with the M4's current count because of
transport timing. Check the integrity checksum before using them.
"""
import argparse
import contextlib
import json
import struct
import time
import hx_ctl

SIG=0x31453142              # BIN8 payload little-endian 'B1E1'
CANARY=0x4D543242
CMD=0x50

def decode(data):
    if not isinstance(data,bytes) or len(data)!=48:
        raise ValueError(f'METRO-TAPSYNC-R02B1E: expected 48 binary bytes, got {type(data).__name__} {len(data) if hasattr(data,"__len__") else "?"}')
    tap,enable,tx,skips,rx,marker,dsp_tap,dsp_enable,check,good,bad,tag=struct.unpack('<12I',data)
    if tag!=SIG:raise ValueError(f'METRO-TAPSYNC-R02B1E: unexpected image signature 0x{tag:08x}')
    checksum=((~(marker ^ dsp_tap ^ dsp_enable))&0xffffffff)
    valid=(marker==CANARY and check==checksum)
    return {'revision':'METRO-TAPSYNC-R02B1E-EVENT-ECHO','tap_led_on_count':tap,
        'metro_41c_enable_count':enable,'spi_tx_stamped':tx,'spi_tx_skipped':skips,
        'dsp_rx_frames_with_gr_marker':rx,
        'dsp_echo_marker':f'0x{marker:08x}',
        'dsp_echo_tap_count':dsp_tap,
        'dsp_echo_enable_count':dsp_enable,
        'dsp_echo_checksum':f'0x{check:08x}',
        'dsp_echo_integrity_valid':valid,
        'dsp_echo_valid_frames':good,'dsp_echo_bad_checksum_frames':bad,
        'tap_count_difference_m4_minus_dsp':(tap-dsp_tap)&0xffffffff,
        'enable_count_difference_m4_minus_dsp':(enable-dsp_enable)&0xffffffff}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples',type=int,default=8)
    p.add_argument('--interval',type=float,default=.4)
    p.add_argument('--out')
    a=p.parse_args()
    if not 1<=a.samples<=250 or not 0<=a.interval<=30:p.error('samples 1..250; interval 0..30 seconds')
    with hx_ctl.HxCtl(timeout=3) as c:
        with (open(a.out,'w') if a.out else contextlib.nullcontext()) as out:
            for i in range(a.samples):
                row={'sample':i,'monotonic':time.monotonic(),**decode(c.ed.request(CMD,timeout=4))}
                msg=json.dumps(row)
                print(msg,flush=True)
                if out:out.write(msg+'\n');out.flush()
                if i+1<a.samples:time.sleep(a.interval)
if __name__=='__main__':main()

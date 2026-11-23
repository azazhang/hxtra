#!/usr/bin/env python3
"""Read-only HXtra IO-LEVEL-R01: collect actual *native* SHARC->M4 RX frames.

Requires user-initiated RAM boot of the separate R01 probe image. Command 0x4f
does not edit presets or settings; its command arms the NEXT frame capture.
Raw traces should be reviewed locally before publishing: payloads are actual
DSP messages, potentially carrying preset IDs and parameters.

No pedal reboot, RAM handoff, image write, or preset change is attempted.
"""
from __future__ import annotations
import argparse,contextlib,json,struct,time
from pathlib import Path
from io_level_native_protocol import parse_frame

NAME='IO-LEVEL-R01-NATIVE-RX-FRAME-PROBE'
CMD=0x4f
BASE_R03C_CMD=0x50
STAMP=0x31524f49      # little endian "IOR1"
BIN_SIZE=1040
WORDS=256
RX_MAGIC=0xf00dface   # low/high halfword-swapped
RX_TRAILER=0xecafd00f

def decode(data):
    if not isinstance(data,bytes) or len(data)!=BIN_SIZE:
        raise ValueError(f'{NAME}: expected {BIN_SIZE} bytes, got {type(data).__name__} length {len(data) if isinstance(data,bytes) else "?"}')
    magic,seq,count,reserved=struct.unpack_from('<4I',data)
    if magic!=STAMP:
        raise ValueError(f'{NAME}: unexpected signature {magic:#010x}')
    w=struct.unpack_from('<256I',data,16)
    return {
      'variant':NAME,'sample_seq':seq,'sampled_frames_total':count,
      'complete':seq>0 and count>=seq,
      'M4_RX_MAGIC_valid':w[0]==RX_MAGIC,
      'M4_RX_TRAILER_valid':w[255]==RX_TRAILER,
      **parse_frame(w),
      'r03c_rx_frame_gr_marker':w[200]==0xf00d600d,
      'words_M4_raw_halfword_swapped':list(w),
      'native_event_bytes_decoded':True,
      'input_output_level_calibrated':False,
    }

def main():
    import hx_ctl,metro_led_r03c_probe
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples',type=int,default=16)
    ap.add_argument('--interval',type=float,default=.4)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    if not 1<=args.samples<=500 or not .05<=args.interval<=60:
        ap.error('samples 1..500, interval .05..60')
    with hx_ctl.HxCtl(timeout=3) as ctl:
        rev=metro_led_r03c_probe.decode(ctl.ed.request(BASE_R03C_CMD,timeout=4))
        print(json.dumps({'r03c_signature':rev['revision'],'R03C_valid_SPI':rev['last_M4_TX_pair_is_valid']}),flush=True)
        with (args.out.open('w') if args.out else contextlib.nullcontext()) as f:
            for i in range(args.samples):
                raw=ctl.ed.request(CMD,timeout=5)
                row={'host_monotonic_s':time.monotonic(),'sample':i,**decode(raw)}
                if not row['complete'] or not row['M4_RX_MAGIC_valid'] or not row['M4_RX_TRAILER_valid']:
                    raise RuntimeError('R01 captured no complete valid RX frame; do not infer an input/output level from this record')
                if i==0:
                    print('RX first 32 words: '+' '.join(f'{v:08x}' for v in row['words_M4_raw_halfword_swapped'][:32]),flush=True)
                print(json.dumps({k:v for k,v in row.items() if k!='words_M4_raw_halfword_swapped'}),flush=True)
                if f:f.write(json.dumps(row)+'\n');f.flush()
                if i+1<args.samples:time.sleep(args.interval)
if __name__=='__main__':
    main()

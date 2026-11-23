#!/usr/bin/env python3
"""Read-only rolling input/output-meter diagnostic for HXtra IO-LEVEL-R03.

R03's M4 receives *every* DSP->M4 44-word native meter packet, copies all
eight native float32 readings and increments counters. This tool retrieves
those stable accumulated values over editor command 0x13; USB sampling
frequency does not determine whether a transient 44-word meter event is seen.

No pedal writes, signal injection, preset changes or device reboot.
"""
import argparse,contextlib,json,math,struct,time
from pathlib import Path

CMD=0x13
MAGIC=0x334d4f49

def unswap32(v):
    return ((v>>16)|(v<<16))&0xffffffff

def decode(raw):
    if not isinstance(raw,bytes) or len(raw)!=64:
        raise ValueError(f'Expected exactly 64 bytes of R03 diagnostic, got {len(raw) if isinstance(raw,bytes) else type(raw).__name__}')
    w=struct.unpack('<16I',raw)
    if w[0]!=MAGIC:
        raise ValueError(f'Unexpected R03 rolling-meter signature {w[0]:#010x}')
    vals=[struct.unpack('<f',struct.pack('<I',unswap32(x)))[0] for x in w[8:16]]
    if any(not math.isfinite(x) for x in vals):
        raise ValueError('Nonfinite native level in R03 diagnostic')
    packed=w[6]
    return {
        'revision':'IO-LEVEL-R03-NATIVE-ROLLING-METER-DIAG',
        'RX_frames_seen':w[1],
        'RX_native_nonempty_frames_seen':w[2],
        'native_44word_candidates_seen':w[3],
        'native_44word_meter_packets_accepted':w[4],
        'bar_state_changes':w[5],
        'bar_state_raw_hex':f'{packed:#010x}',
        'bar_valid':bool(packed&0x80000000),
        'bar_left_pixels':packed&255,
        'bar_right_pixels':(packed>>8)&255,
        'last_native_header_raw_hex':f'{w[7]:#010x}',
        'native_record_ids_in_HW02_order':[2,5,3,6,4,6,1,5],
        'native_8_levels_float32':vals,
        'physical_port_identity_verified':False,
    }

def main():
    import hx_ctl,metro_led_r03c_probe
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples',type=int,default=48)
    ap.add_argument('--interval',type=float,default=.2)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    if not 1<=args.samples<=1000 or not .05<=args.interval<=60:
        ap.error('samples 1..1000 and interval .05..60')
    with hx_ctl.HxCtl(timeout=3) as ctl:
        v=metro_led_r03c_probe.decode(ctl.ed.request(0x50,timeout=4))
        if v['revision']!='METRO-LEDSYNC-R03C-HWGLITCH-REPAIR':
            raise RuntimeError(f'Wrong firmware base: {v["revision"]}')
        print(json.dumps({'base_R03C_revision':v['revision'],'last_M4_TX_pair_is_valid':v['last_M4_TX_pair_is_valid']}),flush=True)
        with (args.out.open('w') if args.out else contextlib.nullcontext()) as f:
            prior=None
            for k in range(args.samples):
                r=decode(ctl.ed.request(CMD,timeout=4))
                row={'sample':k,'host_monotonic_s':time.monotonic(),**r}
                if prior is None or k==args.samples-1 or row['native_44word_meter_packets_accepted']!=prior['native_44word_meter_packets_accepted'] or row['bar_state_changes']!=prior['bar_state_changes']:
                    print(json.dumps(row),flush=True)
                if f:
                    f.write(json.dumps(row)+'\n')
                    f.flush()
                prior=row
                if k+1<args.samples:time.sleep(args.interval)
if __name__=='__main__':
    main()

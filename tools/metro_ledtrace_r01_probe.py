#!/usr/bin/env python3
"""Read-only USB 0x50 M4 final-FS3 LED transition history, M4LEDTRACE-R01.

The diagnostic must be loaded deliberately as a RAM-only image beforehand.
This program cannot install firmware, alter settings or control the pedal.
Its 148-byte response contains a seqlock-protected 16-transition ring.
"""
import argparse,contextlib,json,struct,time

TAG=0x31474c4d
CMD=0x50
EVENTS=16
DATA_BYTES=148
U32=0xffffffff
VARIANT='METRO-LEDSYNC-M4LEDTRACE-R01'

def decode(data):
    if not isinstance(data,bytes) or len(data)!=DATA_BYTES:
        raise ValueError(f'{VARIANT}: expected {DATA_BYTES} bytes')
    tag,gen_before,sequence,lit=struct.unpack_from('<4I',data)
    gen_after=struct.unpack_from('<I',data,DATA_BYTES-4)[0]
    if tag!=TAG:
        raise ValueError(f'{VARIANT}: unexpected firmware signature 0x{tag:08x}')
    if (gen_before & 1) or gen_before!=gen_after:
        raise ValueError(f'{VARIANT}: unstable ring snapshot (generation {gen_before} -> {gen_after})')
    if lit not in (0,1):
        raise ValueError(f'{VARIANT}: invalid LED state {lit}')
    slots=[struct.unpack_from('<2I',data,16+8*i) for i in range(EVENTS)]
    events=[]
    start=max(1,sequence-EVENTS+1)
    for seq in range(start,sequence+1):
        timestamp,encoded=slots[seq & (EVENTS-1)]
        if encoded>>1 != seq:
            raise ValueError(f'{VARIANT}: ring slot sequence mismatch: expected {seq}, got {encoded>>1}')
        events.append({'sequence':seq,'timestamp_us_u32':timestamp,'led_lit':bool(encoded&1)})
    for prev,event in zip(events,events[1:]):
        event['interval_us']=(event['timestamp_us_u32']-prev['timestamp_us_u32']) & U32
    return {'revision':VARIANT,'generation':gen_before,'total_transitions':sequence,
            'currently_lit':bool(lit),'events':events,
            'edge_origin':'M4 after HXtra BPM LED filter, before LED controller',
            'optical_timing_measured':False}

def main():
    import hx_ctl
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples',type=int,default=20)
    p.add_argument('--interval',type=float,default=.25)
    p.add_argument('--out',help='optional JSONL output file; no pedal writes')
    a=p.parse_args()
    if not 1<=a.samples<=1200 or not .05<=a.interval<=30:
        p.error('samples 1..1200, interval .05..30s')
    with hx_ctl.HxCtl(timeout=3) as ctl:
        with (open(a.out,'w') if a.out else contextlib.nullcontext()) as f:
            for i in range(a.samples):
                row={'sample':i,'host_monotonic_s':time.monotonic()}
                try:
                    row.update(decode(ctl.ed.request(CMD,timeout=4)))
                except ValueError as e:
                    row['invalid_sample']=str(e)
                line=json.dumps(row)
                print(line,flush=True)
                if f:f.write(line+'\n');f.flush()
                if i+1<a.samples:time.sleep(a.interval)
if __name__=='__main__':
    main()

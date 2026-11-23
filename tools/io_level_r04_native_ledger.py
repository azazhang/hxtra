#!/usr/bin/env python3
"""Read-only 640-byte rolling ledger of ALL native DSP event records.

HX Stomp IO-LEVEL-R04 firmware collects:
- original R03 complete 44-word bulk meter diagnostic and two trial bars
- individual records in 5/9/13/14/...word native packets discarded in R03
- up to 24 (object-family, parameter-id) keys, with count/last/min/max
- persistent transient peak maxima since RAM boot
This host never writes to the pedal, changes presets, sends audio or reflashes.

The actual physical input/output source assignment is not yet established.
Raw record values are labeled according to native packet IDs, not guessed.
"""
import argparse,contextlib,json,math,struct,time
from pathlib import Path

CMD=0x13
MAGIC=0x344d4f49
WORDS=160
ROWCOUNT=24
HEADWORDS=16

def unswap32(v):
    return ((v>>16)|(v<<16))&0xffffffff

def as_float(v):
    return struct.unpack('<f',struct.pack('<I',unswap32(v)))[0]

def decode(raw):
    if not isinstance(raw,bytes) or len(raw)!=640:
        raise ValueError(f'R04 response must be 640 bytes, got {len(raw) if isinstance(raw,bytes) else type(raw).__name__}')
    w=struct.unpack('<160I',raw)
    if w[0]!=MAGIC:
        raise ValueError(f'Wrong R04 rolling ledger signature {w[0]:#010x}')
    data=[]
    for k in range(ROWCOUNT):
        i=HEADWORDS+6*k
        a=w[i:i+6]
        if not a[0]:
            continue
        fam=unswap32(a[0])
        param=unswap32(a[1])
        count=a[3]
        if not count:
            raise ValueError('Nonzero ledger key without event observations')
        lv=[as_float(j) for j in (a[2],a[4],a[5])]
        if not all(math.isfinite(j) for j in lv):
            raise ValueError('Nonfinite ledger float')
        data.append({
            'object_family':f'{fam:#010x}',
            'parameter_id':param,
            'observations':count,
            'last':lv[0],
            'minimum':lv[1],
            'maximum':lv[2],
            'range':lv[2]-lv[1],
            'raw_value_hex':f'{a[2]:#010x}',
        })
    packed=w[6]
    return {
        'variant':'IO-LEVEL-R04-FULL-NATIVE-EVENT-LEDGER',
        'm4_RX_frames_seen':w[1],
        'native_nonempty_packets_seen':w[2],
        '44word_candidates_seen':w[3],
        '44word_bulk_packets_accepted':w[4],
        'bulk_bar_state_changes':w[5],
        'bulk_bar_valid':bool(packed & 0x80000000),
        'bulk_left_pixels':packed&255,
        'bulk_right_pixels':(packed>>8)&255,
        'native_44word_last_levels': [as_float(v) for v in w[8:16]],
        'observed_record_keys':len(data),
        'native_records':data,
        'record_to_physical_io_mapping_verified':False,
    }

def main():
    import hx_ctl,metro_led_r03c_probe
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples',type=int,default=60)
    ap.add_argument('--interval',type=float,default=.15)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    if not 1<=args.samples<=2000 or not .05<=args.interval<=60:
        ap.error('samples 1..2000, interval .05..60')
    with hx_ctl.HxCtl(timeout=3) as ctl:
        rev=metro_led_r03c_probe.decode(ctl.ed.request(0x50,timeout=4))
        assert rev['revision']=='METRO-LEDSYNC-R03C-HWGLITCH-REPAIR', rev['revision']
        print(json.dumps({'R03C_base':rev['revision'],'metronome_active':rev['M4_Metronome_active_flag'],
                          'led_event_count':rev['LED_on_count_low31']}),flush=True)
        with (args.out.open('w') if args.out else contextlib.nullcontext()) as f:
            last={}
            prev=None
            for k in range(args.samples):
                row={'host_monotonic_s':time.monotonic(),'sample':k,**decode(ctl.ed.request(CMD,timeout=4))}
                if f:
                    f.write(json.dumps(row)+'\n')
                    f.flush()
                latest={(x['object_family'],x['parameter_id']):(x['observations'],x['minimum'],x['maximum']) for x in row['native_records']}
                changed=[{'key':key,'state':v} for key,v in latest.items() if key not in last or last[key]!=v]
                if k==0 or k==args.samples-1 or changed:
                    line={key:row[key] for key in ('sample','m4_RX_frames_seen','native_nonempty_packets_seen',
                        '44word_bulk_packets_accepted','bulk_bar_state_changes','bulk_left_pixels','bulk_right_pixels',
                        'observed_record_keys')}
                    line['changed_records']=changed
                    print(json.dumps(line),flush=True)
                last=latest
                prev=row
                if k+1<args.samples:time.sleep(args.interval)
if __name__=='__main__':
    main()

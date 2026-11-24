#!/usr/bin/env python3
"""Read-only R08 PCM coverage and native/TAP comparison; no audio file capture."""
import argparse,json,math,struct,time
from pathlib import Path
from io_level_r05_tap_peak_audit import keyed,K_OUT1,K_OUT2,K_IN,summarize as native_summary
FIELDS='magic seq calls unstable seeds commits frames rejected skipped_words producer_words boundary next_idx seeded last_input last_output max_input max_output input_hot40 output_hot40 output_hot30 output_hot50 bad_desc bad_marker overtake observed_idx observed_offset current_len boundary_delta resets last_len inactive max_batch_frames'.split()

def decode(raw):
    if len(raw)!=128:raise ValueError('R08 must return 128 bytes')
    d=dict(zip(FIELDS,struct.unpack('<32I',raw)))
    if d['magic']!=0x38524f49 or d['seq']&1:raise ValueError('R08 signature IOR8 missing or snapshot busy')
    if any(d[x]>8388608 for x in ('last_input','last_output','max_input','max_output')):raise ValueError('out-of-range PCM24 amplitude')
    return d

def diff(a,b,k):return (b[k]-a[k])&0xffffffff

def summarize(rows):
    first,last=rows[0]['pcm'],rows[-1]['pcm'];duration=rows[-1]['time_s']-rows[0]['time_s']
    fields=('calls','unstable','seeds','commits','frames','rejected','skipped_words','producer_words','boundary','resets','bad_desc','bad_marker','overtake','inactive','output_hot30','output_hot40','output_hot50','input_hot40')
    d={k:diff(first,last,k) for k in fields};d['duration_s']=duration
    d['accepted_pcm_sample_rate']=d['frames']/duration;d['producer_word_rate']=d['producer_words']/duration
    d['coverage_fraction']=8*d['frames']/d['boundary'] if d['boundary'] and not d['resets'] and d['seeds']==0 else None
    d['input_max_dbfs']=20*math.log10(last['max_input']/8388608) if last['max_input'] else None
    d['output_max_dbfs']=20*math.log10(last['max_output']/8388608) if last['max_output'] else None
    changes=[i for i in range(1,len(rows)) if rows[i]['led_count']!=rows[i-1]['led_count']]
    windows=[]
    for a,b in zip(changes,changes[1:]):
        # Disjoint intervals of cumulative PCM counters, with boundary uncertainty
        # limited by host poll time. No claim of optical/acoustic measurement.
        f,l=rows[a]['pcm'],rows[b]['pcm'];n=rows[a:b]
        w={'tap_count':rows[a]['led_count'],'native_peak':max(x['output1_last'] for x in n),'native_detected':any(x['output1_last']>-30 for x in n),'bar_detected':any(x['output_bar_pixels']>85 for x in n),'pcm_frames':diff(f,l,'frames'),'pcm_hot30':diff(f,l,'output_hot30'),'pcm_hot40':diff(f,l,'output_hot40'),'pcm_hot50':diff(f,l,'output_hot50'),'pcm_skipped_words':diff(f,l,'skipped_words'),'pcm_seeds':diff(f,l,'seeds'),'pcm_resets':diff(f,l,'resets')}
        w['pcm_coverage']=8*w['pcm_frames']/diff(f,l,'boundary') if diff(f,l,'boundary') and w['pcm_seeds']==0 and w['pcm_resets']==0 else None
        windows.append(w)
    d['complete_tap_intervals']=len(windows);d['native_high_intervals']=sum(w['native_detected'] for w in windows);d['pcm_hot30_intervals']=sum(w['pcm_hot30']>0 for w in windows);d['pcm_hot40_intervals']=sum(w['pcm_hot40']>0 for w in windows);d['pcm_hot50_intervals']=sum(w['pcm_hot50']>0 for w in windows);d['per_beat']=windows
    return d

def capture(n,interval,out):
    import hx_ctl,io_level_r04_native_ledger as io,metro_led_r03c_probe as tap
    rows=[];start=time.monotonic()
    with hx_ctl.HxCtl(timeout=4) as ctl,out.open('w') as f:
        for i in range(n):
            p=decode(ctl.ed.request(0x1d,timeout=4));d=io.decode(ctl.ed.request(0x13,timeout=4));t=tap.decode(ctl.ed.request(0x50,timeout=4))
            a=keyed(d,K_OUT1);b=keyed(d,K_OUT2);c=keyed(d,K_IN)
            if not all((a,b,c)):raise ValueError('native keys not available')
            row={'sample':i,'time_s':time.monotonic()-start,'led_count':t['LED_on_count_low31'],'output1_last':a['last'],'output2_last':b['last'],'input_last':c['last'],'output_bar_pixels':d['bulk_right_pixels'],'pcm':p}
            f.write(json.dumps(row)+'\n');f.flush();rows.append(row)
            if i+1<n:time.sleep(interval)
    return rows
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--samples',type=int,default=800);p.add_argument('--interval',type=float,default=.02);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert 2<=a.samples<=5000 and .01<=a.interval<=5
    print(json.dumps(summarize(capture(a.samples,a.interval,a.out)),indent=2))

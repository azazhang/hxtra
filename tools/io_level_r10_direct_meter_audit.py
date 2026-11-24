#!/usr/bin/env python3
"""R10 read-only DSP-window, painted-meter and native event comparison."""
import argparse,json,struct,time,math
from pathlib import Path
from io_level_r05_tap_peak_audit import keyed,K_OUT1,K_OUT2,K_IN
FIELDS='magic lock callbacks wire_valid bad_crc duplicate window accepted gaps in_bits out_bits input_calls dsp_hot m4_hot age live pending display holds tick redraws stale bad_seq bad_values paints painted hot_paints'.split()
def decode(raw):
    assert len(raw)==128
    d=dict(zip(FIELDS,struct.unpack('<32I',raw)))
    if d['magic']!=0x41524f49 or d['lock']&1:raise ValueError('IORA signature missing or busy')
    for field in ('in_bits','out_bits'):
        v=struct.unpack('<f',struct.pack('<I',d[field]))[0]
        if not math.isfinite(v) or v<0:raise ValueError('invalid amplitude')
        d[field[:-5]+'_amplitude']=v
    return d
def delta(a,b,k):return (b[k]-a[k])&0xffffffff
def summarize(rows):
    a,b=rows[0]['direct'],rows[-1]['direct'];duration=rows[-1]['time_s']-rows[0]['time_s']
    fields=('callbacks','wire_valid','bad_crc','duplicate','window','accepted','gaps','dsp_hot','m4_hot','redraws','stale','bad_seq','bad_values','paints','hot_paints')
    d={k:delta(a,b,k) for k in fields};d['duration_s']=duration;d['DSP_windows_per_second']=d['window']/duration;d['sample_rate_estimate']=d['window']*1024/duration
    d['coverage_fraction']=d['accepted']/d['window'] if d['window'] else None
    d['input_calls_per_window_last']=b['input_calls']
    changes=[i for i in range(1,len(rows)) if rows[i]['led_count']!=rows[i-1]['led_count']]
    windows=[]
    for i,j in zip(changes,changes[1:]):
        f,l=rows[i]['direct'],rows[j]['direct']
        windows.append({'tap':rows[i]['led_count'],'native_detected':any(x['native_out_db']>-30 for x in rows[i:j]),'DSP_hot_windows':delta(f,l,'dsp_hot'),'M4_hot_windows':delta(f,l,'m4_hot'),'hot_paints':delta(f,l,'hot_paints'),'DSP_windows':delta(f,l,'window'),'missing_windows':delta(f,l,'gaps')})
    d['complete_tap_intervals']=len(windows)
    for k in ('native_detected','DSP_hot_windows','M4_hot_windows','hot_paints'):
        d['tap_intervals_'+k]=sum(w[k]>0 for w in windows)
    d['per_beat']=windows
    return d
def capture(n,interval,out):
    import hx_ctl,io_level_r04_native_ledger as io,metro_led_r03c_probe as tap
    rows=[];start=time.monotonic()
    with hx_ctl.HxCtl(timeout=4) as ctl,out.open('w') as f:
        for i in range(n):
            p=decode(ctl.ed.request(0x1d,timeout=4));d=io.decode(ctl.ed.request(0x13,timeout=4));t=tap.decode(ctl.ed.request(0x50,timeout=4))
            a=keyed(d,K_OUT1);row={'sample':i,'time_s':time.monotonic()-start,'led_count':t['LED_on_count_low31'],'native_out_db':a['last'] if a else -120,'direct':p}
            f.write(json.dumps(row)+'\n');f.flush();rows.append(row)
            if i+1<n:time.sleep(interval)
    return rows
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--samples',type=int,default=800);p.add_argument('--interval',type=float,default=.02);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert 2<=a.samples<=5000 and .01<=a.interval<=5
    print(json.dumps(summarize(capture(a.samples,a.interval,a.out)),indent=2))

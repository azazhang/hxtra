#!/usr/bin/env python3
"""Read-only HX Stomp USB direct capture diagnostics from ffmpeg raw f32le.

Input must be an already captured 48000-Hz interleaved float32 file.
Reports per-channel active sample coverage, 100-ms peak/rms envelopes
and prominent acoustic transients. Does not modify pedal or settings.
"""
import argparse,json
import numpy as np
p=argparse.ArgumentParser()
p.add_argument('raw')
p.add_argument('--channels',type=int,default=2)
p.add_argument('--rate',type=int,default=48000)
p.add_argument('--summary',action='store_true')
o=p.parse_args()
x=np.fromfile(o.raw,dtype='<f4')
assert x.size%o.channels==0,(x.size,o.channels)
x=x.reshape(-1,o.channels)
rate=o.rate
chunk=rate//10
out=dict(samples=len(x),channels=o.channels,sample_rate=rate,duration_sec=len(x)/rate,
         overall_peak=np.max(np.abs(x),axis=0).tolist(),
         overall_rms=np.sqrt(np.mean(x*x,axis=0)).tolist())
windows=[]
for k in range(0,len(x),chunk):
 s=x[k:k+chunk]
 windows.append([round(k/rate,3),*[round(float(np.max(np.abs(s[:,i]))),6) for i in range(o.channels)]])
out['windows_100ms_max_peak']=windows
for i in range(o.channels):
 a=np.abs(x[:,i])
 # prominent clusters by 1ms windows. Avoid reporting noise as clicks.
 n=rate//1000
 bins=a[:(len(a)//n)*n].reshape(-1,n)
 envelope=np.max(bins,axis=1)
 threshold=max(float(np.quantile(envelope,.95))*.45, .008)
 picks=np.flatnonzero((envelope>threshold) & (np.r_[True,envelope[:-1]<=threshold]))
 out[f'channel_{i}_threshold']=threshold
 out[f'channel_{i}_transient_candidate_ms']=(picks[:50].astype(int)).tolist()
if o.summary:
    out.pop('windows_100ms_max_peak',None)
print(json.dumps(out,indent=2))
